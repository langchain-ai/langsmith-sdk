"""Schemas for the LangSmith API."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Union, cast
from uuid import UUID, uuid4

try:
    from pydantic.v1 import Field, root_validator, validator  # type: ignore[import]
except ImportError:
    from pydantic import Field, root_validator, validator

from langsmith import schemas as ls_schemas
from langsmith import utils
from langsmith.client import ID_TYPE, RUN_TYPE_T, Client

logger = logging.getLogger(__name__)


class RunTree(ls_schemas.RunBase):
    """Run Schema with back-references for posting runs."""

    name: str
    id: UUID = Field(default_factory=uuid4)
    run_type: str = Field(default="chain")
    start_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
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
    extra: Dict = Field(default_factory=dict)
    client: Client = Field(default_factory=Client, exclude=True)
    dotted_order: str = Field(
        default="", description="The order of the run in the tree."
    )
    trace_id: UUID = Field(default="", description="The trace id of the run.")

    class Config:
        """Pydantic model configuration."""

        arbitrary_types_allowed = True
        allow_population_by_field_name = True
        extra = "allow"

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
        if values.get("parent_run") is not None:
            values["parent_run_id"] = values["parent_run"].id
        if "id" not in values:
            values["id"] = uuid4()
        if "trace_id" not in values:
            if "parent_run" in values:
                values["trace_id"] = values["parent_run"].trace_id
            else:
                values["trace_id"] = values["id"]
        cast(dict, values.setdefault("extra", {}))
        return values

    @root_validator(pre=False)
    def ensure_dotted_order(cls, values: dict) -> dict:
        """Ensure the dotted order of the run."""
        current_dotted_order = values.get("dotted_order")
        if current_dotted_order and current_dotted_order.strip():
            return values
        current_dotted_order = values["start_time"].strftime("%Y%m%dT%H%M%S%fZ") + str(
            values["id"]
        )
        if values["parent_run"]:
            values["dotted_order"] = (
                values["parent_run"].dotted_order + "." + current_dotted_order
            )
        else:
            values["dotted_order"] = current_dotted_order
        return values

    def add_tags(self, tags: Union[Sequence[str], str]) -> None:
        """Add tags to the run."""
        if isinstance(tags, str):
            tags = [tags]
        if self.tags is None:
            self.tags = []
        self.tags.extend(tags)

    def add_metadata(self, metadata: Dict[str, Any]) -> None:
        """Add metadata to the run."""
        if self.extra is None:
            self.extra = {}
        metadata_: dict = self.extra.setdefault("metadata", {})
        metadata_.update(metadata)

    def add_event(
        self,
        events: Union[
            ls_schemas.RunEvent,
            Sequence[ls_schemas.RunEvent],
            Sequence[dict],
            dict,
            str,
        ],
    ) -> None:
        """Add an event to the list of events.

        Args:
            events (Union[ls_schemas.RunEvent, Sequence[ls_schemas.RunEvent],
                    Sequence[dict], dict, str]):
                The event(s) to be added. It can be a single event, a sequence
                    of events,
                a sequence of dictionaries, a dictionary, or a string.

        Returns:
            None
        """
        if self.events is None:
            self.events = []
        if isinstance(events, dict):
            self.events.append(events)  # type: ignore[arg-type]
        elif isinstance(events, str):
            self.events.append(
                {
                    "name": "event",
                    "time": datetime.now(timezone.utc).isoformat(),
                    "message": events,
                }
            )
        else:
            self.events.extend(events)  # type: ignore[arg-type]

    def end(
        self,
        *,
        outputs: Optional[Dict] = None,
        error: Optional[str] = None,
        end_time: Optional[datetime] = None,
        events: Optional[Sequence[ls_schemas.RunEvent]] = None,
    ) -> None:
        """Set the end time of the run and all child runs."""
        self.end_time = end_time or datetime.now(timezone.utc)
        if outputs is not None:
            self.outputs = outputs
        if error is not None:
            self.error = error
        if events is not None:
            self.add_event(events)

    def create_child(
        self,
        name: str,
        run_type: RUN_TYPE_T = "chain",
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
            start_time=start_time or datetime.now(timezone.utc),
            end_time=end_time,
            extra=extra or {},
            parent_run=self,
            session_name=self.session_name,
            client=self.client,
            tags=tags,
        )
        self.child_runs.append(run)
        return run

    def _get_dicts_safe(self):
        try:
            return self.dict(exclude={"child_runs"}, exclude_none=True)
        except TypeError:
            # Things like generators cannot be copied
            self_dict = self.dict(
                exclude={"child_runs", "inputs", "outputs"}, exclude_none=True
            )
            if self.inputs:
                # shallow copy
                self_dict["inputs"] = self.inputs.copy()
            if self.outputs:
                # shallow copy
                self_dict["outputs"] = self.outputs.copy()
            return self_dict

    def post(self, exclude_child_runs: bool = True) -> None:
        """Post the run tree to the API asynchronously."""
        kwargs = self._get_dicts_safe()
        self.client.create_run(**kwargs)
        if not exclude_child_runs:
            for child_run in self.child_runs:
                child_run.post(exclude_child_runs=False)

    def patch(self) -> None:
        """Patch the run tree to the API in a background thread."""
        self.client.update_run(
            run_id=self.id,
            outputs=self.outputs.copy() if self.outputs else None,
            error=self.error,
            parent_run_id=self.parent_run_id,
            reference_example_id=self.reference_example_id,
            end_time=self.end_time,
            dotted_order=self.dotted_order,
            trace_id=self.trace_id,
            events=self.events,
            tags=self.tags,
            extra=self.extra,
        )

    def wait(self) -> None:
        """Wait for all _futures to complete."""
        pass

    def get_url(self) -> str:
        """Return the URL of the run."""
        return self.client.get_run_url(run=self)
