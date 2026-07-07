# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Mapping
from typing_extensions import Self, override

import httpx

from . import _exceptions
from ._qs import Querystring
from ._types import (
    Omit,
    Headers,
    Timeout,
    NotGiven,
    Transport,
    ProxiesTypes,
    RequestOptions,
    not_given,
)
from ._utils import (
    is_given,
    is_mapping_t,
    get_async_library,
)
from ._compat import cached_property
from ._version import __version__
from ._streaming import Stream as Stream, AsyncStream as AsyncStream
from ._exceptions import APIStatusError
from ._base_client import (
    DEFAULT_MAX_RETRIES,
    SyncAPIClient,
    AsyncAPIClient,
)

if TYPE_CHECKING:
    from .resources import info, runs, issues, traces, threads, datasets, sandboxes, online_evaluators
    from .resources.info import InfoResource, AsyncInfoResource
    from .resources.runs import RunsResource, AsyncRunsResource
    from .resources.issues import IssuesResource, AsyncIssuesResource
    from .resources.traces import TracesResource, AsyncTracesResource
    from .resources.threads import ThreadsResource, AsyncThreadsResource
    from .resources.datasets.datasets import DatasetsResource, AsyncDatasetsResource
    from .resources.online_evaluators import OnlineEvaluatorsResource, AsyncOnlineEvaluatorsResource
    from .resources.sandboxes.sandboxes import SandboxesResource, AsyncSandboxesResource

__all__ = [
    "Timeout",
    "Transport",
    "ProxiesTypes",
    "RequestOptions",
    "Langsmith",
    "AsyncLangsmith",
    "Client",
    "AsyncClient",
]


