from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from datetime import timedelta
from typing import Optional, Dict, List
from uuid import UUID

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


SCORE_TYPE = Union[bool, int, float, None]
VALUE_TYPE = Union[Dict, bool, int, float, str, None]


# Enum classes remain unchanged.
class DataType(Enum):
    kv = "kv"
    llm = "llm"
    chat = "chat"


class RunTypeEnum(str, Enum):
    tool = "tool"
    chain = "chain"
    llm = "llm"
    retriever = "retriever"
    embedding = "embedding"
    prompt = "prompt"
    parser = "parser"


class FeedbackSourceType(Enum):
    API = "api"
    MODEL = "model"


class ExampleBase:
    def __init__(
        self,
        *,
        dataset_id: Union[UUID, str],
        inputs: Dict[str, Any],
        outputs: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize ExampleBase.

        Arge:
            dataset_id (UUID), ID of the dataset
            inputs: Inputs dictionary
            outputs: Optional Outputs dictionary
        """
        self.dataset_id = (
            dataset_id if isinstance(dataset_id, UUID) else UUID(dataset_id)
        )
        self.inputs = inputs
        self.outputs = outputs


class Example(ExampleBase):
    def __init__(
        self,
        *,
        id: UUID,
        dataset_id: UUID,
        inputs: Dict[str, Any],
        created_at: datetime,
        outputs: Optional[Dict[str, Any]] = None,
        modified_at: Optional[datetime] = None,
        runs: List[Run] = [],
    ) -> None:
        """Initialize Example.

        :param id: ID of the example
        :param dataset_id: ID of the dataset
        :param inputs: Inputs dictionary
        :param outputs: Optional outputs dictionary
        :param created_at: Creation timestamp
        :param modified_at: Optional modification timestamp
        :param runs: List of Runs
        """
        super().__init__(dataset_id=dataset_id, inputs=inputs, outputs=outputs)
        self.id = id
        self.created_at = created_at
        self.modified_at = modified_at
        self.runs = runs


class ExampleUpdate:
    def __init__(
        self,
        dataset_id: Optional[UUID] = None,
        inputs: Optional[Dict[str, Any]] = None,
        outputs: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize ExampleUpdate.

        :param dataset_id: Optional ID of the dataset
        :param inputs: Optional Inputs dictionary
        :param outputs: Optional Outputs dictionary
        """
        self.dataset_id = dataset_id
        self.inputs = inputs
        self.outputs = outputs


class DatasetBase:
    def __init__(
        self,
        *,
        name: str,
        description: Optional[str] = None,
        data_type: Optional[DataType] = None,
    ) -> None:
        """Initialize DatasetBase.

        :param name: Name of the dataset
        :param description: Optional description
        :param data_type: Optional DataType
        """
        self.name = name
        self.description = description
        self.data_type = data_type


class Dataset(DatasetBase):
    def __init__(
        self,
        *
        name: str,
        id: UUID,
        created_at: datetime,
        description: Optional[str] = None,
        modified_at: Optional[datetime] = None,
        data_type: Optional[DataType] = None,
    ) -> None:
        """Initialize Dataset.

        :param name: Name of the dataset
        :param id: ID of the dataset
        :param created_at: Creation timestamp
        :param description: Optional description
        :param modified_at: Optional modification timestamp
        :param data_type: Optional DataType
        """
        super().__init__(name=name, description=description, data_type=data_type)
        self.id = id
        self.created_at = created_at
        self.modified_at = modified_at


class RunBase:
    def __init__(
        self,
        *,
        name: str,
        inputs: dict,
        run_type: str,
        id: Optional[UUID] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        extra: Optional[dict] = None,
        error: Optional[str] = None,
        serialized: Optional[dict] = None,
        events: Optional[List[Dict]] = None,
        outputs: Optional[dict] = None,
        reference_example_id: Optional[UUID] = None,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
    ) -> None:
        """Initialize RunBase.

        :param id: ID of the run
        :param name: Name of the run
        :param start_time: Start time of the run
        :param inputs: Inputs for the run
        :param run_type: Type of run
        :param end_time: Optional end time of the run
        :param extra: Optional extra information
        :param error: Optional error information
        :param serialized: Optional serialized information
        :param events: Optional list of events
        :param outputs: Optional outputs
        :param reference_example_id: Optional reference example ID
        :param parent_run_id: Optional parent run ID
        :param tags: Optional tags
        """
        self.id = id
        self.name = name
        self.start_time = start_time
        self.inputs = inputs
        self.run_type = run_type
        self.end_time = end_time
        self.extra = extra
        self.error = error
        self.serialized = serialized
        self.events = events
        self.outputs = outputs
        self.reference_example_id = reference_example_id
        self.parent_run_id = parent_run_id
        self.tags = tags


class Run(RunBase):
    def __init__(
        self,
        *,
        id: UUID,
        name: str,
        inputs: dict,
        run_type: str,
        start_time: Optional[datetime] = None,
        execution_order: Optional[int] = None,
        session_id: Optional[UUID] = None,
        child_run_ids: Optional[List[UUID]] = None,
        child_runs: Optional[List[Run]] = None,
        feedback_stats: Optional[Dict[str, Any]] = None,
        app_path: Optional[str] = None,
        _host_url: Optional[str] = None,
        end_time: Optional[datetime] = None,
        extra: Optional[dict] = None,
        error: Optional[str] = None,
        serialized: Optional[dict] = None,
        events: Optional[List[Dict]] = None,
        outputs: Optional[dict] = None,
        reference_example_id: Optional[UUID] = None,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
    ) -> None:
        """Initialize Run.
        :param id: ID of the run
        :param name: Name of the run
        :param start_time: Start time of the run
        :param inputs: Inputs for the run
        :param run_type: Type of run
        :param end_time: Optional end time of the run
        :param extra: Optional extra information
        :param error: Optional error information
        :param serialized: Optional serialized information
        :param events: Optional list of events
        :param outputs: Optional outputs
        :param reference_example_id: Optional reference example ID
        :param parent_run_id: Optional parent run ID
        :param tags: Optional tags
        :param execution_order: Optional execution order of the run
        :param session_id: Optional session ID
        :param child_run_ids: Optional child run IDs
        :param child_runs: Optional child runs
        :param feedback_stats: Optional feedback stats
        :param app_path: Optional app path
        :param _host_url: Optional host URL
        """
        super().__init__(
            id=id,
            name=name,
            start_time=start_time,
            inputs=inputs,
            run_type=run_type,
            end_time=end_time,
            extra=extra,
            error=error,
            serialized=serialized,
            events=events,
            outputs=outputs,
            reference_example_id=reference_example_id,
            parent_run_id=parent_run_id,
            tags=tags,
        )
        self.execution_order = execution_order
        self.session_id = session_id
        self.child_run_ids = child_run_ids
        self.child_runs = child_runs
        self.feedback_stats = feedback_stats
        self.app_path = app_path
        self._host_url = _host_url


class FeedbackSource:
    def __init__(
        self, type: FeedbackSourceType, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Initialize FeedbackSource.

        :param type: Type of feedback source
        :param metadata: Optional metadata associated with the feedback source
        """
        self.type = type
        self.metadata = metadata


class Feedback:
    def __init__(
        self,
        id: UUID,
        run_id: UUID,
        key: str,
        score: SCORE_TYPE = None,
        value: VALUE_TYPE = None,
        created_at: Optional[datetime] = None,
        modified_at: Optional[datetime] = None,
        comment: Optional[str] = None,
        correction: Union[str, dict, None] = None,
        feedback_source: Optional[FeedbackSource] = None,
    ) -> None:
        """Initialize Feedback.

        :param id: ID of the feedback
        :param run_id: Associated run ID
        :param key: Metric name, tag, or aspect for feedback
        :param score: Optional value or score to assign the run
        :param value: Optional display value, tag or other value
        :param created_at: Optional creation timestamp
        :param modified_at: Optional modification timestamp
        :param comment: Optional comment or explanation
        :param correction: Optional correction for the run
        :param feedback_source: Optional source of the feedback
        """
        self.id = id
        self.run_id = run_id
        self.key = key
        self.score = score
        self.value = value
        self.created_at = created_at
        self.modified_at = modified_at
        self.comment = comment
        self.correction = correction
        self.feedback_source = feedback_source


class TracerSession:
    def __init__(
        self,
        id: UUID,
        start_time: Optional[datetime] = None,
        name: Optional[str] = None,
        end_time: Optional[datetime] = None,
        events: Optional[List[dict]] = None,
        num_runs: int = 0,
        num_feedback: int = 0,
    ) -> None:
        """Initialize TracerSession.

        :param id: ID of the project
        :param start_time: Creation timestamp, default is current time
        :param name: Optional name of the project
        :param end_time: Optional end time of the project
        :param events: Events associated with the project
        :param num_runs: Number of runs in the project
        :param num_feedback: Number of feedback items in the project
        """
        self.id = id
        self.start_time = start_time or datetime.utcnow()
        self.name = name
        self.end_time = end_time
        self.events = events or []
        self.num_runs = num_runs
        self.num_feedback = num_feedback


class TracerSessionResult(TracerSession):
    """TracerSession schema returned when reading a project
    by ID. Sessions are also referred to as "Projects" in the UI."""

    def __init__(
        self,
        run_count: Optional[int] = None,
        latency_p50: Optional[timedelta] = None,
        latency_p99: Optional[timedelta] = None,
        total_tokens: Optional[int] = None,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        last_run_start_time: Optional[datetime] = None,
        feedback_stats: Optional[Dict[str, Any]] = None,
        reference_dataset_ids: Optional[List[UUID]] = None,
        run_facets: Optional[List[Dict[str, Any]]] = None,
        *args,
        **kwargs,
    ) -> None:
        """Initialize TracerSessionResult.

        :param run_count: The number of runs in the project
        :param latency_p50: The median (50th percentile) latency for the project
        :param latency_p99: The 99th percentile latency for the project
        :param total_tokens: The total number of tokens consumed in the project
        :param prompt_tokens: The total number of prompt tokens consumed in the project
        :param completion_tokens: The total number of completion tokens consumed in the project
        :param last_run_start_time: The start time of the last run in the project
        :param feedback_stats: Feedback stats for the project
        :param reference_dataset_ids: The reference dataset IDs this project's runs were generated on
        :param run_facets: Facets for the runs in the project
        """
        super().__init__(*args, **kwargs)
        self.run_count = run_count
        self.latency_p50 = latency_p50
        self.latency_p99 = latency_p99
        self.total_tokens = total_tokens
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.last_run_start_time = last_run_start_time
        self.feedback_stats = feedback_stats
        self.reference_dataset_ids = reference_dataset_ids
        self.run_facets = run_facets
