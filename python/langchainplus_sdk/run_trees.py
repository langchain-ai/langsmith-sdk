"""Schemas for the langchainplus API."""
from __future__ import annotations

import logging
import os
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from uuid import UUID, uuid4

from pydantic import Field, root_validator
from tenacity import (
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from langchainplus_sdk.schemas import RunBase, RunTypeEnum, RunUpdate
from langchainplus_sdk.utils import (
    LangChainPlusAPIError,
    get_runtime_environment,
    request_with_retries,
)

logger = logging.getLogger(__name__)
_THREAD_POOL_EXECUTOR: Optional[ThreadPoolExecutor] = None


def _ensure_thread_pool() -> ThreadPoolExecutor:
    """Ensure a thread pool exists in the current context."""
    global _THREAD_POOL_EXECUTOR
    if _THREAD_POOL_EXECUTOR is None:
        _THREAD_POOL_EXECUTOR = ThreadPoolExecutor(max_workers=1)
    return _THREAD_POOL_EXECUTOR


def await_all_runs() -> None:
    """Flush the thread pool."""
    global _THREAD_POOL_EXECUTOR
    if _THREAD_POOL_EXECUTOR is not None:
        _THREAD_POOL_EXECUTOR.shutdown(wait=True)
        _THREAD_POOL_EXECUTOR = None


def _default_retry_config() -> Dict[str, Any]:
    return dict(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=10),
        retry=retry_if_exception_type(LangChainPlusAPIError),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )


class RunTree(RunBase):
    """Run Schema with back-references for posting runs."""

    name: str
    id: Optional[UUID] = Field(default_factory=uuid4)
    parent_run: Optional[RunTree] = Field(default=None, exclude=True)
    child_runs: List[RunTree] = Field(
        default_factory=list, exclude={"__all__": {"parent_run_id"}}
    )
    session_name: str = Field(default="default")
    session_id: Optional[UUID] = Field(default=None)
    execution_order: int = 1
    child_execution_order: int = 1
    api_url: str = Field(
        default=os.environ.get("LANGCHAIN_ENDPOINT", "http://localhost:1984"),
        exclude=True,
    )
    api_key: Optional[str] = Field(
        default=os.environ.get("LANGCHAIN_API_KEY"), exclude=True
    )
    retry_config: Dict[str, Any] = Field(
        default_factory=_default_retry_config, exclude=True
    )

    @root_validator(pre=True)
    def infer_defaults(cls, values: dict) -> dict:
        """Assign name to the run."""
        if "name" not in values:
            if "serialized" not in values:
                raise ValueError("Must provide either name or serialized.")
            if "name" not in values["serialized"]:
                raise ValueError(
                    "Must provide either name or serialized with a name attribute."
                )
            values["name"] = values["serialized"]["name"]
        elif "serialized" not in values:
            values["serialized"] = {"name": values["name"]}
        if "execution_order" not in values:
            values["execution_order"] = 1
        if "child_execution_order" not in values:
            values["child_execution_order"] = values["execution_order"]
        if values.get("session_name") is None:
            values["session_name"] = os.environ.get("LANGCHAIN_SESSION", "default")
        if values.get("parent_run") is not None:
            values["parent_run_id"] = values["parent_run"].id
        extra = values.get("extra", {})
        extra["runtime"] = get_runtime_environment()
        values["extra"] = extra
        return values

    @property
    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    def end(
        self,
        *,
        outputs: Optional[Dict] = None,
        error: Optional[str] = None,
        end_time: Optional[datetime] = None,
    ) -> None:
        """Set the end time of the run and all child runs."""
        self.end_time = end_time or datetime.utcnow()
        if outputs is not None:
            self.outputs = outputs
        if error is not None:
            self.error = error
        if self.parent_run:
            self.parent_run.child_execution_order = max(
                self.parent_run.child_execution_order,
                self.child_execution_order,
            )

    def create_child(
        self,
        name: str,
        run_type: Union[str, RunTypeEnum],
        *,
        run_id: Optional[UUID] = None,
        serialized: Optional[Dict] = None,
        inputs: Optional[Dict] = None,
        outputs: Optional[Dict] = None,
        error: Optional[str] = None,
        reference_example_id: Optional[UUID] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        extra: Optional[Dict] = None,
    ) -> RunTree:
        """Add a child run to the run tree."""
        execution_order = self.child_execution_order + 1
        serialized_ = serialized or {"name": name}
        run = RunTree(
            name=name,
            id=run_id or uuid4(),
            serialized=serialized_,
            inputs=inputs or {},
            outputs=outputs or {},
            error=error,
            run_type=run_type,
            reference_example_id=reference_example_id,
            start_time=start_time or datetime.utcnow(),
            end_time=end_time or datetime.utcnow(),
            execution_order=execution_order,
            child_execution_order=execution_order,
            extra=extra or {},
            parent_run=self,
            session_name=self.session_name,
            api_url=self.api_url,
            api_key=self.api_key,
        )
        self.child_runs.append(run)
        return run

    def _post(self, data: str) -> None:
        """Post the run tree to the API."""
        request_with_retries(
            "post",
            f"{self.api_url}/runs",
            request_kwargs={
                "data": data,
                "headers": self._headers,
            },
            retry_config=self.retry_config,
        )

    def post(self, exclude_child_runs: bool = True) -> Future:
        """Post the run tree to the API asynchronously."""
        executor = _ensure_thread_pool()
        exclude = {"child_runs"} if exclude_child_runs else None
        data = self.json(exclude=exclude, exclude_none=True)
        return executor.submit(self._post, data=data)

    def _patch(self, data: str) -> None:
        """Patch the run tree to the API."""
        request_with_retries(
            "patch",
            f"{self.api_url}/runs/{self.id}",
            request_kwargs={
                "data": data,
                "headers": self._headers,
            },
            retry_config=self.retry_config,
        )

    def patch(self) -> Future:
        """Patch the run tree to the API in a background thread."""
        executor = _ensure_thread_pool()
        run_update = RunUpdate(**self.dict(exclude_none=True))
        data = run_update.json(exclude_none=True)
        return executor.submit(self._patch, data=data)
