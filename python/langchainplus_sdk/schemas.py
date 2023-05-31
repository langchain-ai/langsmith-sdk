"""Schemas for the langchainplus API."""
from __future__ import annotations

import os
from datetime import datetime
from enum import Enum
from typing import Any, ClassVar, Dict, List, Mapping, Optional, Sequence, Union
from uuid import UUID, uuid4

import requests
from langchainplus_sdk.utils import raise_for_status_with_text
from pydantic import BaseModel, Field, root_validator


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
    child_execution_order: Optional[int]
    serialized: dict
    inputs: dict
    outputs: Optional[dict]
    reference_example_id: Optional[UUID]
    run_type: RunTypeEnum
    parent_run_id: Optional[UUID]


class Run(RunBase):
    """Run schema when loading from the DB."""

    name: str
    child_runs: List[Run] = Field(default_factory=list)

    @root_validator(pre=True)
    def assign_name(cls, values: dict) -> dict:
        """Assign name to the run."""
        if "name" not in values:
            values["name"] = values["serialized"]["name"]
        return values


class RunTree(RunBase):
    """Run Schema with back-references for posting runs."""

    name: str
    id: Optional[UUID] = Field(default_factory=uuid4)
    parent_run: Optional[RunTree] = Field(default=None, exclude=True)
    child_runs: List[RunTree] = Field(default_factory=list)
    session_name: str = Field(default=os.environ.get("LANGCHAIN_SESSION", "default"))
    session_id: Optional[UUID] = Field(default=None)
    execution_order: int = 1
    child_execution_order: int = 1
    api_url: str = Field(
        default=os.environ.get("LANGCHAIN_API_URL", "http://localhost:1984"),
        exclude=True,
    )
    api_key: Optional[str] = Field(
        default=os.environ.get("LANGCHAIN_API_TOKEN"), exclude=True
    )

    @root_validator(pre=True)
    def infer_defaults(cls, values: dict) -> dict:
        """Assign name to the run."""
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
        return values

    def end(
        self,
        *,
        outputs: Optional[Dict] = None,
        error: Optional[str] = None,
        end_time: Optional[datetime] = None,
    ) -> None:
        """Set the end time of the run and all child runs."""
        self.end_time = end_time or datetime.utcnow()
        if outputs is not None:
            self.outputs = outputs
        if error is not None:
            self.error = error
        if self.parent_run:
            self.parent_run.child_execution_order = max(
                self.parent_run.child_execution_order, self.child_execution_order
            )

    def create_child(
        self,
        name: str,
        run_type: Union[str, RunTypeEnum],
        *,
        run_id: Optional[UUID] = None,
        serialized: Optional[Dict] = None,
        inputs: Optional[Dict] = None,
        outputs: Optional[Dict] = None,
        error: Optional[str] = None,
        reference_example_id: Optional[UUID] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        extra: Optional[Dict] = None,
    ) -> RunTree:
        """Add a child run to the run tree."""
        execution_order = self.child_execution_order + 1
        serialized_ = serialized or {"name": name}
        run = RunTree(
            name=name,
            id=run_id or uuid4(),
            serialized=serialized_,
            inputs=inputs or {},
            outputs=outputs or {},
            error=error,
            run_type=run_type,
            reference_example_id=reference_example_id,
            start_time=start_time or datetime.utcnow(),
            end_time=end_time or datetime.utcnow(),
            execution_order=execution_order,
            child_execution_order=execution_order,
            extra=extra or {},
            parent_run=self,
            session_name=self.session_name,
            api_url=self.api_url,
            api_key=self.api_key,
        )
        self.child_runs.append(run)
        return run

    def post(self) -> Dict:
        """Post the run tree to the API."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        response = requests.post(
            self.api_url + "/runs",
            data=self.json(exclude={"parent_run_id"}, exclude_none=True),
            headers=headers,
        )
        raise_for_status_with_text(response)
        return response.json()

    def patch(self) -> Dict:
        """Patch the run tree to the API."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        response = requests.patch(
            self.api_url + "/runs",
            data=self.json(exclude={"parent_run_id"}, exclude_none=True),
            headers=headers,
        )
        raise_for_status_with_text(response)
        return response.json()


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
    type: ClassVar[str]
    metadata: Dict[str, Any] | None = None

    class Config:
        frozen = True


class APIFeedbackSource(FeedbackSourceBase):
    """API feedback source."""

    type: ClassVar[str] = "api"


class ModelFeedbackSource(FeedbackSourceBase):
    """Model feedback source."""

    type: ClassVar[str] = "model"


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
    score: Union[float, int, bool, None] = None
    """Value or score to assign the run."""
    value: Union[float, int, bool, str, dict, None] = None
    """The display value, tag or other value for the feedback if not a metric."""
    comment: Optional[str] = None
    """Comment or explanation for the feedback."""
    correction: Union[str, dict, None] = None
    """Correction for the run."""
    feedback_source: Optional[
        Union[APIFeedbackSource, ModelFeedbackSource, Mapping[str, Any]]
    ] = None
    """The source of the feedback."""

    class Config:
        frozen = True


class FeedbackCreate(FeedbackBase):
    """Schema used for creating feedback."""

    id: UUID = Field(default_factory=uuid4)

    feedback_source: APIFeedbackSource
    """The source of the feedback."""


class Feedback(FeedbackBase):
    """Schema for getting feedback."""

    id: UUID
    feedback_source: Optional[Dict] = None
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
