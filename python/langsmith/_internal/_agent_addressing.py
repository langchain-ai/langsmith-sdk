"""Resolving whether a run is addressed by project or by target.

The address travels as a whole `Target` everywhere -- context variables, run
trees, replicas, headers -- and is unpacked into wire fields only here, in
`apply_to_payload` and `target_to_wire`. Loose `agent_id` / `agent_environment`
arguments are turned into a `Target` at the entry point that receives them.
"""

from __future__ import annotations

import logging
import warnings
from collections.abc import Mapping
from typing import Any, Optional

from langsmith import utils
from langsmith._internal._beta_decorator import _warn_once
from langsmith._target import EnvTargetError, Target

_LOGGER = logging.getLogger(__name__)


def coerce_target(
    target: Optional[Target] = None, loose: Optional[Mapping[str, Any]] = None
) -> Optional[Target]:
    """Settle the target an entry point was given, if any.

    `loose` holds whatever `agent_*` keyword arguments the caller passed. A
    half named there is completed from the env vars; one still incomplete
    raises here rather than as a 400 that drops the batch.

    Raises:
        utils.LangSmithUserError: If `target` is not a `Target`, is combined
            with loose fields, or the loose fields are incomplete.
    """
    loose_target = Target.from_wire(loose or {}, complete_from_env=True)
    if target is None:
        return loose_target
    if not isinstance(target, Target):
        raise utils.LangSmithUserError(
            f"`target` must be a `langsmith.Target`, got {type(target).__name__}. "
            "Build one with `langsmith.target(id, environment=...)`."
        )
    if loose_target is not None:
        raise utils.LangSmithUserError(
            "Pass either `target` or the loose `agent_*` fields, not both."
        )
    return target


def pop_target(values: dict) -> None:
    """Fold `target` and loose `agent_*` keys in `values` into one `target`.

    For entry points that take the address through a dict or `**kwargs`.
    """
    loose = {k: values.pop(k) for k in Target.wire_keys() if k in values}
    target = coerce_target(values.pop("target", None), loose)
    if target is not None:
        values["target"] = target


def normalize_replicas(replicas: Optional[Any]) -> Optional[list]:
    """Put each replica's address in a `target` key.

    A replica may be a bare `Target`, or a dict naming one through `target` or
    loose `agent_*` keys.
    """
    if replicas is None:
        return None
    normalized = []
    for replica in replicas:
        if isinstance(replica, Target):
            normalized.append({"target": replica})
            continue
        replica = dict(replica)
        pop_target(replica)
        normalized.append(replica)
    return normalized


def warn_is_beta() -> None:
    """Warn the first time a run is actually addressed to a target.

    `_warn_once` caches on the message, so this fires once per process.
    """
    _warn_once(
        "Agent addressing (`langsmith.target` / `agent_id` / "
        "`agent_environment`) is in beta and is enabled per workspace. A "
        "workspace without it rejects the run, so the trace is lost rather than "
        "falling back to a project. The behavior may change without notice."
    )


Tier = tuple[Optional[str], Optional[Target]]
"""One precedence level: the `(project, target)` it names, either may be unset."""


def resolve(*tiers: Tier) -> tuple[Optional[str], Optional[Target]]:
    """Settle a run's single destination, as `(project, target)`.

    `tiers` are the levels named in code, highest precedence first; the env
    vars are the last level, consulted here. The first level that names
    anything decides, whichever mode it names -- a target in `tracing_context`
    beats a project on the decorator, and the other way round.

    Raises:
        utils.LangSmithUserError: If one level named in code names both.
        EnvTargetError: If the env vars are the deciding level and name both,
            or half a target.
    """
    for level, (project, target) in enumerate(tiers, start=1):
        if project and target is not None:
            raise _both_at_one_level(project, target, f"at precedence level {level}")
        if project:
            return project, None
        if target is not None:
            return None, target
    env_project = utils.get_tracer_project(return_default_value=False) or None
    env_target = Target.from_env()
    if env_project and env_target is not None:
        raise EnvTargetError(
            str(_both_at_one_level(env_project, env_target, "in the environment"))
        )
    if env_target is not None:
        return None, env_target
    return env_project or "default", None


