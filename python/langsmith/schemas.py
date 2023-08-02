from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from dataclasses_json import dataclass_json
from typing_extensions import Literal

SCORE_TYPE = Union[bool, int, float, None]
VALUE_TYPE = Union[Dict, bool, int, float, str, None]


class DataType(Enum):
    """Enum for dataset data types."""

    kv = "kv"
    llm = "llm"
    chat = "chat"


class RunTypeEnum(str, Enum):
    """Enum for run types."""

    tool = "tool"
    chain = "chain"
    llm = "llm"
    retriever = "retriever"
    embedding = "embedding"
    prompt = "prompt"
    parser = "parser"


class FeedbackSourceType(Enum):
    """Feedback source type."""

    API = "api"
    """General feedback submitted from the API."""
    MODEL = "model"
    """Model-assisted feedback."""


@dataclass_json
@dataclass(frozen=True)
class ExampleBase:
    """Example base model."""

    dataset_id: UUID
    inputs: Dict[str, Any]
    outputs: Optional[Dict[str, Any]]


@dataclass_json
@dataclass(frozen=True)
class Example(ExampleBase):
    """Example model."""

    id: UUID
    created_at: datetime
    modified_at: Optional[datetime] = None
    runs: List[Run] = field(default_factory=list)


@dataclass_json
@dataclass(frozen=True)
class ExampleUpdate:
    """Update class for Example."""

    dataset_id: Optional[UUID] = None
    inputs: Optional[Dict[str, Any]] = None
    outputs: Optional[Dict[str, Any]] = None


@dataclass_json
@dataclass(frozen=True)
class DatasetBase:
    """Dataset base model."""

    name: str
    description: Optional[str]
    data_type: Optional[DataType]


@dataclass_json
@dataclass(frozen=True)
class Dataset(DatasetBase):
    """Dataset ORM model."""

    id: UUID
    created_at: datetime
    modified_at: Optional[datetime] = None


@dataclass_json
@dataclass
class RunBase:
    """Base Run schema."""

    id: UUID
    name: str
    start_time: datetime
<<<<<<< HEAD
    run_type: str
    """The type of run, such as tool, chain, llm, retriever,
    embedding, prompt, parser."""
=======
    inputs: dict
    run_type: Union[RunTypeEnum, str]
>>>>>>> 86df593 (this sucks)
    end_time: Optional[datetime] = None
    extra: Optional[dict] = None
    error: Optional[str] = None
    serialized: Optional[dict] = None
    events: Optional[List[Dict]] = None
    outputs: Optional[dict] = None
    reference_example_id: Optional[UUID] = None
    parent_run_id: Optional[UUID] = None
    tags: Optional[List[str]] = None


@dataclass_json
@dataclass
class Run(RunBase):
    """Run schema when loading from the DB."""

    execution_order: Optional[int] = None
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
    _host_url: Optional[str] = field(default=None, repr=False)


@dataclass_json
@dataclass(frozen=True)
class FeedbackSource:
    type: FeedbackSourceType
    """The type of feedback source."""
    metadata: Optional[Dict[str, Any]] = None
    """Metadata associated with the feedback source."""


@dataclass_json
@dataclass(frozen=True)
class Feedback:
    """Schema for getting feedback."""

    id: UUID
    """The unique ID of the feedback."""
    run_id: UUID
    """The associated run ID this feedback is logged for."""
    key: str
    """The metric name, tag, or aspect to provide feedback on."""
    score: SCORE_TYPE = None
    """Value or score to assign the run."""
    value: VALUE_TYPE = None
    """The display value, tag or other value for the feedback if not a metric."""
    created_at: Optional[datetime] = None
    """The time the feedback was created."""
    modified_at: Optional[datetime] = None
    """The time the feedback was last modified."""
    comment: Optional[str] = None
    """Comment or explanation for the feedback."""
    correction: Union[str, dict, None] = None
    """Correction for the run."""
    feedback_source: Optional[FeedbackSource] = None
    """The source of the feedback."""


@dataclass_json
@dataclass(frozen=True)
class TracerSession:
    """TracerSession schema for the API.
    Sessions are also referred to as "Projects" in the UI.
    """

    id: UUID
    """The ID of the project."""
    start_time: datetime = field(default_factory=datetime.utcnow)
    """The time the project was created."""
    name: Optional[str] = None
    """The name of the project."""
    end_time: Optional[datetime] = None
    """The time the project ended, if applicable."""
    events: List[dict] = field(default_factory=list)
    """Events associated with the project."""
    num_runs: int = 0
    """The number of runs in this project."""
    num_feedback: int = 0
    """The number of feedback records in this project."""


@dataclass_json
@dataclass(frozen=True)
class TracerSessionResult(TracerSession):
    """TracerSession schema returned when reading a project
    by ID. Sessions are also referred to as "Projects" in the UI."""

    run_count: Optional[int] = None
    """The number of runs in the project."""
    latency_p50: Optional[timedelta] = None
    """The median (50th percentile) latency for the project."""
    latency_p99: Optional[timedelta] = None
    """The 99th percentile latency for the project."""
    total_tokens: Optional[int] = None
    """The total number of tokens consumed in the project."""
    prompt_tokens: Optional[int] = None
    """The total number of prompt tokens consumed in the project."""
    completion_tokens: Optional[int] = None
    """The total number of completion tokens consumed in the project."""
    last_run_start_time: Optional[datetime] = None
    """The start time of the last run in the project."""
    feedback_stats: Optional[Dict[str, Any]] = None
    """Feedback stats for the project."""
    reference_dataset_ids: Optional[List[UUID]] = None
    """The reference dataset IDs this project's runs were generated on."""
    run_facets: Optional[List[Dict[str, Any]]] = None
    """Facets for the runs in the project."""
