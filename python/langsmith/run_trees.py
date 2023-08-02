"""Schemas for the LangSmith API."""
from __future__ import annotations

import logging
import os
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import Field, dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, cast
from uuid import UUID, uuid4

from dataclasses_json import dataclass_json

from langsmith.client import Client
from langsmith.schemas import RunBase
from langsmith.utils import get_runtime_environment

logger = logging.getLogger(__name__)


def _make_thread_pool() -> ThreadPoolExecutor:
    """Ensure a thread pool exists in the current context."""
    return ThreadPoolExecutor(max_workers=1)


@dataclass_json
@dataclass
class RunTree(RunBase):
    """Run Schema with back-references for posting runs."""

    id: UUID = field(default_factory=uuid4)
    start_time: datetime = field(default_factory=datetime.utcnow)
    parent_run: Optional["RunTree"] = field(default=None)
    child_runs: List["RunTree"] = field(default_factory=list)
    session_name: str = field(
        default_factory=lambda: os.environ.get(
            "LANGCHAIN_PROJECT",
            os.environ.get("LANGCHAIN_SESSION", "default"),
        ),
    )
    session_id: Optional[UUID] = field(default=None)
    execution_order: int = 1
    child_execution_order: int = field(default=1)
    extra: Dict = field(default_factory=dict)
    client: Client = field(default_factory=Client)
    executor: ThreadPoolExecutor = field(
        default_factory=_make_thread_pool,
    )
    _futures: List[Future] = field(default_factory=list, repr=False)

    def __post_init__(self):
        if not self.executor or self.executor._shutdown:
            raise ValueError("Executor has been shutdown.")

        if "serialized" not in self.extra:
            self.extra["serialized"] = {"name": self.name}
        if "execution_order" not in self.extra:
            self.extra["execution_order"] = 1
        if "child_execution_order" not in self.extra:
            self.extra["child_execution_order"] = self.execution_order
        if self.parent_run is not None:
            self.extra["parent_run_id"] = self.parent_run.id
        extra = self.extra.setdefault("extra", {})
        runtime = extra.setdefault("runtime", {})
        # `get_runtime_environment()` is not defined in your code snippet,
        # please replace this function with the actual one
        runtime.update(get_runtime_environment())

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
        run_id: Optional[UUID] = None,
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

    def post(self, exclude_child_runs: bool = True) -> Future:
        """Post the run tree to the API asynchronously."""
        exclude = {"child_runs"} if exclude_child_runs else None
        kwargs = self.dict(exclude=exclude, exclude_none=True)
        self._futures.append(
            self.executor.submit(
                self.client.create_run,
                **kwargs,
            )
        )
        return self._futures[-1]

    def patch(self) -> Future:
        """Patch the run tree to the API in a background thread."""
        self._futures.append(
            self.executor.submit(
                self.client.update_run,
                run_id=self.id,
                outputs=self.outputs.copy() if self.outputs else None,
                error=self.error,
                parent_run_id=self.parent_run_id,
                reference_example_id=self.reference_example_id,
            )
        )
        return self._futures[-1]

    def wait(self) -> None:
        """Wait for all _futures to complete."""
        futures = self._futures
        wait(self._futures)
        for future in futures:
            self._futures.remove(future)
