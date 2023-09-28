"""The LangSmith Client."""
from __future__ import annotations

import asyncio
import collections
import concurrent
import contextlib
import datetime
import functools
import io
import json
import logging
import os
import socket
import uuid
import weakref
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    AsyncIterator,
    Callable,
    Coroutine,
    DefaultDict,
    Dict,
    Iterable,
    Iterator,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Union,
    cast,
)
from urllib import parse as urllib_parse

import httpx
from tenacity import (
    AsyncRetrying,
    Retrying,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from langsmith import env as ls_env
from langsmith import schemas as ls_schemas
from langsmith import utils as ls_utils
from langsmith.evaluation import evaluator as ls_evaluator

if TYPE_CHECKING:
    import pandas as pd

logger = logging.getLogger(__name__)


def _is_localhost(url: str) -> bool:
    """Check if the URL is localhost.

    Parameters
    ----------
    url : str
        The URL to check.

    Returns
    -------
    bool
        True if the URL is localhost, False otherwise.
    """
    try:
        netloc = urllib_parse.urlsplit(url).netloc.split(":")[0]
        ip = socket.gethostbyname(netloc)
        return ip == "127.0.0.1" or ip.startswith("0.0.0.0") or ip.startswith("::")
    except socket.gaierror:
        return False


def _is_langchain_hosted(url: str) -> bool:
    """Check if the URL is langchain hosted.

    Parameters
    ----------
    url : str
        The URL to check.

    Returns
    -------
    bool
        True if the URL is langchain hosted, False otherwise.
    """
    try:
        netloc = urllib_parse.urlsplit(url).netloc.split(":")[0]
        return netloc.endswith("langchain.com")
    except Exception:
        return False


ID_TYPE = Union[uuid.UUID, str]


def _serialize_json(obj: Any) -> str:
    """Serialize an object to JSON.

    Parameters
    ----------
    obj : Any
        The object to serialize.

    Returns
    -------
    str
        The serialized JSON string.

    Raises
    ------
    TypeError
        If the object type is not serializable.
    """
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    else:
        return str(obj)


def _get_default_retry_config() -> dict:
    return {
        "stop": stop_after_attempt(3),
        "wait": wait_exponential_jitter(initial=0.5),
        # Retry only on certain status codes ([502, 503, 504, 408, 425, 429])
        "retry": retry_if_exception_type(ls_utils.LangSmithRetryableError),
        "before_sleep": before_sleep_log(logger, logging.DEBUG),
    }


def close_client(client: httpx.Client) -> None:
    """Close the session.

    Parameters
    ----------
    client : client
        The httpx client to close.
    """
    if client.is_closed:
        return
    logger.debug("Closing Client._client")
    client.close()


def close_async_client(client: httpx.AsyncClient) -> None:
    logger.debug("Closing Client._aclient")
    if client.is_closed:
        return
    coro = client.aclose()
    try:
        # Raises RuntimeError if there is no current event loop.
        asyncio.get_running_loop()
        loop_running = True
    except RuntimeError:
        loop_running = False
    try:
        if loop_running:
            # If we try to submit this coroutine to the running loop
            # we end up in a deadlock, as we'd have gotten here from a
            # running coroutine, which we cannot interrupt to run this one.
            # The solution is to create a new loop in a new thread.
            with concurrent.futures.ThreadPoolExecutor(1) as executor:
                executor.submit(_run_coro, coro).result()
        else:
            _run_coro(coro)
    except RuntimeError as e:
        # Race condition: the loop was closed before we could submit the
        # coroutine to it.
        logger.debug("Failed to close Client._aclient: %s", e)


def _run_coro(coro: Coroutine) -> None:
    if hasattr(asyncio, "Runner"):
        # Python 3.11+
        # Run the coroutines in a new event loop, taking care to
        # - install signal handlers
        # - run pending tasks scheduled by `coros`
        # - close asyncgens and executors
        # - close the loop
        with asyncio.Runner() as runner:
            # Run the coroutine, get the result
            runner.run(coro)

            # Run pending tasks scheduled by coros until they are all done
            while pending := asyncio.all_tasks(runner.get_loop()):
                runner.run(asyncio.wait(pending))
    else:
        # Before Python 3.11 we need to run each coroutine in a new event loop
        # as the Runner api is not available.
        asyncio.run(coro)


def _validate_api_key_if_hosted(api_url: str, api_key: Optional[str]) -> None:
    """Verify API key is provided if url not localhost.

    Parameters
    ----------
    api_url : str
        The API URL.
    api_key : str or None
        The API key.

    Raises
    ------
    LangSmithUserError
        If the API key is not provided when using the hosted service.
    """
    # If the domain is langchain.com, raise error if no api_key
    if not api_key:
        if _is_langchain_hosted(api_url):
            raise ls_utils.LangSmithUserError(
                "API key must be provided when using hosted LangSmith API"
            )


def _get_api_key(api_key: Optional[str]) -> Optional[str]:
    api_key = api_key if api_key is not None else os.getenv("LANGCHAIN_API_KEY")
    if api_key is None or not api_key.strip():
        return None
    return api_key.strip().strip('"').strip("'")


def _get_api_url(api_url: Optional[str], api_key: Optional[str]) -> str:
    _api_url = (
        api_url
        if api_url is not None
        else os.getenv(
            "LANGCHAIN_ENDPOINT",
            "https://api.smith.langchain.com" if api_key else "http://localhost:1984",
        )
    )
    if not _api_url.strip():
        raise ls_utils.LangSmithUserError("LangSmith API URL cannot be empty")
    return _api_url.strip().strip('"').strip("'").rstrip("/")


def _hide_inputs(inputs: Dict[str, Any]) -> Dict[str, Any]:
    if os.environ.get("LANGCHAIN_HIDE_INPUTS") == "true":
        return {}
    return inputs


def _hide_outputs(outputs: Dict[str, Any]) -> Dict[str, Any]:
    if os.environ.get("LANGCHAIN_HIDE_OUTPUTS") == "true":
        return {}
    return outputs


@contextlib.contextmanager
def _request_error_handler(request_method: str, url: str):
    handler_state: dict = {}
    retry_statuses = [502, 503, 504, 408, 425, 429]
    try:
        yield handler_state
    except httpx.ConnectError as e:
        raise ls_utils.LangSmithConnectionError(
            f"Connection error caused failure to {request_method} {url}"
            "  in LangSmith API. Please confirm your LANGCHAIN_ENDPOINT."
            f" {repr(e)}"
        ) from e
    except httpx.HTTPError as e:
        status_code = getattr(handler_state.get("response"), "status_code", None)
        if status_code in retry_statuses:
            raise ls_utils.LangSmithRetryableError(
                f"Retryable error ({status_code}) when trying to"
                f" {request_method} {url} in"
                f" LangSmith API. {repr(e)}"
            )
        elif status_code == 500:
            raise ls_utils.LangSmithAPIError(
                f"Server error caused failure to {request_method} {url} in"
                f" LangSmith API. {repr(e)}"
            )
        else:
            raise ls_utils.LangSmithUserError(
                f"Failed to {request_method} {url} in LangSmith API. {repr(e)}"
            )

    except ValueError as e:
        args = list(e.args)
        msg = args[1] if len(args) > 1 else ""
        msg = msg.replace("session", "session (project)")
        emsg = "\n".join([args[0]] + [msg] + args[2:])
        raise ls_utils.LangSmithError(
            f"Failed to {request_method} {url} in LangSmith API. {emsg}"
        ) from e


class Client:
    """Client for interacting with the LangSmith API."""

    __slots__ = [
        "__weakref__",
        "api_url",
        "api_key",
        "timeout_ms",
        "_client",
        "_aclient",
        "_get_data_type_cached",
        "_web_url",
        "_tenant_id",
        "_retry_config",
    ]

    def __init__(
        self,
        api_url: Optional[str] = None,
        *,
        api_key: Optional[str] = None,
        timeout_ms: Optional[int] = None,
        web_url: Optional[str] = None,
        retry_config: Optional[dict] = None,
        httpx_client_config: Optional[dict] = None,
        async_httpx_client_config: Optional[dict] = None,
    ) -> None:
        """Initialize a Client instance.

        Parameters
        ----------
        api_url : str or None, default=None
            URL for the LangSmith API. Defaults to the LANGCHAIN_ENDPOINT
            environment variable or http://localhost:1984 if not set.
        api_key : str or None, default=None
            API key for the LangSmith API. Defaults to the LANGCHAIN_API_KEY
            environment variable.
        timeout_ms : int or None, default=None
            Timeout in milliseconds for the HTTPAdapter.
        web_url : str or None, default=None
            URL for the LangSmith web app. Default is auto-inferred from
            the ENDPOINT.
        retry_config : dict or None, default=None
            Configuration for the tenacity retries.
        httpx_client_config : dict or None, default=None
            Additional configuration for the httpx client.
        async_httpx_client_config : dict or None, default=None
            Additional configuration for the async httpx client.

        Raises
        ------
        LangSmithUserError
            If the API key is not provided when using the hosted service.
        """
        self.api_key = _get_api_key(api_key)
        self.api_url = _get_api_url(api_url, self.api_key)
        _validate_api_key_if_hosted(self.api_url, self.api_key)
        httpx_client_config
        self.timeout_ms = timeout_ms or 7_000
        self._web_url = web_url
        self._tenant_id: Optional[uuid.UUID] = None
        # Create a sync + async client and register a finalizer to close
        httpx_client_config = httpx_client_config or {}
        async_httpx_client_config = async_httpx_client_config or {}
        self._client = httpx.Client(**httpx_client_config)
        weakref.finalize(self, close_client, self._client)
        self._aclient = httpx.AsyncClient(**async_httpx_client_config)
        weakref.finalize(self, close_async_client, self._aclient)
        self._get_data_type_cached = functools.lru_cache(maxsize=10)(
            self._get_data_type
        )
        self._retry_config = retry_config or _get_default_retry_config()

    def _repr_html_(self) -> str:
        """Return an HTML representation of the instance with a link to the URL.

        Returns
        -------
        str
            The HTML representation of the instance.
        """
        link = self._host_url
        return f'<a href="{link}", target="_blank" rel="noopener">LangSmith Client</a>'

    def __repr__(self) -> str:
        """Return a string representation of the instance with a link to the URL.

        Returns
        -------
        str
            The string representation of the instance.
        """
        return f"Client (API URL: {self.api_url})"

    @property
    def _host_url(self) -> str:
        """The web host url."""
        if self._web_url:
            link = self._web_url
        elif _is_localhost(self.api_url):
            link = "http://localhost"
        elif "dev" in self.api_url.split(".", maxsplit=1)[0]:
            link = "https://dev.smith.langchain.com"
        else:
            link = "https://smith.langchain.com"
        return link

    @property
    def _headers(self) -> Dict[str, str]:
        """Get the headers for the API request.

        Returns
        -------
        Dict[str, str]
            The headers for the API request.
        """
        headers = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    @staticmethod
    def _filter_params(request_kwargs: dict) -> dict:
        if "params" in request_kwargs:
            params = request_kwargs["params"]
            if params is not None:
                params = {k: v for k, v in params.items() if v is not None}
            request_kwargs = {
                **request_kwargs,
                "params": params,
            }
        return request_kwargs

    def _sync_retrying(self, **kwargs: Any) -> Retrying:
        return Retrying(**self._retry_config, **kwargs)

    def _async_retrying(self, **kwargs: Any) -> AsyncRetrying:
        return AsyncRetrying(**self._retry_config, **kwargs)

    def request_with_retries(
        self,
        request_method: str,
        url: str,
        **request_kwargs: Any,
    ) -> httpx.Response:
        """Send a request with retries."""
        request_kwargs = self._filter_params(request_kwargs)
        request_kwargs["headers"] = {
            **self._headers,
            **request_kwargs.get("headers", {}),
        }
        for attempt in self._sync_retrying(reraise=True):
            with attempt:
                with _request_error_handler(request_method, url) as handler_state:
                    response = self._client.request(
                        request_method, url, **request_kwargs
                    )
                    handler_state["response"] = response
                    ls_utils.raise_for_status_with_text(response)
        return response

    async def arequest_with_retries(
        self,
        request_method: str,
        url: str,
        **request_kwargs: Any,
    ) -> httpx.Response:
        """Send an async request with retries."""
        request_kwargs = self._filter_params(request_kwargs)
        request_kwargs["headers"] = {
            **self._headers,
            **request_kwargs.get("headers", {}),
        }
        async for attempt in self._async_retrying(reraise=True):
            with attempt:
                with _request_error_handler(request_method, url) as handler_state:
                    response = await self._aclient.request(
                        request_method, url, **request_kwargs
                    )
                    handler_state["response"] = response
                    ls_utils.raise_for_status_with_text(response)
        return response

    def _get_with_retries(
        self, path: str, params: Optional[Dict[str, Any]] = None
    ) -> httpx.Response:
        """Send a GET request with retries."""
        return self.request_with_retries(
            "get",
            f"{self.api_url}{path}",
            params=params,
            timeout=self.timeout_ms / 1000,
        )

    async def _aget_with_retries(
        self, path: str, params: Optional[Dict[str, Any]] = None
    ) -> httpx.Response:
        """Send a GET request with retries."""
        return await self.arequest_with_retries(
            "get",
            f"{self.api_url}{path}",
            params=params,
            timeout=self.timeout_ms / 1000,
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

    async def _aget_paginated_list(
        self, path: str, *, params: Optional[dict] = None
    ) -> AsyncIterator[dict]:
        params_ = params.copy() if params else {}
        offset = params_.get("offset", 0)
        params_["limit"] = params_.get("limit", 100)
        while True:
            params_["offset"] = offset
            response = await self._aget_with_retries(path, params=params_)
            items = response.json()

            if not items:
                break
            for item in items:
                yield item
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
        data_type: Optional[ls_schemas.DataType] = ls_schemas.DataType.kv,
    ) -> ls_schemas.Dataset:
        """Upload a dataframe as individual examples to the LangSmith API.

        Parameters
        ----------
        df : pd.DataFrame
            The dataframe to upload.
        name : str
            The name of the dataset.
        input_keys : Sequence[str]
            The input keys.
        output_keys : Sequence[str]
            The output keys.
        description : str or None, default=None
            The description of the dataset.
        data_type : DataType or None, default=DataType.kv
            The data type of the dataset.

        Returns
        -------
        Dataset
            The uploaded dataset.

        Raises
        ------
        ValueError
            If the csv_file is not a string or tuple.
        """
        csv_file = io.BytesIO()
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
        csv_file: Union[str, Tuple[str, io.BytesIO]],
        input_keys: Sequence[str],
        output_keys: Sequence[str],
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        data_type: Optional[ls_schemas.DataType] = ls_schemas.DataType.kv,
    ) -> ls_schemas.Dataset:
        """Upload a CSV file to the LangSmith API.

        Parameters
        ----------
        csv_file : str or Tuple[str, BytesIO]
            The CSV file to upload. If a string, it should be the path
            If a tuple, it should be a tuple containing the filename
            and a BytesIO object.
        input_keys : Sequence[str]
            The input keys.
        output_keys : Sequence[str]
            The output keys.
        name : str or None, default=None
            The name of the dataset.
        description : str or None, default=None
            The description of the dataset.
        data_type : DataType or None, default=DataType.kv
            The data type of the dataset.

        Returns
        -------
        Dataset
            The uploaded dataset.

        Raises
        ------
        ValueError
            If the csv_file is not a string or tuple.
        """
        data = {
            "input_keys": input_keys,
            "output_keys": output_keys,
        }
        if name:
            data["name"] = name
        if description:
            data["description"] = description
        if data_type:
            data["data_type"] = ls_utils.get_enum_value(data_type)
        if isinstance(csv_file, str):
            with open(csv_file, "rb") as f:
                file_ = {"file": f}
                response = self.request_with_retries(
                    "POST",
                    f"{self.api_url}/datasets/upload",
                    headers=self._headers,
                    data=data,
                    files=file_,
                )
        elif isinstance(csv_file, tuple):
            response = self.request_with_retries(
                "POST",
                f"{self.api_url}/datasets/upload",
                headers=self._headers,
                data=data,
                files={"file": csv_file},
            )
        else:
            raise ValueError("csv_file must be a string or tuple")
        ls_utils.raise_for_status_with_text(response)
        result = response.json()
        # TODO: Make this more robust server-side
        if "detail" in result and "already exists" in result["detail"]:
            file_name = csv_file if isinstance(csv_file, str) else csv_file[0]
            file_name = file_name.split("/")[-1]
            raise ValueError(f"Dataset {file_name} already exists")
        return ls_schemas.Dataset(**result, _host_url=self._host_url)

    def _prepare_run_create(
        self,
        name: str,
        inputs: Dict[str, Any],
        run_type: str,
        *,
        execution_order: Optional[int] = None,
        **kwargs: Any,
    ) -> dict:
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
            "inputs": _hide_inputs(inputs),
            "run_type": run_type,
            "execution_order": execution_order if execution_order is not None else 1,
        }
        if "outputs" in run_create:
            run_create["outputs"] = _hide_outputs(run_create["outputs"])
        run_extra = cast(dict, run_create.setdefault("extra", {}))
        runtime = run_extra.setdefault("runtime", {})
        runtime_env = ls_env.get_runtime_and_metrics()
        run_extra["runtime"] = {**runtime_env, **runtime}
        headers = {**self._headers, "Accept": "application/json"}
        return {
            "content": json.dumps(run_create, default=_serialize_json),
            "headers": headers,
            "timeout": self.timeout_ms / 1000,
        }

    def create_run(
        self,
        name: str,
        inputs: Dict[str, Any],
        run_type: str,
        *,
        execution_order: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        """Persist a run to the LangSmith API.

        Parameters
        ----------
        name : str
            The name of the run.
        inputs : Dict[str, Any]
            The input values for the run.
        run_type : str
            The type of the run, such as tool, chain, llm, retriever,
            embedding, prompt, or parser.
        execution_order : int or None, default=None
            The position of the run in the full trace's execution sequence.
                All root run traces have execution_order 1.
        **kwargs : Any
            Additional keyword arguments.

        Raises
        ------
        LangSmithUserError
            If the API key is not provided when using the hosted service.
        """
        request_kwargs = self._prepare_run_create(
            name,
            inputs,
            run_type,
            execution_order=execution_order,
            **kwargs,
        )
        self.request_with_retries(
            "post",
            f"{self.api_url}/runs",
            **request_kwargs,
        )

    async def acreate_run(
        self,
        name: str,
        inputs: Dict[str, Any],
        run_type: str,
        *,
        execution_order: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        """Persist a run to the LangSmith API.

        Parameters
        ----------
        name : str
            The name of the run.
        inputs : Dict[str, Any]
            The input values for the run.
        run_type : str
            The type of the run, such as tool, chain, llm, retriever,
            embedding, prompt, or parser.
        execution_order : int or None, default=None
            The position of the run in the full trace's execution sequence.
                All root run traces have execution_order 1.
        **kwargs : Any
            Additional keyword arguments.

        Raises
        ------
        LangSmithUserError
            If the API key is not provided when using the hosted service.
        """
        request_kwargs = self._prepare_run_create(
            name,
            inputs,
            run_type,
            execution_order=execution_order,
            **kwargs,
        )
        await self.arequest_with_retries(
            "post",
            f"{self.api_url}/runs",
            **request_kwargs,
        )

    def _prepare_update_run(
        self,
        *,
        end_time: Optional[datetime.datetime] = None,
        error: Optional[str] = None,
        inputs: Optional[Dict] = None,
        outputs: Optional[Dict] = None,
        events: Optional[Sequence[dict]] = None,
        **kwargs: Any,
    ) -> dict:
        headers = {**self._headers, "Accept": "application/json"}
        data: Dict[str, Any] = {}
        if end_time is not None:
            data["end_time"] = end_time.isoformat()
        if error is not None:
            data["error"] = error
        if inputs is not None:
            data["inputs"] = _hide_inputs(inputs)
        if outputs is not None:
            data["outputs"] = _hide_outputs(outputs)
        if events is not None:
            data["events"] = events
        return {
            "content": json.dumps(data, default=_serialize_json),
            "headers": headers,
            "timeout": self.timeout_ms / 1000,
        }

    def update_run(
        self,
        run_id: ID_TYPE,
        *,
        end_time: Optional[datetime.datetime] = None,
        error: Optional[str] = None,
        inputs: Optional[Dict] = None,
        outputs: Optional[Dict] = None,
        events: Optional[Sequence[dict]] = None,
        **kwargs: Any,
    ) -> None:
        """Update a run in the LangSmith API.

        Parameters
        ----------
        run_id : str or UUID
            The ID of the run to update.
        end_time : datetime or None
            The end time of the run.
        error : str or None, default=None
            The error message of the run.
        inputs : Dict or None, default=None
            The input values for the run.
        outputs : Dict or None, default=None
            The output values for the run.
        events : Sequence[dict] or None, default=None
            The events for the run.
        **kwargs : Any
            Kwargs are ignored.
        """
        request_kwargs = self._prepare_update_run(
            end_time=end_time,
            error=error,
            inputs=inputs,
            outputs=outputs,
            events=events,
        )
        self.request_with_retries(
            "patch",
            f"{self.api_url}/runs/{run_id}",
            **request_kwargs,
        )

    async def aupdate_run(
        self,
        run_id: ID_TYPE,
        *,
        end_time: Optional[datetime.datetime] = None,
        error: Optional[str] = None,
        inputs: Optional[Dict] = None,
        outputs: Optional[Dict] = None,
        events: Optional[Sequence[dict]] = None,
        **kwargs: Any,
    ) -> None:
        """Update a run in the LangSmith API.

        Parameters
        ----------
        run_id : str or UUID
            The ID of the run to update.
        end_time : datetime or None
            The end time of the run.
        error : str or None, default=None
            The error message of the run.
        inputs : Dict or None, default=None
            The input values for the run.
        outputs : Dict or None, default=None
            The output values for the run.
        events : Sequence[dict] or None, default=None
            The events for the run.
        **kwargs : Any
            Kwargs are ignored.
        """
        request_kwargs = self._prepare_update_run(
            end_time=end_time,
            error=error,
            inputs=inputs,
            outputs=outputs,
            events=events,
        )
        await self.arequest_with_retries(
            "patch",
            f"{self.api_url}/runs/{run_id}",
            **request_kwargs,
        )

    @staticmethod
    def _postprocess_load_child_runs(
        run: ls_schemas.Run, child_runs: Iterable[ls_schemas.Run]
    ):
        treemap: DefaultDict[uuid.UUID, List[ls_schemas.Run]] = collections.defaultdict(
            list
        )
        runs: Dict[uuid.UUID, ls_schemas.Run] = {}
        for child_run in sorted(
            # TODO: Remove execution_order once it's no longer used
            child_runs,
            key=lambda r: r.dotted_order or str(r.execution_order),
        ):
            if child_run.parent_run_id is None:
                raise ls_utils.LangSmithError(f"Child run {child_run.id} has no parent")
            treemap[child_run.parent_run_id].append(child_run)
            runs[child_run.id] = child_run
        run.child_runs = treemap.pop(run.id, [])
        for run_id, children in treemap.items():
            runs[run_id].child_runs = children
        return run

    def _load_child_runs(self, run: ls_schemas.Run) -> ls_schemas.Run:
        child_runs = self.list_runs(id=run.child_run_ids)
        return self._postprocess_load_child_runs(run, child_runs)

    async def _aload_child_runs(self, run: ls_schemas.Run) -> ls_schemas.Run:
        child_runs = [run async for run in self.alist_runs(id=run.child_run_ids)]
        return self._postprocess_load_child_runs(run, child_runs)

    def read_run(
        self, run_id: ID_TYPE, load_child_runs: bool = False
    ) -> ls_schemas.Run:
        """Read a run from the LangSmith API.

        Parameters
        ----------
        run_id : str or UUID
            The ID of the run to read.
        load_child_runs : bool, default=False
            Whether to load nested child runs.

        Returns
        -------
        Run
            The run.
        """
        response = self._get_with_retries(f"/runs/{run_id}")
        run = ls_schemas.Run(**response.json(), _host_url=self._host_url)
        if load_child_runs and run.child_run_ids:
            run = self._load_child_runs(run)
        return run

    async def aread_run(
        self, run_id: ID_TYPE, load_child_runs: bool = False
    ) -> ls_schemas.Run:
        """Read a run from the LangSmith API.

        Parameters
        ----------
        run_id : str or UUID
            The ID of the run to read.
        load_child_runs : bool, default=False
            Whether to load nested child runs.

        Returns
        -------
        Run
            The run.
        """
        response = await self._aget_with_retries(f"/runs/{run_id}")
        run = ls_schemas.Run(**response.json(), _host_url=self._host_url)
        if load_child_runs and run.child_run_ids:
            run = await self._aload_child_runs(run)
        return run

    def _prepare_list_runs(
        self,
        project_id: Optional[ID_TYPE] = None,
        run_type: Optional[str] = None,
        reference_example_id: Optional[ID_TYPE] = None,
        query: Optional[str] = None,
        filter: Optional[str] = None,
        execution_order: Optional[int] = None,
        parent_run_id: Optional[ID_TYPE] = None,
        start_time: Optional[datetime.datetime] = None,
        error: Optional[bool] = None,
        run_ids: Optional[List[ID_TYPE]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        query_params: Dict[str, Any] = {
            "session": project_id,
            "run_type": run_type,
            **kwargs,
        }
        if reference_example_id is not None:
            query_params["reference_example"] = reference_example_id
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
        if error is not None:
            query_params["error"] = error
        if run_ids is not None:
            query_params["id"] = run_ids
        return query_params

    def list_runs(
        self,
        *,
        project_id: Optional[ID_TYPE] = None,
        project_name: Optional[str] = None,
        run_type: Optional[str] = None,
        reference_example_id: Optional[ID_TYPE] = None,
        query: Optional[str] = None,
        filter: Optional[str] = None,
        execution_order: Optional[int] = None,
        parent_run_id: Optional[ID_TYPE] = None,
        start_time: Optional[datetime.datetime] = None,
        error: Optional[bool] = None,
        run_ids: Optional[List[ID_TYPE]] = None,
        **kwargs: Any,
    ) -> Iterator[ls_schemas.Run]:
        """List runs from the LangSmith API.

        Parameters
        ----------
        project_id : UUID or None, default=None
            The ID of the project to filter by.
        project_name : str or None, default=None
            The name of the project to filter by.
        run_type : str or None, default=None
            The type of the runs to filter by.
        reference_example_id : UUID or None, default=None
            The ID of the reference example to filter by.
        query : str or None, default=None
            The query string to filter by.
        filter : str or None, default=None
            The filter string to filter by.
        execution_order : int or None, default=None
            The execution order to filter by. Execution order is the position
            of the run in the full trace's execution sequence.
                All root run traces have execution_order 1.
        parent_run_id : UUID or None, default=None
            The ID of the parent run to filter by.
        start_time : datetime or None, default=None
            The start time to filter by.
        error : bool or None, default=None
            Whether to filter by error status.
        run_ids : List[str or UUID] or None, default=None
            The IDs of the runs to filter by.
        **kwargs : Any
            Additional keyword arguments.

        Yields
        ------
        Run
            The runs.
        """
        if project_name is not None:
            if project_id is not None:
                raise ValueError("Only one of project_id or project_name may be given")
            project_id = self.read_project(project_name=project_name).id
        query_params = self._prepare_list_runs(
            project_id=project_id,
            project_name=project_name,
            run_type=run_type,
            reference_example_id=reference_example_id,
            query=query,
            filter=filter,
            execution_order=execution_order,
            parent_run_id=parent_run_id,
            start_time=start_time,
            error=error,
            run_ids=run_ids,
            **kwargs,
        )
        yield from (
            ls_schemas.Run(**run, _host_url=self._host_url)
            for run in self._get_paginated_list("/runs", params=query_params)
        )

    async def alist_runs(
        self,
        *,
        project_id: Optional[ID_TYPE] = None,
        project_name: Optional[str] = None,
        run_type: Optional[str] = None,
        reference_example_id: Optional[ID_TYPE] = None,
        query: Optional[str] = None,
        filter: Optional[str] = None,
        execution_order: Optional[int] = None,
        parent_run_id: Optional[ID_TYPE] = None,
        start_time: Optional[datetime.datetime] = None,
        error: Optional[bool] = None,
        run_ids: Optional[List[ID_TYPE]] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[ls_schemas.Run, None]:
        """List runs from the LangSmith API.

        Parameters
        ----------
        project_id : UUID or None, default=None
            The ID of the project to filter by.
        project_name : str or None, default=None
            The name of the project to filter by.
        run_type : str or None, default=None
            The type of the runs to filter by.
        reference_example_id : UUID or None, default=None
            The ID of the reference example to filter by.
        query : str or None, default=None
            The query string to filter by.
        filter : str or None, default=None
            The filter string to filter by.
        execution_order : int or None, default=None
            The execution order to filter by. Execution order is the position
            of the run in the full trace's execution sequence.
                All root run traces have execution_order 1.
        parent_run_id : UUID or None, default=None
            The ID of the parent run to filter by.
        start_time : datetime or None, default=None
            The start time to filter by.
        error : bool or None, default=None
            Whether to filter by error status.
        run_ids : List[str or UUID] or None, default=None
            The IDs of the runs to filter by.
        **kwargs : Any
            Additional keyword arguments.

        Yields
        ------
        Run
            The runs.
        """
        if project_name is not None:
            if project_id is not None:
                raise ValueError("Only one of project_id or project_name may be given")
            project_id = (await self.aread_project(project_name=project_name)).id
        query_params = self._prepare_list_runs(
            project_id=project_id,
            run_type=run_type,
            reference_example_id=reference_example_id,
            query=query,
            filter=filter,
            execution_order=execution_order,
            parent_run_id=parent_run_id,
            start_time=start_time,
            error=error,
            run_ids=run_ids,
            **kwargs,
        )
        runs = self._aget_paginated_list("/runs", params=query_params)
        async for run in runs:
            yield ls_schemas.Run(**run, _host_url=self._host_url)

    def get_run_url(
        self,
        *,
        run: ls_schemas.RunBase,
        project_name: Optional[str] = None,
        project_id: Optional[ID_TYPE] = None,
    ) -> str:
        """Get the URL for a run.

        Parameters
        ----------
        run : Run
            The run.
        project_name : str or None, default=None
            The name of the project.
        project_id : UUID or None, default=None
            The ID of the project.

        Returns
        -------
        str
            The URL for the run.
        """
        if hasattr(run, "session_id") and run.session_id is not None:
            session_id = run.session_id
        elif project_id is not None:
            session_id = project_id
        elif project_name is not None:
            session_id = self.read_project(project_name=project_name).id
        else:
            project_name = os.environ.get(
                "LANGCHAIN_PROJECT",
                "default",
            )
            session_id = self.read_project(project_name=project_name).id
        return (
            f"{self._host_url}/o/{self._get_tenant_id()}/projects/p/{session_id}/"
            f"r/{run.id}?poll=true"
        )

    async def aget_run_url(
        self,
        *,
        run: ls_schemas.RunBase,
        project_name: Optional[str] = None,
        project_id: Optional[ID_TYPE] = None,
    ) -> str:
        """Get the URL for a run.

        Parameters
        ----------
        run : Run
            The run.
        project_name : str or None, default=None
            The name of the project.
        project_id : UUID or None, default=None
            The ID of the project.

        Returns
        -------
        str
            The URL for the run.
        """
        if hasattr(run, "session_id") and run.session_id is not None:
            session_id = run.session_id
        elif project_id is not None:
            session_id = project_id
        elif project_name is not None:
            session_id = (await self.aread_project(project_name=project_name)).id
        else:
            project_name = os.environ.get(
                "LANGCHAIN_PROJECT",
                "default",
            )
            session_id = (await self.aread_project(project_name=project_name)).id
        return (
            f"{self._host_url}/o/{self._get_tenant_id()}/projects/p/{session_id}/"
            f"r/{run.id}?poll=true"
        )

    def share_run(self, run_id: ID_TYPE, *, share_id: Optional[ID_TYPE] = None) -> str:
        """Get a share link for a run."""
        data = {
            "run_id": str(run_id),
            "share_token": share_id or str(uuid.uuid4()),
        }
        response = self.request_with_retries(
            "put",
            f"{self.api_url}/runs/{run_id}/share",
            headers=self._headers,
            json=data,
        )
        ls_utils.raise_for_status_with_text(response)
        share_token = response.json()["share_token"]
        return f"{self._host_url}/public/{share_token}/r"

    async def ashare_run(
        self, run_id: ID_TYPE, *, share_id: Optional[ID_TYPE] = None
    ) -> str:
        """Get a share link for a run."""
        data = {
            "run_id": str(run_id),
            "share_token": share_id or str(uuid.uuid4()),
        }
        response = await self._aclient.put(
            f"{self.api_url}/runs/{run_id}/share",
            headers=self._headers,
            json=data,
        )
        ls_utils.raise_for_status_with_text(response)
        share_token = response.json()["share_token"]
        return f"{self._host_url}/public/{share_token}/r"

    async def aunshare_run(self, run_id: ID_TYPE) -> None:
        """Delete share link for a run."""
        response = await self._aclient.delete(
            f"{self.api_url}/runs/{run_id}/share",
            headers=self._headers,
        )
        ls_utils.raise_for_status_with_text(response)

    def unshare_run(self, run_id: ID_TYPE) -> None:
        """Delete share link for a run."""
        response = self._client.delete(
            f"{self.api_url}/runs/{run_id}/share",
            headers=self._headers,
        )
        ls_utils.raise_for_status_with_text(response)

    def read_run_shared_link(self, run_id: ID_TYPE) -> Optional[str]:
        response = self._get_with_retries(
            f"/runs/{run_id}/share",
        )
        ls_utils.raise_for_status_with_text(response)
        result = response.json()
        if result is None or "share_token" not in result:
            return None
        return f"{self._host_url}/public/{result['share_token']}/r"

    async def aread_run_shared_link(self, run_id: ID_TYPE) -> Optional[str]:
        response = await self._aget_with_retries(
            f"/runs/{run_id}/share",
        )
        ls_utils.raise_for_status_with_text(response)
        result = response.json()
        if result is None or "share_token" not in result:
            return None
        return f"{self._host_url}/public/{result['share_token']}/r"

    def run_is_shared(self, run_id: ID_TYPE) -> bool:
        """Get share state for a run."""
        link = self.read_run_shared_link(run_id)
        return link is not None

    def _prepare_create_project(
        self,
        project_name: str,
        *,
        project_extra: Optional[dict] = None,
        upsert: bool = False,
        reference_dataset_id: Optional[ID_TYPE] = None,
    ) -> dict:
        """Create a project on the LangSmith API.

        Parameters
        ----------
        project_name : str
            The name of the project.
        project_extra : dict or None, default=None
            Additional project information.
        upsert : bool, default=False
            Whether to update the project if it already exists.
        reference_dataset_id: UUID or None, default=None
            The ID of the reference dataset to associate with the project.

        Returns
        -------
        TracerSession
            The created project.
        """
        endpoint = f"{self.api_url}/sessions"
        body: Dict[str, Any] = {
            "name": project_name,
            "extra": project_extra,
        }
        params = {}
        if upsert:
            params["upsert"] = True
        if reference_dataset_id is not None:
            body["reference_dataset_id"] = reference_dataset_id
        return {
            "request_method": "post",
            "url": endpoint,
            "content": json.dumps(body, default=_serialize_json),
        }

    def create_project(
        self,
        project_name: str,
        *,
        project_extra: Optional[dict] = None,
        upsert: bool = False,
        reference_dataset_id: Optional[ID_TYPE] = None,
    ) -> ls_schemas.TracerSession:
        """Create a project on the LangSmith API.

        Parameters
        ----------
        project_name : str
            The name of the project.
        project_extra : dict or None, default=None
            Additional project information.
        upsert : bool, default=False
            Whether to update the project if it already exists.
        reference_dataset_id: UUID or None, default=None
            The ID of the reference dataset to associate with the project.

        Returns
        -------
        TracerSession
            The created project.
        """
        request_kwargs = self._prepare_create_project(
            project_name,
            project_extra=project_extra,
            upsert=upsert,
            reference_dataset_id=reference_dataset_id,
        )
        response = self.request_with_retries(
            **request_kwargs,
        )
        ls_utils.raise_for_status_with_text(response)
        return ls_schemas.TracerSession(**response.json(), _host_url=self._host_url)

    async def acreate_project(
        self,
        project_name: str,
        *,
        project_extra: Optional[dict] = None,
        upsert: bool = False,
        reference_dataset_id: Optional[ID_TYPE] = None,
    ) -> ls_schemas.TracerSession:
        """Create a project on the LangSmith API.

        Parameters
        ----------
        project_name : str
            The name of the project.
        project_extra : dict or None, default=None
            Additional project information.
        upsert : bool, default=False
            Whether to update the project if it already exists.
        reference_dataset_id: UUID or None, default=None
            The ID of the reference dataset to associate with the project.

        Returns
        -------
        TracerSession
            The created project.
        """
        request_kwargs = self._prepare_create_project(
            project_name,
            project_extra=project_extra,
            upsert=upsert,
            reference_dataset_id=reference_dataset_id,
        )
        response = await self.arequest_with_retries(
            **request_kwargs,
        )
        ls_utils.raise_for_status_with_text(response)
        return ls_schemas.TracerSession(**response.json(), _host_url=self._host_url)

    async def _aget_tenant_id(self) -> uuid.UUID:
        if self._tenant_id is not None:
            return self._tenant_id
        response = await self._aget_with_retries("/sessions", params={"limit": 1})
        result = response.json()
        if isinstance(result, list):
            tracer_session = ls_schemas.TracerSessionResult(
                **result[0], _host_url=self._host_url
            )
            self._tenant_id = tracer_session.tenant_id
            return self._tenant_id
        raise ls_utils.LangSmithError("No projects found")

    def _get_tenant_id(self) -> uuid.UUID:
        if self._tenant_id is not None:
            return self._tenant_id
        response = self._get_with_retries("/sessions", params={"limit": 1})
        result = response.json()
        if isinstance(result, list):
            tracer_session = ls_schemas.TracerSessionResult(
                **result[0], _host_url=self._host_url
            )
            self._tenant_id = tracer_session.tenant_id
            return self._tenant_id
        raise ls_utils.LangSmithError("No projects found")

    def _prepare_read_project(
        self, *, project_id: Optional[str] = None, project_name: Optional[str] = None
    ) -> dict:
        path = "/sessions"
        params: Dict[str, Any] = {"limit": 1}
        if project_id is not None:
            path += f"/{project_id}"
        elif project_name is not None:
            params["name"] = project_name
        else:
            raise ValueError("Must provide project_name or project_id")
        return {
            "path": path,
            "params": params,
        }

    def _postprocess_read_project(
        self, result: Union[dict, list], project_name: Optional[str]
    ):
        if isinstance(result, list):
            if len(result) == 0:
                project_name = " " + (project_name or "")
                raise ls_utils.LangSmithError(f"Project{project_name} not found")
            return ls_schemas.TracerSessionResult(**result[0], _host_url=self._host_url)
        return ls_schemas.TracerSessionResult(**result, _host_url=self._host_url)

    def read_project(
        self, *, project_id: Optional[str] = None, project_name: Optional[str] = None
    ) -> ls_schemas.TracerSessionResult:
        """Read a project from the LangSmith API.

        Parameters
        ----------
        project_id : str or None, default=None
            The ID of the project to read.
        project_name : str or None, default=None
            The name of the project to read.
                Note: Only one of project_id or project_name may be given.

        Returns
        -------
        TracerSessionResult
            The project.
        """
        get_args = self._prepare_read_project(
            project_id=project_id, project_name=project_name
        )
        response = self._get_with_retries(**get_args)
        result = response.json()
        return self._postprocess_read_project(result, project_name)

    async def aread_project(
        self, *, project_id: Optional[str] = None, project_name: Optional[str] = None
    ) -> ls_schemas.TracerSessionResult:
        """Read a project from the LangSmith API.

        Parameters
        ----------
        project_id : str or None, default=None
            The ID of the project to read.
        project_name : str or None, default=None
            The name of the project to read.
                Note: Only one of project_id or project_name may be given.

        Returns
        -------
        TracerSessionResult
            The project.
        """
        get_args = self._prepare_read_project(
            project_id=project_id, project_name=project_name
        )
        response = await self._aget_with_retries(**get_args)
        result = response.json()
        return self._postprocess_read_project(result, project_name)

    def _prepare_list_projects(
        self,
        project_ids: Optional[List[ID_TYPE]] = None,
        name: Optional[str] = None,
        name_contains: Optional[str] = None,
        reference_dataset_id: Optional[ID_TYPE] = None,
        reference_dataset_name: Optional[str] = None,
        reference_free: Optional[bool] = None,
    ) -> dict:
        params: Dict[str, Any] = {}
        if project_ids is not None:
            params["id"] = project_ids
        if name is not None:
            params["name"] = name
        if name_contains is not None:
            params["name_contains"] = name_contains
        if reference_dataset_id is not None:
            if reference_dataset_name is not None:
                raise ValueError(
                    "Only one of reference_dataset_id or"
                    " reference_dataset_name may be given"
                )
            params["reference_dataset"] = reference_dataset_id
        elif reference_dataset_name is not None:
            reference_dataset_id = self.read_dataset(
                dataset_name=reference_dataset_name
            ).id
            params["reference_dataset"] = reference_dataset_id
        if reference_free is not None:
            params["reference_free"] = reference_free
        return {"path": "/sessions", "params": params}

    def list_projects(
        self,
        project_ids: Optional[List[ID_TYPE]] = None,
        name: Optional[str] = None,
        name_contains: Optional[str] = None,
        reference_dataset_id: Optional[ID_TYPE] = None,
        reference_dataset_name: Optional[str] = None,
        reference_free: Optional[bool] = None,
    ) -> Iterator[ls_schemas.TracerSession]:
        """
        List projects from the LangSmith API.

        Parameters
        ----------
        project_ids : Optional[List[ID_TYPE]], optional
            A list of project IDs to filter by, by default None
        name : Optional[str], optional
            The name of the project to filter by, by default None
        name_contains : Optional[str], optional
            A string to search for in the project name, by default None
        reference_dataset_id : Optional[List[ID_TYPE]], optional
            A dataset ID to filter by, by default None
        reference_dataset_name : Optional[str], optional
            The name of the reference dataset to filter by, by default None
        reference_free : Optional[bool], optional
            Whether to filter for only projects not associated with a dataset.

        Yields
        ------
        TracerSession
            The projects.
        """
        get_list_kwargs = self._prepare_list_projects(
            project_ids=project_ids,
            name=name,
            name_contains=name_contains,
            reference_dataset_id=reference_dataset_id,
            reference_dataset_name=reference_dataset_name,
            reference_free=reference_free,
        )
        yield from (
            ls_schemas.TracerSession(**project, _host_url=self._host_url)
            for project in self._get_paginated_list(**get_list_kwargs)
        )

    async def alist_projects(
        self,
        *,
        project_ids: Optional[List[ID_TYPE]] = None,
        name: Optional[str] = None,
        name_contains: Optional[str] = None,
        reference_dataset_id: Optional[ID_TYPE] = None,
        reference_dataset_name: Optional[str] = None,
        reference_free: Optional[bool] = None,
    ) -> AsyncGenerator[ls_schemas.TracerSession, None]:
        """
        List projects from the LangSmith API.

        Parameters
        ----------
        project_ids : Optional[List[ID_TYPE]], optional
            A list of project IDs to filter by, by default None
        name : Optional[str], optional
            The name of the project to filter by, by default None
        name_contains : Optional[str], optional
            A string to search for in the project name, by default None
        reference_dataset_id : Optional[List[ID_TYPE]], optional
            A dataset ID to filter by, by default None
        reference_dataset_name : Optional[str], optional
            The name of the reference dataset to filter by, by default None
        reference_free : Optional[bool], optional
            Whether to filter for only projects not associated with a dataset.

        Yields
        ------
        TracerSession
            The projects.
        """
        get_list_kwargs = self._prepare_list_projects(
            project_ids=project_ids,
            name=name,
            name_contains=name_contains,
            reference_dataset_id=reference_dataset_id,
            reference_dataset_name=reference_dataset_name,
            reference_free=reference_free,
        )
        projects = self._aget_paginated_list(**get_list_kwargs)
        async for project in projects:
            yield ls_schemas.TracerSession(**project, _host_url=self._host_url)

    async def adelete_project(
        self,
        *,
        project_name: Optional[str] = None,
        project_id: Optional[ID_TYPE] = None,
    ) -> None:
        """Delete a project from LangSmith.

        Parameters
        ----------
        project_name : str or None, default=None
            The name of the project to delete.
        project_id : str or None, default=None
            The ID of the project to delete.
        """
        if project_name is not None:
            if project_id is not None:
                raise ValueError("Only one of project_id or project_name may be given")
            project_id = (await self.aread_project(project_name=project_name)).id
        elif project_id is None:
            raise ValueError("Must provide project_name or project_id")
        response = self._client.delete(
            self.api_url + f"/sessions/{project_id}",
            headers=self._headers,
        )
        ls_utils.raise_for_status_with_text(response)

    def delete_project(
        self,
        *,
        project_name: Optional[str] = None,
        project_id: Optional[ID_TYPE] = None,
    ) -> None:
        """Delete a project from LangSmith.

        Parameters
        ----------
        project_name : str or None, default=None
            The name of the project to delete.
        project_id : str or None, default=None
            The ID of the project to delete.
        """
        if project_name is not None:
            if project_id is not None:
                raise ValueError("Only one of project_id or project_name may be given")
            project_id = str(self.read_project(project_name=project_name).id)
        elif project_id is None:
            raise ValueError("Must provide project_name or project_id")
        response = self._client.delete(
            self.api_url + f"/sessions/{project_id}",
            headers=self._headers,
        )
        ls_utils.raise_for_status_with_text(response)

    def create_dataset(
        self,
        dataset_name: str,
        *,
        description: Optional[str] = None,
        data_type: ls_schemas.DataType = ls_schemas.DataType.kv,
    ) -> ls_schemas.Dataset:
        """Create a dataset in the LangSmith API.

        Parameters
        ----------
        dataset_name : str
            The name of the dataset.
        description : str or None, default=None
            The description of the dataset.
        data_type : DataType or None, default=DataType.kv
            The data type of the dataset.

        Returns
        -------
        Dataset
            The created dataset.
        """
        dataset = {
            "name": dataset_name,
            "description": description,
            "data_type": data_type,
        }
        response = self.request_with_retries(
            "POST",
            f"{self.api_url}/datasets",
            content=json.dumps(dataset, default=_serialize_json),
        )
        ls_utils.raise_for_status_with_text(response)
        return ls_schemas.Dataset(**response.json(), _host_url=self._host_url)

    async def acreate_dataset(
        self,
        dataset_name: str,
        *,
        description: Optional[str] = None,
        data_type: ls_schemas.DataType = ls_schemas.DataType.kv,
    ) -> ls_schemas.Dataset:
        """Create a dataset in the LangSmith API.

        Parameters
        ----------
        dataset_name : str
            The name of the dataset.
        description : str or None, default=None
            The description of the dataset.
        data_type : DataType or None, default=DataType.kv
            The data type of the dataset.

        Returns
        -------
        Dataset
            The created dataset.
        """
        dataset = {
            "name": dataset_name,
            "description": description,
            "data_type": data_type,
        }
        response = await self.arequest_with_retries(
            "POST",
            f"{self.api_url}/datasets",
            content=json.dumps(dataset, default=_serialize_json),
        )
        ls_utils.raise_for_status_with_text(response)
        return ls_schemas.Dataset(**response.json(), _host_url=self._host_url)

    def _prepare_read_dataset(
        self,
        *,
        dataset_id: Optional[ID_TYPE] = None,
        dataset_name: Optional[str] = None,
    ):
        path = "/datasets"
        params: Dict[str, Any] = {"limit": 1}
        if dataset_id is not None:
            path += f"/{dataset_id}"
        elif dataset_name is not None:
            params["name"] = dataset_name
        else:
            raise ValueError("Must provide dataset_name or dataset_id")
        return {
            "path": path,
            "params": params,
        }

    def read_dataset(
        self,
        *,
        dataset_name: Optional[str] = None,
        dataset_id: Optional[ID_TYPE] = None,
    ) -> ls_schemas.Dataset:
        """Read a dataset from the LangSmith API.

        Parameters
        ----------
        dataset_name : str or None, default=None
            The name of the dataset to read.
        dataset_id : UUID or None, default=None
            The ID of the dataset to read.

        Returns
        -------
        Dataset
            The dataset.
        """
        data = self._prepare_read_dataset(
            dataset_name=dataset_name,
            dataset_id=dataset_id,
        )
        response = self._get_with_retries(**data)
        result = response.json()
        if isinstance(result, list):
            if len(result) == 0:
                raise ls_utils.LangSmithError(f"Dataset {dataset_name} not found")
            return ls_schemas.Dataset(**result[0], _host_url=self._host_url)
        return ls_schemas.Dataset(**result, _host_url=self._host_url)

    async def aread_dataset(
        self,
        *,
        dataset_name: Optional[str] = None,
        dataset_id: Optional[ID_TYPE] = None,
    ) -> ls_schemas.Dataset:
        """Read a dataset from the LangSmith API.

        Parameters
        ----------
        dataset_name : str or None, default=None
            The name of the dataset to read.
        dataset_id : UUID or None, default=None
            The ID of the dataset to read.

        Returns
        -------
        Dataset
            The dataset.
        """
        data = self._prepare_read_dataset(
            dataset_name=dataset_name,
            dataset_id=dataset_id,
        )
        response = await self._aget_with_retries(**data)
        result = response.json()
        if isinstance(result, list):
            if len(result) == 0:
                raise ls_utils.LangSmithError(f"Dataset {dataset_name} not found")
            return ls_schemas.Dataset(**result[0], _host_url=self._host_url)
        return ls_schemas.Dataset(**result, _host_url=self._host_url)

    def list_datasets(
        self,
        *,
        dataset_ids: Optional[List[ID_TYPE]] = None,
        data_type: Optional[str] = None,
        dataset_name: Optional[str] = None,
        dataset_name_contains: Optional[str] = None,
    ) -> Iterator[ls_schemas.Dataset]:
        """List the datasets on the LangSmith API.

        Yields
        ------
        Dataset
            The datasets.
        """
        params: Dict[str, Any] = {}
        if dataset_ids is not None:
            params["id"] = dataset_ids
        if data_type is not None:
            params["data_type"] = data_type
        if dataset_name is not None:
            params["name"] = dataset_name
        if dataset_name_contains is not None:
            params["name_contains"] = dataset_name_contains

        yield from (
            ls_schemas.Dataset(**dataset, _host_url=self._host_url)
            for dataset in self._get_paginated_list("/datasets", params=params)
        )

    @ls_utils.xor_args(("dataset_id", "dataset_name"))
    def delete_dataset(
        self,
        *,
        dataset_id: Optional[ID_TYPE] = None,
        dataset_name: Optional[str] = None,
    ) -> None:
        """Delete a dataset from the LangSmith API.

        Parameters
        ----------
        dataset_id : UUID or None, default=None
            The ID of the dataset to delete.
        dataset_name : str or None, default=None
            The name of the dataset to delete.
        """
        if dataset_name is not None:
            dataset_id = self.read_dataset(dataset_name=dataset_name).id
        if dataset_id is None:
            raise ValueError("Must provide either dataset name or ID")
        response = self._client.delete(
            f"{self.api_url}/datasets/{dataset_id}",
            headers=self._headers,
        )
        ls_utils.raise_for_status_with_text(response)

    def _get_data_type(self, dataset_id: ID_TYPE) -> ls_schemas.DataType:
        dataset = self.read_dataset(dataset_id=dataset_id)
        return dataset.data_type

    @ls_utils.xor_args(("dataset_id", "dataset_name"))
    def create_llm_example(
        self,
        prompt: str,
        generation: Optional[str] = None,
        dataset_id: Optional[ID_TYPE] = None,
        dataset_name: Optional[str] = None,
        created_at: Optional[datetime.datetime] = None,
    ) -> ls_schemas.Example:
        """Add an example (row) to an LLM-type dataset."""
        return self.create_example(
            inputs={"input": prompt},
            outputs={"output": generation},
            dataset_id=dataset_id,
            dataset_name=dataset_name,
            created_at=created_at,
        )

    @ls_utils.xor_args(("dataset_id", "dataset_name"))
    def create_chat_example(
        self,
        messages: List[Union[Mapping[str, Any], ls_schemas.BaseMessageLike]],
        generations: Optional[
            Union[Mapping[str, Any], ls_schemas.BaseMessageLike]
        ] = None,
        dataset_id: Optional[ID_TYPE] = None,
        dataset_name: Optional[str] = None,
        created_at: Optional[datetime.datetime] = None,
    ) -> ls_schemas.Example:
        """Add an example (row) to a Chat-type dataset."""
        final_input = []
        for message in messages:
            if ls_utils.is_base_message_like(message):
                final_input.append(
                    ls_utils.convert_langchain_message(
                        cast(ls_schemas.BaseMessageLike, message)
                    )
                )
            else:
                final_input.append(cast(dict, message))
        final_generations = None
        if generations is not None:
            if ls_utils.is_base_message_like(generations):
                final_generations = ls_utils.convert_langchain_message(
                    cast(ls_schemas.BaseMessageLike, generations)
                )
            else:
                final_generations = cast(dict, generations)
        return self.create_example(
            inputs={"input": final_input},
            outputs={"output": final_generations}
            if final_generations is not None
            else None,
            dataset_id=dataset_id,
            dataset_name=dataset_name,
            created_at=created_at,
        )

    def create_example_from_run(
        self,
        run: ls_schemas.Run,
        dataset_id: Optional[ID_TYPE] = None,
        dataset_name: Optional[str] = None,
        created_at: Optional[datetime.datetime] = None,
    ) -> ls_schemas.Example:
        """Add an example (row) to an LLM-type dataset."""
        if dataset_id is None:
            dataset_id = self.read_dataset(dataset_name=dataset_name).id
            dataset_name = None  # Nested call expects only 1 defined
        dataset_type = self._get_data_type_cached(dataset_id)
        if dataset_type == ls_schemas.DataType.llm:
            if run.run_type != "llm":
                raise ValueError(
                    f"Run type {run.run_type} is not supported"
                    " for dataset of type 'LLM'"
                )
            try:
                prompt = ls_utils.get_prompt_from_inputs(run.inputs)
            except ValueError:
                raise ValueError(
                    "Error converting LLM run inputs to prompt for run"
                    f" {run.id} with inputs {run.inputs}"
                )
            inputs: Dict[str, Any] = {"input": prompt}
            if not run.outputs:
                outputs: Optional[Dict[str, Any]] = None
            else:
                try:
                    generation = ls_utils.get_llm_generation_from_outputs(run.outputs)
                except ValueError:
                    raise ValueError(
                        "Error converting LLM run outputs to generation for run"
                        f" {run.id} with outputs {run.outputs}"
                    )
                outputs = {"output": generation}
        elif dataset_type == ls_schemas.DataType.chat:
            if run.run_type != "llm":
                raise ValueError(
                    f"Run type {run.run_type} is not supported"
                    " for dataset of type 'chat'"
                )
            try:
                inputs = {"input": ls_utils.get_messages_from_inputs(run.inputs)}
            except ValueError:
                raise ValueError(
                    "Error converting LLM run inputs to chat messages for run"
                    f" {run.id} with inputs {run.inputs}"
                )
            if not run.outputs:
                outputs = None
            else:
                try:
                    outputs = {
                        "output": ls_utils.get_message_generation_from_outputs(
                            run.outputs
                        )
                    }
                except ValueError:
                    raise ValueError(
                        "Error converting LLM run outputs to chat generations"
                        f" for run {run.id} with outputs {run.outputs}"
                    )
        elif dataset_type == ls_schemas.DataType.kv:
            # Anything goes
            inputs = run.inputs
            outputs = run.outputs

        else:
            raise ValueError(f"Dataset type {dataset_type} not recognized.")
        return self.create_example(
            inputs=inputs,
            outputs=outputs,
            dataset_id=dataset_id,
            dataset_name=dataset_name,
            created_at=created_at,
        )

    def create_examples(
        self,
        *,
        inputs: Sequence[Mapping[str, Any]],
        outputs: Optional[Sequence[Optional[Mapping[str, Any]]]] = None,
        dataset_id: Optional[ID_TYPE] = None,
        dataset_name: Optional[str] = None,
        max_concurrency: int = 10,
    ) -> None:
        """Create examples in a dataset.

        Parameters
        ----------
        inputs : Sequence[Mapping[str, Any]]
            The input values for the examples.
        outputs : Optional[Sequence[Optional[Mapping[str, Any]]]], default=None
            The output values for the examples.
        dataset_id : Optional[ID_TYPE], default=None
            The ID of the dataset to create the examples in.
        dataset_name : Optional[str], default=None
            The name of the dataset to create the examples in.
        max_concurrency : int, default=10
            The maximum number of concurrent requests to make.

        Returns
        -------
        None

        Raises
        ------
        ValueError
            If both `dataset_id` and `dataset_name` are `None`.
        """
        if dataset_id is None and dataset_name is None:
            raise ValueError("Either dataset_id or dataset_name must be provided.")

        if dataset_id is None:
            dataset_id = self.read_dataset(dataset_name=dataset_name).id

        max_concurrency = min(max_concurrency, len(inputs))
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=max_concurrency
        ) as executor:
            for input_data, output_data in zip(inputs, outputs or [None] * len(inputs)):
                executor.submit(
                    self.create_example,
                    inputs=input_data,
                    outputs=output_data,
                    dataset_id=dataset_id,
                )

    def _prepare_create_example(
        self,
        inputs: Mapping[str, Any],
        dataset_id: ID_TYPE,
        created_at: Optional[datetime.datetime] = None,
        outputs: Optional[Mapping[str, Any]] = None,
        example_id: Optional[ID_TYPE] = None,
    ) -> dict:
        data = {
            "inputs": inputs,
            "outputs": outputs,
            "dataset_id": dataset_id,
        }
        if created_at:
            data["created_at"] = created_at.isoformat()
        if example_id:
            data["id"] = example_id
        return data

    def create_example(
        self,
        inputs: Mapping[str, Any],
        dataset_id: Optional[ID_TYPE] = None,
        dataset_name: Optional[str] = None,
        created_at: Optional[datetime.datetime] = None,
        outputs: Optional[Mapping[str, Any]] = None,
        example_id: Optional[ID_TYPE] = None,
    ) -> ls_schemas.Example:
        """Create a dataset example in the LangSmith API.

        Examples are rows in a dataset, containing the inputs
        and expected outputs (or other reference information)
        for a model or chain.

        Parameters
        ----------
        inputs : Mapping[str, Any]
            The input values for the example.
        dataset_id : UUID or None, default=None
            The ID of the dataset to create the example in.
        dataset_name : str or None, default=None
            The name of the dataset to create the example in.
        created_at : datetime or None, default=None
            The creation timestamp of the example.
        outputs : Mapping[str, Any] or None, default=None
            The output values for the example.
        exemple_id : UUID or None, default=None
            The ID of the example to create. If not provided, a new
            example will be created.

        Returns
        -------
        Example
            The created example.
        """
        if dataset_id is None:
            dataset_id = self.read_dataset(dataset_name=dataset_name).id

        data = self._prepare_create_example(
            inputs,
            dataset_id,
            created_at=created_at,
            outputs=outputs,
            example_id=example_id,
        )
        response = self.request_with_retries(
            "POST",
            f"{self.api_url}/examples",
            content=json.dumps(data, default=_serialize_json),
        )
        ls_utils.raise_for_status_with_text(response)
        result = response.json()
        return ls_schemas.Example(**result)

    async def acreate_example(
        self,
        inputs: Mapping[str, Any],
        dataset_id: Optional[ID_TYPE] = None,
        dataset_name: Optional[str] = None,
        created_at: Optional[datetime.datetime] = None,
        outputs: Optional[Mapping[str, Any]] = None,
        example_id: Optional[ID_TYPE] = None,
    ) -> ls_schemas.Example:
        """Create a dataset example in the LangSmith API.

        Examples are rows in a dataset, containing the inputs
        and expected outputs (or other reference information)
        for a model or chain.

        Parameters
        ----------
        inputs : Mapping[str, Any]
            The input values for the example.
        dataset_id : UUID or None, default=None
            The ID of the dataset to create the example in.
        dataset_name : str or None, default=None
            The name of the dataset to create the example in.
        created_at : datetime or None, default=None
            The creation timestamp of the example.
        outputs : Mapping[str, Any] or None, default=None
            The output values for the example.
        exemple_id : UUID or None, default=None
            The ID of the example to create. If not provided, a new
            example will be created.

        Returns
        -------
        Example
            The created example.
        """
        if dataset_id is None:
            dataset_id = (await self.aread_dataset(dataset_name=dataset_name)).id

        data = self._prepare_create_example(
            inputs,
            dataset_id,
            created_at=created_at,
            outputs=outputs,
            example_id=example_id,
        )
        response = await self.arequest_with_retries(
            "POST",
            f"{self.api_url}/examples",
            content=json.dumps(data, default=_serialize_json),
        )
        ls_utils.raise_for_status_with_text(response)
        result = response.json()
        return ls_schemas.Example(**result)

    def read_example(self, example_id: ID_TYPE) -> ls_schemas.Example:
        """Read an example from the LangSmith API.

        Parameters
        ----------
        example_id : str or UUID
            The ID of the example to read.

        Returns
        -------
        Example
            The example.
        """
        response = self._get_with_retries(f"/examples/{example_id}")
        return ls_schemas.Example(**response.json())

    async def aread_example(self, example_id: ID_TYPE) -> ls_schemas.Example:
        """Read an example from the LangSmith API.

        Parameters
        ----------
        example_id : str or UUID
            The ID of the example to read.

        Returns
        -------
        Example
            The example.
        """
        response = await self._aget_with_retries(f"/examples/{example_id}")
        return ls_schemas.Example(**response.json())

    def _prepare_list_examples(
        self,
        dataset_id: ID_TYPE,
        example_ids: Optional[List[ID_TYPE]] = None,
    ) -> dict:
        params: Dict[str, Any] = {}
        if dataset_id is not None:
            params["dataset"] = dataset_id

        else:
            pass
        if example_ids is not None:
            params["id"] = example_ids
        return params

    def list_examples(
        self,
        dataset_id: Optional[ID_TYPE] = None,
        dataset_name: Optional[str] = None,
        example_ids: Optional[List[ID_TYPE]] = None,
    ) -> Iterator[ls_schemas.Example]:
        """Retrieve the example rows of the specified dataset.

        Parameters
        ----------
        dataset_id : UUID or None, default=None
            The ID of the dataset to filter by.
        dataset_name : str or None, default=None
            The name of the dataset to filter by.
        example_ids : List[UUID] or None, default=None
            The IDs of the examples to filter by.

        Yields
        ------
        Example
            The examples.
        """
        if dataset_id is None:
            if dataset_name is None:
                raise ValueError("Must provide either dataset_id or dataset_name")
            dataset_id = self.read_dataset(dataset_name=dataset_name).id
        params = self._prepare_list_examples(
            dataset_id=dataset_id,
            example_ids=example_ids,
        )
        yield from (
            ls_schemas.Example(**example)
            for example in self._get_paginated_list("/examples", params=params)
        )

    async def alist_examples(
        self,
        dataset_id: Optional[ID_TYPE] = None,
        dataset_name: Optional[str] = None,
        example_ids: Optional[List[ID_TYPE]] = None,
    ) -> AsyncGenerator[ls_schemas.Example, None]:
        """Retrieve the example rows of the specified dataset.

        Parameters
        ----------
        dataset_id : UUID or None, default=None
            The ID of the dataset to filter by.
        dataset_name : str or None, default=None
            The name of the dataset to filter by.
        example_ids : List[UUID] or None, default=None
            The IDs of the examples to filter by.

        Yields
        ------
        Example
            The examples.
        """
        if dataset_id is None:
            if dataset_name is None:
                raise ValueError("Must provide either dataset_id or dataset_name")
            dataset_id = (await self.aread_dataset(dataset_name=dataset_name)).id
        params = self._prepare_list_examples(
            dataset_id=dataset_id,
            example_ids=example_ids,
        )
        all_examples = self._aget_paginated_list("/examples", **params)
        async for example in all_examples:
            yield ls_schemas.Example(**example)

    def update_example(
        self,
        example_id: ID_TYPE,
        *,
        inputs: Optional[Dict[str, Any]] = None,
        outputs: Optional[Mapping[str, Any]] = None,
        dataset_id: Optional[ID_TYPE] = None,
    ) -> Dict[str, Any]:
        """Update a specific example.

        Parameters
        ----------
        example_id : str or UUID
            The ID of the example to update.
        inputs : Dict[str, Any] or None, default=None
            The input values to update.
        outputs : Mapping[str, Any] or None, default=None
            The output values to update.
        dataset_id : UUID or None, default=None
            The ID of the dataset to update.

        Returns
        -------
        Dict[str, Any]
            The updated example.
        """
        example = {
            "inputs": inputs,
            "outputs": outputs,
            "dataset_id": dataset_id,
        }
        response = self.request_with_retries(
            "patch",
            f"{self.api_url}/examples/{example_id}",
            content=json.dumps(example, default=_serialize_json),
        )
        ls_utils.raise_for_status_with_text(response)
        return response.json()

    async def aupdate_example(
        self,
        example_id: ID_TYPE,
        *,
        inputs: Optional[Dict[str, Any]] = None,
        outputs: Optional[Mapping[str, Any]] = None,
        dataset_id: Optional[ID_TYPE] = None,
    ) -> Dict[str, Any]:
        """Update a specific example.

        Parameters
        ----------
        example_id : str or UUID
            The ID of the example to update.
        inputs : Dict[str, Any] or None, default=None
            The input values to update.
        outputs : Mapping[str, Any] or None, default=None
            The output values to update.
        dataset_id : UUID or None, default=None
            The ID of the dataset to update.

        Returns
        -------
        Dict[str, Any]
            The updated example.
        """
        example = {
            "inputs": inputs,
            "outputs": outputs,
            "dataset_id": dataset_id,
        }
        response = await self.arequest_with_retries(
            "patch",
            f"{self.api_url}/examples/{example_id}",
            content=json.dumps(example, default=_serialize_json),
        )
        ls_utils.raise_for_status_with_text(response)
        return response.json()

    def delete_example(self, example_id: ID_TYPE) -> None:
        """Delete an example by ID.

        Parameters
        ----------
        example_id : str or UUID
            The ID of the example to delete.
        """
        response = self._client.delete(
            f"{self.api_url}/examples/{example_id}",
            headers=self._headers,
        )
        ls_utils.raise_for_status_with_text(response)

    async def adelete_example(self, example_id: ID_TYPE) -> None:
        """Delete an example by ID.

        Parameters
        ----------
        example_id : str or UUID
            The ID of the example to delete.
        """
        response = await self._aclient.delete(
            f"{self.api_url}/examples/{example_id}",
            headers=self._headers,
        )
        ls_utils.raise_for_status_with_text(response)

    def _resolve_run_id(
        self,
        run: Union[ls_schemas.Run, ls_schemas.RunBase, str, uuid.UUID],
        load_child_runs: bool,
    ) -> ls_schemas.Run:
        """Resolve the run ID.

        Parameters
        ----------
        run : Run or RunBase or str or UUID
            The run to resolve.
        load_child_runs : bool
            Whether to load child runs.

        Returns
        -------
        Run
            The resolved run.

        Raises
        ------
        TypeError
            If the run type is invalid.
        """
        if isinstance(run, (str, uuid.UUID)):
            run_ = self.read_run(run, load_child_runs=load_child_runs)
        else:
            run_ = run
        return run_

    def _resolve_example_id(
        self,
        example: Union[ls_schemas.Example, str, uuid.UUID, dict, None],
        run: ls_schemas.Run,
    ) -> Optional[ls_schemas.Example]:
        """Resolve the example ID.

        Parameters
        ----------
        example : Example or str or UUID or dict or None
            The example to resolve.
        run : Run
            The run associated with the example.

        Returns
        -------
        Example or None
            The resolved example.
        """
        if isinstance(example, (str, uuid.UUID)):
            reference_example_ = self.read_example(example)
        elif isinstance(example, ls_schemas.Example):
            reference_example_ = example
        elif isinstance(example, dict):
            reference_example_ = ls_schemas.Example(**example)
        elif run.reference_example_id is not None:
            reference_example_ = self.read_example(run.reference_example_id)
        else:
            reference_example_ = None
        return reference_example_

    def evaluate_run(
        self,
        run: Union[ls_schemas.Run, ls_schemas.RunBase, str, uuid.UUID],
        evaluator: ls_evaluator.RunEvaluator,
        *,
        source_info: Optional[Dict[str, Any]] = None,
        reference_example: Optional[
            Union[ls_schemas.Example, str, dict, uuid.UUID]
        ] = None,
        load_child_runs: bool = False,
    ) -> ls_evaluator.EvaluationResult:
        """Evaluate a run.

        Parameters
        ----------
        run : Run or RunBase or str or UUID
            The run to evaluate.
        evaluator : RunEvaluator
            The evaluator to use.
        source_info : Dict[str, Any] or None, default=None
            Additional information about the source of the evaluation to log
            as feedback metadata.
        reference_example : Example or str or dict or UUID or None, default=None
            The example to use as a reference for the evaluation.
            If not provided, the run's reference example will be used.
        load_child_runs : bool, default=False
            Whether to load child runs when resolving the run ID.

        Returns
        -------
        Feedback
            The feedback object created by the evaluation.
        """
        run_ = self._resolve_run_id(run, load_child_runs=load_child_runs)
        reference_example_ = self._resolve_example_id(reference_example, run_)
        evaluation_result = evaluator.evaluate_run(
            run_,
            example=reference_example_,
        )
        source_info = source_info or {}
        if evaluation_result.evaluator_info:
            source_info = {**evaluation_result.evaluator_info, **source_info}
        self.create_feedback(
            run_.id,
            evaluation_result.key,
            score=evaluation_result.score,
            value=evaluation_result.value,
            comment=evaluation_result.comment,
            correction=evaluation_result.correction,
            source_info=source_info,
            source_run_id=evaluation_result.source_run_id,
            feedback_source_type=ls_schemas.FeedbackSourceType.MODEL,
        )
        return evaluation_result

    async def aevaluate_run(
        self,
        run: Union[ls_schemas.Run, str, uuid.UUID],
        evaluator: ls_evaluator.RunEvaluator,
        *,
        source_info: Optional[Dict[str, Any]] = None,
        reference_example: Optional[
            Union[ls_schemas.Example, str, dict, uuid.UUID]
        ] = None,
        load_child_runs: bool = False,
    ) -> ls_evaluator.EvaluationResult:
        """Evaluate a run asynchronously.

        Parameters
        ----------
        run : Run or str or UUID
            The run to evaluate.
        evaluator : RunEvaluator
            The evaluator to use.
        source_info : Dict[str, Any] or None, default=None
            Additional information about the source of the evaluation to log
            as feedback metadata.
        reference_example : Optional Example or UUID, default=None
            The example to use as a reference for the evaluation.
            If not provided, the run's reference example will be used.
        load_child_runs : bool, default=False
            Whether to load child runs when resolving the run ID.

        Returns
        -------
        EvaluationResult
            The evaluation result object created by the evaluation.
        """
        run_ = self._resolve_run_id(run, load_child_runs=load_child_runs)
        reference_example_ = self._resolve_example_id(reference_example, run_)
        evaluation_result = await evaluator.aevaluate_run(
            run_,
            example=reference_example_,
        )
        source_info = source_info or {}
        if evaluation_result.evaluator_info:
            source_info = {**evaluation_result.evaluator_info, **source_info}
        await self.acreate_feedback(
            run_.id,
            evaluation_result.key,
            score=evaluation_result.score,
            value=evaluation_result.value,
            comment=evaluation_result.comment,
            correction=evaluation_result.correction,
            source_info=source_info,
            source_run_id=evaluation_result.source_run_id,
            feedback_source_type=ls_schemas.FeedbackSourceType.MODEL,
        )
        return evaluation_result

    def _prepare_create_feedback(
        self,
        run_id: ID_TYPE,
        key: str,
        *,
        score: Union[float, int, bool, None] = None,
        value: Union[float, int, bool, str, dict, None] = None,
        correction: Union[dict, None] = None,
        comment: Union[str, None] = None,
        source_info: Optional[Dict[str, Any]] = None,
        feedback_source_type: Union[
            ls_schemas.FeedbackSourceType, str
        ] = ls_schemas.FeedbackSourceType.API,
        source_run_id: Optional[ID_TYPE] = None,
        feedback_id: Optional[ID_TYPE] = None,
    ) -> dict:
        if not isinstance(feedback_source_type, ls_schemas.FeedbackSourceType):
            feedback_source_type = ls_schemas.FeedbackSourceType(feedback_source_type)
        if feedback_source_type == ls_schemas.FeedbackSourceType.API:
            feedback_source: ls_schemas.FeedbackSourceBase = (
                ls_schemas.APIFeedbackSource(metadata=source_info)
            )
        elif feedback_source_type == ls_schemas.FeedbackSourceType.MODEL:
            feedback_source = ls_schemas.ModelFeedbackSource(metadata=source_info)
        else:
            raise ValueError(f"Unknown feedback source type {feedback_source_type}")
        feedback_source.metadata = (
            feedback_source.metadata if feedback_source.metadata is not None else {}
        )
        if source_run_id is not None and "__run" not in feedback_source.metadata:
            feedback_source.metadata["__run"] = {"run_id": str(source_run_id)}
        feedback = ls_schemas.FeedbackCreate(
            id=feedback_id or uuid.uuid4(),
            run_id=run_id,
            key=key,
            score=score,
            value=value,
            correction=correction,
            comment=comment,
            feedback_source=feedback_source,
            created_at=datetime.datetime.now(datetime.timezone.utc),
            modified_at=datetime.datetime.now(datetime.timezone.utc),
        )
        return {
            "post_args": {
                "headers": {**self._headers, "Content-Type": "application/json"},
                "content": feedback.json(exclude_none=True),
            },
            "feedback": feedback,
        }

    def create_feedback(
        self,
        run_id: ID_TYPE,
        key: str,
        *,
        score: Union[float, int, bool, None] = None,
        value: Union[float, int, bool, str, dict, None] = None,
        correction: Union[dict, None] = None,
        comment: Union[str, None] = None,
        source_info: Optional[Dict[str, Any]] = None,
        feedback_source_type: Union[
            ls_schemas.FeedbackSourceType, str
        ] = ls_schemas.FeedbackSourceType.API,
        source_run_id: Optional[ID_TYPE] = None,
        feedback_id: Optional[ID_TYPE] = None,
    ) -> ls_schemas.Feedback:
        """Create a feedback in the LangSmith API.

        Parameters
        ----------
        run_id : str or UUID
            The ID of the run to provide feedback on.
        key : str
            The name of the metric, tag, or 'aspect' this feedback is about.
        score : float or int or bool or None, default=None
            The score to rate this run on the metric or aspect.
        value : float or int or bool or str or dict or None, default=None
            The display value or non-numeric value for this feedback.
        correction : dict or None, default=None
            The proper ground truth for this run.
        comment : str or None, default=None
            A comment about this feedback.
        source_info : Dict[str, Any] or None, default=None
            Information about the source of this feedback.
        feedback_source_type : FeedbackSourceType or str, default=FeedbackSourceType.API
            The type of feedback source, such as model (for model-generated feedback)
                or API.
        source_run_id : str or UUID or None, default=None,
            The ID of the run that generated this feedback, if a "model" type.
        feedback_id : str or UUID or None, default=None
            The ID of the feedback to create. If not provided, a random UUID will be
            generated.
        """
        feedback_args = self._prepare_create_feedback(
            run_id,
            key,
            score=score,
            value=value,
            correction=correction,
            comment=comment,
            source_info=source_info,
            feedback_source_type=feedback_source_type,
            source_run_id=source_run_id,
            feedback_id=feedback_id,
        )
        response = self.request_with_retries(
            "POST",
            f"{self.api_url}/feedback",
            **feedback_args["post_args"],
        )
        ls_utils.raise_for_status_with_text(response)
        return ls_schemas.Feedback(**feedback_args["feedback"].dict())

    async def acreate_feedback(
        self,
        run_id: ID_TYPE,
        key: str,
        *,
        score: Union[float, int, bool, None] = None,
        value: Union[float, int, bool, str, dict, None] = None,
        correction: Union[dict, None] = None,
        comment: Union[str, None] = None,
        source_info: Optional[Dict[str, Any]] = None,
        feedback_source_type: Union[
            ls_schemas.FeedbackSourceType, str
        ] = ls_schemas.FeedbackSourceType.API,
        source_run_id: Optional[ID_TYPE] = None,
        feedback_id: Optional[ID_TYPE] = None,
    ) -> ls_schemas.Feedback:
        """Create a feedback in the LangSmith API.

        Parameters
        ----------
        run_id : str or UUID
            The ID of the run to provide feedback on.
        key : str
            The name of the metric, tag, or 'aspect' this feedback is about.
        score : float or int or bool or None, default=None
            The score to rate this run on the metric or aspect.
        value : float or int or bool or str or dict or None, default=None
            The display value or non-numeric value for this feedback.
        correction : dict or None, default=None
            The proper ground truth for this run.
        comment : str or None, default=None
            A comment about this feedback.
        source_info : Dict[str, Any] or None, default=None
            Information about the source of this feedback.
        feedback_source_type : FeedbackSourceType or str, default=FeedbackSourceType.API
            The type of feedback source, such as model (for model-generated feedback)
                or API.
        source_run_id : str or UUID or None, default=None,
            The ID of the run that generated this feedback, if a "model" type.
        feedback_id : str or UUID or None, default=None
            The ID of the feedback to create. If not provided, a random UUID will be
            generated.
        """
        feedback_args = self._prepare_create_feedback(
            run_id,
            key,
            score=score,
            value=value,
            correction=correction,
            comment=comment,
            source_info=source_info,
            feedback_source_type=feedback_source_type,
            source_run_id=source_run_id,
            feedback_id=feedback_id,
        )
        response = await self.arequest_with_retries(
            "POST",
            f"{self.api_url}/feedback",
            **feedback_args["post_args"],
        )
        ls_utils.raise_for_status_with_text(response)
        return ls_schemas.Feedback(**feedback_args["feedback"].dict())

    def _prepare_update_feedback(
        self,
        feedback_id: ID_TYPE,
        *,
        score: Union[float, int, bool, None] = None,
        value: Union[float, int, bool, str, dict, None] = None,
        correction: Union[dict, None] = None,
        comment: Union[str, None] = None,
    ) -> dict:
        feedback_update: Dict[str, Any] = {}
        if score is not None:
            feedback_update["score"] = score
        if value is not None:
            feedback_update["value"] = value
        if correction is not None:
            feedback_update["correction"] = correction
        if comment is not None:
            feedback_update["comment"] = comment
        return {
            "url": self.api_url + f"/feedback/{feedback_id}",
            "headers": {**self._headers, "Content-Type": "application/json"},
            "content": json.dumps(feedback_update, default=_serialize_json),
        }

    def update_feedback(
        self,
        feedback_id: ID_TYPE,
        *,
        score: Union[float, int, bool, None] = None,
        value: Union[float, int, bool, str, dict, None] = None,
        correction: Union[dict, None] = None,
        comment: Union[str, None] = None,
    ) -> None:
        """Update a feedback in the LangSmith API.

        Parameters
        ----------
        feedback_id : str or UUID
            The ID of the feedback to update.
        score : float or int or bool or None, default=None
            The score to update the feedback with.
        value : float or int or bool or str or dict or None, default=None
            The value to update the feedback with.
        correction : dict or None, default=None
            The correction to update the feedback with.
        comment : str or None, default=None
            The comment to update the feedback with.
        """
        feedback_update = self._prepare_update_feedback(
            feedback_id,
            score=score,
            value=value,
            correction=correction,
            comment=comment,
        )
        response = self._client.patch(**feedback_update)
        ls_utils.raise_for_status_with_text(response)

    async def aupdate_feedback(
        self,
        feedback_id: ID_TYPE,
        *,
        score: Union[float, int, bool, None] = None,
        value: Union[float, int, bool, str, dict, None] = None,
        correction: Union[dict, None] = None,
        comment: Union[str, None] = None,
    ) -> None:
        """Update a feedback in the LangSmith API.

        Parameters
        ----------
        feedback_id : str or UUID
            The ID of the feedback to update.
        score : float or int or bool or None, default=None
            The score to update the feedback with.
        value : float or int or bool or str or dict or None, default=None
            The value to update the feedback with.
        correction : dict or None, default=None
            The correction to update the feedback with.
        comment : str or None, default=None
            The comment to update the feedback with.
        """
        feedback_update = self._prepare_update_feedback(
            feedback_id,
            score=score,
            value=value,
            correction=correction,
            comment=comment,
        )
        response = await self._aclient.patch(**feedback_update)
        ls_utils.raise_for_status_with_text(response)

    def read_feedback(self, feedback_id: ID_TYPE) -> ls_schemas.Feedback:
        """Read a feedback from the LangSmith API.

        Parameters
        ----------
        feedback_id : str or UUID
            The ID of the feedback to read.

        Returns
        -------
        Feedback
            The feedback.
        """
        response = self._get_with_retries(f"/feedback/{feedback_id}")
        return ls_schemas.Feedback(**response.json())

    async def aread_feedback(self, feedback_id: ID_TYPE) -> ls_schemas.Feedback:
        """Read a feedback from the LangSmith API.

        Parameters
        ----------
        feedback_id : str or UUID
            The ID of the feedback to read.

        Returns
        -------
        Feedback
            The feedback.
        """
        response = await self._aget_with_retries(f"/feedback/{feedback_id}")
        return ls_schemas.Feedback(**response.json())

    def _prepare_list_feedback(
        self,
        *,
        run_ids: Optional[Sequence[ID_TYPE]] = None,
        feedback_key: Optional[Sequence[str]] = None,
        feedback_source_type: Optional[Sequence[ls_schemas.FeedbackSourceType]] = None,
        **kwargs: Any,
    ) -> dict:
        params: dict = {
            "run": run_ids,
            **kwargs,
        }
        if feedback_key is not None:
            params["key"] = feedback_key
        if feedback_source_type is not None:
            params["source"] = feedback_source_type
        return {
            "path": "/feedback",
            "params": params,
        }

    def list_feedback(
        self,
        *,
        run_ids: Optional[Sequence[ID_TYPE]] = None,
        feedback_key: Optional[Sequence[str]] = None,
        feedback_source_type: Optional[Sequence[ls_schemas.FeedbackSourceType]] = None,
        **kwargs: Any,
    ) -> Iterator[ls_schemas.Feedback]:
        """List the feedback objects on the LangSmith API.

        Parameters
        ----------
        run_ids : List[str or UUID] or None, default=None
            The IDs of the runs to filter by.
        feedback_key: List[str] or None, default=None
            The feedback key(s) to filter by. Example: 'correctness'
            The query performs a union of all feedback keys.
        feedback_source_type: List[FeedbackSourceType] or None, default=None
            The type of feedback source, such as model
            (for model-generated feedback) or API.
        **kwargs : Any
            Additional keyword arguments.

        Yields
        ------
        Feedback
            The feedback objects.
        """
        feedback_args = self._prepare_list_feedback(
            run_ids=run_ids,
            feedback_key=feedback_key,
            feedback_source_type=feedback_source_type,
            **kwargs,
        )
        yield from (
            ls_schemas.Feedback(**feedback)
            for feedback in self._get_paginated_list(**feedback_args)
        )

    async def alist_feedback(
        self,
        *,
        run_ids: Optional[Sequence[ID_TYPE]] = None,
        feedback_key: Optional[Sequence[str]] = None,
        feedback_source_type: Optional[Sequence[ls_schemas.FeedbackSourceType]] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[ls_schemas.Feedback, None]:
        """List the feedback objects on the LangSmith API.

        Parameters
        ----------
        run_ids : List[str or UUID] or None, default=None
            The IDs of the runs to filter by.
        feedback_key: List[str] or None, default=None
            The feedback key(s) to filter by. Example: 'correctness'
            The query performs a union of all feedback keys.
        feedback_source_type: List[FeedbackSourceType] or None, default=None
            The type of feedback source, such as model
            (for model-generated feedback) or API.
        **kwargs : Any
            Additional keyword arguments.

        Yields
        ------
        Feedback
            The feedback objects.
        """
        feedback_args = self._prepare_list_feedback(
            run_ids=run_ids,
            feedback_key=feedback_key,
            feedback_source_type=feedback_source_type,
            **kwargs,
        )
        all_feedback = self._aget_paginated_list(**feedback_args)
        async for feedback in all_feedback:
            yield ls_schemas.Feedback(**feedback)

    def delete_feedback(self, feedback_id: ID_TYPE) -> None:
        """Delete a feedback by ID.

        Parameters
        ----------
        feedback_id : str or UUID
            The ID of the feedback to delete.
        """
        response = self._client.delete(
            f"{self.api_url}/feedback/{feedback_id}",
            headers=self._headers,
        )
        ls_utils.raise_for_status_with_text(response)

    async def adelete_feedback(self, feedback_id: ID_TYPE) -> None:
        """Delete a feedback by ID.

        Parameters
        ----------
        feedback_id : str or UUID
            The ID of the feedback to delete.
        """
        response = await self._aclient.delete(
            f"{self.api_url}/feedback/{feedback_id}",
            headers=self._headers,
        )
        ls_utils.raise_for_status_with_text(response)

    async def arun_on_dataset(
        self,
        dataset_name: str,
        llm_or_chain_factory: Any,
        *,
        evaluation: Optional[Any] = None,
        concurrency_level: int = 5,
        project_name: Optional[str] = None,
        verbose: bool = False,
        tags: Optional[List[str]] = None,
        input_mapper: Optional[Callable[[Dict], Any]] = None,
    ) -> Dict[str, Any]:
        """
        Asynchronously run the Chain or language model on a dataset
        and store traces to the specified project name.

        Args:
            dataset_name: Name of the dataset to run the chain on.
            llm_or_chain_factory: Language model or Chain constructor to run
                over the dataset. The Chain constructor is used to permit
                independent calls on each example without carrying over state.
            evaluation: Optional evaluation configuration to use when evaluating
            concurrency_level: The number of async tasks to run concurrently.
            project_name: Name of the project to store the traces in.
                Defaults to {dataset_name}-{chain class name}-{datetime}.
            verbose: Whether to print progress.
            tags: Tags to add to each run in the project.
            input_mapper: A function to map to the inputs dictionary from an Example
                to the format expected by the model to be evaluated. This is useful if
                your model needs to deserialize more complex schema or if your dataset
                has inputs with keys that differ from what is expected by your chain
                or agent.

        Returns:
            A dictionary containing the run's project name and the
            resulting model outputs.

        For the synchronous version, see client.run_on_dataset.

        Examples
        --------

        .. code-block:: python

            from langsmith import Client
            from langchain.chat_models import ChatOpenAI
            from langchain.chains import LLMChain
            from langchain.smith import RunEvalConfig

            # Chains may have memory. Passing in a constructor function lets the
            # evaluation framework avoid cross-contamination between runs.
            def construct_chain():
                llm = ChatOpenAI(temperature=0)
                chain = LLMChain.from_string(
                    llm,
                    "What's the answer to {your_input_key}"
                )
                return chain

            # Load off-the-shelf evaluators via config or the EvaluatorType (string or enum)
            evaluation_config = RunEvalConfig(
                evaluators=[
                    "qa",  # "Correctness" against a reference answer
                    "embedding_distance",
                    RunEvalConfig.Criteria("helpfulness"),
                    RunEvalConfig.Criteria({
                        "fifth-grader-score": "Do you have to be smarter than a fifth grader to answer this question?"
                    }),
                ]
            )

            client = Client()
            await client.arun_on_dataset(
                "<my_dataset_name>",
                construct_chain,
                evaluation=evaluation_config,
            )

        You can also create custom evaluators by subclassing the
        :class:`StringEvaluator <langchain.evaluation.schema.StringEvaluator>`
        or LangSmith's `RunEvaluator` classes.

        .. code-block:: python

            from typing import Optional
            from langchain.evaluation import StringEvaluator

            class MyStringEvaluator(StringEvaluator):

                @property
                def requires_input(self) -> bool:
                    return False

                @property
                def requires_reference(self) -> bool:
                    return True

                @property
                def evaluation_name(self) -> str:
                    return "exact_match"

                def _evaluate_strings(self, prediction, reference=None, input=None, **kwargs) -> dict:
                    return {"score": prediction == reference}


            evaluation_config = RunEvalConfig(
                custom_evaluators = [MyStringEvaluator()],
            )

            await client.arun_on_dataset(
                "<my_dataset_name>",
                construct_chain,
                evaluation=evaluation_config,
            )
        """  # noqa: E501
        try:
            from langchain.smith import (
                arun_on_dataset as _arun_on_dataset,  # type: ignore[import]
            )
        except ImportError:
            raise ImportError(
                "The client.arun_on_dataset function requires the langchain"
                "package to run.\nInstall with pip install langchain"
            )
        return await _arun_on_dataset(
            dataset_name=dataset_name,
            llm_or_chain_factory=llm_or_chain_factory,
            client=self,
            evaluation=evaluation,
            concurrency_level=concurrency_level,
            project_name=project_name,
            verbose=verbose,
            tags=tags,
            input_mapper=input_mapper,
        )

    def run_on_dataset(
        self,
        dataset_name: str,
        llm_or_chain_factory: Any,
        *,
        evaluation: Optional[Any] = None,
        concurrency_level: int = 5,
        project_name: Optional[str] = None,
        verbose: bool = False,
        tags: Optional[List[str]] = None,
        input_mapper: Optional[Callable[[Dict], Any]] = None,
    ) -> Dict[str, Any]:
        """
        Run the Chain or language model on a dataset and store traces
        to the specified project name.

        Args:
            dataset_name: Name of the dataset to run the chain on.
            llm_or_chain_factory: Language model or Chain constructor to run
                over the dataset. The Chain constructor is used to permit
                independent calls on each example without carrying over state.
            evaluation: Configuration for evaluators to run on the
                results of the chain
            concurrency_level: The number of tasks to execute concurrently.
            project_name: Name of the project to store the traces in.
                Defaults to {dataset_name}-{chain class name}-{datetime}.
            verbose: Whether to print progress.
            tags: Tags to add to each run in the project.
            input_mapper: A function to map to the inputs dictionary from an Example
                to the format expected by the model to be evaluated. This is useful if
                your model needs to deserialize more complex schema or if your dataset
                has inputs with keys that differ from what is expected by your chain
                or agent.

        Returns:
            A dictionary containing the run's project name and the resulting model outputs.


        For the (usually faster) async version of this function, see `client.arun_on_dataset`.

        Examples
        --------

        .. code-block:: python

            from langsmith import Client
            from langchain.chat_models import ChatOpenAI
            from langchain.chains import LLMChain
            from langchain.smith import RunEvalConfig

            # Chains may have memory. Passing in a constructor function lets the
            # evaluation framework avoid cross-contamination between runs.
            def construct_chain():
                llm = ChatOpenAI(temperature=0)
                chain = LLMChain.from_string(
                    llm,
                    "What's the answer to {your_input_key}"
                )
                return chain

            # Load off-the-shelf evaluators via config or the EvaluatorType (string or enum)
            evaluation_config = RunEvalConfig(
                evaluators=[
                    "qa",  # "Correctness" against a reference answer
                    "embedding_distance",
                    RunEvalConfig.Criteria("helpfulness"),
                    RunEvalConfig.Criteria({
                        "fifth-grader-score": "Do you have to be smarter than a fifth grader to answer this question?"
                    }),
                ]
            )

            client = Client()
            client.run_on_dataset(
                "<my_dataset_name>",
                construct_chain,
                evaluation=evaluation_config,
            )

        You can also create custom evaluators by subclassing the
        :class:`StringEvaluator <langchain.evaluation.schema.StringEvaluator>`
        or LangSmith's `RunEvaluator` classes.

        .. code-block:: python

            from typing import Optional
            from langchain.evaluation import StringEvaluator

            class MyStringEvaluator(StringEvaluator):

                @property
                def requires_input(self) -> bool:
                    return False

                @property
                def requires_reference(self) -> bool:
                    return True

                @property
                def evaluation_name(self) -> str:
                    return "exact_match"

                def _evaluate_strings(self, prediction, reference=None, input=None, **kwargs) -> dict:
                    return {"score": prediction == reference}


            evaluation_config = RunEvalConfig(
                custom_evaluators = [MyStringEvaluator()],
            )

            client.run_on_dataset(
                "<my_dataset_name>",
                construct_chain,
                evaluation=evaluation_config,
            )
        """  # noqa: E501
        try:
            from langchain.smith import (
                run_on_dataset as _run_on_dataset,  # type: ignore[import]
            )
        except ImportError:
            raise ImportError(
                "The client.run_on_dataset function requires the langchain"
                "package to run.\nInstall with pip install langchain"
            )
        return _run_on_dataset(
            dataset_name=dataset_name,
            llm_or_chain_factory=llm_or_chain_factory,
            concurrency_level=concurrency_level,
            client=self,
            evaluation=evaluation,
            project_name=project_name,
            verbose=verbose,
            tags=tags,
            input_mapper=input_mapper,
        )
