"""Unit tests for the `langsmith.agent` handle."""

from __future__ import annotations

from typing import Any, Optional
from unittest import mock
from unittest.mock import MagicMock

import pytest

import langsmith as ls
from langsmith import utils as ls_utils
from langsmith._internal import _context
from langsmith.client import Client
from langsmith.run_helpers import (
    get_current_run_tree,
    get_tracing_context,
    trace,
    traceable,
    tracing_context,
)
from langsmith.run_trees import RunTree, configure


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "LANGSMITH_AGENT_ID",
        "LANGSMITH_AGENT_ENVIRONMENT",
        "LANGSMITH_PROJECT",
        "LANGCHAIN_PROJECT",
        "LANGCHAIN_SESSION",
    ):
        monkeypatch.delenv(name, raising=False)
    ls_utils.get_env_var.cache_clear()
    ls_utils.get_tracer_agent_id.cache_clear()
    ls_utils.get_tracer_agent_environment.cache_clear()
    ls_utils.get_tracer_project.cache_clear()


@pytest.fixture
def client() -> Client:
    return Client(session=MagicMock(), api_key="test")


def _address(run: Optional[RunTree]) -> tuple:
    assert run is not None
    return run.agent_id, run.agent_environment, run.session_name


support = ls.agent("customer-support", environment="production")


class TestConstruction:
    @pytest.mark.parametrize("environment", ["prod", "Staging", "eu-canary"])
    def test_passes_any_environment_through(self, environment: str) -> None:
        assert ls.agent("a", environment=environment).environment == environment

    @pytest.mark.parametrize("environment", ["", None])
    def test_rejects_a_missing_environment(self, environment: Any) -> None:
        with pytest.raises(ls_utils.LangSmithUserError, match="environment"):
            ls.agent("a", environment=environment)

    @pytest.mark.parametrize("agent_id", ["", "x" * 256, None])
    def test_rejects_an_invalid_id(self, agent_id: Any) -> None:
        with pytest.raises(ls_utils.LangSmithUserError, match="id"):
            ls.agent(agent_id, environment="staging")

    def test_environment_is_required(self) -> None:
        with pytest.raises(TypeError):
            ls.agent("a")  # type: ignore[call-arg]

    def test_switching_environment_keeps_the_agent(self) -> None:
        assert support.with_environment("staging") == ls.Agent(
            "customer-support", "staging"
        )
        assert support.environment == "production"


class TestRendering:
    def test_bare_decorator(self, client: Client) -> None:
        seen: dict = {}

        @support.traceable
        def foo() -> None:
            seen["value"] = _address(get_current_run_tree())

        with tracing_context(enabled=True, client=client):
            foo()

        assert seen["value"] == ("customer-support", "production", None)

    def test_decorator_with_arguments(self, client: Client) -> None:
        seen: dict = {}

        @support.with_environment("staging").traceable(run_type="llm", name="named")
        def foo() -> None:
            run = get_current_run_tree()
            assert run is not None
            seen["value"] = (*_address(run), run.run_type, run.name)

        with tracing_context(enabled=True, client=client):
            foo()

        assert seen["value"] == ("customer-support", "staging", None, "llm", "named")

    def test_trace(self, client: Client) -> None:
        with tracing_context(enabled=True, client=client):
            with support.trace("r") as run:
                assert _address(run) == ("customer-support", "production", None)

    def test_tracing_context_beats_the_decorator(self, client: Client) -> None:
        """Same ordering as `project_name`: the context var wins."""
        seen: dict = {}

        @support.traceable
        def foo() -> None:
            seen["value"] = _address(get_current_run_tree())

        with support.with_environment("staging").tracing_context(
            enabled=True, client=client
        ):
            foo()

        assert seen["value"] == ("customer-support", "staging", None)

    def test_replica(self) -> None:
        assert support.with_environment("staging").replica(updates={"x": 1}) == {
            "agent_id": "customer-support",
            "agent_environment": "staging",
            "updates": {"x": 1},
        }

    @pytest.mark.parametrize("kwarg", ["project_name", "agent_id", "agent_environment"])
    @pytest.mark.parametrize(
        "method", ["traceable", "trace", "tracing_context", "replica"]
    )
    def test_rejects_a_second_address(self, method: str, kwarg: str) -> None:
        args = ("r",) if method == "trace" else ()
        with pytest.raises(ls_utils.LangSmithUserError, match="already addresses"):
            getattr(support, method)(*args, **{kwarg: "x"})


staging = support.with_environment("staging")


