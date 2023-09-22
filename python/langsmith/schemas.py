from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, Set, Union, runtime_checkable
from uuid import UUID, uuid4

from typing_extensions import Literal

from langsmith.utils import DictMixin

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


class ExampleBase(DictMixin):
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

        Args:
            id: ID of the example
            dataset_id: ID of the dataset
            inputs: Inputs dictionary
            created_at: Creation timestamp
            outputs: Optional outputs dictionary
            modified_at: Optional modification timestamp
            runs: List of Runs
            **kwargs: Additional keyword arguments

        Returns:
            None
        """
        super().__init__(
            dataset_id=dataset_id, inputs=inputs, outputs=outputs, **kwargs
        )
        self.id = _coerce_req_uuid(id)
        self.created_at = _parse_datetime(created_at)
        self.modified_at = modified_at
        self.runs = runs


class DatasetBase(DictMixin):
    class DatasetBase(DictMixin):
        def __init__(
            self,
            *,
            name: str,
            description: Optional[str] = None,
            data_type: Optional[DataType] = None,
            **kwargs: Any,
        ) -> None:
            """Initialize DatasetBase.

            Function description.

            Args:
                name: Name of the dataset
                description: Optional description
                data_type: Optional DataType
                **kwargs: Additional keyword arguments
            """
            self.name = name
            self.description = description
            self.data_type = data_type
            for key, value in kwargs.items():
                setattr(self, key, value)


class Dataset(DatasetBase):
    def __init__(
        self,
        name: str,
        id: ID_TYPE,
        created_at: DATE_TYPE,
        description: Optional[str] = None,
        modified_at: Optional[DATE_TYPE] = None,
        data_type: Optional[DataType] = None,
        tenant_id: Optional[ID_TYPE] = None,
        _host_url: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize Dataset.

        Args:
            name: Name of the dataset
            id: ID of the dataset
            created_at: Creation timestamp
            description: Optional description
            modified_at: Optional modification timestamp
            data_type: Optional DataType
            tenant_id: Optional tenant ID
            **kwargs: Additional keyword arguments
        """
        super().__init__(
            name=name, description=description, data_type=data_type, **kwargs
        )
        self.id = _coerce_req_uuid(id)
        self.created_at = _parse_datetime(created_at)
        self.modified_at = modified_at
        self.tenant_id = _coerce_uuid(tenant_id)
        if _host_url:
            self.url = f"{_host_url}/datasets/{self.id}"


