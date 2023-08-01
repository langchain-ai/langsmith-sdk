"""Schemas for the LangSmith API."""
from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, PrivateAttr, StrictBool, StrictFloat, StrictInt
from typing_extensions import Literal

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


class DataType(str, Enum):
    """Enum for dataset data types."""

    kv = "kv"
    llm = "llm"
    chat = "chat"


class DatasetBase(BaseModel):
    """Dataset base model."""

    name: str
    description: Optional[str] = None
    data_type: Optional[DataType] = None

    class Config:
        frozen = True


class DatasetCreate(DatasetBase):
    """Dataset create model."""

    id: Optional[UUID] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Dataset(DatasetBase):
    """Dataset ORM model."""

    id: UUID
    created_at: datetime
    modified_at: Optional[datetime] = Field(default=None)


class RunTypeEnum(str, Enum):
    """(Deprecated) Enum for run types. Use string directly."""

    tool = "tool"
    chain = "chain"
    llm = "llm"
    retriever = "retriever"
    embedding = "embedding"
    prompt = "prompt"
    parser = "parser"


class RunBase(BaseModel):
    """Base Run schema."""

    id: UUID
    name: str
    start_time: datetime
    run_type: str
    """The type of run, such as tool, chain, llm, retriever,
    embedding, prompt, parser."""
    end_time: Optional[datetime] = None
    extra: Optional[dict] = None
    error: Optional[str] = None
    serialized: Optional[dict]
    events: Optional[List[Dict]] = None
    inputs: dict
    outputs: Optional[dict] = None
    reference_example_id: Optional[UUID] = None
    parent_run_id: Optional[UUID] = None
    tags: Optional[List[str]] = None


class Run(RunBase):
    """Run schema when loading from the DB."""

    execution_order: int
    """The execution order of the run within a run trace."""
    session_id: Optional[UUID] = None
    """The project ID this run belongs to."""
    child_run_ids: Optional[List[UUID]] = None
    """The child run IDs of this run."""
    child_runs: Optional[List[Run]] = None
    """The child runs of this run, if instructed to load using the client
    These are not populated by default, as it is a heavier query to make."""
    feedback_stats: Optional[Dict[str, Any]] = None
    """Feedback stats for this run."""
    app_path: Optional[str] = None
    """Relative URL path of this run within the app."""
    _host_url: Optional[str] = PrivateAttr(default=None)

    def __init__(self, _host_url: Optional[str] = None, **kwargs: Any) -> None:
        """Initialize a Run object."""
        super().__init__(**kwargs)
        self._host_url = _host_url

    @property
    def url(self) -> Optional[str]:
        """URL of this run within the app."""
        if self._host_url and self.app_path:
            return f"{self._host_url}{self.app_path}"
        return None


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

    id: UUID
    """The unique ID of the feedback."""
    created_at: Optional[datetime] = None
    """The time the feedback was created."""
    modified_at: Optional[datetime] = None
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

    feedback_source: FeedbackSourceBase
    """The source of the feedback."""


class Feedback(FeedbackBase):
    """Schema for getting feedback."""

    id: UUID
    created_at: datetime
    """The time the feedback was created."""
    modified_at: datetime
    """The time the feedback was last modified."""
    feedback_source: Optional[FeedbackSourceBase] = None
    """The source of the feedback. In this case"""


class TracerSession(BaseModel):
    """TracerSession schema for the API.

    Sessions are also referred to as "Projects" in the UI.
    """

    id: UUID
    """The ID of the project."""
    start_time: datetime = Field(default_factory=datetime.utcnow)
    """The time the project was created."""
    name: Optional[str] = None
    """The name of the session."""
    extra: Optional[Dict[str, Any]] = None
    """Extra metadata for the project."""
    tenant_id: UUID
    """The tenant ID this project belongs to."""


class TracerSessionResult(TracerSession):
    """TracerSession schema returned when reading a project
    by ID. Sessions are also referred to as "Projects" in the UI."""

    run_count: Optional[int]
    """The number of runs in the project."""
    latency_p50: Optional[timedelta]
    """The median (50th percentile) latency for the project."""
    latency_p99: Optional[timedelta]
    """The 99th percentile latency for the project."""
    total_tokens: Optional[int]
    """The total number of tokens consumed in the project."""
    prompt_tokens: Optional[int]
    """The total number of prompt tokens consumed in the project."""
    completion_tokens: Optional[int]
    """The total number of completion tokens consumed in the project."""
    last_run_start_time: Optional[datetime]
    """The start time of the last run in the project."""
    feedback_stats: Optional[Dict[str, Any]]
    """Feedback stats for the project."""
    reference_dataset_ids: Optional[List[UUID]]
    """The reference dataset IDs this project's runs were generated on."""
    run_facets: Optional[List[Dict[str, Any]]]
    """Facets for the runs in the project."""
