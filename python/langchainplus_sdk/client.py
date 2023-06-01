from __future__ import annotations

import logging
import socket
from datetime import datetime
from io import BytesIO
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterator,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Union,
)
from urllib.parse import urlsplit
from uuid import UUID

import requests
from pydantic import BaseSettings, Field, root_validator
from requests import Response
from tenacity import (
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from langchainplus_sdk.schemas import (
    APIFeedbackSource,
    Dataset,
    DatasetCreate,
    Example,
    ExampleCreate,
    ExampleUpdate,
    Feedback,
    FeedbackCreate,
    FeedbackSourceBase,
    FeedbackSourceType,
    ListFeedbackQueryParams,
    ListRunsQueryParams,
    ModelFeedbackSource,
    Run,
    TracerSession,
)
from langchainplus_sdk.utils import (
    LangChainPlusAPIError,
    raise_for_status_with_text,
    request_with_retries,
    xor_args,
)

if TYPE_CHECKING:
    import pandas as pd

logger = logging.getLogger(__name__)


def _is_localhost(url: str) -> bool:
    """Check if the URL is localhost."""
    try:
        netloc = urlsplit(url).netloc.split(":")[0]
        ip = socket.gethostbyname(netloc)
        return ip == "127.0.0.1" or ip.startswith("0.0.0.0") or ip.startswith("::")
    except socket.gaierror:
        return False


ID_TYPE = Union[UUID, str]


def _default_retry_config() -> Dict[str, Any]:
    return dict(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(LangChainPlusAPIError),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )


class LangChainPlusClient(BaseSettings):
    """Client for interacting with the LangChain+ API."""

    api_key: Optional[str] = Field(default=None, env="LANGCHAIN_API_KEY")
    api_url: str = Field(default="http://localhost:1984", env="LANGCHAIN_ENDPOINT")
    retry_config: Mapping[str, Any] = Field(
        default_factory=_default_retry_config, exclude=True
    )

    @root_validator(pre=True)
    def validate_api_key_if_hosted(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Verify API key is provided if url not localhost."""
        api_url: str = values.get("api_url", "http://localhost:1984")
        api_key: Optional[str] = values.get("api_key")
        if not _is_localhost(api_url):
            if not api_key:
                raise ValueError(
                    "API key must be provided when using hosted LangChain+ API"
                )
        return values

    def _repr_html_(self) -> str:
        """Return an HTML representation of the instance with a link to the URL."""
        if _is_localhost(self.api_url):
            link = "http://localhost"
        elif "dev" in self.api_url.split("."):
            link = "https://dev.langchain.plus"
        else:
            link = "https://www.langchain.plus"
        return f'<a href="{link}", target="_blank" rel="noopener">LangChain+ Client</a>'

    def __repr__(self) -> str:
        """Return a string representation of the instance with a link to the URL."""
        return f"LangChainPlusClient (API URL: {self.api_url})"

    @property
    def _headers(self) -> Dict[str, str]:
        """Get the headers for the API request."""
        headers = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    def _get_with_retries(
        self, path: str, params: Optional[Dict[str, Any]] = None
    ) -> Response:
        return request_with_retries(
            "get",
            f"{self.api_url}{path}",
            request_kwargs={"params": params, "headers": self._headers},
            retry_config=self.retry_config,
        )

    def upload_dataframe(
        self,
        df: pd.DataFrame,
        name: str,
        description: str,
        input_keys: Sequence[str],
        output_keys: Sequence[str],
    ) -> Dataset:
        """Upload a dataframe as individual examples to the LangChain+ API."""
        dataset = self.create_dataset(dataset_name=name, description=description)
        for row in df.itertuples():
            inputs = {key: getattr(row, key) for key in input_keys}
            outputs = {key: getattr(row, key) for key in output_keys}
            self.create_example(inputs, outputs=outputs, dataset_id=dataset.id)
        return dataset

    def upload_csv(
        self,
        csv_file: Union[str, Tuple[str, BytesIO]],
        description: str,
        input_keys: Sequence[str],
        output_keys: Sequence[str],
    ) -> Dataset:
        """Upload a CSV file to the LangChain+ API."""
        files = {"file": csv_file}
        data = {
            "input_keys": ",".join(input_keys),
            "output_keys": ",".join(output_keys),
            "description": description,
        }
        response = requests.post(
            self.api_url + "/datasets/upload",
            headers=self._headers,
            data=data,
            files=files,
        )
        raise_for_status_with_text(response)
        result = response.json()
        # TODO: Make this more robust server-side
        if "detail" in result and "already exists" in result["detail"]:
            file_name = csv_file if isinstance(csv_file, str) else csv_file[0]
            file_name = file_name.split("/")[-1]
            raise ValueError(f"Dataset {file_name} already exists")
        return Dataset(**result)

    def read_run(self, run_id: ID_TYPE) -> Run:
        """Read a run from the LangChain+ API."""
        response = self._get_with_retries(f"/runs/{run_id}")
        return Run(**response.json())

    def list_runs(
        self,
        *,
        session_id: Optional[ID_TYPE] = None,
        session_name: Optional[str] = None,
        run_type: Optional[str] = None,
        **kwargs: Any,
    ) -> Iterator[Run]:
        """List runs from the LangChain+ API."""
        if session_name is not None:
            if session_id is not None:
                raise ValueError("Only one of session_id or session_name may be given")
            session_id = self.read_session(session_name=session_name).id
        query_params = ListRunsQueryParams(
            session_id=session_id, run_type=run_type, **kwargs
        )
        response = self._get_with_retries(
            "/runs", params=query_params.dict(exclude_none=True)
        )
        yield from [Run(**run) for run in response.json()]

    def delete_run(self, run_id: ID_TYPE) -> None:
        """Delete a run from the LangChain+ API."""
        response = requests.delete(
            f"{self.api_url}/runs/{run_id}",
            headers=self._headers,
        )
        raise_for_status_with_text(response)
        return

    def create_session(
        self, session_name: str, session_extra: Optional[dict] = None
    ) -> TracerSession:
        """Create a session on the LangChain+ API."""
        endpoint = f"{self.api_url}/sessions?upsert=true"
        body = {
            "name": session_name,
            "extra": session_extra,
        }
        response = requests.post(
            endpoint,
            headers=self._headers,
            json=body,
        )
        raise_for_status_with_text(response)
        return TracerSession(**response.json())

    @xor_args(("session_id", "session_name"))
    def read_session(
        self, *, session_id: Optional[str] = None, session_name: Optional[str] = None
    ) -> TracerSession:
        """Read a session from the LangChain+ API."""
        path = "/sessions"
        params: Dict[str, Any] = {"limit": 1}
        if session_id is not None:
            path += f"/{session_id}"
        elif session_name is not None:
            params["name"] = session_name
        else:
            raise ValueError("Must provide session_name or session_id")
        response = self._get_with_retries(
            path,
            params=params,
        )
        response = self._get_with_retries(
            path,
            params=params,
        )
        result = response.json()
        if isinstance(result, list):
            if len(result) == 0:
                raise ValueError(f"Session {session_name} not found")
            return TracerSession(**result[0])
        return TracerSession(**response.json())

    def list_sessions(self) -> Iterator[TracerSession]:
        """List sessions from the LangChain+ API."""
        response = self._get_with_retries("/sessions")
        yield from [TracerSession(**session) for session in response.json()]

    @xor_args(("session_name", "session_id"))
    def delete_session(
        self, *, session_name: Optional[str] = None, session_id: Optional[str] = None
    ) -> None:
        """Delete a session from the LangChain+ API."""
        if session_name is not None:
            session_id = self.read_session(session_name=session_name).id
        elif session_id is None:
            raise ValueError("Must provide session_name or session_id")
        response = requests.delete(
            self.api_url + f"/sessions/{session_id}",
            headers=self._headers,
        )
        raise_for_status_with_text(response)
        return None

    def create_dataset(
        self, dataset_name: str, *, description: Optional[str] = None
    ) -> Dataset:
        """Create a dataset in the LangChain+ API."""
        dataset = DatasetCreate(
            name=dataset_name,
            description=description,
        )
        response = requests.post(
            self.api_url + "/datasets",
            headers=self._headers,
            data=dataset.json(),
        )
        raise_for_status_with_text(response)
        return Dataset(**response.json())

    @xor_args(("dataset_name", "dataset_id"))
    def read_dataset(
        self,
        *,
        dataset_name: Optional[str] = None,
        dataset_id: Optional[ID_TYPE] = None,
    ) -> Dataset:
        path = "/datasets"
        params: Dict[str, Any] = {"limit": 1}
        if dataset_id is not None:
            path += f"/{dataset_id}"
        elif dataset_name is not None:
            params["name"] = dataset_name
        else:
            raise ValueError("Must provide dataset_name or dataset_id")
        response = self._get_with_retries(
            path,
            params=params,
        )
        result = response.json()
        if isinstance(result, list):
            if len(result) == 0:
                raise ValueError(f"Dataset {dataset_name} not found")
            return Dataset(**result[0])
        return Dataset(**result)

    def list_datasets(self, limit: int = 100) -> Iterator[Dataset]:
        """List the datasets on the LangChain+ API."""
        response = self._get_with_retries("/datasets", params={"limit": limit})
        yield from [Dataset(**dataset) for dataset in response.json()]

    @xor_args(("dataset_id", "dataset_name"))
    def delete_dataset(
        self,
        *,
        dataset_id: Optional[ID_TYPE] = None,
        dataset_name: Optional[str] = None,
    ) -> Dataset:
        """Delete a dataset by ID or name."""
        if dataset_name is not None:
            dataset_id = self.read_dataset(dataset_name=dataset_name).id
        if dataset_id is None:
            raise ValueError("Must provide either dataset name or ID")
        response = requests.delete(
            f"{self.api_url}/datasets/{dataset_id}",
            headers=self._headers,
        )
        raise_for_status_with_text(response)
        return Dataset(**response.json())

    @xor_args(("dataset_id", "dataset_name"))
    def create_example(
        self,
        inputs: Mapping[str, Any],
        dataset_id: Optional[ID_TYPE] = None,
        dataset_name: Optional[str] = None,
        created_at: Optional[datetime] = None,
        outputs: Optional[Mapping[str, Any]] = None,
    ) -> Example:
        """Create a dataset example in the LangChain+ API."""
        if dataset_id is None:
            dataset_id = self.read_dataset(dataset_name=dataset_name).id

        data = {
            "inputs": inputs,
            "outputs": outputs,
            "dataset_id": dataset_id,
        }
        if created_at:
            data["created_at"] = created_at.isoformat()
        example = ExampleCreate(**data)
        response = requests.post(
            f"{self.api_url}/examples", headers=self._headers, data=example.json()
        )
        raise_for_status_with_text(response)
        result = response.json()
        return Example(**result)

    def read_example(self, example_id: ID_TYPE) -> Example:
        """Read an example from the LangChain+ API."""
        response = self._get_with_retries(f"/examples/{example_id}")
        return Example(**response.json())

    def list_examples(
        self, dataset_id: Optional[ID_TYPE] = None, dataset_name: Optional[str] = None
    ) -> Iterator[Example]:
        """List the datasets on the LangChain+ API."""
        params = {}
        if dataset_id is not None:
            params["dataset"] = dataset_id
        elif dataset_name is not None:
            dataset_id = self.read_dataset(dataset_name=dataset_name).id
            params["dataset"] = dataset_id
        else:
            pass
        response = self._get_with_retries("/examples", params=params)
        yield from [Example(**dataset) for dataset in response.json()]

    def update_example(
        self,
        example_id: str,
        *,
        inputs: Optional[Dict[str, Any]] = None,
        outputs: Optional[Mapping[str, Any]] = None,
        dataset_id: Optional[ID_TYPE] = None,
    ) -> Dict[str, Any]:
        """Update a specific example."""
        example = ExampleUpdate(
            inputs=inputs,
            outputs=outputs,
            dataset_id=dataset_id,
        )
        response = requests.patch(
            f"{self.api_url}/examples/{example_id}",
            headers=self._headers,
            data=example.json(exclude_none=True),
        )
        raise_for_status_with_text(response)
        return response.json()

    def delete_example(self, example_id: ID_TYPE) -> Example:
        """Delete an example by ID."""
        response = requests.delete(
            f"{self.api_url}/examples/{example_id}",
            headers=self._headers,
        )
        raise_for_status_with_text(response)
        return Example(**response.json())

    def create_feedback(
        self,
        run_id: ID_TYPE,
        key: str,
        *,
        score: Union[float, int, bool, None] = None,
        value: Union[float, int, bool, str, dict, None] = None,
        correction: Union[str, dict, None] = None,
        comment: Union[str, None] = None,
        source_info: Optional[Dict[str, Any]] = None,
        feedback_source_type: Union[FeedbackSourceType, str] = FeedbackSourceType.API,
    ) -> Feedback:
        """Create a feedback in the LangChain+ API.

        Args:
            run_id: The ID of the run to provide feedback on.
            key: The name of the metric, tag, or 'aspect' this
                feedback is about.
            score: The score to rate this run on the metric
                or aspect.
            value: The display value or non-numeric value for this feedback.
            correction: The proper ground truth for this run.
            comment: A comment about this feedback.
            source_info: Information about the source of this feedback.
            feedback_source_type: The type of feedback source.
        """
        if feedback_source_type == FeedbackSourceType.API:
            feedback_source: FeedbackSourceBase = APIFeedbackSource(
                metadata=source_info
            )
        elif feedback_source_type == FeedbackSourceType.MODEL:
            feedback_source = ModelFeedbackSource(metadata=source_info)
        else:
            raise ValueError(f"Unknown feedback source type {feedback_source_type}")
        feedback = FeedbackCreate(
            run_id=run_id,
            key=key,
            score=score,
            value=value,
            correction=correction,
            comment=comment,
            feedback_source=feedback_source,
        )
        response = requests.post(
            self.api_url + "/feedback",
            headers={**self._headers, "Content-Type": "application/json"},
            data=feedback.json(),
        )
        raise_for_status_with_text(response)
        return Feedback(**feedback.dict())

    def read_feedback(self, feedback_id: ID_TYPE) -> Feedback:
        """Read a feedback from the LangChain+ API."""
        response = self._get_with_retries(f"/feedback/{feedback_id}")
        return Feedback(**response.json())

    def list_feedback(
        self,
        *,
        run_ids: Optional[Sequence[ID_TYPE]] = None,
        **kwargs: Any,
    ) -> Iterator[Feedback]:
        """List the feedback objects on the LangChain+ API."""
        params = ListFeedbackQueryParams(
            run=run_ids,
            **kwargs,
        )
        response = self._get_with_retries(
            "/feedback", params=params.dict(exclude_none=True)
        )
        yield from [Feedback(**feedback) for feedback in response.json()]

    def delete_feedback(self, feedback_id: ID_TYPE) -> None:
        """Delete a feedback by ID."""
        response = requests.delete(
            f"{self.api_url}/feedback/{feedback_id}",
            headers=self._headers,
        )
        raise_for_status_with_text(response)