def first_named(*tiers: Tier) -> Tier:
    """Return the highest level that names a destination, without the env vars.

    Raises:
        utils.LangSmithUserError: If that level names both.
    """
    for level, (project, target) in enumerate(tiers, start=1):
        if project and target is not None:
            raise _both_at_one_level(project, target, f"at precedence level {level}")
        if project or target is not None:
            return project or None, target
    return None, None


def _both_at_one_level(
    project: str, target: Target, where: str
) -> utils.LangSmithUserError:
    return utils.LangSmithUserError(
        f"A project ({project!r}) and a target ({target!r}) are both set "
        f"{where}, so neither outranks the other. Set only one there, or set "
        "the one you want at a higher-precedence level."
    )


def log_untraced(error: EnvTargetError) -> None:
    """Log that a call runs untraced because the env can't address it."""
    _LOGGER.warning("LangSmith is not tracing this call: %s", error)


def warn_on_env() -> None:
    """Warn when the environment's target cannot be used.

    Half a target, or one beside a configured project, leaves calls that name
    nothing in code untraced -- and a name like `TARGET_ENVIRONMENT` is generic
    enough to be set by accident.

    Emitted at client construction rather than per run, so it is seen once.
    """
    present = [name for name, value in Target.env_values().items() if value]
    if not present:
        return
    try:
        target = Target.from_env()
    except EnvTargetError:
        warnings.warn(
            f"{', '.join(present)} is set, but not every LANGSMITH_TARGET_* "
            "variable a target needs, so calls that name no destination in "
            "code are not traced.",
            utils.LangSmithWarning,
            stacklevel=3,
        )
        return
    if target is None:
        return
    project = utils.get_tracer_project(return_default_value=False)
    if project is None:
        return
    warnings.warn(
        f"LANGSMITH_TARGET_ID ({target.id!r}) and a configured project "
        f"({project!r}) are both set in the environment, so calls that name "
        "no destination in code are not traced. Unset one of them.",
        utils.LangSmithWarning,
        stacklevel=3,
    )


def reject_url(session_id: Optional[Any], target: Optional[Target]) -> None:
    """Refuse to build a run URL the SDK cannot know.

    A run URL is keyed on the project id, and the endpoint resolves a target
    to its project without telling the SDK which.
    """
    if session_id is not None or target is None:
        return
    raise utils.LangSmithUserError(
        "No run URL is available for a target-addressed run yet. The endpoint "
        "resolves the target to its project, so only it knows the project this "
        "run is in. Read the run back and build the URL from its `session_id`."
    )


def reject_conflicting(
    *,
    project: Optional[Any] = None,
    session_id: Optional[Any] = None,
    target: Optional[Target] = None,
) -> None:
    """Reject a call that names both a project and a target.

    Pass only values the caller supplied in this call: an inherited or
    ambient target beside an explicit project is not a conflict -- the project
    wins, which is what lets an evaluation set its own project while
    `LANGSMITH_TARGET_ID` is set process-wide.

    Raises:
        utils.LangSmithUserError: If a project and a target are both named.
    """
    named_project = project if project is not None else session_id
    if named_project is not None and target is not None:
        raise utils.LangSmithUserError(
            f"A run is addressed by project ({named_project!r}) or by target "
            f"({target!r}), not both."
        )


def apply_to_payload(payload: dict, *, update: bool = False) -> None:
    """Render a run payload's address into its wire fields.

    The one place a run's `target` is unpacked. A project already on the
    payload addresses the run, so the environment is not consulted. With no
    project, an ambient target fills in and the null project keys are dropped.

    On an update the environment is not consulted: a patch inherits its
    target from the post that established it, and one naming nothing is
    resolved by run id.
    """
    pop_target(payload)
    target = payload.pop("target", None)
    named_project = (
        payload.get("session_id") is not None or payload.get("session_name") is not None
    )
    if target is None and not (update or named_project):
        target = Target.from_env()
    if target is None:
        return
    warn_is_beta()
    payload.update(target.to_wire())
    if not named_project:
        payload.pop("session_name", None)
        payload.pop("session_id", None)


def target_to_wire(values: dict) -> None:
    """Render a feedback payload's `target` into its wire fields."""
    target = values.pop("target", None)
    if target is not None:
        values.update(target.to_wire())