class Langsmith(SyncAPIClient):
    # client options
    api_key: str | None
    tenant_id: str | None

    def __init__(
        self,
        *,
        api_key: str | None = None,
        tenant_id: str | None = None,
        base_url: str | httpx.URL | None = None,
        timeout: float | Timeout | None | NotGiven = not_given,
        max_retries: int = DEFAULT_MAX_RETRIES,
        default_headers: Mapping[str, str] | None = None,
        default_query: Mapping[str, object] | None = None,
        # Configure a custom httpx client.
        # We provide a `DefaultHttpxClient` class that you can pass to retain the default values we use for `limits`, `timeout` & `follow_redirects`.
        # See the [httpx documentation](https://www.python-httpx.org/api/#client) for more details.
        http_client: httpx.Client | None = None,
        # Enable or disable schema validation for data returned by the API.
        # When enabled an error APIResponseValidationError is raised
        # if the API responds with invalid data for the expected schema.
        #
        # This parameter may be removed or changed in the future.
        # If you rely on this feature, please open a GitHub issue
        # outlining your use-case to help us decide if it should be
        # part of our public interface in the future.
        _strict_response_validation: bool = False,
    ) -> None:
        """Construct a new synchronous Langsmith client instance.

        This automatically infers the following arguments from their corresponding environment variables if they are not provided:
        - `api_key` from `LANGSMITH_API_KEY`
        - `tenant_id` from `LANGSMITH_TENANT_ID`
        """
        if api_key is None:
            api_key = os.environ.get("LANGSMITH_API_KEY")
        self.api_key = api_key

        if tenant_id is None:
            tenant_id = os.environ.get("LANGSMITH_TENANT_ID")
        self.tenant_id = tenant_id

        if base_url is None:
            base_url = os.environ.get("LANGCHAIN_BASE_URL")
        if base_url is None:
            base_url = f"https://api.smith.langchain.com/"

        custom_headers_env = os.environ.get("LANGCHAIN_CUSTOM_HEADERS")
        if custom_headers_env is not None:
            parsed: dict[str, str] = {}
            for line in custom_headers_env.split("\n"):
                colon = line.find(":")
                if colon >= 0:
                    parsed[line[:colon].strip()] = line[colon + 1 :].strip()
            default_headers = {**parsed, **(default_headers if is_mapping_t(default_headers) else {})}

        super().__init__(
            version=__version__,
            base_url=base_url,
            max_retries=max_retries,
            timeout=timeout,
            http_client=http_client,
            custom_headers=default_headers,
            custom_query=default_query,
            _strict_response_validation=_strict_response_validation,
        )

    @cached_property
    def datasets(self) -> DatasetsResource:
        from .resources.datasets import DatasetsResource

        return DatasetsResource(self)

    @cached_property
    def runs(self) -> RunsResource:
        from .resources.runs import RunsResource

        return RunsResource(self)

    @cached_property
    def threads(self) -> ThreadsResource:
        from .resources.threads import ThreadsResource

        return ThreadsResource(self)

    @cached_property
    def traces(self) -> TracesResource:
        from .resources.traces import TracesResource

        return TracesResource(self)

    @cached_property
    def online_evaluators(self) -> OnlineEvaluatorsResource:
        from .resources.online_evaluators import OnlineEvaluatorsResource

        return OnlineEvaluatorsResource(self)

    @cached_property
    def info(self) -> InfoResource:
        from .resources.info import InfoResource

        return InfoResource(self)

    @cached_property
    def issues(self) -> IssuesResource:
        from .resources.issues import IssuesResource

        return IssuesResource(self)

    @cached_property
    def sandboxes(self) -> SandboxesResource:
        from .resources.sandboxes import SandboxesResource

        return SandboxesResource(self)

    @cached_property
    def with_raw_response(self) -> LangsmithWithRawResponse:
        return LangsmithWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> LangsmithWithStreamedResponse:
        return LangsmithWithStreamedResponse(self)

    @property
    @override
    def qs(self) -> Querystring:
        return Querystring(array_format="repeat")

    @property
    @override
    def auth_headers(self) -> dict[str, str]:
        return {**self._api_key, **self._tenant_id}

    @property
    def _api_key(self) -> dict[str, str]:
        api_key = self.api_key
        if api_key is None:
            return {}
        return {"X-API-Key": api_key}

    @property
    def _tenant_id(self) -> dict[str, str]:
        tenant_id = self.tenant_id
        if tenant_id is None:
            return {}
        return {"X-Tenant-Id": tenant_id}

    @property
    @override
    def default_headers(self) -> dict[str, str | Omit]:
        return {
            **super().default_headers,
            "X-Stainless-Async": "false",
            **self._custom_headers,
        }

    @override
    def _validate_headers(self, headers: Headers, custom_headers: Headers) -> None:
        if headers.get("X-API-Key") or isinstance(custom_headers.get("X-API-Key"), Omit):
            return

        if headers.get("X-Tenant-Id") or isinstance(custom_headers.get("X-Tenant-Id"), Omit):
            return

        raise TypeError(
            '"Could not resolve authentication method. Expected either api_key or tenant_id to be set. Or for one of the `X-API-Key` or `X-Tenant-Id` headers to be explicitly omitted"'
        )

    def copy(
        self,
        *,
        api_key: str | None = None,
        tenant_id: str | None = None,
        base_url: str | httpx.URL | None = None,
        timeout: float | Timeout | None | NotGiven = not_given,
        http_client: httpx.Client | None = None,
        max_retries: int | NotGiven = not_given,
        default_headers: Mapping[str, str] | None = None,
        set_default_headers: Mapping[str, str] | None = None,
        default_query: Mapping[str, object] | None = None,
        set_default_query: Mapping[str, object] | None = None,
        _extra_kwargs: Mapping[str, Any] = {},
    ) -> Self:
        """
        Create a new client instance re-using the same options given to the current client with optional overriding.
        """
        if default_headers is not None and set_default_headers is not None:
            raise ValueError("The `default_headers` and `set_default_headers` arguments are mutually exclusive")

        if default_query is not None and set_default_query is not None:
            raise ValueError("The `default_query` and `set_default_query` arguments are mutually exclusive")

        headers = self._custom_headers
        if default_headers is not None:
            headers = {**headers, **default_headers}
        elif set_default_headers is not None:
            headers = set_default_headers

        params = self._custom_query
        if default_query is not None:
            params = {**params, **default_query}
        elif set_default_query is not None:
            params = set_default_query

        http_client = http_client or self._client
        return self.__class__(
            api_key=api_key or self.api_key,
            tenant_id=tenant_id or self.tenant_id,
            base_url=base_url or self.base_url,
            timeout=self.timeout if isinstance(timeout, NotGiven) else timeout,
            http_client=http_client,
            max_retries=max_retries if is_given(max_retries) else self.max_retries,
            default_headers=headers,
            default_query=params,
            **_extra_kwargs,
        )

    # Alias for `copy` for nicer inline usage, e.g.
    # client.with_options(timeout=10).foo.create(...)
    with_options = copy

    @override
    def _make_status_error(
        self,
        err_msg: str,
        *,
        body: object,
        response: httpx.Response,
    ) -> APIStatusError:
        if response.status_code == 400:
            return _exceptions.BadRequestError(err_msg, response=response, body=body)

        if response.status_code == 401:
            return _exceptions.AuthenticationError(err_msg, response=response, body=body)

        if response.status_code == 403:
            return _exceptions.PermissionDeniedError(err_msg, response=response, body=body)

        if response.status_code == 404:
            return _exceptions.NotFoundError(err_msg, response=response, body=body)

        if response.status_code == 409:
            return _exceptions.ConflictError(err_msg, response=response, body=body)

        if response.status_code == 422:
            return _exceptions.UnprocessableEntityError(err_msg, response=response, body=body)

        if response.status_code == 429:
            return _exceptions.RateLimitError(err_msg, response=response, body=body)

        if response.status_code >= 500:
            return _exceptions.InternalServerError(err_msg, response=response, body=body)
        return APIStatusError(err_msg, response=response, body=body)


