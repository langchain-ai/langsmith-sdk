from __future__ import annotations

import json
import logging
import os
import socket
import weakref
from collections import defaultdict
from datetime import datetime
from io import BytesIO
from typing import (
    TYPE_CHECKING,
    Any,
    DefaultDict,
    Dict,
    Iterator,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Union,
    cast,
)
from urllib.parse import urlsplit
from uuid import UUID

from requests import ConnectionError, HTTPError, Response, Session
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from langsmith.evaluation.evaluator import RunEvaluator
from langsmith.schemas import (
    APIFeedbackSource,
    Dataset,
    DatasetCreate,
    DataType,
    Example,
    ExampleCreate,
    ExampleUpdate,
    Feedback,
    FeedbackCreate,
    FeedbackSourceBase,
    FeedbackSourceType,
    ModelFeedbackSource,
    Run,
    RunBase,
    RunTypeEnum,
    TracerSession,
    TracerSessionResult,
)
from langsmith.utils import (
    LangSmithAPIError,
    LangSmithConnectionError,
    LangSmithError,
    LangSmithUserError,
    get_runtime_environment,
    raise_for_status_with_text,
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


def _default_retry_config() -> Retry:
    return Retry(
        total=3,
        allowed_methods=None,  # Retry on all methods
        status_forcelist=[502, 503, 504, 408, 425, 429],
        backoff_factor=0.5,
        # Sadly urllib3 1.x doesn't support backoff_jitter
        raise_on_redirect=False,
        raise_on_status=False,
    )


def _serialize_json(obj: Any) -> str:
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, UUID):
        return str(obj)
    raise TypeError("Type %s not serializable" % type(obj))


def close_session(session: Session) -> None:
    """Close the session."""
    logger.debug("Closing Client.session")
    session.close()


def _validate_api_key_if_hosted(api_url: str, api_key: Optional[str]) -> None:
    """Verify API key is provided if url not localhost."""
    if not _is_localhost(api_url):
        if not api_key:
            raise LangSmithUserError(
                "API key must be provided when using hosted LangSmith API"
            )


