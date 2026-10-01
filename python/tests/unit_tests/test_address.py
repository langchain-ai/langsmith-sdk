"""Addressing runs to an `Address` instead of a project."""

from __future__ import annotations

import logging
import warnings
from typing import Any, Optional
from unittest import mock

import pytest

import langsmith as ls
from langsmith import utils as ls_utils
from langsmith._address import EnvAddressError
from langsmith._internal import _agent_addressing, _context
from langsmith.client import Client
from langsmith.run_helpers import get_current_run_tree, trace, traceable
from langsmith.run_trees import RunTree
from langsmith.schemas import FeedbackCreate

SUPPORT = ls.address(agent_id="support", agent_environment="production")
STAGING = SUPPORT.with_agent_environment("staging")
UNTRACED = "LangSmith is not tracing this call"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> Any:
    for name in (
        "LANGSMITH_AGENT_ID",
        "LANGSMITH_AGENT_ENVIRONMENT",
        "LANGSMITH_PROJECT",
        "LANGCHAIN_PROJECT",
        "LANGCHAIN_SESSION",
        "HOSTED_LANGSERVE_PROJECT_NAME",
    ):
        monkeypatch.delenv(name, raising=False)
    _clear_caches()
    yield
    ls.configure(project_name=None, address=None)
    _clear_caches()


def _clear_caches() -> None:
    ls_utils.get_env_var.cache_clear()
    ls_utils.get_tracer_project.cache_clear()
    _agent_addressing._log_untraced_once.cache_clear()


def _set_env(monkeypatch: pytest.MonkeyPatch, **values: str) -> None:
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    _clear_caches()


@pytest.fixture
def client() -> Client:
    return Client(session=mock.MagicMock(), api_key="test", api_url="http://x")


def _destination(run: Optional[RunTree]) -> tuple:
    assert run is not None
    return run.session_name, run.address


@traceable
def _root() -> tuple:
    return _destination(get_current_run_tree())


# -- The handle ---------------------------------------------------------------


class TestAddress:
    @pytest.mark.parametrize(
        ("kwargs", "error"),
        [
            ({"agent_id": "", "agent_environment": "prod"}, "agent_id must be"),
            ({"agent_id": "x", "agent_environment": ""}, "agent_environment must be"),
            ({"agent_id": "x" * 64, "agent_environment": "prod"}, "1 to 63"),
            ({"agent_id": "Support", "agent_environment": "prod"}, "lowercase"),
            ({"agent_id": "1support", "agent_environment": "prod"}, "start with"),
            ({"agent_id": "support-", "agent_environment": "prod"}, "end with"),
            ({"agent_id": "sup_port", "agent_environment": "prod"}, "hyphens"),
        ],
        ids=[
            "empty_agent_id",
            "empty_agent_environment",
            "agent_id_too_long",
            "uppercase",
            "leading_digit",
            "trailing_hyphen",
            "underscore",
        ],
    )
    def test_invalid_values_fail_at_construction(
        self, kwargs: dict, error: str
    ) -> None:
        with pytest.raises(ls_utils.LangSmithUserError, match=error):
            ls.address(**kwargs)

    @pytest.mark.parametrize("agent_id", ["a", "a" * 63, "support-v2"])
    def test_valid_agent_ids(self, agent_id: str) -> None:
        assert ls.address(agent_id=agent_id, agent_environment="prod").agent_id == (
            agent_id
        )

    def test_renders_to_the_wire_fields(self) -> None:
        assert SUPPORT._to_wire() == {
            "agent_id": "support",
            "agent_environment": "production",
        }
        assert ls.Address._from_wire(SUPPORT._to_wire()) == SUPPORT

    def test_half_an_address_is_rejected(self) -> None:
        with pytest.raises(ls_utils.LangSmithUserError, match="agent_environment"):
            ls.Address._from_wire({"agent_id": "support"})

    def test_reads_the_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert ls.Address._from_env() is None
        _set_env(monkeypatch, LANGSMITH_AGENT_ID="a", LANGSMITH_AGENT_ENVIRONMENT="e")
        assert ls.Address._from_env() == ls.address(agent_id="a", agent_environment="e")

    def test_half_an_address_in_the_env_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _set_env(monkeypatch, LANGSMITH_AGENT_ID="a")
        with pytest.raises(EnvAddressError, match="LANGSMITH_AGENT_ID='a'"):
            ls.Address._from_env()

    def test_a_non_address_is_rejected(self) -> None:
        with pytest.raises(ls_utils.LangSmithUserError, match="langsmith.Address"):
            with ls.tracing_context(address="support"):  # type: ignore[arg-type]
                pass


