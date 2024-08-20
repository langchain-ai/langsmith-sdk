"""The Async LangSmith Client."""

from __future__ import annotations

import asyncio
import logging
from typing import (
    Any,
    AsyncIterator,
    Dict,
    List,
    Mapping,
    Optional,
    Tuple,
    Union,
    cast,
)

import httpx

from langsmith import schemas as ls_schemas
from langsmith import utils as ls_utils
from langsmith.client import (
    ID_TYPE,
    X_API_KEY,
    _as_uuid,
    _dumps_json,
    _ensure_uuid,
)

logger = logging.getLogger(__name__)


class AsyncClient:
    """Async Client for interacting with the LangSmith API."""

    __slots__ = (
        "_retry_config",
        "_client",
    )

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout_ms: Optional[
            Union[
                int, Tuple[Optional[int], Optional[int], Optional[int], Optional[int]]
            ]
        ] = None,
        retry_config: Optional[Mapping[str, Any]] = None,
    ):
        """Initialize the async client."""
        self._retry_config = retry_config or {"max_retries": 3}
        _headers = {
            "Content-Type": "application/json",
        }
        api_key = ls_utils.get_api_key(api_key)
        if api_key:
            _headers[X_API_KEY] = api_key

        if isinstance(timeout_ms, int):
            timeout_: Union[Tuple, float] = (timeout_ms / 1000, None, None, None)
        elif isinstance(timeout_ms, tuple):
            timeout_ = tuple([t / 1000 if t is not None else None for t in timeout_ms])
        else:
            timeout_ = 10
        self._client = httpx.AsyncClient(
            base_url=ls_utils.get_api_url(api_url), headers=_headers, timeout=timeout_
        )

    async def __aenter__(self) -> "AsyncClient":
        """Enter the async client."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the async client."""
        await self.aclose()

    async def aclose(self):
        """Close the async client."""
        await self._client.aclose()

    async def _arequest_with_retries(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make an async HTTP request with retries."""
        max_retries = cast(int, self._retry_config.get("max_retries", 3))
        for attempt in range(max_retries):
            try:
                response = await self._client.request(method, endpoint, **kwargs)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as e:
                if attempt == max_retries - 1:
                    raise ls_utils.LangSmithAPIError(f"HTTP error: {e}")
                await asyncio.sleep(2**attempt)
            except httpx.RequestError as e:
                if attempt == max_retries - 1:
                    raise ls_utils.LangSmithConnectionError(f"Request error: {e}")
                await asyncio.sleep(2**attempt)
        raise ls_utils.LangSmithAPIError(
            "Unexpected error connecting to the LangSmith API"
        )

    async def _aget_paginated_list(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Get a paginated list of items."""
        params = params or {}
        offset = params.get("offset", 0)
        params["limit"] = params.get("limit", 100)
        while True:
            params["offset"] = offset
            response = await self._arequest_with_retries("GET", path, params=params)
            items = response.json()
            if not items:
                break
            yield items
            if len(items) < params["limit"]:
                break
            offset += len(items)

    async def create_run(
        self,
        name: str,
        inputs: Dict[str, Any],
        run_type: str,
        project_name: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Create a run asynchronously."""
        run_create = {
            "name": name,
            "inputs": inputs,
            "run_type": run_type,
            "session_name": project_name or ls_utils.get_tracer_project(),
            **kwargs,
        }
        await self._arequest_with_retries("POST", "/runs", json=_dumps_json(run_create))

    async def update_run(
        self,
        run_id: ID_TYPE,
        **kwargs: Any,
    ) -> None:
        """Update a run asynchronously."""
        data = {**kwargs, "id": _as_uuid(run_id)}
        await self._arequest_with_retries(
            "PATCH",
            f"/runs/{_as_uuid(run_id)}",
            json=_dumps_json(data),
        )

    async def read_run(self, run_id: ID_TYPE) -> ls_schemas.Run:
        """Read a run asynchronously."""
        response = await self._arequest_with_retries(
            "GET",
            f"/runs/{_as_uuid(run_id)}",
        )
        return ls_schemas.Run(**response.json())

    async def list_runs(
        self,
        project_id: Optional[ID_TYPE] = None,
        project_name: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ls_schemas.Run]:
        """List runs asynchronously."""
        params = kwargs.copy()
        if project_id:
            params["session"] = _as_uuid(project_id)
        elif project_name:
            project = await self.read_project(project_name=project_name)
            params["session"] = project.id

        async for run in self._aget_paginated_list("/runs", params=params):
            yield ls_schemas.Run(**run)

    async def create_project(
        self,
        project_name: str,
        **kwargs: Any,
    ) -> ls_schemas.TracerSession:
        """Create a project asynchronously."""
        data = {"name": project_name, **kwargs}
        response = await self._arequest_with_retries("POST", "/sessions", json=data)
        return ls_schemas.TracerSession(**response.json())

    async def read_project(
        self,
        project_name: Optional[str] = None,
        project_id: Optional[ID_TYPE] = None,
    ) -> ls_schemas.TracerSession:
        """Read a project asynchronously."""
        if project_id:
            response = await self._arequest_with_retries(
                "GET", f"/sessions/{_as_uuid(project_id)}"
            )
        elif project_name:
            response = await self._arequest_with_retries(
                "GET", "/sessions", params={"name": project_name}
            )
        else:
            raise ValueError("Either project_name or project_id must be provided")

        data = response.json()
        if isinstance(data, list):
            if not data:
                raise ls_utils.LangSmithNotFoundError(
                    f"Project {project_name} not found"
                )
            return ls_schemas.TracerSession(**data[0])
        return ls_schemas.TracerSession(**data)

    async def list_projects(
        self,
        **kwargs: Any,
    ) -> AsyncIterator[ls_schemas.TracerSession]:
        """List projects asynchronously."""
        async for project in self._aget_paginated_list("/sessions", params=kwargs):
            yield ls_schemas.TracerSession(**project)

    async def create_dataset(
        self,
        dataset_name: str,
        **kwargs: Any,
    ) -> ls_schemas.Dataset:
        """Create a dataset asynchronously."""
        data = {"name": dataset_name, **kwargs}
        response = await self._arequest_with_retries("POST", "/datasets", json=data)
        return ls_schemas.Dataset(**response.json())

    async def read_dataset(
        self,
        dataset_name: Optional[str] = None,
        dataset_id: Optional[ID_TYPE] = None,
    ) -> ls_schemas.Dataset:
        """Read a dataset asynchronously."""
        if dataset_id:
            response = await self._arequest_with_retries(
                "GET", f"/datasets/{_as_uuid(dataset_id)}"
            )
        elif dataset_name:
            response = await self._arequest_with_retries(
                "GET", "/datasets", params={"name": dataset_name}
            )
        else:
            raise ValueError("Either dataset_name or dataset_id must be provided")

        data = response.json()
        if isinstance(data, list):
            if not data:
                raise ls_utils.LangSmithNotFoundError(
                    f"Dataset {dataset_name} not found"
                )
            return ls_schemas.Dataset(**data[0])
        return ls_schemas.Dataset(**data)

    async def delete_dataset(self, dataset_id: ID_TYPE) -> None:
        """Delete a dataset asynchronously."""
        await self._arequest_with_retries(
            "DELETE",
            f"/datasets/{_as_uuid(dataset_id)}",
        )

    async def list_datasets(
        self,
        **kwargs: Any,
    ) -> AsyncIterator[ls_schemas.Dataset]:
        """List datasets asynchronously."""
        async for dataset in self._aget_paginated_list("/datasets", params=kwargs):
            yield ls_schemas.Dataset(**dataset)

    async def create_example(
        self,
        inputs: Dict[str, Any],
        outputs: Optional[Dict[str, Any]] = None,
        dataset_id: Optional[ID_TYPE] = None,
        dataset_name: Optional[str] = None,
        **kwargs: Any,
    ) -> ls_schemas.Example:
        """Create an example asynchronously."""
        if dataset_id is None and dataset_name is None:
            raise ValueError("Either dataset_id or dataset_name must be provided")
        if dataset_id is None:
            dataset = await self.read_dataset(dataset_name=dataset_name)
            dataset_id = dataset.id

        data = {
            "inputs": inputs,
            "outputs": outputs,
            "dataset_id": str(dataset_id),
            **kwargs,
        }
        response = await self._arequest_with_retries("POST", "/examples", json=data)
        return ls_schemas.Example(**response.json())

    async def read_example(self, example_id: ID_TYPE) -> ls_schemas.Example:
        """Read an example asynchronously."""
        response = await self._arequest_with_retries(
            "GET", f"/examples/{_as_uuid(example_id)}"
        )
        return ls_schemas.Example(**response.json())

    async def list_examples(
        self,
        dataset_id: Optional[ID_TYPE] = None,
        dataset_name: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ls_schemas.Example]:
        """List examples asynchronously."""
        params = kwargs.copy()
        if dataset_id:
            params["dataset"] = _as_uuid(dataset_id)
        elif dataset_name:
            dataset = await self.read_dataset(dataset_name=dataset_name)
            params["dataset"] = dataset.id

        async for example in self._aget_paginated_list("/examples", params=params):
            yield ls_schemas.Example(**example)

    async def create_feedback(
        self,
        run_id: Optional[ID_TYPE],
        key: str,
        score: Optional[float] = None,
        value: Optional[Any] = None,
        comment: Optional[str] = None,
        **kwargs: Any,
    ) -> ls_schemas.Feedback:
        """Create feedback asynchronously."""
        data = {
            "run_id": _ensure_uuid(run_id, accept_null=True),
            "key": key,
            "score": score,
            "value": value,
            "comment": comment,
            **kwargs,
        }
        response = await self._arequest_with_retries("POST", "/feedback", json=data)
        return ls_schemas.Feedback(**response.json())

    async def read_feedback(self, feedback_id: ID_TYPE) -> ls_schemas.Feedback:
        """Read feedback asynchronously."""
        response = await self._arequest_with_retries(
            "GET", f"/feedback/{_as_uuid(feedback_id)}"
        )
        return ls_schemas.Feedback(**response.json())

    async def list_feedback(
        self,
        run_ids: Optional[List[ID_TYPE]] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ls_schemas.Feedback]:
        """List feedback asynchronously."""
        params = kwargs.copy()
        if run_ids:
            params["run"] = [str(_as_uuid(run_id)) for run_id in run_ids]

        async for feedback in self._aget_paginated_list("/feedback", params=params):
            yield ls_schemas.Feedback(**feedback)

    async def update_feedback(
        self,
        feedback_id: ID_TYPE,
        **kwargs: Any,
    ) -> None:
        """Update feedback asynchronously."""
        await self._arequest_with_retries(
            "PATCH",
            f"/feedback/{_as_uuid(feedback_id)}",
            json=kwargs,
        )

    async def delete_feedback(self, feedback_id: ID_TYPE) -> None:
        """Delete feedback asynchronously."""
        await self._arequest_with_retries(
            "DELETE",
            f"/feedback/{_as_uuid(feedback_id)}",
        )

    async def create_dataset_split(
        self,
        dataset_id: ID_TYPE,
        split_name: str,
        example_ids: List[ID_TYPE],
    ) -> None:
        """Create a dataset split asynchronously."""
        data = {
            "split_name": split_name,
            "examples": [str(_as_uuid(id)) for id in example_ids],
        }
        await self._arequest_with_retries(
            "PUT", f"/datasets/{_as_uuid(dataset_id)}/splits", json=data
        )

    async def read_dataset_split(
        self,
        dataset_id: ID_TYPE,
        split_name: str,
    ) -> List[str]:
        """Read a dataset split asynchronously."""
        response = await self._arequest_with_retries(
            "GET",
            f"/datasets/{_as_uuid(dataset_id)}/splits",
            params={"split_name": split_name},
        )
        return response.json()

    async def list_dataset_splits(
        self,
        dataset_id: ID_TYPE,
    ) -> List[str]:
        """List dataset splits asynchronously."""
        response = await self._arequest_with_retries(
            "GET",
            f"/datasets/{_as_uuid(dataset_id)}/splits",
        )
        return response.json()

    async def delete_dataset_split(
        self,
        dataset_id: ID_TYPE,
        split_name: str,
    ) -> None:
        """Delete a dataset split asynchronously."""
        await self._arequest_with_retries(
            "DELETE",
            f"/datasets/{_as_uuid(dataset_id)}/splits/{split_name}",
        )

    async def create_annotation_queue(
        self,
        name: str,
        description: Optional[str] = None,
        **kwargs: Any,
    ) -> ls_schemas.AnnotationQueue:
        """Create an annotation queue asynchronously."""
        data = {"name": name, "description": description, **kwargs}
        response = await self._arequest_with_retries(
            "POST", "/annotation-queues", json=data
        )
        return ls_schemas.AnnotationQueue(**response.json())

    async def read_annotation_queue(
        self, queue_id: ID_TYPE
    ) -> ls_schemas.AnnotationQueue:
        """Read an annotation queue asynchronously."""
        response = await self._arequest_with_retries(
            "GET", f"/annotation-queues/{_as_uuid(queue_id)}"
        )
        return ls_schemas.AnnotationQueue(**response.json())

    async def update_annotation_queue(
        self,
        queue_id: ID_TYPE,
        name: Optional[str] = None,
        description: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Update an annotation queue asynchronously."""
        data = {
            "name": name,
            "description": description,
            **kwargs,
        }
        await self._arequest_with_retries(
            "PATCH",
            f"/annotation-queues/{_as_uuid(queue_id)}",
            json={k: v for k, v in data.items() if v is not None},
        )

    async def delete_annotation_queue(self, queue_id: ID_TYPE) -> None:
        """Delete an annotation queue asynchronously."""
        await self._arequest_with_retries(
            "DELETE",
            f"/annotation-queues/{_as_uuid(queue_id)}",
        )

    async def list_annotation_queues(
        self,
        **kwargs: Any,
    ) -> AsyncIterator[ls_schemas.AnnotationQueue]:
        """List annotation queues asynchronously."""
        async for queue in self._aget_paginated_list(
            "/annotation-queues", params=kwargs
        ):
            yield ls_schemas.AnnotationQueue(**queue)

    async def add_runs_to_annotation_queue(
        self,
        queue_id: ID_TYPE,
        run_ids: List[ID_TYPE],
    ) -> None:
        """Add runs to an annotation queue asynchronously."""
        data = [str(_as_uuid(run_id)) for run_id in run_ids]
        await self._arequest_with_retries(
            "POST",
            f"/annotation-queues/{_as_uuid(queue_id)}/runs",
            json=data,
        )

    async def list_runs_from_annotation_queue(
        self,
        queue_id: ID_TYPE,
        **kwargs: Any,
    ) -> AsyncIterator[ls_schemas.RunWithAnnotationQueueInfo]:
        """List runs from an annotation queue asynchronously."""
        async for run in self._aget_paginated_list(
            f"/annotation-queues/{_as_uuid(queue_id)}/runs", params=kwargs
        ):
            yield ls_schemas.RunWithAnnotationQueueInfo(**run)

    async def create_comparative_experiment(
        self,
        name: str,
        experiment_ids: List[ID_TYPE],
        reference_dataset_id: ID_TYPE,
        **kwargs: Any,
    ) -> ls_schemas.ComparativeExperiment:
        """Create a comparative experiment asynchronously."""
        data = {
            "name": name,
            "experiment_ids": [str(_as_uuid(id)) for id in experiment_ids],
            "reference_dataset_id": _as_uuid(reference_dataset_id),
            **kwargs,
        }
        response = await self._arequest_with_retries(
            "POST", "/datasets/comparative", json=data
        )
        return ls_schemas.ComparativeExperiment(**response.json())

    async def read_comparative_experiment(
        self, experiment_id: ID_TYPE
    ) -> ls_schemas.ComparativeExperiment:
        """Read a comparative experiment asynchronously."""
        response = await self._arequest_with_retries(
            "GET", f"/datasets/comparative/{_as_uuid(experiment_id)}"
        )
        return ls_schemas.ComparativeExperiment(**response.json())

    async def list_comparative_experiments(
        self, **kwargs: Any
    ) -> AsyncIterator[ls_schemas.ComparativeExperiment]:
        """List comparative experiments asynchronously."""
        async for experiment in self._aget_paginated_list(
            "/datasets/comparative", params=kwargs
        ):
            yield ls_schemas.ComparativeExperiment(**experiment)

    async def delete_comparative_experiment(self, experiment_id: ID_TYPE) -> None:
        """Delete a comparative experiment asynchronously."""
        await self._arequest_with_retries(
            "DELETE",
            f"/datasets/comparative/{_as_uuid(experiment_id)}",
        )

    async def create_prompt(
        self,
        name: str,
        prompt: Any,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> ls_schemas.Prompt:
        """Create a prompt asynchronously."""
        data = {
            "name": name,
            "prompt": prompt,
            "description": description,
            "tags": tags,
            **kwargs,
        }
        response = await self._arequest_with_retries("POST", "/prompts", json=data)
        return ls_schemas.Prompt(**response.json())

    async def read_prompt(self, prompt_id: ID_TYPE) -> ls_schemas.Prompt:
        """Read a prompt asynchronously."""
        response = await self._arequest_with_retries(
            "GET", f"/prompts/{_as_uuid(prompt_id)}"
        )
        return ls_schemas.Prompt(**response.json())

    async def update_prompt(
        self,
        prompt_id: ID_TYPE,
        name: Optional[str] = None,
        prompt: Optional[Any] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Update a prompt asynchronously."""
        data = {
            "name": name,
            "prompt": prompt,
            "description": description,
            "tags": tags,
            **kwargs,
        }
        await self._arequest_with_retries(
            "PATCH",
            f"/prompts/{_as_uuid(prompt_id)}",
            json={k: v for k, v in data.items() if v is not None},
        )

    async def delete_prompt(self, prompt_id: ID_TYPE) -> None:
        """Delete a prompt asynchronously."""
        await self._arequest_with_retries(
            "DELETE",
            f"/prompts/{_as_uuid(prompt_id)}",
        )

    async def list_prompts(self, **kwargs: Any) -> AsyncIterator[ls_schemas.Prompt]:
        """List prompts asynchronously."""
        async for prompt in self._aget_paginated_list("/prompts", params=kwargs):
            yield ls_schemas.Prompt(**prompt)

    async def index_dataset(
        self,
        *,
        dataset_id: ID_TYPE,
        tag: str = "latest",
        **kwargs: Any,
    ) -> None:
        """Enable dataset indexing. Examples are indexed by their inputs.

        This enables searching for similar examples by inputs with
        ``client.similar_examples()``.

        Args:
            dataset_id (UUID): The ID of the dataset to index.
            tag (str, optional): The version of the dataset to index. If 'latest'
                then any updates to the dataset (additions, updates, deletions of
                examples) will be reflected in the index.

        Returns:
            None

        Raises:
            requests.HTTPError
        """  # noqa: E501
        dataset_id = _as_uuid(dataset_id, "dataset_id")
        resp = await self._arequest_with_retries(
            "POST", f"/datasets/{dataset_id}/index", json={"tag": tag, **kwargs}
        )
        ls_utils.raise_for_status_with_text(resp)

    async def similar_examples(
        self,
        inputs: dict,
        /,
        *,
        limit: int,
        dataset_id: ID_TYPE,
        **kwargs: Any,
    ) -> List[ls_schemas.ExampleSearch]:
        r"""Retrieve the dataset examples whose inputs best match the current inputs.

        **Note**: Must have few-shot indexing enabled for the dataset. See
        ``client.index_dataset()``.

        Args:
            inputs (dict): The inputs to use as a search query. Must match the dataset
                input schema. Must be JSON serializable.
            limit (int): The maximum number of examples to return.
            dataset_id (str or UUID): The ID of the dataset to search over.
            kwargs (Any): Additional keyword args to pass as part of request body.

        Returns:
            List of ExampleSearch objects.

        Example:
            .. code-block:: python

                from langsmith import Client

                client = Client()
                await client.similar_examples(
                    {"question": "When would i use the runnable generator"},
                    limit=3,
                    dataset_id="...",
                )

            .. code-block:: pycon

                [
                    ExampleSearch(
                        inputs={'question': 'How do I cache a Chat model? What caches can I use?'},
                        outputs={'answer': 'You can use LangChain\'s caching layer for Chat Models. This can save you money by reducing the number of API calls you make to the LLM provider, if you\'re often requesting the same completion multiple times, and speed up your application.\n\n```python\n\nfrom langchain.cache import InMemoryCache\nlangchain.llm_cache = InMemoryCache()\n\n# The first time, it is not yet in cache, so it should take longer\nllm.predict(\'Tell me a joke\')\n\n```\n\nYou can also use SQLite Cache which uses a SQLite database:\n\n```python\n  rm .langchain.db\n\nfrom langchain.cache import SQLiteCache\nlangchain.llm_cache = SQLiteCache(database_path=".langchain.db")\n\n# The first time, it is not yet in cache, so it should take longer\nllm.predict(\'Tell me a joke\') \n```\n'},
                        metadata=None,
                        id=UUID('b2ddd1c4-dff6-49ae-8544-f48e39053398'),
                        dataset_id=UUID('01b6ce0f-bfb6-4f48-bbb8-f19272135d40')
                    ),
                    ExampleSearch(
                        inputs={'question': "What's a runnable lambda?"},
                        outputs={'answer': "A runnable lambda is an object that implements LangChain's `Runnable` interface and runs a callbale (i.e., a function). Note the function must accept a single argument."},
                        metadata=None,
                        id=UUID('f94104a7-2434-4ba7-8293-6a283f4860b4'),
                        dataset_id=UUID('01b6ce0f-bfb6-4f48-bbb8-f19272135d40')
                    ),
                    ExampleSearch(
                        inputs={'question': 'Show me how to use RecursiveURLLoader'},
                        outputs={'answer': 'The RecursiveURLLoader comes from the langchain.document_loaders.recursive_url_loader module. Here\'s an example of how to use it:\n\n```python\nfrom langchain.document_loaders.recursive_url_loader import RecursiveUrlLoader\n\n# Create an instance of RecursiveUrlLoader with the URL you want to load\nloader = RecursiveUrlLoader(url="https://example.com")\n\n# Load all child links from the URL page\nchild_links = loader.load()\n\n# Print the child links\nfor link in child_links:\n    print(link)\n```\n\nMake sure to replace "https://example.com" with the actual URL you want to load. The load() method returns a list of child links found on the URL page. You can iterate over this list to access each child link.'},
                        metadata=None,
                        id=UUID('0308ea70-a803-4181-a37d-39e95f138f8c'),
                        dataset_id=UUID('01b6ce0f-bfb6-4f48-bbb8-f19272135d40')
                    ),
                ]

        """  # noqa: E501
        dataset_id = _as_uuid(dataset_id, "dataset_id")
        resp = await self._arequest_with_retries(
            "POST",
            f"/datasets/{dataset_id}/search",
            json={"inputs": inputs, "limit": limit, **kwargs},
        )
        ls_utils.raise_for_status_with_text(resp)
        examples = []
        for ex in resp.json()["examples"]:
            examples.append(ls_schemas.ExampleSearch(**ex, dataset_id=dataset_id))
        return examples