class AsyncLangsmith(AsyncAPIClient):
    # client options
    api_key: str | None
    tenant_id: str | None

    def __init__(
        self,
        *,
        api_key: str | None = None,
        tenant_id: str | None = None,
        base_url: str | httpx.URL | None = None,
        timeout: float | Timeout | None | NotGiven = not_given,
        max_retries: int = DEFAULT_MAX_RETRIES,
        default_headers: Mapping[str, str] | None = None,
        default_query: Mapping[str, object] | None = None,
        # Configure a custom httpx client.
        # We provide a `DefaultAsyncHttpxClient` class that you can pass to retain the default values we use for `limits`, `timeout` & `follow_redirects`.
        # See the [httpx documentation](https://www.python-httpx.org/api/#asyncclient) for more details.
        http_client: httpx.AsyncClient | None = None,
        # Enable or disable schema validation for data returned by the API.
        # When enabled an error APIResponseValidationError is raised
        # if the API responds with invalid data for the expected schema.
        #
        # This parameter may be removed or changed in the future.
        # If you rely on this feature, please open a GitHub issue
        # outlining your use-case to help us decide if it should be
        # part of our public interface in the future.
        _strict_response_validation: bool = False,
    ) -> None:
        """Construct a new async AsyncLangsmith client instance.

        This automatically infers the following arguments from their corresponding environment variables if they are not provided:
        - `api_key` from `LANGSMITH_API_KEY`
        - `tenant_id` from `LANGSMITH_TENANT_ID`
        """
        if api_key is None:
            api_key = os.environ.get("LANGSMITH_API_KEY")
        self.api_key = api_key

        if tenant_id is None:
            tenant_id = os.environ.get("LANGSMITH_TENANT_ID")
        self.tenant_id = tenant_id

        if base_url is None:
            base_url = os.environ.get("LANGCHAIN_BASE_URL")
        if base_url is None:
            base_url = f"https://api.smith.langchain.com/"

        custom_headers_env = os.environ.get("LANGCHAIN_CUSTOM_HEADERS")
        if custom_headers_env is not None:
            parsed: dict[str, str] = {}
            for line in custom_headers_env.split("\n"):
                colon = line.find(":")
                if colon >= 0:
                    parsed[line[:colon].strip()] = line[colon + 1 :].strip()
            default_headers = {**parsed, **(default_headers if is_mapping_t(default_headers) else {})}

        super().__init__(
            version=__version__,
            base_url=base_url,
            max_retries=max_retries,
            timeout=timeout,
            http_client=http_client,
            custom_headers=default_headers,
            custom_query=default_query,
            _strict_response_validation=_strict_response_validation,
        )

    @cached_property
    def datasets(self) -> AsyncDatasetsResource:
        from .resources.datasets import AsyncDatasetsResource

        return AsyncDatasetsResource(self)

    @cached_property
    def runs(self) -> AsyncRunsResource:
        from .resources.runs import AsyncRunsResource

        return AsyncRunsResource(self)

    @cached_property
    def threads(self) -> AsyncThreadsResource:
        from .resources.threads import AsyncThreadsResource

        return AsyncThreadsResource(self)

    @cached_property
    def traces(self) -> AsyncTracesResource:
        from .resources.traces import AsyncTracesResource

        return AsyncTracesResource(self)

    @cached_property
    def online_evaluators(self) -> AsyncOnlineEvaluatorsResource:
        from .resources.online_evaluators import AsyncOnlineEvaluatorsResource

        return AsyncOnlineEvaluatorsResource(self)

    @cached_property
    def info(self) -> AsyncInfoResource:
        from .resources.info import AsyncInfoResource

        return AsyncInfoResource(self)

    @cached_property
    def issues(self) -> AsyncIssuesResource:
        from .resources.issues import AsyncIssuesResource

        return AsyncIssuesResource(self)

    @cached_property
    def sandboxes(self) -> AsyncSandboxesResource:
        from .resources.sandboxes import AsyncSandboxesResource

        return AsyncSandboxesResource(self)

    @cached_property
    def with_raw_response(self) -> AsyncLangsmithWithRawResponse:
        return AsyncLangsmithWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncLangsmithWithStreamedResponse:
        return AsyncLangsmithWithStreamedResponse(self)

    @property
    @override
    def qs(self) -> Querystring:
        return Querystring(array_format="repeat")

    @property
    @override
    def auth_headers(self) -> dict[str, str]:
        return {**self._api_key, **self._tenant_id}

    @property
    def _api_key(self) -> dict[str, str]:
        api_key = self.api_key
        if api_key is None:
            return {}
        return {"X-API-Key": api_key}

    @property
    def _tenant_id(self) -> dict[str, str]:
        tenant_id = self.tenant_id
        if tenant_id is None:
            return {}
        return {"X-Tenant-Id": tenant_id}

    @property
    @override
    def default_headers(self) -> dict[str, str | Omit]:
        return {
            **super().default_headers,
            "X-Stainless-Async": f"async:{get_async_library()}",
            **self._custom_headers,
        }

    @override
    def _validate_headers(self, headers: Headers, custom_headers: Headers) -> None:
        if headers.get("X-API-Key") or isinstance(custom_headers.get("X-API-Key"), Omit):
            return

        if headers.get("X-Tenant-Id") or isinstance(custom_headers.get("X-Tenant-Id"), Omit):
            return

        raise TypeError(
            '"Could not resolve authentication method. Expected either api_key or tenant_id to be set. Or for one of the `X-API-Key` or `X-Tenant-Id` headers to be explicitly omitted"'
        )

    def copy(
        self,
        *,
        api_key: str | None = None,
        tenant_id: str | None = None,
        base_url: str | httpx.URL | None = None,
        timeout: float | Timeout | None | NotGiven = not_given,
        http_client: httpx.AsyncClient | None = None,
        max_retries: int | NotGiven = not_given,
        default_headers: Mapping[str, str] | None = None,
        set_default_headers: Mapping[str, str] | None = None,
        default_query: Mapping[str, object] | None = None,
        set_default_query: Mapping[str, object] | None = None,
        _extra_kwargs: Mapping[str, Any] = {},
    ) -> Self:
        """
        Create a new client instance re-using the same options given to the current client with optional overriding.
        """
        if default_headers is not None and set_default_headers is not None:
            raise ValueError("The `default_headers` and `set_default_headers` arguments are mutually exclusive")

        if default_query is not None and set_default_query is not None:
            raise ValueError("The `default_query` and `set_default_query` arguments are mutually exclusive")

        headers = self._custom_headers
        if default_headers is not None:
            headers = {**headers, **default_headers}
        elif set_default_headers is not None:
            headers = set_default_headers

        params = self._custom_query
        if default_query is not None:
            params = {**params, **default_query}
        elif set_default_query is not None:
            params = set_default_query

        http_client = http_client or self._client
        return self.__class__(
            api_key=api_key or self.api_key,
            tenant_id=tenant_id or self.tenant_id,
            base_url=base_url or self.base_url,
            timeout=self.timeout if isinstance(timeout, NotGiven) else timeout,
            http_client=http_client,
            max_retries=max_retries if is_given(max_retries) else self.max_retries,
            default_headers=headers,
            default_query=params,
            **_extra_kwargs,
        )

    # Alias for `copy` for nicer inline usage, e.g.
    # client.with_options(timeout=10).foo.create(...)
    with_options = copy

    @override
    def _make_status_error(
        self,
        err_msg: str,
        *,
        body: object,
        response: httpx.Response,
    ) -> APIStatusError:
        if response.status_code == 400:
            return _exceptions.BadRequestError(err_msg, response=response, body=body)

        if response.status_code == 401:
            return _exceptions.AuthenticationError(err_msg, response=response, body=body)

        if response.status_code == 403:
            return _exceptions.PermissionDeniedError(err_msg, response=response, body=body)

        if response.status_code == 404:
            return _exceptions.NotFoundError(err_msg, response=response, body=body)

        if response.status_code == 409:
            return _exceptions.ConflictError(err_msg, response=response, body=body)

        if response.status_code == 422:
            return _exceptions.UnprocessableEntityError(err_msg, response=response, body=body)

        if response.status_code == 429:
            return _exceptions.RateLimitError(err_msg, response=response, body=body)

        if response.status_code >= 500:
            return _exceptions.InternalServerError(err_msg, response=response, body=body)
        return APIStatusError(err_msg, response=response, body=body)


