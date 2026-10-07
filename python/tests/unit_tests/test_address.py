"""Addressing runs to an `Address` instead of a project."""

from __future__ import annotations

import json
import logging
import urllib.parse
import warnings
from typing import Any, Optional
from unittest import mock

import pytest

import langsmith as ls
from langsmith import utils as ls_utils
from langsmith._internal import _addressing, _context
from langsmith._internal._uuid import uuid7_deterministic
from langsmith.address import EnvAddressError
from langsmith.client import Client
from langsmith.run_helpers import get_current_run_tree, trace, traceable
from langsmith.run_trees import RunTree, _Baggage
from langsmith.schemas import FeedbackCreate

SUPPORT = ls.Agent("support", "production")
STAGING = ls.Agent("support", "staging")
SUPPORT_LRN = "lrn:agents/support/environments/production"
STAGING_LRN = "lrn:agents/support/environments/staging"
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
    _addressing._log_untraced_once.cache_clear()


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


def _agent(agent_id: str, environment: str) -> str:
    return ls.Agent(agent_id, environment)._lrn()


def _from_env() -> Optional[str]:
    agent = ls.Agent.from_env()
    return None if agent is None else agent._lrn()


# -- The handle ---------------------------------------------------------------


class TestConstructors:
    def test_agent_renders_its_lrn(self) -> None:
        assert SUPPORT._lrn() == SUPPORT_LRN

    @pytest.mark.parametrize("agent_id", ["a", "a" * 63, "support-v2"])
    def test_valid_agent_ids(self, agent_id: str) -> None:
        assert _agent(agent_id, "local") == (
            f"lrn:agents/{agent_id}/environments/local"
        )

    @pytest.mark.parametrize(
        ("agent_id", "error"),
        [
            ("", "agent id must be"),
            ("x" * 64, "1 to 63"),
            ("Support", "lowercase"),
            ("1support", "start with"),
            ("support-", "end with"),
            ("sup_port", "hyphens"),
            ("a/b", "agent id must be"),
        ],
    )
    def test_invalid_agent_ids(self, agent_id: str, error: str) -> None:
        with pytest.raises(ls_utils.LangSmithUserError, match=error):
            _agent(agent_id, "production")

    @pytest.mark.parametrize("environment", ["", "prod", "qa", "production/x"])
    def test_invalid_environments(self, environment: str) -> None:
        with pytest.raises(ls_utils.LangSmithUserError, match="environment must be"):
            _agent("support", environment)

    @pytest.mark.parametrize(
        "environment", ["local", "development", "staging", "production"]
    )
    def test_environments_are_lowercased(self, environment: str) -> None:
        for given in (environment, environment.upper(), environment.title()):
            assert ls.Agent("a", given).env == environment

    def test_from_env_with_nothing_set(self) -> None:
        assert _from_env() is None

    def test_from_env_with_both_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(
            monkeypatch,
            LANGSMITH_AGENT_ID="support",
            LANGSMITH_AGENT_ENVIRONMENT="Staging",
        )
        assert _from_env() == STAGING_LRN

    @pytest.mark.parametrize(
        ("env", "match"),
        [
            ({"LANGSMITH_AGENT_ID": "support"}, "LANGSMITH_AGENT_ID='support'"),
            ({"LANGSMITH_AGENT_ENVIRONMENT": "staging"}, "needs LANGSMITH_AGENT_ID"),
            (
                {
                    "LANGSMITH_AGENT_ID": "Bad_Id",
                    "LANGSMITH_AGENT_ENVIRONMENT": "local",
                },
                "1 to 63",
            ),
            (
                {"LANGSMITH_AGENT_ID": "support", "LANGSMITH_AGENT_ENVIRONMENT": "x"},
                "environment must be",
            ),
        ],
        ids=["only_id", "only_environment", "bad_id", "bad_environment"],
    )
    def test_from_env_rejects_half_or_invalid(
        self, monkeypatch: pytest.MonkeyPatch, env: dict, match: str
    ) -> None:
        _set_env(monkeypatch, **env)
        with pytest.raises(EnvAddressError, match=match):
            _from_env()

    def test_there_is_no_address_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(monkeypatch, LANGSMITH_ADDRESS=SUPPORT_LRN)
        assert _from_env() is None

    def test_agent_is_an_address(self) -> None:
        assert isinstance(SUPPORT, ls.Address)
        assert not isinstance(SUPPORT_LRN, ls.Address)
        assert ls.Agent(id="support", env="PRODUCTION") == SUPPORT

    def test_agent_renders_the_api_address(self) -> None:
        assert SUPPORT.to_api_address() == {
            "kind": "AGENT",
            "id": "support",
            "environment": "PRODUCTION",
        }

    def test_agent_is_immutable(self) -> None:
        with pytest.raises(AttributeError):
            SUPPORT.env = "staging"  # type: ignore[misc]

    @pytest.mark.parametrize("value", ["support", SUPPORT_LRN, 42, object()])
    def test_entry_points_reject_anything_but_an_address(self, value: Any) -> None:
        with pytest.raises(ls_utils.LangSmithUserError, match="(?i)address"):
            with ls.tracing_context(address=value):
                pass
        with pytest.raises(ls_utils.LangSmithUserError, match="(?i)address"):
            ls.configure(address=value)
        with pytest.raises(ls_utils.LangSmithUserError, match="(?i)address"):
            traceable(address=value)
        with pytest.raises(ls_utils.LangSmithUserError, match="(?i)address"):
            RunTree(name="r", address=value)


