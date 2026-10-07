# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Literal, Required, TypedDict

__all__ = ["ProjectResolveParams"]


class ProjectResolveParams(TypedDict, total=False):
    kind: Required[Literal["AGENT", "EXPERIMENT", "EVALUATOR"]]
    """The kind of address."""

    id: str
    """The Agent's user-assigned id for AGENT, or the experiment's id for EXPERIMENT.

    Not set for EVALUATOR.
    """

    environment: Literal["LOCAL", "DEVELOPMENT", "STAGING", "PRODUCTION"]
    """The Agent environment. Only set for AGENT."""