class LangsmithWithRawResponse:
    _client: Langsmith

    def __init__(self, client: Langsmith) -> None:
        self._client = client

    @cached_property
    def datasets(self) -> datasets.DatasetsResourceWithRawResponse:
        from .resources.datasets import DatasetsResourceWithRawResponse

        return DatasetsResourceWithRawResponse(self._client.datasets)

    @cached_property
    def runs(self) -> runs.RunsResourceWithRawResponse:
        from .resources.runs import RunsResourceWithRawResponse

        return RunsResourceWithRawResponse(self._client.runs)

    @cached_property
    def threads(self) -> threads.ThreadsResourceWithRawResponse:
        from .resources.threads import ThreadsResourceWithRawResponse

        return ThreadsResourceWithRawResponse(self._client.threads)

    @cached_property
    def traces(self) -> traces.TracesResourceWithRawResponse:
        from .resources.traces import TracesResourceWithRawResponse

        return TracesResourceWithRawResponse(self._client.traces)

    @cached_property
    def online_evaluators(self) -> online_evaluators.OnlineEvaluatorsResourceWithRawResponse:
        from .resources.online_evaluators import OnlineEvaluatorsResourceWithRawResponse

        return OnlineEvaluatorsResourceWithRawResponse(self._client.online_evaluators)

    @cached_property
    def info(self) -> info.InfoResourceWithRawResponse:
        from .resources.info import InfoResourceWithRawResponse

        return InfoResourceWithRawResponse(self._client.info)

    @cached_property
    def issues(self) -> issues.IssuesResourceWithRawResponse:
        from .resources.issues import IssuesResourceWithRawResponse

        return IssuesResourceWithRawResponse(self._client.issues)

    @cached_property
    def sandboxes(self) -> sandboxes.SandboxesResourceWithRawResponse:
        from .resources.sandboxes import SandboxesResourceWithRawResponse

        return SandboxesResourceWithRawResponse(self._client.sandboxes)


