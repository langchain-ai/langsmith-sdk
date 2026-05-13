# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union, Iterable, Optional
from datetime import datetime
from typing_extensions import Literal, Required, Annotated, TypeAlias, TypedDict

from ..._types import SequenceNotStr
from ..._utils import PropertyInfo

__all__ = [
    "RunCreateParams",
    "RunsUuidArray",
    "RunsAnnotationQueueRunAddSchemaArray",
    "RunsAnnotationQueueRunAddSchemaArrayBody",
    "Variant2",
    "Variant2Body",
]


class RunsUuidArray(TypedDict, total=False):
    body: Required[SequenceNotStr[str]]


class RunsAnnotationQueueRunAddSchemaArray(TypedDict, total=False):
    body: Required[Iterable[RunsAnnotationQueueRunAddSchemaArrayBody]]


class RunsAnnotationQueueRunAddSchemaArrayBody(TypedDict, total=False):
    """
    Add a single run to AQ (CH path) with an optional back-pointer to the
    issues-agent proposal that seeded this add. Use when bulk-adding runs
    that come from different proposals — each row carries its own
    source_proposed_example_id. For unrelated bulk adds, prefer plain
    List[UUID] on the same endpoint.
    """

    run_id: Required[str]

    source_proposed_example_id: Optional[str]


class Variant2(TypedDict, total=False):
    body: Required[Iterable[Variant2Body]]


class Variant2Body(TypedDict, total=False):
    """Deprecated: use plain UUID list or AddRunToQueueByKeyRequest instead."""

    run_id: Required[str]

    parent_run_id: Optional[str]

    session_id: Optional[str]

    start_time: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]

    trace_id: Optional[str]

    trace_tier: Optional[Literal["longlived", "shortlived"]]


RunCreateParams: TypeAlias = Union[RunsUuidArray, RunsAnnotationQueueRunAddSchemaArray, Variant2]
