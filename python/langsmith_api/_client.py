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
from ._utils import is_given, get_async_library
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
    from .resources import (
        runs,
        repos,
        public,
        traces,
        threads,
        datasets,
        examples,
        feedback,
        sessions,
        settings,
        workspaces,
        annotation_queues,
    )
    from .resources.settings import SettingsResource, AsyncSettingsResource
    from .resources.runs.runs import RunsResource, AsyncRunsResource
    from .resources.repos.repos import ReposResource, AsyncReposResource
    from .resources.public.public import PublicResource, AsyncPublicResource
    from .resources.traces.traces import TracesResource, AsyncTracesResource
    from .resources.threads.threads import ThreadsResource, AsyncThreadsResource
    from .resources.datasets.datasets import DatasetsResource, AsyncDatasetsResource
    from .resources.examples.examples import ExamplesResource, AsyncExamplesResource
    from .resources.feedback.feedback import FeedbackResource, AsyncFeedbackResource
    from .resources.sessions.sessions import SessionsResource, AsyncSessionsResource
    from .resources.workspaces.workspaces import WorkspacesResource, AsyncWorkspacesResource
    from .resources.annotation_queues.annotation_queues import AnnotationQueuesResource, AsyncAnnotationQueuesResource

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
    bearer_token: str | None
    organization_id: str | None

    def __init__(
        self,
        *,
        api_key: str | None = None,
        tenant_id: str | None = None,
        bearer_token: str | None = None,
        organization_id: str | None = None,
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
        - `bearer_token` from `LANGSMITH_BEARER_TOKEN`
        - `organization_id` from `LANGSMITH_ORGANIZATION_ID`
        """
        if api_key is None:
            api_key = os.environ.get("LANGSMITH_API_KEY")
        self.api_key = api_key

        if tenant_id is None:
            tenant_id = os.environ.get("LANGSMITH_TENANT_ID")
        self.tenant_id = tenant_id

        if bearer_token is None:
            bearer_token = os.environ.get("LANGSMITH_BEARER_TOKEN")
        self.bearer_token = bearer_token

        if organization_id is None:
            organization_id = os.environ.get("LANGSMITH_ORGANIZATION_ID")
        self.organization_id = organization_id

        if base_url is None:
            base_url = os.environ.get("LANGCHAIN_BASE_URL")
        if base_url is None:
            base_url = f"https://api.smith.langchain.com/"

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
    def sessions(self) -> SessionsResource:
        from .resources.sessions import SessionsResource

        return SessionsResource(self)

    @cached_property
    def examples(self) -> ExamplesResource:
        from .resources.examples import ExamplesResource

        return ExamplesResource(self)

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
    def feedback(self) -> FeedbackResource:
        from .resources.feedback import FeedbackResource

        return FeedbackResource(self)

    @cached_property
    def public(self) -> PublicResource:
        from .resources.public import PublicResource

        return PublicResource(self)

    @cached_property
    def annotation_queues(self) -> AnnotationQueuesResource:
        from .resources.annotation_queues import AnnotationQueuesResource

        return AnnotationQueuesResource(self)

    @cached_property
    def repos(self) -> ReposResource:
        from .resources.repos import ReposResource

        return ReposResource(self)

    @cached_property
    def settings(self) -> SettingsResource:
        from .resources.settings import SettingsResource

        return SettingsResource(self)

    @cached_property
    def workspaces(self) -> WorkspacesResource:
        from .resources.workspaces import WorkspacesResource

        return WorkspacesResource(self)

    @cached_property
    def with_raw_response(self) -> LangsmithWithRawResponse:
        return LangsmithWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> LangsmithWithStreamedResponse:
        return LangsmithWithStreamedResponse(self)

    @property
    @override
    def qs(self) -> Querystring:
        return Querystring(array_format="comma")

    @property
    @override
    def auth_headers(self) -> dict[str, str]:
        return {**self._api_key, **self._tenant_id, **self._bearer_auth, **self._organization_id}

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
    def _bearer_auth(self) -> dict[str, str]:
        bearer_token = self.bearer_token
        if bearer_token is None:
            return {}
        return {"Authorization": f"Bearer {bearer_token}"}

    @property
    def _organization_id(self) -> dict[str, str]:
        organization_id = self.organization_id
        if organization_id is None:
            return {}
        return {"X-Organization-Id": organization_id}

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

        if headers.get("Authorization") or isinstance(custom_headers.get("Authorization"), Omit):
            return

        if headers.get("X-Organization-Id") or isinstance(custom_headers.get("X-Organization-Id"), Omit):
            return

        raise TypeError(
            '"Could not resolve authentication method. Expected one of api_key, tenant_id, bearer_token or organization_id to be set. Or for one of the `X-API-Key`, `X-Tenant-Id`, `Authorization` or `X-Organization-Id` headers to be explicitly omitted"'
        )

    def copy(
        self,
        *,
        api_key: str | None = None,
        tenant_id: str | None = None,
        bearer_token: str | None = None,
        organization_id: str | None = None,
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
            bearer_token=bearer_token or self.bearer_token,
            organization_id=organization_id or self.organization_id,
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
    bearer_token: str | None
    organization_id: str | None

    def __init__(
        self,
        *,
        api_key: str | None = None,
        tenant_id: str | None = None,
        bearer_token: str | None = None,
        organization_id: str | None = None,
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
        - `bearer_token` from `LANGSMITH_BEARER_TOKEN`
        - `organization_id` from `LANGSMITH_ORGANIZATION_ID`
        """
        if api_key is None:
            api_key = os.environ.get("LANGSMITH_API_KEY")
        self.api_key = api_key

        if tenant_id is None:
            tenant_id = os.environ.get("LANGSMITH_TENANT_ID")
        self.tenant_id = tenant_id

        if bearer_token is None:
            bearer_token = os.environ.get("LANGSMITH_BEARER_TOKEN")
        self.bearer_token = bearer_token

        if organization_id is None:
            organization_id = os.environ.get("LANGSMITH_ORGANIZATION_ID")
        self.organization_id = organization_id

        if base_url is None:
            base_url = os.environ.get("LANGCHAIN_BASE_URL")
        if base_url is None:
            base_url = f"https://api.smith.langchain.com/"

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
    def sessions(self) -> AsyncSessionsResource:
        from .resources.sessions import AsyncSessionsResource

        return AsyncSessionsResource(self)

    @cached_property
    def examples(self) -> AsyncExamplesResource:
        from .resources.examples import AsyncExamplesResource

        return AsyncExamplesResource(self)

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
    def feedback(self) -> AsyncFeedbackResource:
        from .resources.feedback import AsyncFeedbackResource

        return AsyncFeedbackResource(self)

    @cached_property
    def public(self) -> AsyncPublicResource:
        from .resources.public import AsyncPublicResource

        return AsyncPublicResource(self)

    @cached_property
    def annotation_queues(self) -> AsyncAnnotationQueuesResource:
        from .resources.annotation_queues import AsyncAnnotationQueuesResource

        return AsyncAnnotationQueuesResource(self)

    @cached_property
    def repos(self) -> AsyncReposResource:
        from .resources.repos import AsyncReposResource

        return AsyncReposResource(self)

    @cached_property
    def settings(self) -> AsyncSettingsResource:
        from .resources.settings import AsyncSettingsResource

        return AsyncSettingsResource(self)

    @cached_property
    def workspaces(self) -> AsyncWorkspacesResource:
        from .resources.workspaces import AsyncWorkspacesResource

        return AsyncWorkspacesResource(self)

    @cached_property
    def with_raw_response(self) -> AsyncLangsmithWithRawResponse:
        return AsyncLangsmithWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncLangsmithWithStreamedResponse:
        return AsyncLangsmithWithStreamedResponse(self)

    @property
    @override
    def qs(self) -> Querystring:
        return Querystring(array_format="comma")

    @property
    @override
    def auth_headers(self) -> dict[str, str]:
        return {**self._api_key, **self._tenant_id, **self._bearer_auth, **self._organization_id}

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
    def _bearer_auth(self) -> dict[str, str]:
        bearer_token = self.bearer_token
        if bearer_token is None:
            return {}
        return {"Authorization": f"Bearer {bearer_token}"}

    @property
    def _organization_id(self) -> dict[str, str]:
        organization_id = self.organization_id
        if organization_id is None:
            return {}
        return {"X-Organization-Id": organization_id}

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

        if headers.get("Authorization") or isinstance(custom_headers.get("Authorization"), Omit):
            return

        if headers.get("X-Organization-Id") or isinstance(custom_headers.get("X-Organization-Id"), Omit):
            return

        raise TypeError(
            '"Could not resolve authentication method. Expected one of api_key, tenant_id, bearer_token or organization_id to be set. Or for one of the `X-API-Key`, `X-Tenant-Id`, `Authorization` or `X-Organization-Id` headers to be explicitly omitted"'
        )

    def copy(
        self,
        *,
        api_key: str | None = None,
        tenant_id: str | None = None,
        bearer_token: str | None = None,
        organization_id: str | None = None,
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
            bearer_token=bearer_token or self.bearer_token,
            organization_id=organization_id or self.organization_id,
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
    def sessions(self) -> sessions.SessionsResourceWithRawResponse:
        from .resources.sessions import SessionsResourceWithRawResponse

        return SessionsResourceWithRawResponse(self._client.sessions)

    @cached_property
    def examples(self) -> examples.ExamplesResourceWithRawResponse:
        from .resources.examples import ExamplesResourceWithRawResponse

        return ExamplesResourceWithRawResponse(self._client.examples)

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
    def feedback(self) -> feedback.FeedbackResourceWithRawResponse:
        from .resources.feedback import FeedbackResourceWithRawResponse

        return FeedbackResourceWithRawResponse(self._client.feedback)

    @cached_property
    def public(self) -> public.PublicResourceWithRawResponse:
        from .resources.public import PublicResourceWithRawResponse

        return PublicResourceWithRawResponse(self._client.public)

    @cached_property
    def annotation_queues(self) -> annotation_queues.AnnotationQueuesResourceWithRawResponse:
        from .resources.annotation_queues import AnnotationQueuesResourceWithRawResponse

        return AnnotationQueuesResourceWithRawResponse(self._client.annotation_queues)

    @cached_property
    def repos(self) -> repos.ReposResourceWithRawResponse:
        from .resources.repos import ReposResourceWithRawResponse

        return ReposResourceWithRawResponse(self._client.repos)

    @cached_property
    def settings(self) -> settings.SettingsResourceWithRawResponse:
        from .resources.settings import SettingsResourceWithRawResponse

        return SettingsResourceWithRawResponse(self._client.settings)

    @cached_property
    def workspaces(self) -> workspaces.WorkspacesResourceWithRawResponse:
        from .resources.workspaces import WorkspacesResourceWithRawResponse

        return WorkspacesResourceWithRawResponse(self._client.workspaces)


class AsyncLangsmithWithRawResponse:
    _client: AsyncLangsmith

    def __init__(self, client: AsyncLangsmith) -> None:
        self._client = client

    @cached_property
    def sessions(self) -> sessions.AsyncSessionsResourceWithRawResponse:
        from .resources.sessions import AsyncSessionsResourceWithRawResponse

        return AsyncSessionsResourceWithRawResponse(self._client.sessions)

    @cached_property
    def examples(self) -> examples.AsyncExamplesResourceWithRawResponse:
        from .resources.examples import AsyncExamplesResourceWithRawResponse

        return AsyncExamplesResourceWithRawResponse(self._client.examples)

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
    def feedback(self) -> feedback.AsyncFeedbackResourceWithRawResponse:
        from .resources.feedback import AsyncFeedbackResourceWithRawResponse

        return AsyncFeedbackResourceWithRawResponse(self._client.feedback)

    @cached_property
    def public(self) -> public.AsyncPublicResourceWithRawResponse:
        from .resources.public import AsyncPublicResourceWithRawResponse

        return AsyncPublicResourceWithRawResponse(self._client.public)

    @cached_property
    def annotation_queues(self) -> annotation_queues.AsyncAnnotationQueuesResourceWithRawResponse:
        from .resources.annotation_queues import AsyncAnnotationQueuesResourceWithRawResponse

        return AsyncAnnotationQueuesResourceWithRawResponse(self._client.annotation_queues)

    @cached_property
    def repos(self) -> repos.AsyncReposResourceWithRawResponse:
        from .resources.repos import AsyncReposResourceWithRawResponse

        return AsyncReposResourceWithRawResponse(self._client.repos)

    @cached_property
    def settings(self) -> settings.AsyncSettingsResourceWithRawResponse:
        from .resources.settings import AsyncSettingsResourceWithRawResponse

        return AsyncSettingsResourceWithRawResponse(self._client.settings)

    @cached_property
    def workspaces(self) -> workspaces.AsyncWorkspacesResourceWithRawResponse:
        from .resources.workspaces import AsyncWorkspacesResourceWithRawResponse

        return AsyncWorkspacesResourceWithRawResponse(self._client.workspaces)


class LangsmithWithStreamedResponse:
    _client: Langsmith

    def __init__(self, client: Langsmith) -> None:
        self._client = client

    @cached_property
    def sessions(self) -> sessions.SessionsResourceWithStreamingResponse:
        from .resources.sessions import SessionsResourceWithStreamingResponse

        return SessionsResourceWithStreamingResponse(self._client.sessions)

    @cached_property
    def examples(self) -> examples.ExamplesResourceWithStreamingResponse:
        from .resources.examples import ExamplesResourceWithStreamingResponse

        return ExamplesResourceWithStreamingResponse(self._client.examples)

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
    def feedback(self) -> feedback.FeedbackResourceWithStreamingResponse:
        from .resources.feedback import FeedbackResourceWithStreamingResponse

        return FeedbackResourceWithStreamingResponse(self._client.feedback)

    @cached_property
    def public(self) -> public.PublicResourceWithStreamingResponse:
        from .resources.public import PublicResourceWithStreamingResponse

        return PublicResourceWithStreamingResponse(self._client.public)

    @cached_property
    def annotation_queues(self) -> annotation_queues.AnnotationQueuesResourceWithStreamingResponse:
        from .resources.annotation_queues import AnnotationQueuesResourceWithStreamingResponse

        return AnnotationQueuesResourceWithStreamingResponse(self._client.annotation_queues)

    @cached_property
    def repos(self) -> repos.ReposResourceWithStreamingResponse:
        from .resources.repos import ReposResourceWithStreamingResponse

        return ReposResourceWithStreamingResponse(self._client.repos)

    @cached_property
    def settings(self) -> settings.SettingsResourceWithStreamingResponse:
        from .resources.settings import SettingsResourceWithStreamingResponse

        return SettingsResourceWithStreamingResponse(self._client.settings)

    @cached_property
    def workspaces(self) -> workspaces.WorkspacesResourceWithStreamingResponse:
        from .resources.workspaces import WorkspacesResourceWithStreamingResponse

        return WorkspacesResourceWithStreamingResponse(self._client.workspaces)


class AsyncLangsmithWithStreamedResponse:
    _client: AsyncLangsmith

    def __init__(self, client: AsyncLangsmith) -> None:
        self._client = client

    @cached_property
    def sessions(self) -> sessions.AsyncSessionsResourceWithStreamingResponse:
        from .resources.sessions import AsyncSessionsResourceWithStreamingResponse

        return AsyncSessionsResourceWithStreamingResponse(self._client.sessions)

    @cached_property
    def examples(self) -> examples.AsyncExamplesResourceWithStreamingResponse:
        from .resources.examples import AsyncExamplesResourceWithStreamingResponse

        return AsyncExamplesResourceWithStreamingResponse(self._client.examples)

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
    def feedback(self) -> feedback.AsyncFeedbackResourceWithStreamingResponse:
        from .resources.feedback import AsyncFeedbackResourceWithStreamingResponse

        return AsyncFeedbackResourceWithStreamingResponse(self._client.feedback)

    @cached_property
    def public(self) -> public.AsyncPublicResourceWithStreamingResponse:
        from .resources.public import AsyncPublicResourceWithStreamingResponse

        return AsyncPublicResourceWithStreamingResponse(self._client.public)

    @cached_property
    def annotation_queues(self) -> annotation_queues.AsyncAnnotationQueuesResourceWithStreamingResponse:
        from .resources.annotation_queues import AsyncAnnotationQueuesResourceWithStreamingResponse

        return AsyncAnnotationQueuesResourceWithStreamingResponse(self._client.annotation_queues)

    @cached_property
    def repos(self) -> repos.AsyncReposResourceWithStreamingResponse:
        from .resources.repos import AsyncReposResourceWithStreamingResponse

        return AsyncReposResourceWithStreamingResponse(self._client.repos)

    @cached_property
    def settings(self) -> settings.AsyncSettingsResourceWithStreamingResponse:
        from .resources.settings import AsyncSettingsResourceWithStreamingResponse

        return AsyncSettingsResourceWithStreamingResponse(self._client.settings)

    @cached_property
    def workspaces(self) -> workspaces.AsyncWorkspacesResourceWithStreamingResponse:
        from .resources.workspaces import AsyncWorkspacesResourceWithStreamingResponse

        return AsyncWorkspacesResourceWithStreamingResponse(self._client.workspaces)


Client = Langsmith

AsyncClient = AsyncLangsmith
