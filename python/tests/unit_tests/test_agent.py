"""Unit tests for the `langsmith.agent` handle."""

from __future__ import annotations

from typing import Any, Optional
from unittest.mock import MagicMock

import pytest

import langsmith as ls
from langsmith import utils as ls_utils
from langsmith.client import Client
from langsmith.run_helpers import get_current_run_tree, tracing_context
from langsmith.run_trees import RunTree


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