EXPERIMENT = ls.Experiment("0190C3D4-0000-7000-8000-0000000000B1")
EVALUATOR = ls.Evaluator()


class TestOtherAddresses:
    """Addresses of other features name a project for the query APIs only."""

    def test_the_api_addresses(self) -> None:
        assert EXPERIMENT.to_api_address() == {
            "kind": "EXPERIMENT",
            "id": "0190c3d4-0000-7000-8000-0000000000b1",
        }
        assert EVALUATOR.to_api_address() == {"kind": "EVALUATOR"}

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "x",
            "0190c3d4",
            42,
            # Spellings of a UUID that the JS SDK does not take either.
            "0190c3d400007000800000000000b1aa",
            "{0190c3d4-0000-7000-8000-0000000000b1}",
            "urn:uuid:0190c3d4-0000-7000-8000-0000000000b1",
        ],
    )
    def test_an_experiment_id_must_be_a_uuid(self, value: Any) -> None:
        with pytest.raises(ls_utils.LangSmithUserError, match="UUID"):
            ls.Experiment(value)

    def test_they_are_addresses(self) -> None:
        for address in (SUPPORT, EXPERIMENT, EVALUATOR):
            assert isinstance(address, ls.Address)

    @pytest.mark.parametrize("address", [EXPERIMENT, EVALUATOR], ids=["exp", "eval"])
    def test_only_an_agent_can_receive_traces(self, address: Any) -> None:
        match = "Only an `Agent` can receive traces"
        with pytest.raises(ls_utils.LangSmithUserError, match=match):
            with ls.tracing_context(address=address):
                pass
        with pytest.raises(ls_utils.LangSmithUserError, match=match):
            ls.configure(address=address)
        with pytest.raises(ls_utils.LangSmithUserError, match=match):
            traceable(address=address)
        with pytest.raises(ls_utils.LangSmithUserError, match=match):
            RunTree(name="r", address=address)
        with pytest.raises(ls_utils.LangSmithUserError, match=match):
            _addressing.normalize_replicas([address])
        with pytest.raises(ls_utils.LangSmithUserError, match=match):
            _addressing.apply_to_payload({"id": "x", "address": address})


