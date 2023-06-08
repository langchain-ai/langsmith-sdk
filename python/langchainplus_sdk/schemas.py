"""Schemas for the langchainplus API."""
from __future__ import annotations

import os
from datetime import datetime
from enum import Enum
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
from typing_extensions import Literal

from langchainplus_sdk.utils import get_runtime_environment

SCORE_TYPE = Union[StrictBool, StrictInt, StrictFloat, None]
VALUE_TYPE = Union[Dict, StrictBool, StrictInt, StrictFloat, str, None]


class ExampleBase(BaseModel):
    """Example base model."""

    dataset_id: UUID
    inputs: Dict[str, Any]
    outputs: Optional[Dict[str, Any]] = Field(default=None)

    class Config:
        frozen = True


class ExampleCreate(ExampleBase):
    """Example create model."""

    id: Optional[UUID]
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Example(ExampleBase):
    """Example model."""

    id: UUID
    created_at: datetime
    modified_at: Optional[datetime] = Field(default=None)
    runs: List[Run] = Field(default_factory=list)


class ExampleUpdate(BaseModel):
    """Update class for Example."""

    dataset_id: Optional[UUID] = None
    inputs: Optional[Dict[str, Any]] = None
    outputs: Optional[Dict[str, Any]] = None

    class Config:
        frozen = True


class DatasetBase(BaseModel):
    """Dataset base model."""

    name: str
    description: Optional[str] = None

    class Config:
        frozen = True


class DatasetCreate(DatasetBase):
    """Dataset create model."""

    id: Optional[UUID]
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Dataset(DatasetBase):
    """Dataset ORM model."""

    id: UUID
    created_at: datetime
    modified_at: Optional[datetime] = Field(default=None)


class RunTypeEnum(str, Enum):
    """Enum for run types."""

    tool = "tool"
    chain = "chain"
    llm = "llm"


class RunBase(BaseModel):
    """Base Run schema."""

    id: Optional[UUID]
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: datetime = Field(default_factory=datetime.utcnow)
    extra: dict = Field(default_factory=dict)
    error: Optional[str]
    execution_order: int
    serialized: dict
    inputs: dict
    outputs: Optional[dict]
    reference_example_id: Optional[UUID]
    run_type: RunTypeEnum
    parent_run_id: Optional[UUID]


class Run(RunBase):
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


def infer_default_run_values(values: Dict[str, Any]) -> Dict[str, Any]:
    if "name" not in values:
        if "serialized" not in values:
            raise ValueError("Must provide either name or serialized.")
        if "name" not in values["serialized"]:
            raise ValueError(
                "Must provide either name or serialized with a name attribute."
            )
        values["name"] = values["serialized"]["name"]
    elif "serialized" not in values:
        values["serialized"] = {"name": values["name"]}
    if "execution_order" not in values:
        values["execution_order"] = 1
    if "child_execution_order" not in values:
        values["child_execution_order"] = values["execution_order"]
    if values.get("parent_run") is not None:
        values["parent_run_id"] = values["parent_run"].id
    extra = values.get("extra", {})
    if "runtime" not in extra:
        extra["runtime"] = {}
    runtime_env = get_runtime_environment()
    for k, v in runtime_env.items():
        if k not in extra["runtime"]:
            extra["runtime"][k] = v
    values["extra"] = extra
    return values


class RunCreate(RunBase):
    """Run create schema."""

    id: UUID = Field(default_factory=uuid4)
    name: str
    session_name: str = Field(
        default_factory=lambda: os.environ.get("LANGCHAIN_SESSION", "default")
    )
    child_runs: Optional[List[RunCreate]] = None

    @root_validator(pre=True)
    def add_runtime_env(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Add env info to the run."""
        return infer_default_run_values(values)


class RunUpdate(BaseModel):
    end_time: Optional[datetime]
    error: Optional[str]
    outputs: Optional[dict]
    parent_run_id: Optional[UUID]
    reference_example_id: Optional[UUID]


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


class FeedbackSourceBase(BaseModel):
    type: str
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        frozen = True


class APIFeedbackSource(FeedbackSourceBase):
    """API feedback source."""

    type: Literal["api"] = "api"


class ModelFeedbackSource(FeedbackSourceBase):
    """Model feedback source."""

    type: Literal["model"] = "model"


class FeedbackSourceType(Enum):
    """Feedback source type."""

    API = "api"
    """General feedback submitted from the API."""
    MODEL = "model"
    """Model-assisted feedback."""


class FeedbackBase(BaseModel):
    """Feedback schema."""

    created_at: datetime = Field(default_factory=datetime.utcnow)
    """The time the feedback was created."""
    modified_at: datetime = Field(default_factory=datetime.utcnow)
    """The time the feedback was last modified."""
    run_id: UUID
    """The associated run ID this feedback is logged for."""
    key: str
    """The metric name, tag, or aspect to provide feedback on."""
    score: SCORE_TYPE = None
    """Value or score to assign the run."""
    value: VALUE_TYPE = None
    """The display value, tag or other value for the feedback if not a metric."""
    comment: Optional[str] = None
    """Comment or explanation for the feedback."""
    correction: Union[str, dict, None] = None
    """Correction for the run."""
    feedback_source: Optional[FeedbackSourceBase] = None
    """The source of the feedback."""

    class Config:
        frozen = True


class FeedbackCreate(FeedbackBase):
    """Schema used for creating feedback."""

    id: UUID = Field(default_factory=uuid4)

    feedback_source: FeedbackSourceBase
    """The source of the feedback."""


class Feedback(FeedbackBase):
    """Schema for getting feedback."""

    id: UUID
    feedback_source: Optional[FeedbackSourceBase] = None
    """The source of the feedback. In this case"""


class ListFeedbackQueryParams(BaseModel):
    """Query Params for listing feedbacks."""

    run: Optional[Sequence[UUID]] = None
    limit: int = 100
    offset: int = 0

    class Config:
        """Config for query params."""

        extra = "forbid"
        frozen = True


class TracerSession(BaseModel):
    """TracerSession schema for the V2 API."""

    id: UUID
    start_time: datetime = Field(default_factory=datetime.utcnow)
    name: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None
    tenant_id: UUID
