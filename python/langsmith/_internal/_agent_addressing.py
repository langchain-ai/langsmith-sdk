"""Resolving whether a run is addressed by project or by address.

The address travels as a whole `Address` everywhere -- context variables, run
trees, replicas, headers -- and is unpacked into wire fields only here, in
`apply_to_payload` and `FeedbackCreate.model_dump`.
"""

from __future__ import annotations

import functools
import logging
import warnings
from typing import Any, Optional

from langsmith import utils
from langsmith._address import Address, EnvAddressError
from langsmith._internal._beta_decorator import _warn_once

_LOGGER = logging.getLogger(__name__)


def check_address(address: Any) -> Optional[Address]:
    """Return `address` if it is an `Address` or `None`, else raise.

    Raises:
        utils.LangSmithUserError: If `address` is anything else.
    """
    if address is None or isinstance(address, Address):
        return address
    raise utils.LangSmithUserError(
        f"`address` must be a `langsmith.Address`, got {type(address).__name__}. "
        "Build one with `langsmith.address(agent_id=..., agent_environment=...)`."
    )


def normalize_replicas(replicas: Optional[Any]) -> Optional[list]:
    """Put a bare `Address` replica in an `address` key, and check the rest."""
    if replicas is None:
        return None
    normalized = []
    for replica in replicas:
        if isinstance(replica, Address):
            normalized.append({"address": replica})
            continue
        check_address(replica.get("address"))
        normalized.append(dict(replica))
    return normalized


def warn_is_beta() -> None:
    """Warn the first time a run is actually addressed to an address.

    `_warn_once` caches on the message, so this fires once per process.
    """
    _warn_once(
        "Address addressing (`langsmith.address`) is in beta and is enabled per "
        "workspace. A workspace without it rejects the run, so the trace is "
        "lost rather than falling back to a project. The behavior may change "
        "without notice."
    )


Tier = tuple[Optional[str], Optional[Address]]
"""One precedence level: the `(project, address)` it names, either may be unset."""


def resolve(*tiers: Tier) -> tuple[Optional[str], Optional[Address]]:
    """Settle a run's single destination, as `(project, address)`.

    `tiers` are the levels named in code, highest precedence first; the env
    vars are the last level, consulted here. The first level that names
    anything decides, whichever mode it names -- an address in `tracing_context`
    beats a project on the decorator, and the other way round.

    Raises:
        utils.LangSmithUserError: If one level named in code names both.
        EnvAddressError: If the env vars are the deciding level and name both,
            or half an address.
    """
    for level, (project, address) in enumerate(tiers, start=1):
        if project and address is not None:
            raise _both_at_one_level(project, address, f"at precedence level {level}")
        if project:
            return project, None
        if address is not None:
            return None, address
    env_project = utils.get_tracer_project(return_default_value=False) or None
    env_address = Address.from_env()
    if env_project and env_address is not None:
        raise EnvAddressError(
            str(_both_at_one_level(env_project, env_address, "in the environment"))
        )
    if env_address is not None:
        return None, env_address
    return env_project or "default", None


def first_named(*tiers: Tier) -> Tier:
    """Return the highest level that names a destination, without the env vars.

    Raises:
        utils.LangSmithUserError: If that level names both.
    """
    for level, (project, address) in enumerate(tiers, start=1):
        if project and address is not None:
            raise _both_at_one_level(project, address, f"at precedence level {level}")
        if project or address is not None:
            return project or None, address
    return None, None


def _both_at_one_level(
    project: str, address: Address, where: str
) -> utils.LangSmithUserError:
    return utils.LangSmithUserError(
        f"A project ({project!r}) and an address ({address!r}) are both set "
        f"{where}, so neither outranks the other. Set only one there, or set "
        "the one you want at a higher-precedence level."
    )


def log_untraced(error: EnvAddressError) -> None:
    """Log, once per distinct cause, that calls run untraced for a bad env."""
    _log_untraced_once(str(error))


@functools.cache
def _log_untraced_once(message: str) -> None:
    _LOGGER.warning("LangSmith is not tracing this call: %s", message)


def warn_on_env() -> None:
    """Warn when the environment's address cannot be used.

    Half an address, or one beside a configured project, leaves calls that name
    nothing in code untraced -- and a name like `TARGET_ENVIRONMENT` is generic
    enough to be set by accident.

    Emitted at client construction rather than per run, so it is seen once.
    """
    present = [name for name, value in Address.env_values().items() if value]
    if not present:
        return
    try:
        address = Address.from_env()
    except EnvAddressError:
        warnings.warn(
            f"{', '.join(present)} is set, but not every LANGSMITH_AGENT_* "
            "variable an address needs, so calls that name no destination in "
            "code are not traced.",
            utils.LangSmithWarning,
            stacklevel=3,
        )
        return
    if address is None:
        return
    project = utils.get_tracer_project(return_default_value=False)
    if project is None:
        return
    warnings.warn(
        f"LANGSMITH_AGENT_ID ({address.agent_id!r}) and a configured "
        f"project "
        f"({project!r}) are both set in the environment, so calls that name "
        "no destination in code are not traced. Unset one of them.",
        utils.LangSmithWarning,
        stacklevel=3,
    )


def reject_url(session_id: Optional[Any], address: Optional[Address]) -> None:
    """Refuse to build a run URL the SDK cannot know.

    A run URL is keyed on the project id, and the endpoint resolves an address
    to its project without telling the SDK which.
    """
    if session_id is not None or address is None:
        return
    raise utils.LangSmithUserError(
        "No run URL is available for an address-addressed run yet. The endpoint "
        "resolves the address to its project, so only it knows the project this "
        "run is in. Read the run back and build the URL from its `session_id`."
    )


def reject_conflicting(
    *,
    project: Optional[Any] = None,
    session_id: Optional[Any] = None,
    address: Optional[Address] = None,
) -> None:
    """Reject a call that names both a project and an address.

    Pass only values the caller supplied in this call: an inherited or
    ambient address beside an explicit project is not a conflict -- the project
    wins, which is what lets an evaluation set its own project while
    `LANGSMITH_AGENT_ID` is set process-wide.

    Raises:
        utils.LangSmithUserError: If a project and an address are both named.
    """
    named_project = project if project is not None else session_id
    if named_project is not None and address is not None:
        raise utils.LangSmithUserError(
            f"A run is addressed by project ({named_project!r}) or by address "
            f"({address!r}), not both."
        )


def apply_to_payload(payload: dict, *, update: bool = False) -> None:
    """Render a run payload's address into its wire fields.

    The one place a run's `address` is unpacked. A project already on the
    payload addresses the run, so the environment is not consulted. With no
    project, an ambient address fills in and the null project keys are dropped.

    On an update the environment is not consulted: a patch inherits its
    address from the post that established it, and one naming nothing is
    resolved by run id.
    """
    address = check_address(payload.pop("address", None))
    named_project = (
        payload.get("session_id") is not None or payload.get("session_name") is not None
    )
    if address is None and not (update or named_project):
        address = Address.from_env()
    if address is None:
        return
    warn_is_beta()
    payload.update(address.to_wire())
    if not named_project:
        payload.pop("session_name", None)
        payload.pop("session_id", None)
