"""Resolving whether a run is addressed by project or by agent.

Agent addressing is in beta. The rules changed repeatedly while it was being
built, so they live in one module rather than spread across the client, the
run tree and the tracing helpers, where three copies had already drifted
apart.
"""

from __future__ import annotations

import warnings
from typing import Any, Optional

from langsmith import utils
from langsmith._internal._beta_decorator import _warn_once


def resolve_pair(
    agent_id: Optional[str] = None,
    agent_environment: Optional[str] = None,
) -> tuple[Optional[str], Optional[str]]:
    """Fill each half of the agent pair from its env var unless given.

    An explicitly provided value is left alone, including when the other half
    comes from the environment -- that combination is a complete pair.
    """
    return (
        agent_id if agent_id is not None else utils.get_tracer_agent_id(),
        agent_environment
        if agent_environment is not None
        else utils.get_tracer_agent_environment(),
    )


def is_addressed(agent_id: Optional[str], agent_environment: Optional[str]) -> bool:
    """Whether a run is addressed by agent rather than by project.

    Either half is enough. A lone ``agent_environment`` is incomplete and the
    endpoint rejects it, but it must not fall through to a project the caller
    never named -- that would quietly send the run somewhere else instead of
    reporting the mistake.
    """
    return agent_id is not None or agent_environment is not None


def warn_is_beta() -> None:
    """Warn the first time a run is actually addressed to an agent.

    The docstrings say the feature is in beta, but a caller who reaches it
    through an env var never read them, and the first sign of trouble would
    otherwise be a 400 from a workspace without the flag. Emitted where the
    addressing is settled rather than at client construction: a process that
    configures an agent and never traces to one has nothing to hear about.

    `_warn_once` caches on the message, so this fires once per process no
    matter how many runs are addressed. The call site's depth varies by entry
    point -- `create_run`, `update_run`, and the two batch methods all arrive
    here through `_run_transform` -- so the warning points at the SDK rather
    than guessing a `stacklevel` that would be wrong for most of them.
    """
    _warn_once(
        "Agent addressing (`agent_id` / `agent_environment`) is in beta and is "
        "enabled per workspace. A workspace without it rejects the run, so the "
        "trace is lost rather than falling back to a project. The behavior may "
        "change without notice."
    )


