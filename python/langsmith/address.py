"""Plain dictionary addresses for tracing and project lookup.

Pass ``{"kind": "AGENT", "id": "support", "environment": "production"}``
to tracing entry points. Addresses stay JSON serializable in contexts and replicas;
only wire payloads and baggage headers use LRN strings.
"""

from __future__ import annotations

import re
from typing import Any, Optional, Union, cast

from typing_extensions import Literal, TypedDict

from langsmith import utils

__all__ = [
    "Address",
    "AgentAddress",
    "EvaluatorAddress",
    "EnvAddressError",
    "ExperimentAddress",
    "agent_address",
    "experiment_address",
    "evaluator_address",
]

# The server's agent id rule: a DNS label, so a hostname can carry the id.
_AGENT_ID_PATTERN = re.compile(r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?")
_ENVIRONMENTS = ("local", "development", "staging", "production")
# The canonical, hyphenated UUID. Other spellings of one are not accepted, so the
# Python and JS SDKs take the same experiment ids.
_UUID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE
)
# The wire form of an agent address. The parts are validated at the SDK boundary.
_LRN_PATTERN = re.compile(r"lrn:agents/([^/]+)/environments/([^/]+)")


class AgentAddress(TypedDict):
    """An agent environment; accepted directly as a plain dictionary."""

    kind: Literal["AGENT"]
    id: str
    environment: Literal["LOCAL", "DEVELOPMENT", "STAGING", "PRODUCTION"]


class ExperimentAddress(TypedDict):
    """An experiment's tracing project, for lookup only."""

    kind: Literal["EXPERIMENT"]
    id: str


class EvaluatorAddress(TypedDict):
    """The workspace's shared evaluators project, for lookup only."""

    kind: Literal["EVALUATOR"]


Address = Union[AgentAddress, ExperimentAddress, EvaluatorAddress]


class EnvAddressError(utils.LangSmithUserError):
    """The LANGSMITH_AGENT_* environment variables cannot address a run."""


def agent_address(id: str, environment: str) -> AgentAddress:
    """(beta) Construct and validate an agent address."""
    return ensure_agent({"kind": "AGENT", "id": id, "environment": environment})


def experiment_address(id: str) -> ExperimentAddress:
    """(beta) Construct an experiment address with a lowercase UUID."""
    return cast(ExperimentAddress, ensure_address({"kind": "EXPERIMENT", "id": id}))


def evaluator_address() -> EvaluatorAddress:
    """(beta) Construct the workspace shared evaluators project address."""
    return {"kind": "EVALUATOR"}


def ensure_agent(address: Any) -> AgentAddress:
    """Validate and normalize a plain agent dictionary."""
    if not isinstance(address, dict):
        raise utils.LangSmithUserError("An address must be an AgentAddress dictionary.")
    if address.get("kind") in ("EXPERIMENT", "EVALUATOR"):
        raise utils.LangSmithUserError("Only an `AgentAddress` can receive traces.")
    if address.get("kind") != "AGENT":
        raise utils.LangSmithUserError(
            "An address must be an AgentAddress dictionary with kind 'AGENT'."
        )
    agent_id = address.get("id")
    if not isinstance(agent_id, str) or not _AGENT_ID_PATTERN.fullmatch(agent_id):
        raise utils.LangSmithUserError(
            "Address agent id must be 1 to 63 lowercase ASCII letters, digits, "
            "or hyphens, start with a letter, and end with a letter or digit, "
            f"got {agent_id!r}. Use an id such as 'support-agent'."
        )
    environment = address.get("environment")
    normalized = environment.lower() if isinstance(environment, str) else None
    if normalized not in _ENVIRONMENTS:
        raise utils.LangSmithUserError(
            f"Address environment must be one of {', '.join(_ENVIRONMENTS)}, "
            f"got {environment!r}."
        )
    return {
        "kind": "AGENT",
        "id": agent_id,
        "environment": cast(
            Literal["LOCAL", "DEVELOPMENT", "STAGING", "PRODUCTION"],
            cast(str, normalized).upper(),
        ),
    }


def ensure_address(address: Any) -> Address:
    """Validate and normalize any supported address dictionary."""
    if not isinstance(address, dict):
        raise utils.LangSmithUserError("An address must be an address dictionary.")
    kind = address.get("kind")
    if kind == "AGENT":
        return ensure_agent(address)
    if kind == "EXPERIMENT":
        experiment_id = address.get("id")
        if not isinstance(experiment_id, str) or not _UUID_PATTERN.fullmatch(
            experiment_id
        ):
            raise utils.LangSmithUserError(
                "An experiment id must be a UUID with hyphens."
            )
        return {"kind": "EXPERIMENT", "id": experiment_id.lower()}
    if kind == "EVALUATOR":
        return {"kind": "EVALUATOR"}
    raise utils.LangSmithUserError(
        "An address must have kind AGENT, EXPERIMENT or EVALUATOR."
    )


def address_to_lrn(address: AgentAddress) -> str:
    """Serialize an agent dictionary for a wire payload or header."""
    normalized = ensure_agent(address)
    environment = normalized["environment"].lower()
    return f"lrn:agents/{normalized['id']}/environments/{environment}"


def address_from_lrn(value: Any) -> AgentAddress:
    """Parse an untrusted wire address without echoing it in errors."""
    match = _LRN_PATTERN.fullmatch(value) if isinstance(value, str) else None
    if match is None:
        raise utils.LangSmithUserError("Not an agent address.")
    return ensure_agent({"kind": "AGENT", "id": match[1], "environment": match[2]})


def address_from_env() -> Optional[AgentAddress]:
    """Read and validate the LANGSMITH_AGENT_* variables, if either is set."""
    values = env_values()
    if not any(values.values()):
        return None
    try:
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise utils.LangSmithUserError(
                f"An address needs {' and '.join(missing)} as well."
            )
        return ensure_agent(
            {
                "kind": "AGENT",
                "id": values["LANGSMITH_AGENT_ID"],
                "environment": values["LANGSMITH_AGENT_ENVIRONMENT"],
            }
        )
    except utils.LangSmithUserError as e:
        present = ", ".join(
            f"{name}={value!r}" for name, value in values.items() if value
        )
        raise EnvAddressError(
            f"The LANGSMITH_AGENT_* env vars can't address a run ({present}): {e}"
        ) from e


def env_values() -> dict[str, Optional[str]]:
    """Return each LANGSMITH_AGENT_* variable and its value."""
    return {
        f"LANGSMITH_{name}": utils.get_env_var(name, namespaces=("LANGSMITH",))
        for name in ("AGENT_ID", "AGENT_ENVIRONMENT")
    }
