from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union
from uuid import UUID, uuid4

SCORE_TYPE = Union[bool, int, float, None]
VALUE_TYPE = Union[Dict, bool, int, float, str, None]
DATE_TYPE = Union[datetime, str]
ID_TYPE = Union[UUID, str]


def _coerce_req_uuid(value: ID_TYPE) -> UUID:
    return value if isinstance(value, UUID) else UUID(value)


def _coerce_uuid(value: Optional[ID_TYPE]) -> Optional[UUID]:
    if value is None:
        return value
    return _coerce_req_uuid(value)


def _parse_datetime(value: Union[str, datetime]) -> datetime:
    if isinstance(value, datetime):
        return value
    elif isinstance(value, str):
        return datetime.fromisoformat(value)
    else:
        raise ValueError("The input must be either a string or a datetime object.")


class DataType(str, Enum):
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


class FeedbackSourceType(str, Enum):
    """Feedback source type."""

    API = "api"
    """General feedback submitted from the API."""
    MODEL = "model"
    """Model-assisted feedback."""


class ExampleBase:
    def __init__(
        self,
        *,
        dataset_id: Union[UUID, str],
        inputs: Dict[str, Any],
        outputs: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize ExampleBase.

        Arge:
            dataset_id (UUID), ID of the dataset
            inputs: Inputs dictionary
            outputs: Optional Outputs dictionary
        """
        self.dataset_id = _coerce_req_uuid(dataset_id)
        self.inputs = inputs
        self.outputs = outputs
        for key, value in kwargs.items():
            setattr(self, key, value)


class Example(ExampleBase):
    def __init__(
        self,
        *,
        id: ID_TYPE,
        dataset_id: ID_TYPE,
        inputs: Dict[str, Any],
        created_at: DATE_TYPE,
        outputs: Optional[Dict[str, Any]] = None,
        modified_at: Optional[datetime] = None,
        runs: List[Run] = [],
        **kwargs: Any,
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
        super().__init__(
            dataset_id=dataset_id, inputs=inputs, outputs=outputs, **kwargs
        )
        self.id = _coerce_req_uuid(id)
        self.created_at = _parse_datetime(created_at)
        self.modified_at = modified_at
        self.runs = runs


class ExampleUpdate:
    def __init__(
        self,
        dataset_id: Optional[ID_TYPE] = None,
        inputs: Optional[Dict[str, Any]] = None,
        outputs: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize ExampleUpdate.

        :param dataset_id: Optional ID of the dataset
        :param inputs: Optional Inputs dictionary
        :param outputs: Optional Outputs dictionary
        """
        self.dataset_id = _coerce_uuid(dataset_id)
        self.inputs = inputs
        self.outputs = outputs


class DatasetBase:
    def __init__(
        self,
        *,
        name: str,
        description: Optional[str] = None,
        data_type: Optional[DataType] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize DatasetBase.

        :param name: Name of the dataset
        :param description: Optional description
        :param data_type: Optional DataType
        """
        self.name = name
        self.description = description
        self.data_type = data_type
        for key, value in kwargs.items():
            setattr(self, key, value)


class Dataset(DatasetBase):
    def __init__(
        self,
        *,
        name: str,
        id: ID_TYPE,
        created_at: DATE_TYPE,
        description: Optional[str] = None,
        modified_at: Optional[DATE_TYPE] = None,
        data_type: Optional[DataType] = None,
        tenant_id: Optional[ID_TYPE] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Dataset.

        :param name: Name of the dataset
        :param id: ID of the dataset
        :param created_at: Creation timestamp
        :param description: Optional description
        :param modified_at: Optional modification timestamp
        :param data_type: Optional DataType
        """
        super().__init__(
            name=name, description=description, data_type=data_type, **kwargs
        )
        self.id = _coerce_uuid(id)
        self.created_at = _parse_datetime(created_at)
        self.modified_at = modified_at
        self.tenant_id = _coerce_uuid(tenant_id)


class RunBase(dict):
    def __init__(
        self,
        *,
        name: str,
        inputs: dict,
        run_type: str,
        id: Optional[ID_TYPE] = None,
        start_time: Optional[DATE_TYPE] = None,
        end_time: Optional[DATE_TYPE] = None,
        extra: Optional[dict] = None,
        error: Optional[str] = None,
        serialized: Optional[dict] = None,
        events: Optional[List[Dict]] = None,
        outputs: Optional[dict] = None,
        reference_example_id: Optional[ID_TYPE] = None,
        parent_run_id: Optional[ID_TYPE] = None,
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
        self.id = _coerce_req_uuid(id) if id is not None else uuid4()
        self.name = name
        self.start_time = _parse_datetime(start_time) if start_time else None
        self.inputs = inputs
        self.run_type = run_type
        self.end_time = _parse_datetime(end_time) if end_time else None
        self.extra = extra
        self.error = error
        self.serialized = serialized
        self.events = events
        self.outputs = outputs
        self.reference_example_id = reference_example_id
        self.parent_run_id = _coerce_uuid(parent_run_id)
        self.tags = tags

    def dict(
        self, exclude: Optional[Set[str]] = None, exclude_none: bool = False
    ) -> Dict:
        d = self.__dict__.copy()
        if exclude is not None:
            for key in exclude:
                d.pop(key, None)
        if exclude_none:
            d = {k: v for k, v in d.items() if v is not None}
        return d

    def __repr__(self) -> str:
        d = self.dict()
        return f"{self.__class__.__name__}({d})"


class Run(RunBase):
    def __init__(
        self,
        *,
        id: UUID,
        name: str,
        inputs: dict,
        run_type: str,
        start_time: Optional[DATE_TYPE] = None,
        execution_order: Optional[int] = None,
        session_id: Optional[ID_TYPE] = None,
        child_run_ids: Optional[List[ID_TYPE]] = None,
        child_runs: Optional[List[Run]] = None,
        feedback_stats: Optional[Dict[str, Any]] = None,
        app_path: Optional[str] = None,
        end_time: Optional[DATE_TYPE] = None,
        extra: Optional[dict] = None,
        error: Optional[str] = None,
        serialized: Optional[dict] = None,
        events: Optional[List[Dict]] = None,
        outputs: Optional[dict] = None,
        reference_example_id: Optional[ID_TYPE] = None,
        parent_run_id: Optional[ID_TYPE] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
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
        self.id = _coerce_req_uuid(id)
        self.execution_order = execution_order if execution_order is not None else 1
        self.session_id = _coerce_uuid(session_id)
        self.child_run_ids = (
            [_coerce_uuid(_child_id) for _child_id in child_run_ids]
            if child_run_ids is not None
            else None
        )
        self.child_runs = child_runs
        self.feedback_stats = feedback_stats
        self.app_path = app_path
        self._host_url = kwargs.get("_host_url")
        for key, value in kwargs.items():
            setattr(self, key, value)


class Feedback:
    def __init__(
        self,
        id: ID_TYPE,
        run_id: ID_TYPE,
        key: str,
        *,
        score: SCORE_TYPE = None,
        value: VALUE_TYPE = None,
        created_at: Optional[DATE_TYPE] = None,
        modified_at: Optional[DATE_TYPE] = None,
        comment: Optional[str] = None,
        correction: Union[str, dict, None] = None,
        feedback_source: Optional[dict] = None,
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
        self.id = _coerce_req_uuid(id)
        self.run_id = _coerce_req_uuid(run_id)
        self.key = key
        self.score = score
        self.value = value
        self.created_at = _parse_datetime(created_at) if created_at else None
        self.modified_at = _parse_datetime(modified_at) if modified_at else None
        self.comment = comment
        self.correction = correction
        self.feedback_source = feedback_source


class TracerSession:
    def __init__(
        self,
        *,
        id: ID_TYPE,
        name: Optional[str] = None,
        events: Optional[List[dict]] = None,
        num_runs: int = 0,
        num_feedback: int = 0,
        last_run_start_time: Optional[DATE_TYPE] = None,
        last_run_start_time_live: Optional[DATE_TYPE] = None,
        reference_dataset_ids: Optional[List[ID_TYPE]] = None,
        tenant_id: Optional[ID_TYPE] = None,
        run_count: Optional[int] = None,
        start_time: Optional[DATE_TYPE] = None,
        extra: Optional[dict] = None,
        default_dataset_id: Optional[ID_TYPE] = None,
        latency_p50: Optional[float] = None,
        latency_p99: Optional[Union[float, timedelta]] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize TracerSession.

        :param id: ID of the project
        :param start_time: Creation timestamp, default is current time
        :param name: Optional name of the project
        :param end_time: Optional end time of the project
        :param events: Events associated with the project
        :param num_runs: Number of runs in the project
        :param num_feedback: Number of feedback items in the project
        :param last_run_start_time: Optional last run start time
        :param last_run_start_time_live: Optional last run start time live
        :param reference_dataset_ids: Optional list of reference dataset IDs
        :param tenant_id: Optional tenant ID
        :param run_count: Optional run count
        :param extra: Optional extra information
        :param default_dataset_id: Optional default dataset ID
        :param latency_p50: Optional latency p50
        :param latency_p99: Optional latency p99
        """
        self.id = _coerce_req_uuid(id)
        self.name = name
        self.events = events or []
        self.num_runs = num_runs
        self.num_feedback = num_feedback
        self.tenant_id = _coerce_uuid(tenant_id)
        self.run_count = run_count
        self.start_time = _parse_datetime(start_time) if start_time else None
        self.last_run_start_time = (
            _parse_datetime(last_run_start_time) if last_run_start_time else None
        )
        self.last_run_start_time_live = (
            _parse_datetime(last_run_start_time_live)
            if last_run_start_time_live
            else None
        )
        self.extra = extra
        self.default_dataset_id = _coerce_uuid(default_dataset_id)
        self.reference_dataset_ids = (
            [_coerce_req_uuid(_id) for _id in reference_dataset_ids]
            if reference_dataset_ids is not None
            else None
        )
        self.latency_p50 = (
            timedelta(latency_p50) if isinstance(latency_p50, float) else latency_p50
        )
        self.latency_p99 = (
            timedelta(latency_p99) if isinstance(latency_p99, float) else latency_p50
        )
        for key, value in kwargs.items():
            setattr(self, key, value)