# -- Where a root run lands -----------------------------------------------------


class TestPrecedence:
    """The first level naming a project or an address decides, either mode."""

    def test_tracing_context_address_beats_a_decorator_project(
        self, client: Client
    ) -> None:
        f = traceable(project_name="deco")(_root.__wrapped__)
        with ls.tracing_context(enabled=True, client=client, address=SUPPORT):
            assert f() == (None, SUPPORT)

    def test_tracing_context_project_beats_a_decorator_address(
        self, client: Client
    ) -> None:
        f = traceable(address=SUPPORT)(_root.__wrapped__)
        with ls.tracing_context(enabled=True, client=client, project_name="ctx"):
            assert f() == ("ctx", None)

    def test_langsmith_extra_beats_the_decorator(self, client: Client) -> None:
        f = traceable(address=SUPPORT)(_root.__wrapped__)
        with ls.tracing_context(enabled=True, client=client):
            assert f(langsmith_extra={"address": STAGING}) == (None, STAGING)
            assert f(langsmith_extra={"project_name": "p"}) == ("p", None)

    def test_an_address_in_code_beats_a_project_in_the_env(
        self, client: Client, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _set_env(monkeypatch, LANGSMITH_PROJECT="env-project")
        with ls.tracing_context(enabled=True, client=client, address=SUPPORT):
            assert _root() == (None, SUPPORT)

    def test_the_env_address_applies_when_nothing_names_one(
        self, client: Client, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _set_env(monkeypatch, LANGSMITH_AGENT_ID="a", LANGSMITH_AGENT_ENVIRONMENT="e")
        with ls.tracing_context(enabled=True, client=client):
            assert _root() == (None, ls.address(agent_id="a", agent_environment="e"))

    @pytest.mark.parametrize(
        "call",
        [
            lambda: ls.tracing_context(project_name="p", address=SUPPORT).__enter__(),
            lambda: traceable(project_name="p", address=SUPPORT),
            lambda: trace("r", project_name="p", address=SUPPORT),
            lambda: RunTree(name="r", project_name="p", address=SUPPORT),
            lambda: _root(langsmith_extra={"project_name": "p", "address": SUPPORT}),
        ],
        ids=["tracing_context", "traceable", "trace", "run_tree", "langsmith_extra"],
    )
    def test_both_at_one_level_raises(self, call: Any, client: Client) -> None:
        with ls.tracing_context(enabled=True, client=client):
            with pytest.raises(ls_utils.LangSmithUserError):
                call()

    @pytest.mark.parametrize(
        "settle", [_agent_addressing.resolve, _agent_addressing.first_named]
    )
    def test_the_level_naming_both_is_reported(self, settle: Any) -> None:
        with pytest.raises(ls_utils.LangSmithUserError, match="precedence level 2"):
            settle((None, None), ("p", SUPPORT))


class TestConfigure:
    def test_configure_sets_the_address(self) -> None:
        ls.configure(address=SUPPORT)
        assert _context._GLOBAL_ADDRESS == SUPPORT

    def test_unrelated_options_keep_the_address(self) -> None:
        ls.configure(address=SUPPORT)
        ls.configure(tags=["x"])
        ls.configure(enabled=True)
        assert _context._GLOBAL_ADDRESS == SUPPORT
        ls.configure(tags=None, enabled=None)

    def test_naming_a_project_replaces_the_address(self) -> None:
        ls.configure(address=SUPPORT)
        ls.configure(project_name="p")
        assert _context._GLOBAL_ADDRESS is None
        assert _context._GLOBAL_PROJECT_NAME == "p"

    def test_clearing_the_project_keeps_the_address(self) -> None:
        """`project_name=None` clears the project, as `address=None` does."""
        ls.configure(address=SUPPORT)
        ls.configure(project_name=None)
        assert _context._GLOBAL_ADDRESS == SUPPORT

    def test_naming_an_address_replaces_the_project(self) -> None:
        ls.configure(project_name="p")
        ls.configure(address=SUPPORT)
        assert (_context._GLOBAL_PROJECT_NAME, _context._GLOBAL_ADDRESS) == (
            None,
            SUPPORT,
        )


# -- A bad environment never breaks the app -----------------------------------------

BAD_ENVS = {
    "half_an_address": {"LANGSMITH_AGENT_ID": "a"},
    "address_and_project": {
        "LANGSMITH_AGENT_ID": "a",
        "LANGSMITH_AGENT_ENVIRONMENT": "e",
        "LANGSMITH_PROJECT": "p",
    },
}


@pytest.mark.parametrize("env", BAD_ENVS.values(), ids=BAD_ENVS.keys())
class TestBadEnv:
    def test_traceable_runs_untraced(
        self,
        env: dict,
        client: Client,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        _set_env(monkeypatch, **env)

        @traceable
        def f() -> Optional[RunTree]:
            return get_current_run_tree()

        with caplog.at_level(logging.WARNING):
            with ls.tracing_context(enabled=True, client=client):
                assert f() is None
                assert f() is None
        warned = [r for r in caplog.records if UNTRACED in r.getMessage()]
        assert len(warned) == 1, "expected one warning for one cause"

    def test_trace_runs_untraced(
        self, env: dict, client: Client, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _set_env(monkeypatch, **env)
        with mock.patch.object(Client, "create_run") as create_run:
            with ls.tracing_context(enabled=True, client=client):
                with trace("r", client=client):
                    pass
        create_run.assert_not_called()

    def test_create_run_drops_the_run(
        self, env: dict, client: Client, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _set_env(monkeypatch, **env)
        with mock.patch.object(Client, "_filter_for_sampling") as sampled:
            assert client.create_run("r", {}, "chain") is None
            assert client.create_run("r", {}, "chain", session_name=None) is None
        sampled.assert_not_called()

    def test_no_warning_when_tracing_is_off(
        self,
        env: dict,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        _set_env(monkeypatch, **env)
        with caplog.at_level(logging.WARNING):
            with ls.tracing_context(enabled=False):
                traceable(lambda: None)()
        assert not [r for r in caplog.records if UNTRACED in r.getMessage()]


@pytest.mark.parametrize(
    ("env", "warning"),
    [
        ({"LANGSMITH_AGENT_ID": "a"}, "needs agent_environment"),
        (
            {"LANGSMITH_AGENT_ID": "Bad_Id", "LANGSMITH_AGENT_ENVIRONMENT": "e"},
            "1 to 63",
        ),
        (
            {
                "LANGSMITH_AGENT_ID": "a",
                "LANGSMITH_AGENT_ENVIRONMENT": "e",
                "LANGSMITH_PROJECT": "p",
            },
            "both set",
        ),
        ({"LANGSMITH_AGENT_ID": "a", "LANGSMITH_AGENT_ENVIRONMENT": "e"}, None),
    ],
    ids=["half_an_address", "invalid_agent_id", "address_and_project", "address_only"],
)
def test_client_warns_about_an_unusable_env(
    monkeypatch: pytest.MonkeyPatch, env: dict, warning: Optional[str]
) -> None:
    _set_env(monkeypatch, **env)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _agent_addressing.warn_on_env()
    messages = [str(w.message) for w in caught]
    if warning is None:
        assert messages == []
    else:
        assert len(messages) == 1 and warning in messages[0]


def test_a_parent_naming_a_destination_survives_a_bad_env(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only a root consults the env; a child copies its parent."""
    headers = RunTree(name="up", project_name="upstream").to_headers()
    _set_env(monkeypatch, LANGSMITH_AGENT_ENVIRONMENT="staging")
    with ls.tracing_context(enabled=True, client=client):
        with trace("child", parent=headers, client=client) as run:
            assert run.session_name == "upstream"


# -- Children and other services -------------------------------------------------------


class TestPropagation:
    def test_children_keep_the_roots_address(self, client: Client) -> None:
        @traceable
        def child() -> tuple:
            return _destination(get_current_run_tree())

        @traceable(address=SUPPORT)
        def root() -> tuple:
            with ls.tracing_context(address=STAGING):
                return child()

        with ls.tracing_context(enabled=True, client=client):
            assert root() == (None, SUPPORT)

    def test_nested_trace_exposes_the_parents_address(self, client: Client) -> None:
        with ls.tracing_context(enabled=True, client=client, address=SUPPORT):
            with trace("root", client=client):
                with trace("inner", client=client):
                    ctx = ls.get_tracing_context()
        assert (ctx["project_name"], ctx["address"]) == (None, SUPPORT)

    def test_headers_round_trip(self) -> None:
        headers = RunTree(
            name="up", address=SUPPORT, tags=["t"], extra={"metadata": {"k": "v"}}
        ).to_headers()
        assert "langsmith-address=" in headers["baggage"]
        child = RunTree.from_headers(headers)
        assert child is not None
        assert _destination(child) == (None, SUPPORT)
        assert (child.tags, child.metadata["k"]) == (["t"], "v")

    def test_the_header_beats_the_receiver(self, client: Client) -> None:
        """As for `project_name` on `main`: a child joins its parent's."""
        headers = RunTree(name="up", address=SUPPORT).to_headers()
        with ls.tracing_context(enabled=True, client=client):
            got = _root(langsmith_extra={"parent": headers, "project_name": "mine"})
        assert got == (None, SUPPORT)

    @pytest.mark.parametrize(
        "named",
        [{"project_name": "mine"}, {"address": SUPPORT}],
        ids=["project", "address"],
    )
    def test_trace_names_a_header_parent_without_a_destination(
        self, client: Client, named: dict
    ) -> None:
        headers = {"langsmith-trace": RunTree(name="up").dotted_order}
        with ls.tracing_context(enabled=True, client=client):
            with trace("child", parent=headers, client=client, **named) as run:
                got = _destination(run)
        assert got == (named.get("project_name"), named.get("address"))

    def test_a_header_naming_both_is_rejected(self) -> None:
        project = RunTree(name="up", project_name="upstream").to_headers()
        address = RunTree(name="up", address=SUPPORT).to_headers()
        both = {**project, "baggage": f"{project['baggage']},{address['baggage']}"}
        assert RunTree.from_headers(both) is None

    def test_a_malformed_header_address_is_ignored(self) -> None:
        headers = RunTree(name="up", project_name="upstream").to_headers()
        headers["baggage"] += ",langsmith-address=%7B%22agent_id%22%3A%22a%22%7D"
        child = RunTree.from_headers(headers)
        assert child is not None
        assert _destination(child) == ("upstream", None)


class TestReplicas:
    def test_a_bare_address_is_a_replica(self) -> None:
        run = RunTree(name="r", replicas=[SUPPORT, {"project_name": "p"}])
        assert run.replicas == [{"address": SUPPORT}, {"project_name": "p"}]

    def test_replicas_to_different_addresses_get_distinct_ids(self) -> None:
        run = RunTree(name="r", project_name="p")
        a = run._remap_for_project(None, address=SUPPORT)
        b = run._remap_for_project(None, address=STAGING)
        assert a["id"] != b["id"]
        assert (a["address"], b["address"]) == (SUPPORT, STAGING)


# -- On the wire ----------------------------------------------------------------------


class TestWire:
    def test_a_run_payload_carries_the_address_object(self) -> None:
        payload = RunTree(name="r", address=SUPPORT)._get_dicts_safe()
        _agent_addressing.apply_to_payload(payload)
        assert payload["address"] == {
            "kind": "AGENT",
            "id": "support",
            "environment": "PRODUCTION",
        }
        assert "agent_id" not in payload
        assert "agent_environment" not in payload
        assert "session_name" not in payload

    @pytest.mark.parametrize("update", [False, True])
    def test_a_run_tree_keeps_its_address_on_the_batch_path(
        self, client: Client, update: bool
    ) -> None:
        """`batch_ingest_runs` / `multipart_ingest` dump pydantic runs."""
        run = RunTree(name="r", address=SUPPORT)
        payload = client._run_transform(run, update=update)
        assert payload["address"] == {
            "kind": "AGENT",
            "id": "support",
            "environment": "PRODUCTION",
        }

    def test_a_rendered_payload_is_not_rendered_again(self) -> None:
        """A retried batch re-sends the caller's dicts, already rendered."""
        payload = {"id": "x", "address": SUPPORT}
        _agent_addressing.apply_to_payload(payload)
        rendered = dict(payload)
        _agent_addressing.apply_to_payload(payload)
        assert payload == rendered

    def test_retrying_the_same_batch_keeps_the_address(self, client: Client) -> None:
        run = {"name": "r", "address": SUPPORT, "run_type": "chain"}
        first = client._run_transform(run, copy=False)["address"]
        second = client._run_transform(run, copy=False)["address"]
        assert first == second == SUPPORT._to_payload()["address"]

    def test_a_project_payload_is_untouched(self) -> None:
        payload = {"name": "r", "session_name": "p"}
        _agent_addressing.apply_to_payload(payload)
        assert payload == {"name": "r", "session_name": "p"}

    def test_an_update_does_not_read_the_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _set_env(monkeypatch, LANGSMITH_AGENT_ID="a", LANGSMITH_AGENT_ENVIRONMENT="e")
        payload: dict = {"id": "x"}
        _agent_addressing.apply_to_payload(payload, update=True)
        assert "address" not in payload

    def test_feedback_carries_the_address_object(self) -> None:
        feedback = FeedbackCreate(
            key="k",
            feedback_source={"type": "api"},  # type: ignore[arg-type]
            id="00000000-0000-0000-0000-000000000000",  # type: ignore[arg-type]
            run_id=None,
            trace_id=None,
            address=SUPPORT,
        )
        dumped = feedback.model_dump(exclude_none=True)
        assert dumped["address"] == {
            "kind": "AGENT",
            "id": "support",
            "environment": "PRODUCTION",
        }
        assert "agent_id" not in dumped

    @pytest.mark.parametrize(
        "project",
        [{"project_id": "p"}, {"session_id": "s"}],
        ids=lambda k: next(iter(k)),
    )
    def test_feedback_rejects_a_project_beside_an_address(
        self, client: Client, project: dict
    ) -> None:
        with pytest.raises(ls_utils.LangSmithUserError, match="not both"):
            client.create_feedback(key="k", address=SUPPORT, **project)

    def test_feedback_rejects_a_non_address(self) -> None:
        with pytest.raises(ls_utils.LangSmithUserError):
            FeedbackCreate(
                key="k",
                feedback_source={"type": "api"},  # type: ignore[arg-type]
                id="00000000-0000-0000-0000-000000000000",  # type: ignore[arg-type]
                run_id=None,
                trace_id=None,
                address="support",
            )

    def test_no_run_url_for_an_addressed_run(self) -> None:
        with pytest.raises(ls_utils.LangSmithUserError, match="run URL"):
            RunTree(name="r", address=SUPPORT).get_url()