class TestAddressObjectsAtEntryPoints:
    """An `Address` is validated once at the entry point; the SDK carries an `Agent`."""

    def test_tracing_context(self, client: Client) -> None:
        with ls.tracing_context(enabled=True, client=client, address=SUPPORT):
            assert _root() == (None, SUPPORT)

    def test_traceable(self, client: Client) -> None:
        f = traceable(address=SUPPORT)(_root.__wrapped__)
        with ls.tracing_context(enabled=True, client=client):
            assert f() == (None, SUPPORT)

    def test_langsmith_extra(self, client: Client) -> None:
        with ls.tracing_context(enabled=True, client=client):
            assert _root(langsmith_extra={"address": SUPPORT}) == (
                None,
                SUPPORT,
            )

    def test_trace(self, client: Client) -> None:
        with ls.tracing_context(enabled=True, client=client):
            with trace("r", client=client, address=SUPPORT) as run:
                assert _destination(run) == (None, SUPPORT)

    def test_configure(self) -> None:
        ls.configure(address=SUPPORT)
        assert _context._GLOBAL_ADDRESS == SUPPORT

    def test_run_tree_carries_an_agent(self) -> None:
        assert RunTree(name="r", address=SUPPORT).address == SUPPORT

    def test_replica_objects(self) -> None:
        assert _addressing.normalize_replicas([SUPPORT]) == [{"address": SUPPORT}]
        assert _addressing.normalize_replicas([{"address": SUPPORT}]) == [
            {"address": SUPPORT}
        ]

    def test_a_replica_must_be_an_address(self) -> None:
        with pytest.raises(ls_utils.LangSmithUserError, match="(?i)address"):
            _addressing.normalize_replicas([SUPPORT_LRN])
        with pytest.raises(ls_utils.LangSmithUserError, match="(?i)address"):
            _addressing.normalize_replicas([{"address": SUPPORT_LRN}])

    def test_wire_carries_the_lrn_string(self) -> None:
        payload = RunTree(name="r", address=SUPPORT)._get_dicts_safe()
        _addressing.apply_to_payload(payload)
        assert payload["address"] == SUPPORT_LRN

    def test_an_object_that_is_not_an_address_is_rejected(self) -> None:
        with pytest.raises(ls_utils.LangSmithUserError, match="(?i)address"):
            RunTree(name="r", address=object())  # type: ignore[arg-type]