class AsyncLangsmithWithRawResponse:
    _client: AsyncLangsmith

    def __init__(self, client: AsyncLangsmith) -> None:
        self._client = client

    @cached_property
    def datasets(self) -> datasets.AsyncDatasetsResourceWithRawResponse:
        from .resources.datasets import AsyncDatasetsResourceWithRawResponse

        return AsyncDatasetsResourceWithRawResponse(self._client.datasets)

    @cached_property
    def runs(self) -> runs.AsyncRunsResourceWithRawResponse:
        from .resources.runs import AsyncRunsResourceWithRawResponse

        return AsyncRunsResourceWithRawResponse(self._client.runs)

    @cached_property
    def threads(self) -> threads.AsyncThreadsResourceWithRawResponse:
        from .resources.threads import AsyncThreadsResourceWithRawResponse

        return AsyncThreadsResourceWithRawResponse(self._client.threads)

    @cached_property
    def traces(self) -> traces.AsyncTracesResourceWithRawResponse:
        from .resources.traces import AsyncTracesResourceWithRawResponse

        return AsyncTracesResourceWithRawResponse(self._client.traces)

    @cached_property
    def online_evaluators(self) -> online_evaluators.AsyncOnlineEvaluatorsResourceWithRawResponse:
        from .resources.online_evaluators import AsyncOnlineEvaluatorsResourceWithRawResponse

        return AsyncOnlineEvaluatorsResourceWithRawResponse(self._client.online_evaluators)

    @cached_property
    def info(self) -> info.AsyncInfoResourceWithRawResponse:
        from .resources.info import AsyncInfoResourceWithRawResponse

        return AsyncInfoResourceWithRawResponse(self._client.info)

    @cached_property
    def issues(self) -> issues.AsyncIssuesResourceWithRawResponse:
        from .resources.issues import AsyncIssuesResourceWithRawResponse

        return AsyncIssuesResourceWithRawResponse(self._client.issues)

    @cached_property
    def sandboxes(self) -> sandboxes.AsyncSandboxesResourceWithRawResponse:
        from .resources.sandboxes import AsyncSandboxesResourceWithRawResponse

        return AsyncSandboxesResourceWithRawResponse(self._client.sandboxes)


