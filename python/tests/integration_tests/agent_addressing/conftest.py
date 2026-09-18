"""Shared harness for the agent addressing integration tests.

Every test configures the SDK, sends a run, and asserts which tracing project
it landed in. This module owns the configuring and the asserting, so a test
file is a table of cases.
"""

from __future__ import annotations

import contextlib
import dataclasses
import datetime
import logging
import time
import urllib.parse
import uuid
import warnings
from typing import Any, Callable, Iterator, Optional, TypeVar, Union

import pytest

from langsmith import client as ls_client
from langsmith import schemas as ls_schemas
from langsmith import utils as ls_utils
from langsmith.client import Client
from langsmith.run_helpers import get_current_run_tree, traceable, tracing_context
from langsmith.run_trees import configure as ls_configure

logger = logging.getLogger(__name__)

# Cleared before every test, since a stray value in the shell would otherwise
# pick the destination. `get_tracer_project` reads the project ones in the
# order below, and HOSTED_LANGSERVE_PROJECT_NAME beats all of them. The agent
# pair is LANGSMITH_-only by design: there is no LANGCHAIN_ alias.
ADDRESSING_ENV_VARS = (
    "LANGSMITH_AGENT_ID",
    "LANGSMITH_AGENT_ENVIRONMENT",
    "HOSTED_LANGSERVE_PROJECT_NAME",
    "LANGSMITH_PROJECT",
    "LANGCHAIN_PROJECT",
    "LANGSMITH_SESSION",
    "LANGCHAIN_SESSION",
)

# Placeholders for the names a test owns. `Harness.format` substitutes this
# run's unique values, so no case hard-codes a name.
AGENT = "{agent}"
PROJECT = "{project}"

PRODUCTION_HOSTS = frozenset({"api.smith.langchain.com", "eu.api.smith.langchain.com"})

_POLL_TIMEOUT_SECONDS = 60
_POLL_INTERVAL_SECONDS = 2

T = TypeVar("T")


@dataclasses.dataclass(frozen=True)
class InAgent:
    """The run belongs in this test's agent, under `environment`."""

    environment: str


@dataclasses.dataclass(frozen=True)
class InProject:
    """The run belongs in the tracing project named `name`.

    Also asserts no agent exists under the test's agent key, which is what
    catches a payload that reached the agent despite naming a project.
    """

    name: str


@dataclasses.dataclass(frozen=True)
class Rejected:
    """The endpoint refuses the part, and creates no agent.

    `reason` and `remedy` are the endpoint's own two halves, asserted together
    because they are what a customer reads. A case spells them out rather than
    naming a shared constant, so a reviewer can see what it expects; keep them
    in step with `smith-go/runs/agent_addressing.go`.
    """

    reason: str
    remedy: str
    status: int = 400


Destination = Union[InAgent, InProject, Rejected]


@dataclasses.dataclass(frozen=True)
class Child:
    """A nested `@traceable` call. Lands with the root unless `lands_in` says."""

    extra: dict[str, Any] = dataclasses.field(default_factory=dict)
    context: dict[str, Any] = dataclasses.field(default_factory=dict)
    lands_in: Optional[Destination] = None


@dataclasses.dataclass(frozen=True)
class Case:
    """One SDK configuration and the destination it should resolve to.

    `env` and `kwargs` apply to any method. The rest are `@traceable` only:
    `decorator` is `@traceable(...)`, `extra` is `langsmith_extra`, `context`
    is the surrounding `tracing_context(...)`, `configure` is `ls.configure`.
    """

    id: str
    lands_in: Destination
    env: dict[str, str] = dataclasses.field(default_factory=dict)
    kwargs: dict[str, Any] = dataclasses.field(default_factory=dict)
    decorator: dict[str, Any] = dataclasses.field(default_factory=dict)
    extra: dict[str, Any] = dataclasses.field(default_factory=dict)
    context: dict[str, Any] = dataclasses.field(default_factory=dict)
    configure: dict[str, Any] = dataclasses.field(default_factory=dict)
    child: Optional[Child] = None

    def __str__(self) -> str:
        return self.id


@dataclasses.dataclass(frozen=True)
class CallArgs:
    """A case's keyword arguments, per method.

    `create_run` calls the project `project_name`, `update_run` calls it
    `session_name`. A case declares it once and gets both.
    """

    create: dict[str, Any]
    update: dict[str, Any]


@dataclasses.dataclass(frozen=True)
class TracedIds:
    """The run ids a `Harness.trace` call produced."""

    root: uuid.UUID
    child: Optional[uuid.UUID]