class TestLrnIsWireOnly:
    """An LRN string is the wire format, never an input."""

    def test_tracing_context(self) -> None:
        with pytest.raises(ls_utils.LangSmithUserError, match="(?i)address"):
            with ls.tracing_context(address=SUPPORT_LRN):  # type: ignore[arg-type]
                pass

    def test_traceable(self) -> None:
        with pytest.raises(ls_utils.LangSmithUserError, match="(?i)address"):
            traceable(address=SUPPORT_LRN)  # type: ignore[arg-type]

    def test_langsmith_extra(self, client: Client) -> None:
        with ls.tracing_context(enabled=True, client=client):
            with pytest.raises(ls_utils.LangSmithUserError, match="(?i)address"):
                _root(langsmith_extra={"address": SUPPORT_LRN})  # type: ignore[typeddict-item]

    def test_configure(self) -> None:
        with pytest.raises(ls_utils.LangSmithUserError, match="(?i)address"):
            ls.configure(address=SUPPORT_LRN)  # type: ignore[arg-type]

    def test_run_tree(self) -> None:
        with pytest.raises(ls_utils.LangSmithUserError, match="(?i)address"):
            RunTree(name="r", address=SUPPORT_LRN)  # type: ignore[arg-type]

    def test_create_run(self, client: Client) -> None:
        with pytest.raises(ls_utils.LangSmithUserError, match="(?i)address"):
            client.create_run(
                name="r",
                inputs={},
                run_type="chain",
                address=SUPPORT_LRN,  # type: ignore[arg-type]
            )


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
        _set_env(
            monkeypatch,
            LANGSMITH_AGENT_ID="support",
            LANGSMITH_AGENT_ENVIRONMENT="production",
        )
        with ls.tracing_context(enabled=True, client=client):
            assert _root() == (None, SUPPORT)

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

    @pytest.mark.parametrize("settle", [_addressing.resolve, _addressing.first_named])
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
    "half_an_address": {"LANGSMITH_AGENT_ID": "support"},
    "address_and_project": {
        "LANGSMITH_AGENT_ID": "support",
        "LANGSMITH_AGENT_ENVIRONMENT": "staging",
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
        ({"LANGSMITH_AGENT_ID": "support"}, "needs LANGSMITH_AGENT_ENVIRONMENT"),
        (
            {"LANGSMITH_AGENT_ID": "Bad_Id", "LANGSMITH_AGENT_ENVIRONMENT": "staging"},
            "1 to 63",
        ),
        (
            {
                "LANGSMITH_AGENT_ID": "support",
                "LANGSMITH_AGENT_ENVIRONMENT": "staging",
                "LANGSMITH_PROJECT": "p",
            },
            "both set",
        ),
        (
            {"LANGSMITH_AGENT_ID": "support", "LANGSMITH_AGENT_ENVIRONMENT": "staging"},
            None,
        ),
    ],
    ids=["half_an_address", "invalid_agent_id", "address_and_project", "address_only"],
)
def test_client_warns_about_an_unusable_env(
    monkeypatch: pytest.MonkeyPatch, env: dict, warning: Optional[str]
) -> None:
    _set_env(monkeypatch, **env)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _addressing.warn_on_env()
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
        baggage = headers["baggage"]
        assert f"langsmith-address={urllib.parse.quote(SUPPORT_LRN)}" in baggage
        assert "langsmith-agent" not in baggage
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

    @pytest.mark.parametrize(
        "bad",
        [
            "langsmith-address=support",
            "langsmith-address=",
            "langsmith-address=lrn%3Aagents/Bad_Id/environments/local",
            "langsmith-address=lrn%3Aagents/support/environments/prod",
            "langsmith-address=lrn%3Aagents/support/environments/",
            "langsmith-address=lrn%3Aagents/a/b/environments/local",
            "langsmith-address=lrn%3Aagents/support/environments/local/extra",
            "langsmith-address=lrn%3Aagents/support/environments/local%0A",
            # The flat fields an earlier format used are not read.
            "langsmith-agent-id=support,langsmith-agent-environment=production",
        ],
    )
    def test_a_malformed_header_address_is_ignored(self, bad: str) -> None:
        headers = RunTree(name="up", project_name="upstream").to_headers()
        child = RunTree.from_headers(
            {**headers, "baggage": f"{headers['baggage']},{bad}"}
        )
        assert child is not None
        assert _destination(child) == ("upstream", None)

    def test_a_header_replica_with_an_address_round_trips(self) -> None:
        replicas = [
            {"address": STAGING_LRN},
            {"address": "bad"},
            # The fields an earlier format used are not read.
            {"address": {"agent_id": "support", "agent_environment": "staging"}},
            {"project_name": "p"},
        ]
        quoted = urllib.parse.quote(json.dumps(replicas))
        parsed = _Baggage.from_header(f"langsmith-replicas={quoted}")
        assert parsed.replicas == [{"address": STAGING}, {"project_name": "p"}]


class TestReplicas:
    def test_a_bare_address_is_a_replica(self) -> None:
        run = RunTree(name="r", replicas=[SUPPORT, {"project_name": "p"}])
        assert run.replicas == [{"address": SUPPORT}, {"project_name": "p"}]

    def test_the_replica_seed_is_the_address_string(self) -> None:
        run = RunTree(name="r", project_name="p")
        dup = run._remap_for_project(None, address=STAGING)
        assert dup["id"] == uuid7_deterministic(run.id, STAGING_LRN)

    def test_replicas_to_different_addresses_get_distinct_ids(self) -> None:
        run = RunTree(name="r", project_name="p")
        a = run._remap_for_project(None, address=SUPPORT)
        b = run._remap_for_project(None, address=STAGING)
        assert a["id"] != b["id"]
        assert (a["address"], b["address"]) == (SUPPORT, STAGING)


# -- On the wire ----------------------------------------------------------------------


