"""`@traceable`, addressed by agent.

The most used entry point, and its own resolver: `run_helpers._setup_run`.
Every case calls a decorated root, and a nested decorated child when the case
has one, then asserts where each landed, post and patch alike.
"""

from __future__ import annotations

import pytest

from langsmith import address as ls_address
from langsmith.run_helpers import get_current_run_tree, traceable, tracing_context
from tests.integration_tests.agent_addressing.conftest import (
    AGENT,
    PROJECT,
    Case,
    Child,
    Harness,
    InAgent,
    InProject,
    Untraced,
)

ENV_AGENT = {
    "LANGSMITH_AGENT_ID": AGENT,
    "LANGSMITH_AGENT_ENVIRONMENT": "staging",
}
CONTEXT_AGENT = {"address": ls_address(agent_id=AGENT, agent_environment="staging")}

CASES = [
    # -- root, environment only ----------------------------------------------
    Case("env_agent", env=ENV_AGENT, lands_in=InAgent("STAGING")),
    # Half an address is not dropped into `default`: the call runs untraced,
    # and the SDK logs why.
    Case(
        "env_agent_id_only",
        env={"LANGSMITH_AGENT_ID": AGENT},
        lands_in=Untraced(reason="incomplete address"),
    ),
    # The other half.
    Case(
        "env_environment_only",
        env={"LANGSMITH_AGENT_ENVIRONMENT": "staging"},
        lands_in=Untraced(reason="incomplete address"),
    ),
    Case(
        "env_project", env={"LANGSMITH_PROJECT": PROJECT}, lands_in=InProject(PROJECT)
    ),
    Case("no_addressing", lands_in=InProject("default")),
    # Both from the environment, the same level: neither outranks the other,
    # so the call runs untraced and the SDK logs why, rather than picking one.
    Case(
        "env_agent_and_env_project",
        env={**ENV_AGENT, "LANGSMITH_PROJECT": PROJECT},
        lands_in=Untraced(reason="are both set in the environment"),
    ),
    # `HOSTED_LANGSERVE_PROJECT_NAME` is a configured project too, not the
    # `default` the SDK invents, so it conflicts like the one above.
    Case(
        "env_agent_and_hosted_project",
        env={**ENV_AGENT, "HOSTED_LANGSERVE_PROJECT_NAME": PROJECT},
        lands_in=Untraced(reason="are both set in the environment"),
    ),
    # -- root, a project named in code beats an agent in the environment ------
    Case(
        "env_agent_and_decorator_project",
        env=ENV_AGENT,
        decorator={"project_name": PROJECT},
        lands_in=InProject(PROJECT),
    ),
    Case(
        "env_agent_and_context_project",
        env=ENV_AGENT,
        context={"project_name": PROJECT},
        lands_in=InProject(PROJECT),
    ),
    Case(
        "configure_project_and_env_agent",
        env=ENV_AGENT,
        configure={"project_name": PROJECT},
        lands_in=InProject(PROJECT),
    ),
    # -- root, an agent named in code -----------------------------------------
    Case("context_agent", context=CONTEXT_AGENT, lands_in=InAgent("STAGING")),
    # The mirror of `env_agent_and_decorator_project`: code beats environment.
    Case(
        "context_agent_and_env_project",
        env={"LANGSMITH_PROJECT": PROJECT},
        context=CONTEXT_AGENT,
        lands_in=InAgent("STAGING"),
    ),
    # Two destinations named in code, at different levels: the higher level
    # wins, whichever mode it names -- here the context's agent over the
    # decorator's project.
    Case(
        "context_agent_and_decorator_project",
        context=CONTEXT_AGENT,
        decorator={"project_name": PROJECT},
        lands_in=InAgent("STAGING"),
    ),
    # The decorator's own arguments, beside `project_name`.
    Case(
        "decorator_agent",
        decorator={"address": ls_address(agent_id=AGENT, agent_environment="staging")},
        lands_in=InAgent("STAGING"),
    ),
    # -- nested calls ----------------------------------------------------------
    Case(
        "child_of_agent_root", env=ENV_AGENT, lands_in=InAgent("STAGING"), child=Child()
    ),
    # A child joins its parent's trace whatever it names: `create_child` copies
    # the parent's addressing and ignores what the child resolved for itself.
    Case(
        "child_of_agent_root_with_extra_project",
        env=ENV_AGENT,
        lands_in=InAgent("STAGING"),
        child=Child(extra={"project_name": PROJECT}),
    ),
    # An agent in the environment does not leak into a project-addressed trace.
    Case(
        "child_of_project_root_with_env_agent",
        env=ENV_AGENT,
        decorator={"project_name": PROJECT},
        lands_in=InProject(PROJECT),
        child=Child(),
    ),
    # Nor does an agent named mid-trace move the children out of it.
    Case(
        "child_context_agent_inside_project_root",
        decorator={"project_name": PROJECT},
        lands_in=InProject(PROJECT),
        child=Child(context=CONTEXT_AGENT),
    ),
]


@pytest.mark.parametrize("case", CASES, ids=str)
def test_addressing(case: Case, ls: Harness) -> None:
    """A configuration resolves to one destination, for the root and its child."""
    ls.assert_traced(ls.trace(case), case)


def test_a_child_forced_on_under_an_untraced_root_lands_in_the_agent(
    ls: Harness,
) -> None:
    """An untraced root hands nothing down, so the child resolves on its own."""
    ls.configure(Case("forced_on", env=ENV_AGENT, lands_in=InAgent("STAGING")))
    ids: dict = {}

    @traceable
    def child() -> None:
        run = get_current_run_tree()
        assert run is not None
        ids["child"] = run.id

    @traceable
    def root() -> None:
        assert get_current_run_tree() is None
        with tracing_context(enabled=True):
            child(langsmith_extra={"client": ls.client})

    with tracing_context(enabled=False):
        root()
    ls.client.flush()

    ls.assert_landed(ids["child"], InAgent("STAGING"))
