"""Schemas for the LangSmith API."""
from __future__ import annotations

import logging
import os
from concurrent.futures import Future, ThreadPoolExecutor, wait
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from uuid import UUID, uuid4

from langsmith.client import Client
from langsmith.schemas import ID_TYPE, RunBase, _coerce_req_uuid
from langsmith.utils import get_runtime_environment

logger = logging.getLogger(__name__)


def _make_thread_pool() -> ThreadPoolExecutor:
    """Ensure a thread pool exists in the current context."""
    return ThreadPoolExecutor(max_workers=1)


class RunTree(RunBase):
    """Run Schema with back-references for posting runs."""

    def __init__(
        self,
        *,
        name: str,
        id: Optional[ID_TYPE] = None,
        start_time: Optional[datetime] = None,
        parent_run: Optional[RunTree] = None,
        child_runs: Optional[List[RunTree]] = None,
        project_name: Optional[str] = None,
        project_id: Optional[ID_TYPE] = None,
        execution_order: int = 1,
        child_execution_order: Optional[int] = None,
        extra: Optional[Dict] = None,
        client: Optional[Client] = None,
        executor: Optional[ThreadPoolExecutor] = None,
        **kwargs: Any,
    ):
        _session_name = kwargs.pop("session_name", None)
        _session_id = kwargs.pop("session_id", None)
        _parent_run_id = kwargs.pop("parent_run_id", None)
        super().__init__(name=name, **kwargs)
        self.id = _coerce_req_uuid(id) if id else uuid4()
        self.start_time = start_time if start_time else datetime.utcnow()
        self.child_runs = child_runs if child_runs else []
        self.session_name = (
            project_name
            if project_name
            else (
                _session_name
                if _session_name
                else os.environ.get(
                    "LANGCHAIN_PROJECT", os.environ.get("LANGCHAIN_SESSION", "default")
                )
            )
        )
        self.session_id = project_id or _session_id
        self.execution_order = execution_order
        self.extra = extra if extra else {}
        self.child_execution_order = child_execution_order or self.execution_order
        self.parent_run = parent_run
        self._client = client if client else Client()
        self._executor = executor if executor else _make_thread_pool()
        self._futures: List[Future] = []
        if not self._executor or self._executor._shutdown:
            raise ValueError("Executor has been shutdown.")
        serialized: Optional[dict] = self.serialized
        if not serialized:
            self.serialized = {"name": self.name}
        if self.parent_run is not None:
            self.parent_run_id = self.parent_run.id
        elif _parent_run_id is not None:
            self.parent_run_id = _parent_run_id
        runtime = self.extra.setdefault("runtime", {})
        runtime.update(get_runtime_environment())
        self._ended = False

    @property
    def project_name(self) -> str:
        """Alias for session_name."""
        return self.session_name

    @property
    def project_id(self) -> Optional[ID_TYPE]:
        """Alias for session_id."""
        return self.session_id

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
        if self.parent_run is not None:
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
            project_name=self.project_name,
            client=self._client,
            executor=self._executor,
            tags=tags,
        )
        self.child_runs.append(run)
        return run

    def dict(
        self, exclude: Optional[Set[str]] = None, exclude_none: bool = False
    ) -> Dict:
        """Return a dictionary representation of the run tree."""
        exclude = exclude or set()
        exclude.update()
        run_dict = super().dict(exclude=exclude, exclude_none=exclude_none)
        if "child_runs" in run_dict:
            # If we are posting a nested run tree, parent_run_id is redundant
            exclude.add("parent_run_id")
            run_dict["child_runs"] = [
                run.dict(exclude=exclude, exclude_none=exclude_none)
                for run in run_dict["child_runs"]
            ]
        return run_dict

    def post(self, exclude_child_runs: bool = True) -> Future:
        """Post the run tree to the API asynchronously."""
        exclude = {"child_runs", "parent_run"} if exclude_child_runs else {"parent_run"}
        kwargs = self.dict(exclude=exclude, exclude_none=True)
        self._futures.append(self._executor.submit(self._client.create_run, **kwargs))
        return self._futures[-1]

    def patch(self) -> Future:
        """Patch the run tree to the API in a background thread."""
        if not self._ended:
            self.end()
        self._futures.append(
            self._executor.submit(
                self._client.update_run,
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
