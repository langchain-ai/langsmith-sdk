"""Schemas for the LangSmith API."""
from __future__ import annotations

import logging
import warnings
from concurrent.futures import Future, ThreadPoolExecutor, wait
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, cast
from uuid import UUID, uuid4

try:
    from pydantic.v1 import (  # type: ignore[import]
        Field,
        PrivateAttr,
        root_validator,
        validator,
    )
except ImportError:
    from pydantic import Field, PrivateAttr, root_validator, validator

from langsmith import utils
from langsmith.client import ID_TYPE, Client
from langsmith.schemas import RunBase

logger = logging.getLogger(__name__)


def _make_thread_pool() -> ThreadPoolExecutor:
    """Ensure a thread pool exists in the current context."""
    return ThreadPoolExecutor(max_workers=1)


class RunTree(RunBase):
    """Run Schema with back-references for posting runs."""

    name: str
    id: UUID = Field(default_factory=uuid4)
    start_time: datetime = Field(default_factory=datetime.utcnow)
    parent_run: Optional[RunTree] = Field(default=None, exclude=True)
    child_runs: List[RunTree] = Field(
        default_factory=list,
        exclude={"__all__": {"parent_run_id"}},
    )
    session_name: str = Field(
        default_factory=lambda: utils.get_tracer_project(),
        alias="project_name",
    )
    session_id: Optional[UUID] = Field(default=None, alias="project_id")
    execution_order: int = 1
    child_execution_order: int = Field(default=1, exclude=True)
    extra: Dict = Field(default_factory=dict)
    client: Client = Field(default_factory=Client, exclude=True)
    executor: ThreadPoolExecutor = Field(
        default_factory=_make_thread_pool, exclude=True
    )
    _futures: List[Future] = PrivateAttr(default_factory=list)

    class Config:
        arbitrary_types_allowed = True
        allow_population_by_field_name = True

    @validator("executor", pre=True)
    def validate_executor(cls, v: Optional[ThreadPoolExecutor]) -> ThreadPoolExecutor:
        """Ensure the executor is running."""
        if v is None:
            return _make_thread_pool()
        if v._shutdown:
            raise ValueError("Executor has been shutdown.")
        return v

    @validator("client", pre=True)
    def validate_client(cls, v: Optional[Client]) -> Client:
        """Ensure the client is specified."""
        if v is None:
            return Client()
        return v

    @root_validator(pre=True)
    def infer_defaults(cls, values: dict) -> dict:
        """Assign name to the run."""
        if "serialized" not in values:
            values["serialized"] = {"name": values["name"]}
        if "execution_order" not in values:
            values["execution_order"] = 1
        if "child_execution_order" not in values:
            values["child_execution_order"] = values["execution_order"]
        if values.get("parent_run") is not None:
            values["parent_run_id"] = values["parent_run"].id
        cast(dict, values.setdefault("extra", {}))
        return values

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
        run_type: str,
        *,
        run_id: Optional[ID_TYPE] = None,
        serialized: Optional[Dict] = None,
        inputs: Optional[Dict] = None,
        outputs: Optional[Dict] = None,
        error: Optional[str] = None,
        reference_example_id: Optional[UUID] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        tags: Optional[List[str]] = None,
        extra: Optional[Dict] = None,
    ) -> RunTree:
        """Add a child run to the run tree."""
        execution_order = self.child_execution_order + 1
        self.child_execution_order += 1
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
            end_time=end_time,
            execution_order=execution_order,
            child_execution_order=execution_order,
            extra=extra or {},
            parent_run=self,
            session_name=self.session_name,
            client=self.client,
            executor=self.executor,
            tags=tags,
        )
        self.child_runs.append(run)
        return run

    def _execute(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.exception(e)
            raise e

    def post(self, exclude_child_runs: bool = True) -> Future:
        """Post the run tree to the API asynchronously."""
        kwargs = self.dict(exclude={"child_runs"}, exclude_none=True)
        self._futures.append(
            self.executor.submit(
                self._execute,
                self.client.create_run,
                **kwargs,
            )
        )
        if not exclude_child_runs:
            warnings.warn(
                "Posting with exclude_child_runs=False is deprecated"
                " and will be removed in a future version.",
                DeprecationWarning,
            )
            for child_run in self.child_runs:
                self._futures.append(child_run.post(exclude_child_runs=False))
        return self._futures[-1]

    def patch(self) -> Future:
        """Patch the run tree to the API in a background thread."""
        self._futures.append(
            self.executor.submit(
                self._execute,
                self.client.update_run,
                run_id=self.id,
                outputs=self.outputs.copy() if self.outputs else None,
                error=self.error,
                parent_run_id=self.parent_run_id,
                reference_example_id=self.reference_example_id,
                end_time=self.end_time,
            )
        )
        return self._futures[-1]

    def wait(self) -> None:
        """Wait for all _futures to complete."""
        futures = self._futures
        wait(self._futures)
        for future in futures:
            self._futures.remove(future)