class LangsmithWithStreamedResponse:
    _client: Langsmith

    def __init__(self, client: Langsmith) -> None:
        self._client = client

    @cached_property
    def datasets(self) -> datasets.DatasetsResourceWithStreamingResponse:
        from .resources.datasets import DatasetsResourceWithStreamingResponse

        return DatasetsResourceWithStreamingResponse(self._client.datasets)

    @cached_property
    def runs(self) -> runs.RunsResourceWithStreamingResponse:
        from .resources.runs import RunsResourceWithStreamingResponse

        return RunsResourceWithStreamingResponse(self._client.runs)

    @cached_property
    def threads(self) -> threads.ThreadsResourceWithStreamingResponse:
        from .resources.threads import ThreadsResourceWithStreamingResponse

        return ThreadsResourceWithStreamingResponse(self._client.threads)

    @cached_property
    def traces(self) -> traces.TracesResourceWithStreamingResponse:
        from .resources.traces import TracesResourceWithStreamingResponse

        return TracesResourceWithStreamingResponse(self._client.traces)

    @cached_property
    def online_evaluators(self) -> online_evaluators.OnlineEvaluatorsResourceWithStreamingResponse:
        from .resources.online_evaluators import OnlineEvaluatorsResourceWithStreamingResponse

        return OnlineEvaluatorsResourceWithStreamingResponse(self._client.online_evaluators)

    @cached_property
    def info(self) -> info.InfoResourceWithStreamingResponse:
        from .resources.info import InfoResourceWithStreamingResponse

        return InfoResourceWithStreamingResponse(self._client.info)

    @cached_property
    def issues(self) -> issues.IssuesResourceWithStreamingResponse:
        from .resources.issues import IssuesResourceWithStreamingResponse

        return IssuesResourceWithStreamingResponse(self._client.issues)

    @cached_property
    def sandboxes(self) -> sandboxes.SandboxesResourceWithStreamingResponse:
        from .resources.sandboxes import SandboxesResourceWithStreamingResponse

        return SandboxesResourceWithStreamingResponse(self._client.sandboxes)


class AsyncLangsmithWithStreamedResponse:
    _client: AsyncLangsmith

    def __init__(self, client: AsyncLangsmith) -> None:
        self._client = client

    @cached_property
    def datasets(self) -> datasets.AsyncDatasetsResourceWithStreamingResponse:
        from .resources.datasets import AsyncDatasetsResourceWithStreamingResponse

        return AsyncDatasetsResourceWithStreamingResponse(self._client.datasets)

    @cached_property
    def runs(self) -> runs.AsyncRunsResourceWithStreamingResponse:
        from .resources.runs import AsyncRunsResourceWithStreamingResponse

        return AsyncRunsResourceWithStreamingResponse(self._client.runs)

    @cached_property
    def threads(self) -> threads.AsyncThreadsResourceWithStreamingResponse:
        from .resources.threads import AsyncThreadsResourceWithStreamingResponse

        return AsyncThreadsResourceWithStreamingResponse(self._client.threads)

    @cached_property
    def traces(self) -> traces.AsyncTracesResourceWithStreamingResponse:
        from .resources.traces import AsyncTracesResourceWithStreamingResponse

        return AsyncTracesResourceWithStreamingResponse(self._client.traces)

    @cached_property
    def online_evaluators(self) -> online_evaluators.AsyncOnlineEvaluatorsResourceWithStreamingResponse:
        from .resources.online_evaluators import AsyncOnlineEvaluatorsResourceWithStreamingResponse

        return AsyncOnlineEvaluatorsResourceWithStreamingResponse(self._client.online_evaluators)

    @cached_property
    def info(self) -> info.AsyncInfoResourceWithStreamingResponse:
        from .resources.info import AsyncInfoResourceWithStreamingResponse

        return AsyncInfoResourceWithStreamingResponse(self._client.info)

    @cached_property
    def issues(self) -> issues.AsyncIssuesResourceWithStreamingResponse:
        from .resources.issues import AsyncIssuesResourceWithStreamingResponse

        return AsyncIssuesResourceWithStreamingResponse(self._client.issues)

    @cached_property
    def sandboxes(self) -> sandboxes.AsyncSandboxesResourceWithStreamingResponse:
        from .resources.sandboxes import AsyncSandboxesResourceWithStreamingResponse

        return AsyncSandboxesResourceWithStreamingResponse(self._client.sandboxes)


Client = Langsmith

AsyncClient = AsyncLangsmith