class Client:
    """Client for interacting with the LangSmith API."""

    __slots__ = [
        "__weakref__",
        "api_url",
        "api_key",
        "retry_config",
        "timeout_ms",
        "session",
    ]

    def __init__(
        self,
        api_url: Optional[str] = None,
        *,
        api_key: Optional[str] = None,
        retry_config: Optional[Retry] = None,
        timeout_ms: Optional[int] = None,
    ) -> None:
        """Initialize a Client instance.

        Args:
            api_key: API key for the LangSmith API. Defaults to the
                LANGCHAIN_API_KEY environment variable.
            api_url: URL for the LangSmith API. Defaults to the
                LANGCHAIN_ENDPOINT environment variable or
                http://localhost:1984 if not set.
            retry_config: Retry configuration for the HTTPAdapter.
            timeout_ms: Timeout in milliseconds for the HTTPAdapter.

        Raises:
            LangSmithUserError: If the API key is not provided when using the
             hosted service.
        """
        self.api_url = (
            api_url
            if api_url is not None
            else os.getenv("LANGCHAIN_ENDPOINT", "http://localhost:1984")
        )
        self.api_key = (
            api_key if api_key is not None else os.getenv("LANGCHAIN_API_KEY")
        )
        _validate_api_key_if_hosted(self.api_url, self.api_key)
        self.retry_config = retry_config or _default_retry_config()
        self.timeout_ms = timeout_ms or 7000
        # Create a session and register a finalizer to close it
        self.session = Session()
        weakref.finalize(self, close_session, self.session)

        # Mount the HTTPAdapter with the retry configuration
        adapter = HTTPAdapter(max_retries=self.retry_config)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _repr_html_(self) -> str:
        """Return an HTML representation of the instance with a link to the URL."""
        if _is_localhost(self.api_url):
            link = "http://localhost"
        elif "dev" in self.api_url.split(".", maxsplit=1)[0]:
            link = "https://dev.smith.langchain.com/"
        else:
            link = "https://smith.langchain.com"
        return f'<a href="{link}", target="_blank" rel="noopener">LangSmith Client</a>'

    def __repr__(self) -> str:
        """Return a string representation of the instance with a link to the URL."""
        return f"Client (API URL: {self.api_url})"

    @property
    def _headers(self) -> Dict[str, str]:
        """Get the headers for the API request."""
        headers = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    def request_with_retries(
        self,
        request_method: str,
        url: str,
        request_kwargs: Mapping,
    ) -> Response:
        try:
            response = self.session.request(
                request_method, url, stream=False, **request_kwargs
            )
            raise_for_status_with_text(response)
            return response
        except HTTPError as e:
            if response is not None and response.status_code == 500:
                raise LangSmithAPIError(
                    f"Server error caused failure to {request_method} {url} in"
                    f" LangChain+ API. {e}"
                )
            else:
                raise LangSmithUserError(
                    f"Failed to {request_method} {url} in LangChain+ API. {e}"
                )
        except ConnectionError as e:
            raise LangSmithConnectionError(
                f"Connection error caused failure to {request_method} {url}"
                "  in LangChain+ API. Please confirm your LANGCHAIN_ENDPOINT."
            ) from e
        except Exception as e:
            raise LangSmithError(
                f"Failed to {request_method} {url} in LangChain+ API. {e}"
            ) from e

    def _get_with_retries(
        self, path: str, params: Optional[Dict[str, Any]] = None
    ) -> Response:
        return self.request_with_retries(
            "get",
            f"{self.api_url}{path}",
            request_kwargs={
                "params": params,
                "headers": self._headers,
                "timeout": self.timeout_ms / 1000,
            },
        )

    def _get_paginated_list(
        self, path: str, *, params: Optional[dict] = None
    ) -> Iterator[dict]:
        params_ = params.copy() if params else {}
        offset = params_.get("offset", 0)
        params_["limit"] = params_.get("limit", 100)
        while True:
            params_["offset"] = offset
            response = self._get_with_retries(path, params=params_)
            items = response.json()
            if not items:
                break
            yield from items
            if len(items) < params_["limit"]:
                # offset and limit isn't respected if we're
                # querying for specific values
                break
            offset += len(items)

    def upload_dataframe(
        self,
        df: pd.DataFrame,
        name: str,
        input_keys: Sequence[str],
        output_keys: Sequence[str],
        *,
        description: Optional[str] = None,
        data_type: Optional[DataType] = DataType.kv,
    ) -> Dataset:
        """Upload a dataframe as individual examples to the LangSmith API."""
        csv_file = BytesIO()
        df.to_csv(csv_file, index=False)
        csv_file.seek(0)
        return self.upload_csv(
            ("data.csv", csv_file),
            input_keys=input_keys,
            output_keys=output_keys,
            description=description,
            name=name,
            data_type=data_type,
        )

    def upload_csv(
        self,
        csv_file: Union[str, Tuple[str, BytesIO]],
        input_keys: Sequence[str],
        output_keys: Sequence[str],
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        data_type: Optional[DataType] = DataType.kv,
    ) -> Dataset:
        """Upload a CSV file to the LangSmith API."""
        data = {
            "input_keys": input_keys,
            "output_keys": output_keys,
        }
        if name:
            data["name"] = name
        if description:
            data["description"] = description
        if data_type:
            data["data_type"] = data_type.value
        if isinstance(csv_file, str):
            with open(csv_file, "rb") as f:
                file_ = {"file": f}
                response = self.session.post(
                    self.api_url + "/datasets/upload",
                    headers=self._headers,
                    data=data,
                    files=file_,
                )
        elif isinstance(csv_file, tuple):
            response = self.session.post(
                self.api_url + "/datasets/upload",
                headers=self._headers,
                data=data,
                files={"file": csv_file},
            )
        else:
            raise ValueError("csv_file must be a string or tuple")
        raise_for_status_with_text(response)
        result = response.json()
        # TODO: Make this more robust server-side
        if "detail" in result and "already exists" in result["detail"]:
            file_name = csv_file if isinstance(csv_file, str) else csv_file[0]
            file_name = file_name.split("/")[-1]
            raise ValueError(f"Dataset {file_name} already exists")
        return Dataset(**result)

    def create_run(
        self,
        name: str,
        inputs: Dict[str, Any],
        run_type: Union[str, RunTypeEnum],
        *,
        execution_order: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        """Persist a run to the LangSmith API."""
        project_name = kwargs.pop(
            "project_name",
            kwargs.pop(
                "session_name",
                os.environ.get(
                    # TODO: Deprecate LANGCHAIN_SESSION
                    "LANGCHAIN_PROJECT",
                    os.environ.get("LANGCHAIN_SESSION", "default"),
                ),
            ),
        )
        run_create = {
            **kwargs,
            "session_name": project_name,
            "name": name,
            "inputs": inputs,
            "run_type": run_type,
            "execution_order": execution_order if execution_order is not None else 1,
        }
        run_extra = cast(dict, run_create.setdefault("extra", {}))
        runtime = run_extra.setdefault("runtime", {})
        runtime_env = get_runtime_environment()
        run_extra["runtime"] = {**runtime_env, **runtime}
        headers = {**self._headers, "Accept": "application/json"}
        self.request_with_retries(
            "post",
            f"{self.api_url}/runs",
            request_kwargs={
                "data": json.dumps(run_create, default=_serialize_json),
                "headers": headers,
                "timeout": self.timeout_ms / 1000,
            },
        )

    def update_run(
        self,
        run_id: ID_TYPE,
        **kwargs: Any,
    ) -> None:
        """Update a run to the LangSmith API."""
        headers = {**self._headers, "Accept": "application/json"}
        self.request_with_retries(
            "patch",
            f"{self.api_url}/runs/{run_id}",
            request_kwargs={
                "data": json.dumps(kwargs, default=_serialize_json),
                "headers": headers,
                "timeout": self.timeout_ms / 1000,
            },
        )

    def _load_child_runs(self, run: Run) -> Run:
        child_runs = self.list_runs(id=run.child_run_ids)
        treemap: DefaultDict[UUID, List[Run]] = defaultdict(list)
        runs: Dict[UUID, Run] = {}
        for child_run in sorted(child_runs, key=lambda r: r.execution_order):
            if child_run.parent_run_id is None:
                raise LangSmithError(f"Child run {child_run.id} has no parent")
            treemap[child_run.parent_run_id].append(child_run)
            runs[child_run.id] = child_run
        run.child_runs = treemap.pop(run.id, [])
        for run_id, children in treemap.items():
            runs[run_id].child_runs = children
        return run

    def read_run(self, run_id: ID_TYPE, load_child_runs: bool = False) -> Run:
        """Read a run from the LangSmith API.

        Args:
            run_id: The ID of the run to read.
            load_child_runs: Whether to load nested child runs.

        Returns:
            The run.
        """
        response = self._get_with_retries(f"/runs/{run_id}")
        run = Run(**response.json())
        if load_child_runs and run.child_run_ids:
            run = self._load_child_runs(run)
        return run

    def list_runs(
        self,
        *,
        project_id: Optional[ID_TYPE] = None,
        project_name: Optional[str] = None,
        run_type: Optional[str] = None,
        dataset_name: Optional[str] = None,
        dataset_id: Optional[ID_TYPE] = None,
        reference_example_id: Optional[ID_TYPE] = None,
        query: Optional[str] = None,
        filter: Optional[str] = None,
        execution_order: Optional[int] = None,
        parent_run_id: Optional[ID_TYPE] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        error: Optional[bool] = None,
        run_ids: Optional[List[ID_TYPE]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        order_by: Optional[Sequence[str]] = None,
        **kwargs: Any,
    ) -> Iterator[Run]:
        """List runs from the LangSmith API."""
        if project_name is not None:
            if project_id is not None:
                raise ValueError("Only one of project_id or project_name may be given")
            project_id = self.read_project(project_name=project_name).id
        if dataset_name is not None:
            if dataset_id is not None:
                raise ValueError("Only one of dataset_id or dataset_name may be given")
            dataset_id = self.read_dataset(dataset_name=dataset_name).id
        query_params: Dict[str, Any] = {
            "session": project_id,
            "run_type": run_type,
            **kwargs,
        }
        if reference_example_id is not None:
            query_params["reference_example"] = reference_example_id
        if dataset_id is not None:
            query_params["dataset"] = dataset_id
        if query is not None:
            query_params["query"] = query
        if filter is not None:
            query_params["filter"] = filter
        if execution_order is not None:
            query_params["execution_order"] = execution_order
        if parent_run_id is not None:
            query_params["parent_run"] = parent_run_id
        if start_time is not None:
            query_params["start_time"] = start_time.isoformat()
        if end_time is not None:
            query_params["end_time"] = end_time.isoformat()
        if error is not None:
            query_params["error"] = error
        if run_ids is not None:
            query_params["id"] = run_ids
        if limit is not None:
            query_params["limit"] = limit
        if offset is not None:
            query_params["offset"] = offset
        if order_by is not None:
            query_params["order"] = order_by
        yield from (
            Run(**run) for run in self._get_paginated_list("/runs", params=query_params)
        )

    def delete_run(self, run_id: ID_TYPE) -> None:
        """Delete a run from the LangSmith API."""
        response = self.session.delete(
            f"{self.api_url}/runs/{run_id}",
            headers=self._headers,
        )
        raise_for_status_with_text(response)

    def create_project(
        self,
        project_name: str,
        *,
        project_extra: Optional[dict] = None,
        upsert: bool = False,
    ) -> TracerSession:
        """Create a project on the LangSmith API."""
        endpoint = f"{self.api_url}/sessions"
        body = {
            "name": project_name,
            "extra": project_extra,
        }
        params = {}
        if upsert:
            params["upsert"] = True
        response = self.session.post(
            endpoint,
            headers=self._headers,
            json=body,
        )
        raise_for_status_with_text(response)
        return TracerSession(**response.json())

    @xor_args(("project_id", "project_name"))
    def read_project(
        self, *, project_id: Optional[str] = None, project_name: Optional[str] = None
    ) -> TracerSessionResult:
        """Read a project from the LangSmith API.

        Args:
            project_id: The ID of the project to read.
            project_name: The name of the project to read.
                Note: Only one of project_id or project_name may be given.
        """
        path = "/sessions"
        params: Dict[str, Any] = {"limit": 1}
        if project_id is not None:
            path += f"/{project_id}"
        elif project_name is not None:
            params["name"] = project_name
        else:
            raise ValueError("Must provide project_name or project_id")
        response = self._get_with_retries(path, params=params)
        result = response.json()
        if isinstance(result, list):
            if len(result) == 0:
                raise LangSmithError(f"Project {project_name} not found")
            return TracerSessionResult(**result[0])
        return TracerSessionResult(**response.json())

    def list_projects(self) -> Iterator[TracerSession]:
        """List projects from the LangSmith API."""
        yield from (
            TracerSession(**project)
            for project in self._get_paginated_list("/sessions")
        )

    @xor_args(("project_name", "project_id"))
    def delete_project(
        self, *, project_name: Optional[str] = None, project_id: Optional[str] = None
    ) -> None:
        """Delete a project from the LangSmith API."""
        if project_name is not None:
            project_id = str(self.read_project(project_name=project_name).id)
        elif project_id is None:
            raise ValueError("Must provide project_name or project_id")
        response = self.session.delete(
            self.api_url + f"/sessions/{project_id}",
            headers=self._headers,
        )
        raise_for_status_with_text(response)

    def create_dataset(
        self,
        dataset_name: str,
        *,
        description: Optional[str] = None,
        data_type: DataType = DataType.kv,
    ) -> Dataset:
        """Create a dataset in the LangSmith API."""
        dataset = DatasetCreate(
            name=dataset_name,
            description=description,
            data_type=data_type,
        )
        response = self.session.post(
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
                raise LangSmithError(f"Dataset {dataset_name} not found")
            return Dataset(**result[0])
        return Dataset(**result)

    def list_datasets(self) -> Iterator[Dataset]:
        """List the datasets on the LangSmith API."""
        yield from (
            Dataset(**dataset) for dataset in self._get_paginated_list("/datasets")
        )

    @xor_args(("dataset_id", "dataset_name"))
    def delete_dataset(
        self,
        *,
        dataset_id: Optional[ID_TYPE] = None,
        dataset_name: Optional[str] = None,
    ) -> None:
        """Delete a dataset by ID or name."""
        if dataset_name is not None:
            dataset_id = self.read_dataset(dataset_name=dataset_name).id
        if dataset_id is None:
            raise ValueError("Must provide either dataset name or ID")
        response = self.session.delete(
            f"{self.api_url}/datasets/{dataset_id}",
            headers=self._headers,
        )
        raise_for_status_with_text(response)

    @xor_args(("dataset_id", "dataset_name"))
    def create_example(
        self,
        inputs: Mapping[str, Any],
        dataset_id: Optional[ID_TYPE] = None,
        dataset_name: Optional[str] = None,
        created_at: Optional[datetime] = None,
        outputs: Optional[Mapping[str, Any]] = None,
    ) -> Example:
        """Create a dataset example in the LangSmith API."""
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
        response = self.session.post(
            f"{self.api_url}/examples", headers=self._headers, data=example.json()
        )
        raise_for_status_with_text(response)
        result = response.json()
        return Example(**result)

    def read_example(self, example_id: ID_TYPE) -> Example:
        """Read an example from the LangSmith API."""
        response = self._get_with_retries(f"/examples/{example_id}")
        return Example(**response.json())

    def list_examples(
        self, dataset_id: Optional[ID_TYPE] = None, dataset_name: Optional[str] = None
    ) -> Iterator[Example]:
        """List the datasets on the LangSmith API."""
        params = {}
        if dataset_id is not None:
            params["dataset"] = dataset_id
        elif dataset_name is not None:
            dataset_id = self.read_dataset(dataset_name=dataset_name).id
            params["dataset"] = dataset_id
        else:
            pass
        yield from (
            Example(**dataset)
            for dataset in self._get_paginated_list("/examples", params=params)
        )

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
        response = self.session.patch(
            f"{self.api_url}/examples/{example_id}",
            headers=self._headers,
            data=example.json(exclude_none=True),
        )
        raise_for_status_with_text(response)
        return response.json()

    def delete_example(self, example_id: ID_TYPE) -> None:
        """Delete an example by ID."""
        response = self.session.delete(
            f"{self.api_url}/examples/{example_id}",
            headers=self._headers,
        )
        raise_for_status_with_text(response)

    def _resolve_run_id(
        self, run: Union[Run, RunBase, str, UUID], load_child_runs: bool
    ) -> Run:
        if isinstance(run, (str, UUID)):
            run_ = self.read_run(run, load_child_runs=load_child_runs)
        elif isinstance(run, Run):
            run_ = run
        elif isinstance(run, RunBase):
            run_ = Run(**run.dict())
        else:
            raise TypeError(f"Invalid run type: {type(run)}")
        return run_

    def _resolve_example_id(
        self, example: Union[Example, str, UUID, dict, None], run: Run
    ) -> Optional[Example]:
        if isinstance(example, (str, UUID)):
            reference_example_ = self.read_example(example)
        elif isinstance(example, Example):
            reference_example_ = example
        elif isinstance(example, dict):
            reference_example_ = Example(**example)
        elif run.reference_example_id is not None:
            reference_example_ = self.read_example(run.reference_example_id)
        else:
            reference_example_ = None
        return reference_example_

    def evaluate_run(
        self,
        run: Union[Run, RunBase, str, UUID],
        evaluator: RunEvaluator,
        *,
        source_info: Optional[Dict[str, Any]] = None,
        reference_example: Optional[Union[Example, str, dict, UUID]] = None,
        load_child_runs: bool = False,
    ) -> Feedback:
        """Evaluate a run.

        Args:
            run: The run to evaluate. Can be a run_id or a Run object.
            evaluator: The evaluator to use.
            source_info: Additional information about the source of the
                 evaluation to log as feedback metadata.
            reference_example: The example to use as a reference for the
                evaluation. If not provided, the run's reference example
                will be used.
            load_child_runs: Whether to load child runs when
                 resolving the run ID.

        Returns:
            The feedback object created by the evaluation.
        """
        run_ = self._resolve_run_id(run, load_child_runs=load_child_runs)
        reference_example_ = self._resolve_example_id(reference_example, run_)
        feedback_result = evaluator.evaluate_run(
            run_,
            example=reference_example_,
        )
        source_info = source_info or {}
        if feedback_result.evaluator_info:
            source_info = {**feedback_result.evaluator_info, **source_info}
        return self.create_feedback(
            run_.id,
            feedback_result.key,
            score=feedback_result.score,
            value=feedback_result.value,
            comment=feedback_result.comment,
            correction=feedback_result.correction,
            source_info=source_info,
            feedback_source_type=FeedbackSourceType.MODEL,
        )

    async def aevaluate_run(
        self,
        run: Union[Run, str, UUID],
        evaluator: RunEvaluator,
        *,
        source_info: Optional[Dict[str, Any]] = None,
        reference_example: Optional[Union[Example, str, dict, UUID]] = None,
        load_child_runs: bool = False,
    ) -> Feedback:
        """Evaluate a run.

        Args:
            run: The run to evaluate. Can be a run_id or a Run object.
            evaluator: The evaluator to use.
            source_info: Additional information about the source of
                the evaluation to log as feedback metadata.
            reference_example: The example to use as a reference
                for the evaluation. If not provided, the run's
                reference example will be used.
            load_child_runs: Whether to load child runs when
                resolving the run ID.

        Returns:
            The feedback created by the evaluation.
        """
        run_ = self._resolve_run_id(run, load_child_runs=load_child_runs)
        reference_example_ = self._resolve_example_id(reference_example, run_)
        feedback_result = await evaluator.aevaluate_run(
            run_,
            example=reference_example_,
        )
        source_info = source_info or {}
        if feedback_result.evaluator_info:
            source_info = {**feedback_result.evaluator_info, **source_info}
        return self.create_feedback(
            run_.id,
            feedback_result.key,
            score=feedback_result.score,
            value=feedback_result.value,
            comment=feedback_result.comment,
            correction=feedback_result.correction,
            source_info=source_info,
            feedback_source_type=FeedbackSourceType.MODEL,
        )

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
        """Create a feedback in the LangSmith API.

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
        response = self.session.post(
            self.api_url + "/feedback",
            headers={**self._headers, "Content-Type": "application/json"},
            data=feedback.json(exclude_none=True),
        )
        raise_for_status_with_text(response)
        return Feedback(**response.json())

    def read_feedback(self, feedback_id: ID_TYPE) -> Feedback:
        """Read a feedback from the LangSmith API."""
        response = self._get_with_retries(f"/feedback/{feedback_id}")
        return Feedback(**response.json())

    def list_feedback(
        self,
        *,
        run_ids: Optional[Sequence[ID_TYPE]] = None,
        **kwargs: Any,
    ) -> Iterator[Feedback]:
        """List the feedback objects on the LangSmith API."""
        params = {
            "run": run_ids,
            **kwargs,
        }

        yield from (
            Feedback(**feedback)
            for feedback in self._get_paginated_list("/feedback", params=params)
        )

    def delete_feedback(self, feedback_id: ID_TYPE) -> None:
        """Delete a feedback by ID."""
        response = self.session.delete(
            f"{self.api_url}/feedback/{feedback_id}",
            headers=self._headers,
        )
        raise_for_status_with_text(response)