def resolve(
    project: Optional[str] = None,
    agent_id: Optional[str] = None,
    agent_environment: Optional[str] = None,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Settle a run's single destination, as `(project, agent_id, environment)`.

    The arguments are the values named in code -- a parameter, a context
    variable, a parent run, `ls.configure`. The environment fills in below
    them, so callers pass their own chain of code-level tiers and leave the
    env vars to this function.

    Code beats the environment in both directions: a project named in code
    drops the ambient agent, and an agent named in code drops the ambient
    project. Half an agent named in code is completed from the environment
    rather than competing with it.

    When only the environment addresses the run, both modes travel and the
    endpoint refuses the pair -- there is no tier to choose between, and
    picking one would move the caller's traces without telling them. Only the
    `default` project the SDK would otherwise invent is suppressed.

    A project variable set to the empty string names no project, so it falls
    back to `default` the way an unset one does.
    """
    if project:
        return project, None, None
    if is_addressed(agent_id, agent_environment):
        return None, *resolve_pair(agent_id, agent_environment)
    env_agent_id = utils.get_tracer_agent_id()
    env_agent_environment = utils.get_tracer_agent_environment()
    if is_addressed(env_agent_id, env_agent_environment):
        return (
            utils.get_tracer_project(return_default_value=False) or None,
            env_agent_id,
            env_agent_environment,
        )
    return utils.get_tracer_project() or "default", None, None


def warn_on_env() -> None:
    """Warn when the environment's agent addressing cannot reach the endpoint.

    Either half of the pair addresses a run, so either half alone is refused
    with a 400 that takes the whole batch with it -- and `AGENT_ENVIRONMENT`
    is a generic enough name to be set by accident. A project configured
    beside a complete pair is refused the same way.

    Emitted at client construction rather than per run, so it is seen once
    instead of drowned out by the background flush's warnings, which only
    log.
    """
    agent_id = utils.get_tracer_agent_id()
    agent_environment = utils.get_tracer_agent_environment()
    if not is_addressed(agent_id, agent_environment):
        return
    if agent_id is None or agent_environment is None:
        missing, present = (
            (
                "LANGSMITH_AGENT_ID",
                f"LANGSMITH_AGENT_ENVIRONMENT ({agent_environment!r})",
            )
            if agent_id is None
            else ("LANGSMITH_AGENT_ENVIRONMENT", f"LANGSMITH_AGENT_ID ({agent_id!r})")
        )
        warnings.warn(
            f"{present} is set without {missing}. Agent addressing needs both, "
            "so the API refuses the request and the whole batch of runs is "
            f"dropped. Set {missing}, or unset the other to trace to a project.",
            utils.LangSmithWarning,
            stacklevel=3,
        )
        return
    project = utils.get_tracer_project(return_default_value=False)
    if project is None:
        return
    warnings.warn(
        f"LANGSMITH_AGENT_ID ({agent_id!r}) and a configured project "
        f"({project!r}) both address runs, and the API accepts only one. "
        "Unset LANGSMITH_AGENT_ID to trace to the project, or unset "
        "LANGSMITH_PROJECT (and LANGCHAIN_PROJECT / LANGCHAIN_SESSION) to "
        "trace to the agent.",
        utils.LangSmithWarning,
        stacklevel=3,
    )


def reject_url(
    session_id: Optional[Any],
    agent_id: Optional[str],
    agent_environment: Optional[str],
) -> None:
    """Refuse to build a run URL the SDK cannot know.

    A run URL is keyed on the project id. The endpoint resolves an agent to
    its environment's project and never tells the SDK which, so an
    agent-addressed run has no project id here until it is read back. Falling
    through would resolve the literal `default` project and hand back a link
    to the wrong place, or raise a not-found from inside what callers treat as
    a convenience.
    """
    if session_id is not None or not is_addressed(agent_id, agent_environment):
        return
    raise utils.LangSmithUserError(
        "No run URL is available for an agent-addressed run yet. The endpoint "
        "resolves the agent to its environment's project, so only it knows "
        "the project this run is in; there is no agent-shaped run URL. Read "
        "the run back and build the URL from its `session_id`."
    )


def reject_conflicting(
    *,
    project: Optional[Any] = None,
    session_id: Optional[Any] = None,
    agent_id: Optional[str] = None,
    agent_environment: Optional[str] = None,
) -> None:
    """Reject a call that names both a project and an agent.

    A run goes to one or the other, and the endpoint never sees this particular
    conflict: resolution drops the agent before the payload is built, so without
    this the agent would be discarded in silence. Every other rejection is left
    to the endpoint, which can see what it is sent.

    Callers pass only values a caller supplied in this one call. A resolved run
    body can legitimately carry both -- a project configured in the environment
    travels with the agent so the endpoint refuses the pair -- and an inherited
    pair must not be mistaken for a conflict.

    Pass only values the caller supplied in this call. An agent that came from
    the environment alongside an explicit project is not a conflict -- the
    project wins and the agent is dropped, which is what lets an evaluation set
    its own project while `LANGSMITH_AGENT_ID` is set process-wide.

    Raises:
        utils.LangSmithUserError: If a project and an agent are both named.
    """
    named_project = project if project is not None else session_id
    named_agent = agent_id if agent_id is not None else agent_environment
    if named_project is not None and named_agent is not None:
        raise utils.LangSmithUserError(
            f"A run is addressed by project ({named_project!r}) or by agent "
            f"({named_agent!r}), not both. Pass one of them, or set "
            "LANGSMITH_AGENT_ID and leave the project off the call."
        )


def apply_to_payload(payload: dict, *, update: bool = False) -> None:
    """Settle the addressing mode on a run payload.

    A project already on the payload addresses the run, so the environment
    is not consulted; whatever agent fields the caller put there travel
    alongside it and the endpoint refuses the pair. With no project, the
    agent env vars fill in and the null project keys are dropped, so the
    payload never carries a null for the mode it isn't using.

    Which project reaches this payload is decided upstream, in `create_run`
    and in the `RunTree` validator: a project named on the call replaces the
    agent outright, and only one the caller *configured* travels with it.

    On an update the environment is not consulted: a patch inherits its
    target from the post that established it. Filling it in here would
    address a patch to the agent while its post went to a project, because
    an update carries a project only when the caller passed one and most
    callers don't -- the endpoint resolves the run by id. A patch that
    names nothing falls to that same lookup, which is how every patch is
    resolved today.

    Both members are required, but the endpoint is the one that says so:
    whatever resolved is forwarded, and a partial pair comes back as a 400
    carrying the server's own message. Dropping it instead would route the
    run to the `default` project, so a typo would quietly succeed in the
    wrong place rather than failing.

    The keys read are the keys written, so running this twice re-resolves an
    explicit value to itself rather than letting the environment replace it.

    Applies to creates and updates alike: a `patch.<run_id>` part has to be
    addressed the same way as the `post.<run_id>` it belongs to.
    """
    agent_id = payload.pop("agent_id", None)
    agent_environment = payload.pop("agent_environment", None)
    named_project = (
        payload.get("session_id") is not None or payload.get("session_name") is not None
    )
    if not (update or named_project):
        # A patch inherits its post's target, and a project already on the
        # payload addresses the run on its own; neither consults the
        # environment. Every other create does, including one that named
        # half an agent in code -- the missing half comes from the env var
        # rather than reaching the endpoint as an incomplete pair.
        agent_id, agent_environment = resolve_pair(agent_id, agent_environment)
    if not is_addressed(agent_id, agent_environment):
        # Neither mode is addressed; leave the server-side fallback to it.
        return
    warn_is_beta()
    if agent_id is not None:
        payload["agent_id"] = agent_id
    if agent_environment is not None:
        payload["agent_environment"] = agent_environment
    if not named_project:
        # Nothing to drop, and nothing to keep: the null project keys would
        # otherwise be serialized.
        payload.pop("session_name", None)
        payload.pop("session_id", None)