class RunBase(DictMixin):
    """Base class for Run."""

    def __init__(
        self,
        *,
        inputs: dict,
        run_type: str,
        name: Optional[str] = None,
        id: Optional[ID_TYPE] = None,
        start_time: Optional[DATE_TYPE] = None,
        end_time: Optional[DATE_TYPE] = None,
        execution_order: Optional[int] = None,
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
        """
        Initialize RunBase.

        Args:
            inputs: Inputs for the run
            run_type: Type of run
            name: Name of the run
            id: ID of the run
            start_time: Start time of the run
            end_time: Optional end time of the run
            execution_order: Optional execution order
            extra: Optional extra information
            error: Optional error information
            serialized: Optional serialized information
            events: Optional list of events
            outputs: Optional outputs
            reference_example_id: Optional reference example ID
            parent_run_id: Optional parent run ID
            tags: Optional tags
            **kwargs: Additional keyword arguments
        """
        self.id = _coerce_req_uuid(id) if id is not None else uuid4()
        self.name = name or RunBase._get_name_from_serialized(serialized)
        self.start_time = _parse_datetime(start_time) if start_time else None
        self.inputs = inputs
        self.outputs = outputs
        self.run_type = run_type
        self.end_time = _parse_datetime(end_time) if end_time else None
        self.extra = extra
        self.error = error
        self.serialized = serialized
        self.events = events
        self.reference_example_id = _coerce_uuid(reference_example_id)
        self.parent_run_id = _coerce_uuid(parent_run_id)
        self.tags = tags
        self.execution_order = execution_order if execution_order is not None else 1
        for key, value in kwargs.items():
            setattr(self, key, value)

    @staticmethod
    def _get_name_from_serialized(serialized: Optional[dict]) -> Optional[str]:
        if not serialized:
            return None
        if "name" in serialized:
            return serialized["name"]
        elif "id" in serialized:
            return serialized["id"][-1]
        return None

    def dict(
        self, exclude: Optional[Set[str]] = None, exclude_none: bool = False
    ) -> Dict:
        exclude = exclude or set()
        res = {}
        for k, v in self.items():
            if k not in exclude and (v is not None or not exclude_none):
                res[k] = v
        return res


class Run(RunBase):
    def __init__(
        self,
        *,
        id: UUID,
        name: str,
        inputs: dict,
        run_type: str,
        session_id: Optional[ID_TYPE] = None,
        child_run_ids: Optional[List[ID_TYPE]] = None,
        feedback_stats: Optional[Dict[str, Any]] = None,
        app_path: Optional[str] = None,
        manifest_id: Optional[UUID] = None,
        status: Optional[str] = None,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        first_token_time: Optional[datetime] = None,
        parent_run_ids: Optional[List[UUID]] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Run.

        Args:
            id: ID of the run
            name: Name of the run
            inputs: Inputs for the run
            run_type: Type of run
            session_id: Optional session ID (default: None)
            child_run_ids: Optional child run IDs (default: None)
            feedback_stats: Optional feedback stats (default: None)
            app_path: Optional app path (default: None)
            manifest_id: Unique identifier for the serialized object
            status: Status (pending, error, success)
            prompt_tokens: Aggregate input token counts contained in this
                and all child runs
            completion_tokens: Aggregate output token counts contained in
                this and all child runs
            total_tokens: Aggregate total token counts contained in this
                and all child runs
            first_token_time: Time the first token was emitted, if applicable
            parent_run_ids: Parent and grandparent run IDs

        """
        self.name = name
        super().__init__(
            id=id,
            name=name,
            inputs=inputs,
            run_type=run_type,
            **kwargs,
        )
        self.id = _coerce_req_uuid(id)
        self.session_id = _coerce_uuid(session_id)
        self.child_run_ids = (
            [_coerce_uuid(_child_id) for _child_id in child_run_ids]
            if child_run_ids is not None
            else None
        )
        self.feedback_stats = feedback_stats
        self.app_path = app_path
        self._host_url = kwargs.get("_host_url")
        self._manifest_id: Optional[UUID] = manifest_id
        self._status: Optional[str] = status
        self._prompt_tokens: Optional[int] = prompt_tokens
        self._completion_tokens: Optional[int] = completion_tokens
        self._total_tokens: Optional[int] = total_tokens
        self._manifest_id: Optional[UUID] = manifest_id
        self._first_token_time: Optional[datetime] = (
            datetime.fromisoformat(first_token_time) if first_token_time else None
        )
        self._parent_run_ids: Optional[List[UUID]] = (
            [_coerce_req_uuid(_uid) for _uid in parent_run_ids]
            if parent_run_ids
            else None
        )
        self._trace_id: Optional[UUID] = _coerce_uuid(kwargs.get("trace_id"))

    def dict(
        self, exclude: Optional[Set[str]] = None, exclude_none: bool = False
    ) -> Dict:
        exclude = exclude or set()
        res: Dict[Any, Any] = {}
        for k, v in self.items():
            if k not in exclude and (v is not None or not exclude_none):
                if isinstance(v, RunBase):
                    res[k] = v.dict(exclude=exclude, exclude_none=exclude_none)
                elif isinstance(v, (list, tuple)):
                    res[k] = [
                        _v.dict(exclude=exclude, exclude_none=exclude_none)
                        if isinstance(_v, RunBase)
                        else _v
                        for _v in v
                    ]
                else:
                    res[k] = v
        return res

    @property
    def url(self) -> Optional[str]:
        """URL of this run within the app."""
        if self._host_url and self.app_path:
            return f"{self._host_url}{self.app_path}"
        return None


class Feedback(DictMixin):
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

        Args:
            id: ID of the feedback
            run_id: Associated run ID
            key: Metric name, tag, or aspect for feedback
            score: Optional value or score to assign the run
            value: Optional display value, tag or other value
            created_at: Optional creation timestamp
            modified_at: Optional modification timestamp
            comment: Optional comment or explanation
            correction: Optional correction for the run
            feedback_source: Optional source of the feedback
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


class TracerSession(DictMixin):
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
            timedelta(seconds=latency_p50)
            if isinstance(latency_p50, float)
            else latency_p50
        )
        self.latency_p99 = (
            timedelta(seconds=latency_p99)
            if isinstance(latency_p99, float)
            else latency_p99
        )
        for key, value in kwargs.items():
            setattr(self, key, value)


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

    _host_url: Optional[str] = PrivateAttr(default=None)

    def __init__(self, _host_url: Optional[str] = None, **kwargs: Any) -> None:
        """Initialize a Run object."""
        super().__init__(**kwargs)
        self._host_url = _host_url

    @property
    def url(self) -> Optional[str]:
        """URL of this run within the app."""
        if self._host_url:
            return f"{self._host_url}/o/{self.tenant_id}/projects/p/{self.id}"
        return None


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


@runtime_checkable
class BaseMessageLike(Protocol):
    """
    A protocol representing objects similar to BaseMessage.
    """

    content: str
    additional_kwargs: Dict

    @property
    def type(self) -> str:
        """Type of the Message, used for serialization."""