class TestWire:
    def test_a_run_payload_carries_one_lowercase_string(self) -> None:
        payload = RunTree(name="r", address=SUPPORT)._get_dicts_safe()
        _addressing.apply_to_payload(payload)
        assert payload["address"] == "lrn:agents/support/environments/production"
        assert "agent_id" not in payload
        assert "agent_environment" not in payload
        assert "session_name" not in payload

    def test_a_wire_address_is_checked_and_kept(self) -> None:
        """A retried batch re-sends an address it already applied."""
        payload = {"address": "lrn:agents/support/environments/PRODUCTION"}
        _addressing.apply_to_payload(payload)
        assert payload["address"] == SUPPORT_LRN

    @pytest.mark.parametrize(
        "bad",
        [
            "support",
            "",
            "lrn:agents/Bad_Id/environments/local",
            "lrn:agents/support/environments/prod",
            "lrn:agents/a/b/environments/local",
        ],
    )
    def test_a_malformed_wire_address_is_rejected(self, bad: str) -> None:
        """It is caught here, rather than failing the whole batch in the backend."""
        with pytest.raises(ls_utils.LangSmithUserError, match="not a valid") as error:
            _addressing.apply_to_payload({"address": bad})
        if bad:
            assert bad not in str(error.value)

    @pytest.mark.parametrize("update", [False, True])
    def test_a_run_tree_keeps_its_address_on_the_batch_path(
        self, client: Client, update: bool
    ) -> None:
        """`batch_ingest_runs` / `multipart_ingest` dump pydantic runs."""
        run = RunTree(name="r", address=SUPPORT)
        payload = client._run_transform(run, update=update)
        assert payload["address"] == SUPPORT_LRN

    def test_a_payload_address_object_is_rendered_once(self) -> None:
        payload = {"id": "x", "address": ls.Agent("support", "Production")}
        _addressing.apply_to_payload(payload)
        assert payload["address"] == SUPPORT_LRN

    def test_applying_to_a_payload_twice_is_a_no_op(self) -> None:
        """A retried batch re-sends the caller's dicts, already applied."""
        payload = {"id": "x", "address": SUPPORT}
        _addressing.apply_to_payload(payload)
        applied = dict(payload)
        _addressing.apply_to_payload(payload)
        assert payload == applied

    def test_retrying_the_same_batch_keeps_the_address(self, client: Client) -> None:
        run = {"name": "r", "address": SUPPORT, "run_type": "chain"}
        first = client._run_transform(run, copy=False)["address"]
        second = client._run_transform(run, copy=False)["address"]
        assert first == second == SUPPORT_LRN

    def test_a_payload_address_must_be_an_address_or_wire_data(self) -> None:
        with pytest.raises(ls_utils.LangSmithUserError, match="(?i)address"):
            _addressing.apply_to_payload({"id": "x", "address": 42})

    def test_a_project_payload_is_untouched(self) -> None:
        payload = {"name": "r", "session_name": "p"}
        _addressing.apply_to_payload(payload)
        assert payload == {"name": "r", "session_name": "p"}

    def test_the_env_fills_in_an_unaddressed_post(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _set_env(
            monkeypatch,
            LANGSMITH_AGENT_ID="support",
            LANGSMITH_AGENT_ENVIRONMENT="Staging",
        )
        payload: dict = {"id": "x", "session_name": None}
        _addressing.apply_to_payload(payload)
        assert payload == {"id": "x", "address": STAGING_LRN}

    def test_an_update_does_not_read_the_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _set_env(
            monkeypatch,
            LANGSMITH_AGENT_ID="support",
            LANGSMITH_AGENT_ENVIRONMENT="staging",
        )
        payload: dict = {"id": "x"}
        _addressing.apply_to_payload(payload, update=True)
        assert "address" not in payload

    def _feedback(self, address: Any) -> FeedbackCreate:
        return FeedbackCreate(
            key="k",
            feedback_source={"type": "api"},  # type: ignore[arg-type]
            id="00000000-0000-0000-0000-000000000000",  # type: ignore[arg-type]
            run_id=None,
            trace_id=None,
            address=address,
        )

    def test_feedback_carries_one_lowercase_string(self) -> None:
        dumped = self._feedback(SUPPORT).model_dump(exclude_none=True)
        assert dumped["address"] == SUPPORT_LRN
        assert "agent_id" not in dumped

    def test_feedback_without_an_address_has_no_key(self) -> None:
        assert "address" not in self._feedback(None).model_dump(exclude_none=True)

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

    def test_feedback_rejects_a_malformed_address(self) -> None:
        with pytest.raises(ls_utils.LangSmithUserError):
            self._feedback("support")

    def test_no_run_url_for_an_addressed_run(self) -> None:
        with pytest.raises(ls_utils.LangSmithUserError, match="run URL"):
            RunTree(name="r", address=SUPPORT).get_url()