class Harness:
    """One test's client, names, environment and assertions."""

    def __init__(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        self._monkeypatch = monkeypatch
        self._caplog = caplog
        token = uuid.uuid4().hex[:12]
        # Lower case and dashes only: an agent key becomes a project name, and
        # a key the backend cannot slug is rejected outright.
        self.agent_key = f"sdk-it-{token}"
        self.project_name = f"sdk-it-project-{token}"
        self.start_time = datetime.datetime.now(datetime.timezone.utc)
        # Multipart flushes on a background thread, so a rejection is reported
        # here rather than raised.
        self.errors: list[Exception] = []
        self.client = Client(tracing_error_callback=self.errors.append)
        host = urllib.parse.urlparse(self.client.api_url).hostname or ""
        if host in PRODUCTION_HOSTS:
            pytest.fail(
                f"Refusing to run the agent addressing tests against {host}:"
                " each one creates an agent and four tracing projects. Point"
                " LANGSMITH_ENDPOINT at a local or dev deployment."
            )

    # -- configuration -----------------------------------------------------

    def format(self, value: Any) -> Any:
        """Substitute this test's names into a case's placeholders."""
        if isinstance(value, str):
            return value.format(agent=self.agent_key, project=self.project_name)
        if isinstance(value, dict):
            return {key: self.format(item) for key, item in value.items()}
        return value

    def configure(self, case: Case) -> CallArgs:
        """Apply the case's environment and return its call arguments."""
        for name, value in case.env.items():
            self._monkeypatch.setenv(name, self.format(value))
        _clear_env_caches()
        create = {name: self.format(value) for name, value in case.kwargs.items()}
        update = {
            ("session_name" if name == "project_name" else name): value
            for name, value in create.items()
        }
        return CallArgs(create=create, update=update)

    def root_run(self) -> dict[str, Any]:
        """A root run's identity fields.

        Both are required, not cosmetic: without `trace_id` and `dotted_order`,
        `create_run` and `update_run` use `POST /runs` and `PATCH /runs/{id}`
        instead of multipart, and those ignore the agent pair, so the run lands
        in `default` with nothing reported.
        """
        run_id = uuid.uuid4()
        return {
            "id": run_id,
            "trace_id": run_id,
            "dotted_order": f"{self.start_time.strftime('%Y%m%dT%H%M%S%fZ')}{run_id}",
        }

    # -- @traceable ----------------------------------------------------------

    def trace(self, case: Case) -> TracedIds:
        """Call a `@traceable` root, and a nested one if the case has a child.

        The client travels in `langsmith_extra` because every `tracing_context`
        resets the context client, and the default client would not report
        rejections to this harness.
        """
        self.configure(case)
        if case.configure:
            ls_configure(**self.format(case.configure))
        ids: dict[str, uuid.UUID] = {}
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")

            @traceable
            def child() -> None:
                ids["child"] = _current_run_id()

            @traceable(**self.format(case.decorator))
            def root() -> None:
                ids["root"] = _current_run_id()
                if case.child is not None:
                    with tracing_context(**self.format(case.child.context)):
                        child(
                            langsmith_extra={
                                "client": self.client,
                                **self.format(case.child.extra),
                            }
                        )

            with (
                tracing_context(enabled=True),
                tracing_context(**self.format(case.context)),
            ):
                root(langsmith_extra={"client": self.client, **self.format(case.extra)})
        self.client.flush()
        # An argument the decorator does not know is dropped with a warning, so
        # the case would silently test something else.
        ignored = [str(w.message) for w in caught if "not recognized" in str(w.message)]
        assert not ignored, f"the decorator ignored part of the case: {ignored}"
        return TracedIds(root=ids["root"], child=ids.get("child"))

    # -- lookups -----------------------------------------------------------

    def agents_url(self, path: str = "") -> str:
        """An agent API route.

        Hand-built because `/agents` has no alias at the API root the way
        `/runs` does, and the SDK has no agent methods yet. `api_url` may or
        may not already carry the prefix, so it is normalized away first.
        """
        root = ls_client._get_openapi_base_url(self.client.api_url)
        return f"{root}/api/v1/agents{path}"

    def agent(self, key: Optional[str] = None) -> Optional[dict]:
        """An agent as the API reports it, or None.

        Defaults to this test's key. The legacy path registers an agent under
        the *project* name instead, hence the argument. Read by key: the list
        route's `agent_key` filter is not honored and returns every agent.
        """
        try:
            response = self.client.request_with_retries(
                "GET", self.agents_url(f"/{key or self.agent_key}")
            )
        except ls_utils.LangSmithNotFoundError:
            return None
        ls_utils.raise_for_status_with_text(response)
        return response.json()

    def agent_project_id(self, environment: str) -> Optional[uuid.UUID]:
        """The tracing project bound to (this test's agent, `environment`)."""
        agent = self.agent()
        if agent is None:
            return None
        for env in agent.get("environments") or []:
            if env.get("environment") == environment:
                return uuid.UUID(env["tracer_session_id"])
        raise AssertionError(
            f"agent {self.agent_key!r} has no {environment} environment;"
            f" it has {[e.get('environment') for e in agent['environments']]}"
        )

    def project_id(self, name: str) -> Optional[uuid.UUID]:
        """The tracing project named `name`, or None."""
        try:
            return self.client.read_project(project_name=name).id
        except ls_utils.LangSmithNotFoundError:
            return None

    # -- assertions --------------------------------------------------------

    def assert_landed(
        self,
        run_id: uuid.UUID,
        destination: Destination,
        *,
        patched: bool = True,
    ) -> Optional[ls_schemas.Run]:
        """Assert the run reached `destination`, waiting for it to show up.

        `patched` also requires the update to have landed in the same place.
        Each half of a run is addressed separately, and the two have gone to
        different projects before, so checking the create alone says half.
        """
        if isinstance(destination, Rejected):
            self.assert_rejected(destination, run_id)
            return None

        expected = self._expected_project(destination, run_id)
        assert not self.errors, f"the SDK reported ingestion errors: {self.errors}"
        run = _wait_for(
            lambda: self._read_run(run_id, expected, patched=patched),
            what=f"run {run_id} to be ingested{' and patched' if patched else ''}",
            on_timeout=lambda: self._describe_run(run_id),
        )
        assert run.session_id == expected, (
            f"the run landed in project {run.session_id}, not {expected}"
        )
        return run

    def assert_traced(self, ids: TracedIds, case: Case) -> None:
        """Assert the root landed, and the child landed under it."""
        self.assert_landed(ids.root, case.lands_in)
        if case.child is None:
            return
        assert ids.child is not None, "the child was not traced"
        child = self.assert_landed(ids.child, case.child.lands_in or case.lands_in)
        if child is not None:
            assert child.parent_run_id == ids.root, (
                f"the child's parent is {child.parent_run_id}, not the root {ids.root}"
            )

    def assert_rejected(
        self, rejected: Rejected, run_id: Optional[uuid.UUID] = None
    ) -> None:
        """Assert the endpoint refused this, said why, logged it, created nothing.

        `run_id` only improves the failure message: it says where the run went
        instead.
        """
        wanted = (str(rejected.status), rejected.reason, rejected.remedy)
        reported = [str(error) for error in self.errors]
        assert reported, (
            "the endpoint accepted what it should have refused with"
            f" {rejected.status} {rejected.reason!r}, since the SDK reported"
            " no error at all"
            + (f"; {self._describe_run(run_id)}" if run_id is not None else "")
        )
        assert any(all(part in error for part in wanted) for error in reported), (
            f"expected the reported error to carry {wanted}; got {reported}"
        )
        # The log line is the only copy a caller who is not watching the error
        # callback ever sees, so it has to carry both halves too.
        logged = [
            record.getMessage()
            for record in self._caplog.records
            if record.levelno >= logging.WARNING
        ]
        assert any(
            rejected.reason in message and rejected.remedy in message
            for message in logged
        ), f"expected the rejection logged at warning or above; got {logged}"
        assert self.agent() is None, (
            f"a rejected run must not create an agent, but {self.agent_key!r} exists"
        )

    def _expected_project(
        self, destination: Destination, run_id: uuid.UUID
    ) -> uuid.UUID:
        where = lambda: self._describe_run(run_id)  # noqa: E731 - for the message
        if isinstance(destination, InProject):
            # Before the wait below, because it is the faster and more specific
            # failure when a payload reached the agent anyway.
            self._assert_no_agent_created()
            name = self.format(destination.name)
            return _wait_for(
                lambda: self.project_id(name),
                what=f"project {name!r} to exist",
                on_timeout=where,
            )
        assert isinstance(destination, InAgent)
        return _wait_for(
            lambda: self.agent_project_id(destination.environment),
            what=f"agent {self.agent_key!r} to have a"
            f" {destination.environment} project",
            on_timeout=where,
        )

    def _assert_no_agent_created(self) -> None:
        agent = self.agent()
        assert agent is None, (
            f"a project-addressed run must not create an agent, but"
            f" {self.agent_key!r} exists with"
            f" {[e.get('environment') for e in agent['environments']]}"
        )

    def _read_run(
        self, run_id: uuid.UUID, project_id: uuid.UUID, *, patched: bool
    ) -> Optional[ls_schemas.Run]:
        """The run once ingested, or None while it is not there yet.

        `project_id` and `start_time` are what a SmithDB-only backend needs to
        find a run at all. A ClickHouse-backed one ignores both and answers
        from the run id, which is why the caller compares `session_id` rather
        than trusting this to have scoped the read.
        """
        try:
            run = self.client.read_run(
                run_id, project_id=project_id, start_time=self.start_time
            )
        except ls_utils.LangSmithNotFoundError:
            return None
        if patched and run.end_time is None:
            return None
        return run

    def _describe_run(self, run_id: uuid.UUID) -> str:
        """Where the run actually went, for the failure message."""

        def read() -> Optional[ls_schemas.Run]:
            try:
                return self.client.read_run(run_id)
            except ls_utils.LangSmithNotFoundError:
                return None

        try:
            run = _wait_for(read, what="the run to be ingested anywhere", timeout=30)
            name = self.client.read_project(project_id=run.session_id).name
        except Exception as error:  # noqa: BLE001 - diagnostics only
            return f"could not say where the run landed: {error}"
        return (
            f"the run is in project {name!r} ({run.session_id}) with end_time"
            f" {run.end_time!r}"
        )

    # -- teardown ----------------------------------------------------------

    def cleanup(self) -> None:
        """Delete what this test created, logging whatever will not go."""
        # Two keys: the one a test addressed, and the project name the legacy
        # path registers an agent under.
        for key in (self.agent_key, self.project_name):
            with self._quietly(f"delete agent {key}"):
                agent = self.agent(key)
                if agent is not None:
                    self.client.request_with_retries(
                        "DELETE", self.agents_url(f"/{agent['id']}")
                    )
        with self._quietly(f"delete project {self.project_name}"):
            project_id = self.project_id(self.project_name)
            if project_id is not None:
                self.client.delete_project(project_id=str(project_id))

    @contextlib.contextmanager
    def _quietly(self, what: str) -> Iterator[None]:
        """Teardown must not fail a test, so log instead of raising."""
        try:
            yield
        except Exception as error:  # noqa: BLE001 - teardown is best effort
            logger.warning("Could not %s: %s", what, error)


def _current_run_id() -> uuid.UUID:
    run = get_current_run_tree()
    assert run is not None, "the call was not traced"
    return run.id


def _clear_env_caches() -> None:
    """Make the SDK re-read the environment. Each of these is cached for the
    life of the process."""
    ls_utils.get_env_var.cache_clear()
    ls_utils.get_tracer_project.cache_clear()
    ls_utils.get_tracer_agent_id.cache_clear()
    ls_utils.get_tracer_agent_environment.cache_clear()


def _wait_for(
    probe: Callable[[], Optional[T]],
    *,
    what: str,
    on_timeout: Optional[Callable[[], str]] = None,
    timeout: int = _POLL_TIMEOUT_SECONDS,
) -> T:
    """Poll `probe` until it returns something, then return it."""
    deadline = time.monotonic() + timeout
    last_error: Optional[Exception] = None
    while time.monotonic() < deadline:
        try:
            result = probe()
            if result is not None:
                return result
        except AssertionError:
            raise
        except Exception as error:  # noqa: BLE001 - retried until the deadline
            last_error = error
        time.sleep(_POLL_INTERVAL_SECONDS)
    detail = f" ({on_timeout()})" if on_timeout else ""
    if last_error is not None:
        detail += f" (last error: {last_error})"
    raise AssertionError(f"Waited {timeout}s for {what}{detail}")


@pytest.fixture
def ls(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> Iterator[Harness]:
    """A client, unique names, and a clean addressing environment."""
    for name in ADDRESSING_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    _clear_env_caches()
    # Set explicitly rather than relying on caplog's default, so a rejection
    # assertion cannot pass or fail on how capturing happens to be configured.
    caplog.set_level(logging.WARNING)
    harness = Harness(monkeypatch, caplog)
    try:
        yield harness
    finally:
        # `ls.configure` is process-wide, not a context var.
        ls_configure(project_name=None)
        harness.cleanup()
        _clear_env_caches()