class TestEntryPointsTakeAHandle:
    """`agent=` is accepted wherever `agent_id` / `agent_environment` are."""

    def test_tracing_context(self) -> None:
        with tracing_context(agent=staging):
            ctx = get_tracing_context()
        assert (ctx["agent_id"], ctx["agent_environment"]) == (
            "customer-support",
            "staging",
        )

    def test_traceable(self, client: Client) -> None:
        seen: dict = {}

        @traceable(agent=staging)
        def foo() -> None:
            seen["value"] = _address(get_current_run_tree())

        with tracing_context(enabled=True, client=client):
            foo()

        assert seen["value"] == ("customer-support", "staging", None)

    def test_langsmith_extra_beats_the_decorator(self, client: Client) -> None:
        seen: dict = {}

        @support.traceable
        def foo() -> None:
            seen["value"] = _address(get_current_run_tree())

        extra: Any = {"agent": staging}
        with tracing_context(enabled=True, client=client):
            foo(langsmith_extra=extra)

        assert seen["value"] == ("customer-support", "staging", None)
        # The caller's dict is left alone.
        assert extra == {"agent": staging}

    def test_trace(self, client: Client) -> None:
        with tracing_context(enabled=True, client=client):
            with trace("r", agent=staging) as run:
                assert _address(run) == ("customer-support", "staging", None)

    def test_run_tree(self) -> None:
        run = RunTree(name="r", agent=staging)
        assert _address(run) == ("customer-support", "staging", None)

    def test_configure(self) -> None:
        try:
            configure(agent=staging)
            assert (
                _context._GLOBAL_AGENT_ID,
                _context._GLOBAL_AGENT_ENVIRONMENT,
            ) == ("customer-support", "staging")
            configure(agent=None)
            assert _context._GLOBAL_AGENT_ID is None
            assert _context._GLOBAL_AGENT_ENVIRONMENT is None
        finally:
            configure(agent=None)

    def test_configure_rejects_both_forms(self) -> None:
        with pytest.raises(ls_utils.LangSmithUserError, match="not both"):
            configure(agent=staging, agent_id="x")

    def test_replicas(self) -> None:
        run = RunTree(name="r", replicas=[staging, {"project_name": "p"}])
        assert run.replicas == [
            {"agent_id": "customer-support", "agent_environment": "staging"},
            {"project_name": "p"},
        ]

    def test_tracing_context_replicas(self) -> None:
        with tracing_context(replicas=[staging]):
            ctx = get_tracing_context()
        assert ctx["replicas"] == [
            {"agent_id": "customer-support", "agent_environment": "staging"}
        ]

    def test_client_create_run(self, client: Client) -> None:
        with mock.patch.object(
            Client, "_filter_for_sampling", return_value=[]
        ) as filtered:
            client.create_run("r", {}, "chain", agent=staging)
        (run_create,) = filtered.call_args.args[0]
        assert "agent" not in run_create
        assert (run_create["agent_id"], run_create["agent_environment"]) == (
            "customer-support",
            "staging",
        )

    def test_client_update_run(self, client: Client) -> None:
        from langsmith._internal import _agent_addressing

        with mock.patch.object(
            _agent_addressing,
            "apply_to_payload",
            wraps=_agent_addressing.apply_to_payload,
        ) as apply:
            client.update_run("00000000-0000-0000-0000-000000000000", agent=staging)
        data = apply.call_args.args[0]
        assert (data["agent_id"], data["agent_environment"]) == (
            "customer-support",
            "staging",
        )

    @pytest.mark.parametrize(
        "call",
        [
            lambda: tracing_context(agent=staging, agent_id="x").__enter__(),
            lambda: traceable(agent=staging, agent_environment="x"),
            lambda: trace("r", agent=staging, agent_id="x"),
            lambda: RunTree(name="r", agent=staging, agent_id="x"),
            lambda: Client(session=MagicMock(), api_key="t").create_feedback(
                run_id="00000000-0000-0000-0000-000000000000",
                key="k",
                agent=staging,
                agent_id="x",
            ),
        ],
        ids=["tracing_context", "traceable", "trace", "run_tree", "create_feedback"],
    )
    def test_rejects_a_handle_beside_the_pair(self, call: Any) -> None:
        with pytest.raises(ls_utils.LangSmithUserError, match="not both"):
            call()

    def test_rejects_a_handle_beside_a_project(self) -> None:
        with pytest.raises(ls_utils.LangSmithUserError, match="not both"):
            with tracing_context(agent=staging, project_name="p"):
                pass

    def test_rejects_a_non_handle(self) -> None:
        with pytest.raises(ls_utils.LangSmithUserError, match="langsmith.Agent"):
            with tracing_context(agent="customer-support"):  # type: ignore[arg-type]
                pass
