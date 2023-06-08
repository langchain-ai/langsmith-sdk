"""Schemas for the langchainplus API."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Union
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    root_validator,
)

from langchainplus_sdk.internal.models import (
    APIFeedbackSource,
    Dataset,
    DatasetUpdate,
    Example,
    FeedbackCreateSchema,
    FeedbackSchema,
    FeedbackUpdateSchema,
    ModelFeedbackSource,
    RunCreateSchema,
    RunSchema,
    RunTypeEnum,
    RunUpdateSchema,
)
from langchainplus_sdk.internal.models import (
    DatasetCreate as DatasetCreateSchema,
)
from langchainplus_sdk.internal.models import (
    ExampleCreate as ExampleCreateSchema,
)
from langchainplus_sdk.internal.models import (
    ExampleUpdate as ExampleUpdateSchema,
)
from langchainplus_sdk.internal.models import (
    TracerSession as TracerSessionSchema,
)
from langchainplus_sdk.internal.models import (
    TracerSessionCreate as TracerSessionCreateSchema,
)

SCORE_TYPE = Union[StrictBool, StrictInt, StrictFloat, None]
VALUE_TYPE = Union[Dict, StrictBool, StrictInt, StrictFloat, str, None]


class DatasetCreate(DatasetCreateSchema):
    """Dataset schema when creating a new dataset."""

    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ExampleCreate(ExampleCreateSchema):
    """Example schema when creating a new example."""

    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ExampleUpdate(ExampleUpdateSchema):
    """Example schema when updating an existing example."""

    updated_at: datetime = Field(default_factory=datetime.utcnow)


class RunCreate(RunCreateSchema):
    id: UUID = Field(default_factory=uuid4)
    start_time: datetime = Field(default_factory=datetime.utcnow)


class Run(RunSchema):
    """Run schema when loading from the DB."""

    id: UUID
    name: str
    child_runs: List[Run] = Field(default_factory=list)

    @root_validator(pre=True)
    def assign_name(cls, values: dict) -> dict:
        """Assign name to the run."""
        if "name" not in values:
            values["name"] = values["serialized"]["name"]
        return values


class RunUpdate(RunUpdateSchema):
    end_time: datetime = Field(default_factory=datetime.utcnow)


class ListRunsQueryParams(BaseModel):
    """Query params for GET /runs endpoint."""

    id: Optional[List[UUID]]
    """Filter runs by id."""
    parent_run: Optional[UUID]
    """Filter runs by parent run."""
    run_type: Optional[RunTypeEnum]
    """Filter runs by type."""
    session: Optional[UUID] = Field(default=None, alias="session_id")
    """Only return runs within a session."""
    reference_example: Optional[UUID]
    """Only return runs that reference the specified dataset example."""
    execution_order: Optional[int]
    """Filter runs by execution order."""
    error: Optional[bool]
    """Whether to return only runs that errored."""
    offset: Optional[int]
    """The offset of the first run to return."""
    limit: Optional[int]
    """The maximum number of runs to return."""
    start_time: Optional[datetime] = Field(
        default=None,
        alias="start_before",
        description="Query Runs that started <= this time",
    )
    end_time: Optional[datetime] = Field(
        default=None,
        alias="end_after",
        description="Query Runs that ended >= this time",
    )

    class Config:
        extra = "forbid"
        frozen = True

    @root_validator
    def validate_time_range(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that start_time <= end_time."""
        start_time = values.get("start_time")
        end_time = values.get("end_time")
        if start_time and end_time and start_time > end_time:
            raise ValueError("start_time must be <= end_time")
        return values


class FeedbackMixin(BaseModel):
    # Override with stricter types
    """The source of the feedback. In this case"""
    score: SCORE_TYPE = None
    """Value or score to assign the run."""
    value: VALUE_TYPE = None
    """The display value, tag or other value for the feedback if not a metric."""


class FeedbackCreate(FeedbackMixin, FeedbackCreateSchema):
    """Schema used for creating feedback."""

    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    """The time the feedback was created."""
    modified_at: datetime = Field(default_factory=datetime.utcnow)
    """The time the feedback was last modified."""


class FeedbackUpdate(FeedbackMixin, FeedbackUpdateSchema):
    """Schema used for updating feedback."""

    modified_at: datetime = Field(default_factory=datetime.utcnow)
    """The time the feedback was last modified."""


class Feedback(FeedbackMixin, FeedbackSchema):
    """Schema for getting feedback."""


class ListFeedbackQueryParams(BaseModel):
    """Query Params for listing feedbacks."""

    run: Optional[Sequence[UUID]] = None
    limit: int = 100
    offset: int = 0

    class Config:
        """Config for query params."""

        extra = "forbid"
        frozen = True


class TracerSession(TracerSessionSchema):
    run_count: int = Field(default=0)


class TracerSessionCreate(TracerSessionCreateSchema):
    """Schema for creating a tracer session."""

    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)


__all__ = [
    "Example",
    "ExampleCreate",
    "ExampleUpdate",
    "Dataset",
    "DatasetCreate",
    "DatasetUpdate",
    "Run",
    "RunCreate",
    "RunUpdate",
    "ListRunsQueryParams",
    "Feedback",
    "FeedbackCreate",
    "FeedbackUpdate",
    "ListFeedbackQueryParams",
    "TracerSession",
    "TracerSessionCreate",
    "APIFeedbackSource",
    "ModelFeedbackSource",
    "RunTypeEnum",
]
