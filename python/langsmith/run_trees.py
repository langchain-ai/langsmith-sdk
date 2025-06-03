"""Schemas for the LangSmith API."""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, Union, cast
from uuid import UUID, uuid4

try:
    from pydantic.v1 import Field, root_validator  # type: ignore[import]
except ImportError:
    pass

import threading
import urllib.parse

from langsmith import schemas as ls_schemas
from langsmith import utils
from langsmith.client import ID_TYPE, RUN_TYPE_T, Client, _dumps_json, _ensure_uuid

logger = logging.getLogger(__name__)

LANGSMITH_PREFIX = "langsmith-"
LANGSMITH_DOTTED_ORDER = sys.intern(f"{LANGSMITH_PREFIX}trace")
LANGSMITH_DOTTED_ORDER_BYTES = LANGSMITH_DOTTED_ORDER.encode("utf-8")
LANGSMITH_METADATA = sys.intern(f"{LANGSMITH_PREFIX}metadata")
LANGSMITH_TAGS = sys.intern(f"{LANGSMITH_PREFIX}tags")
LANGSMITH_PROJECT = sys.intern(f"{LANGSMITH_PREFIX}project")
OVERRIDE_OUTPUTS = sys.intern("__omit_auto_outputs")
NOT_PROVIDED = cast(None, object())
_CLIENT: Optional[Client] = None
_LOCK = threading.Lock()  # Keeping around for a while for backwards compat


# Note, this is called directly by langchain. Do not remove.


def get_cached_client(**init_kwargs: Any) -> Client:
    global _CLIENT
    if _CLIENT is None:
        if _CLIENT is None:
            _CLIENT = Client(**init_kwargs)
    return _CLIENT


def validate_extracted_usage_metadata(
    data: ls_schemas.ExtractedUsageMetadata,
) -> ls_schemas.ExtractedUsageMetadata:
    """Validate that the dict only contains allowed keys."""
    allowed_keys = {
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "input_token_details",
        "output_token_details",
        "input_cost",
        "output_cost",
        "total_cost",
        "input_cost_details",
        "output_cost_details",
    }

    extra_keys = set(data.keys()) - allowed_keys
    if extra_keys:
        raise ValueError(f"Unexpected keys in usage metadata: {extra_keys}")
    return data  # type: ignore


@dataclass
class RunTree(ls_schemas.RunBase):
    """Run Schema with back-references for posting runs."""

    name: str = "Unnamed"
    id: UUID = field(default_factory=uuid4)
    run_type: str = "chain"
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    # Note: no longer set.
    parent_run: Optional[RunTree] = field(default=None, init=False)
    parent_dotted_order: Optional[str] = field(default=None, init=False)
    child_runs: list[RunTree] = field(default_factory=list, init=False)
    session_name: str = field(
        default_factory=lambda: utils.get_tracer_project() or "default"
    )
    session_id: Optional[UUID] = None
    extra: dict = field(default_factory=dict)
    tags: Optional[list[str]] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    """List of events associated with the run, like
    start and end events."""
    ls_client: Optional[Any] = field(default=None, init=False)
    dotted_order: str = ""
    trace_id: UUID = field(default_factory=uuid4)  # type: ignore
    dangerously_allow_filesystem: Optional[bool] = False

    def __init__(self, **kwargs):
        """Initialize RunTree with backwards compatibility for 'client' parameter."""
        # Handle backwards compatibility for 'client' parameter
        if "client" in kwargs:
            kwargs["ls_client"] = kwargs.pop("client")
        if "_client" in kwargs:
            kwargs["ls_client"] = kwargs.pop("_client")
        if "project_name" in kwargs:
            kwargs["session_name"] = kwargs.pop("project_name")
        if "project_id" in kwargs:
            kwargs["session_id"] = kwargs.pop("project_id")

        # Extract parent_run if provided
        parent_run = kwargs.pop("parent_run", None)

        # Set defaults for required fields if not provided
        if "name" not in kwargs:
            kwargs["name"] = "Unnamed"
        if "id" not in kwargs:
            kwargs["id"] = uuid4()
        if "run_type" not in kwargs:
            kwargs["run_type"] = "chain"
        if "start_time" not in kwargs:
            kwargs["start_time"] = datetime.now(timezone.utc)
        if "extra" not in kwargs:
            kwargs["extra"] = {}
        if "tags" not in kwargs:
            kwargs["tags"] = []
        if "events" not in kwargs or kwargs["events"] is None:
            kwargs["events"] = []
        if "session_name" not in kwargs:
            kwargs["session_name"] = utils.get_tracer_project() or "default"
        if "trace_id" not in kwargs:
            kwargs["trace_id"] = kwargs.get("id", uuid4())
        if "dangerously_allow_filesystem" not in kwargs:
            kwargs["dangerously_allow_filesystem"] = False
        if "inputs" not in kwargs:
            kwargs["inputs"] = {}
        if "outputs" not in kwargs:
            kwargs["outputs"] = {}
        if "attachments" not in kwargs:
            kwargs["attachments"] = {}

        # Handle name inference from serialized
        if (
            "serialized" in kwargs
            and kwargs["serialized"] is not None
            and kwargs["name"] == "Unnamed"
        ):
            serialized = kwargs["serialized"]
            if "name" in serialized:
                kwargs["name"] = serialized["name"]
            elif "id" in serialized:
                kwargs["name"] = serialized["id"][-1]

        # Extract fields that are not part of the parent class
        ls_client = kwargs.pop("ls_client", None)
        session_name = kwargs.pop(
            "session_name", utils.get_tracer_project() or "default"
        )
        session_id = kwargs.pop("session_id", None)

        # Extract RunTree-specific fields for later assignment
        trace_id = kwargs.pop("trace_id", kwargs.get("id", uuid4()))
        dotted_order = kwargs.pop("dotted_order", "")
        dangerously_allow_filesystem = kwargs.pop("dangerously_allow_filesystem", False)

        # Remove any unknown kwargs that aren't part of RunBase
        runbase_fields = {
            "id",
            "name",
            "start_time",
            "run_type",
            "end_time",
            "extra",
            "error",
            "serialized",
            "events",
            "inputs",
            "outputs",
            "reference_example_id",
            "parent_run_id",
            "tags",
            "attachments",
        }
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in runbase_fields}

        # Call parent constructors with only RunBase fields
        super().__init__(**filtered_kwargs)

        # Set RunTree-specific fields
        self.session_name = session_name
        self.session_id = session_id
        self.trace_id = trace_id
        self.dotted_order = dotted_order
        self.dangerously_allow_filesystem = dangerously_allow_filesystem

        # Initialize fields not in the dataclass
        self.parent_run = None
        self.parent_dotted_order = None
        self.child_runs = []
        self.ls_client = ls_client

        # Set parent run if provided
        if parent_run is not None:
            self.set_parent_run(parent_run)

        # Handle dotted order
        self._ensure_dotted_order()

    def _ensure_dotted_order(self) -> None:
        """Ensure the dotted order of the run."""
        if self.dotted_order and self.dotted_order.strip():
            return
        current_dotted_order = _create_current_dotted_order(self.start_time, self.id)
        if self.parent_dotted_order is not None:
            self.dotted_order = self.parent_dotted_order + "." + current_dotted_order
        else:
            self.dotted_order = current_dotted_order

    def set_parent_run(self, parent_run: Optional[RunTree]) -> None:
        """Set the parent run and update related fields."""
        self.parent_run = parent_run
        if parent_run is not None:
            self.parent_run_id = parent_run.id
            self.parent_dotted_order = parent_run.dotted_order
            self.trace_id = parent_run.trace_id
            self._ensure_dotted_order()

    @property
    def client(self) -> Client:
        """Return the client."""
        # Lazily load the client
        # If you never use this for API calls, it will never be loaded
        if self.ls_client is None:
            self.ls_client = get_cached_client()
        return self.ls_client

    @property
    def _client(self) -> Optional[Client]:
        # For backwards compat
        return self.ls_client

    def __setattr__(self, name, value):
        """Set the _client specially."""
        # For backwards compat
        if name == "_client":
            self.ls_client = value
        else:
            return super().__setattr__(name, value)

    def set(
        self,
        *,
        inputs: Optional[Mapping[str, Any]] = NOT_PROVIDED,
        outputs: Optional[Mapping[str, Any]] = NOT_PROVIDED,
        tags: Optional[Sequence[str]] = NOT_PROVIDED,
        metadata: Optional[Mapping[str, Any]] = NOT_PROVIDED,
        usage_metadata: Optional[ls_schemas.ExtractedUsageMetadata] = NOT_PROVIDED,
    ) -> None:
        """Set the inputs, outputs, tags, and metadata of the run.

        If performed, this will override the default behavior of the
        end() method to ignore new outputs (that would otherwise be added)
        by the @traceable decorator.

        If your LangChain or LangGraph versions are sufficiently up-to-date,
        this will also override the default behavior LangChainTracer.

        Args:
            inputs: The inputs to set.
            outputs: The outputs to set.
            tags: The tags to set.
            metadata: The metadata to set.
            usage_metadata: Usage information to set.

        Returns:
            None
        """
        if tags is not NOT_PROVIDED:
            self.tags = list(tags)
        if metadata is not NOT_PROVIDED:
            self.extra.setdefault("metadata", {}).update(metadata or {})
        if inputs is not NOT_PROVIDED:
            # Used by LangChain core to determine whether to
            # re-upload the inputs upon run completion
            self.extra["inputs_is_truthy"] = False
            if inputs is None:
                self.inputs = {}
            else:
                self.inputs = dict(inputs)
        if outputs is not NOT_PROVIDED:
            self.extra[OVERRIDE_OUTPUTS] = True
            if outputs is None:
                self.outputs = {}
            else:
                self.outputs = dict(outputs)
        if usage_metadata is not NOT_PROVIDED:
            self.extra.setdefault("metadata", {})["usage_metadata"] = (
                validate_extracted_usage_metadata(usage_metadata)
            )

    def add_tags(self, tags: Union[Sequence[str], str]) -> None:
        """Add tags to the run."""
        if isinstance(tags, str):
            tags = [tags]
        if self.tags is None:
            self.tags = []
        self.tags.extend(tags)

    def add_metadata(self, metadata: dict[str, Any]) -> None:
        """Add metadata to the run."""
        if self.extra is None:
            self.extra = {}
        metadata_: dict = cast(dict, self.extra).setdefault("metadata", {})
        metadata_.update(metadata)

    def add_outputs(self, outputs: dict[str, Any]) -> None:
        """Upsert the given outputs into the run.

        Args:
            outputs (Dict[str, Any]): A dictionary containing the outputs to be added.

        Returns:
            None
        """
        if self.outputs is None:
            self.outputs = {}
        self.outputs.update(outputs)

    def add_inputs(self, inputs: dict[str, Any]) -> None:
        """Upsert the given outputs into the run.

        Args:
            outputs (Dict[str, Any]): A dictionary containing the outputs to be added.

        Returns:
            None
        """
        if self.inputs is None:
            self.inputs = {}
        self.inputs.update(inputs)
        # Set to False so LangChain things it needs to
        # re-upload inputs
        self.extra["inputs_is_truthy"] = False

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
                of events, a sequence of dictionaries, a dictionary, or a string.

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
        outputs: Optional[dict] = None,
        error: Optional[str] = None,
        end_time: Optional[datetime] = None,
        events: Optional[Sequence[ls_schemas.RunEvent]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Set the end time of the run and all child runs."""
        self.end_time = end_time or datetime.now(timezone.utc)
        # We've already 'set' the outputs, so ignore
        # the ones that are automatically included
        if not self.extra.get(OVERRIDE_OUTPUTS):
            if outputs is not None:
                if not self.outputs:
                    self.outputs = outputs
                else:
                    self.outputs.update(outputs)
        if error is not None:
            self.error = error
        if events is not None:
            self.add_event(events)
        if metadata is not None:
            self.add_metadata(metadata)

    def create_child(
        self,
        name: str,
        run_type: RUN_TYPE_T = "chain",
        *,
        run_id: Optional[ID_TYPE] = None,
        serialized: Optional[dict] = None,
        inputs: Optional[dict] = None,
        outputs: Optional[dict] = None,
        error: Optional[str] = None,
        reference_example_id: Optional[UUID] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        tags: Optional[list[str]] = None,
        extra: Optional[dict] = None,
        attachments: Optional[ls_schemas.Attachments] = None,
    ) -> RunTree:
        """Add a child run to the run tree."""
        serialized_ = serialized or {"name": name}
        run = RunTree(
            name=name,
            id=_ensure_uuid(run_id),
            run_type=run_type,
            start_time=start_time or datetime.now(timezone.utc),
            end_time=end_time,
            extra=extra or {},
            session_name=self.session_name,
            dangerously_allow_filesystem=self.dangerously_allow_filesystem,
            serialized=serialized_,
            inputs=inputs or {},
            outputs=outputs or {},
            error=error,
            reference_example_id=reference_example_id,
            tags=tags,
            attachments=attachments or {},  # type: ignore
        )
        # Set the parent after initialization
        run.set_parent_run(self)
        run.ls_client = self.ls_client
        self.child_runs.append(run)
        return run

    def _get_dicts_safe(self):
        # Things like generators cannot be copied
        self_dict = self.model_dump(
            exclude={"child_runs", "inputs", "outputs"}, exclude_none=True
        )
        if self.inputs is not None:
            # shallow copy. deep copying will occur in the client
            self_dict["inputs"] = self.inputs.copy()
        if self.outputs is not None:
            # shallow copy; deep copying will occur in the client
            self_dict["outputs"] = self.outputs.copy()
        return self_dict

    def post(self, exclude_child_runs: bool = True) -> None:
        """Post the run tree to the API asynchronously."""
        kwargs = self._get_dicts_safe()
        self.client.create_run(**kwargs)
        if attachments := kwargs.get("attachments"):
            keys = [str(name) for name in attachments]
            self.events.append(
                {
                    "name": "uploaded_attachment",
                    "time": datetime.now(timezone.utc).isoformat(),
                    "message": set(keys),
                }
            )
        if not exclude_child_runs:
            for child_run in self.child_runs:
                child_run.post(exclude_child_runs=False)

    def patch(self) -> None:
        """Patch the run tree to the API in a background thread."""
        if not self.end_time:
            self.end()
        attachments = {
            a: v for a, v in self.attachments.items() if isinstance(v, tuple)
        }
        try:
            # Avoid loading the same attachment twice
            if attachments:
                uploaded = next(
                    (
                        ev
                        for ev in self.events
                        if ev.get("name") == "uploaded_attachment"
                    ),
                    None,
                )
                if uploaded:
                    attachments = {
                        a: v
                        for a, v in attachments.items()
                        if a not in uploaded["message"]
                    }
        except Exception as e:
            logger.warning(f"Error filtering attachments to upload: {e}")
        self.client.update_run(
            name=self.name,
            run_id=self.id,
            inputs=self.inputs.copy() if self.inputs else None,
            outputs=self.outputs.copy() if self.outputs else None,
            error=self.error,
            parent_run_id=self.parent_run_id,
            session_name=self.session_name,
            reference_example_id=self.reference_example_id,
            end_time=self.end_time,
            dotted_order=self.dotted_order,
            trace_id=self.trace_id,
            events=self.events,
            tags=self.tags,
            extra=self.extra,
            attachments=attachments,
        )

    def wait(self) -> None:
        """Wait for all _futures to complete."""
        pass

    def get_url(self) -> str:
        """Return the URL of the run."""
        return self.client.get_run_url(run=self)

    @classmethod
    def from_dotted_order(
        cls,
        dotted_order: str,
        **kwargs: Any,
    ) -> RunTree:
        """Create a new 'child' span from the provided dotted order.

        Returns:
            RunTree: The new span.
        """
        headers = {
            LANGSMITH_DOTTED_ORDER: dotted_order,
        }
        return cast(RunTree, cls.from_headers(headers, **kwargs))  # type: ignore[arg-type]

    @classmethod
    def from_runnable_config(
        cls,
        config: Optional[dict],
        **kwargs: Any,
    ) -> Optional[RunTree]:
        """Create a new 'child' span from the provided runnable config.

        Requires langchain to be installed.

        Returns:
            Optional[RunTree]: The new span or None if
                no parent span information is found.
        """
        try:
            from langchain_core.callbacks.manager import (
                AsyncCallbackManager,
                CallbackManager,
            )
            from langchain_core.runnables import RunnableConfig, ensure_config
            from langchain_core.tracers.langchain import LangChainTracer
        except ImportError as e:
            raise ImportError(
                "RunTree.from_runnable_config requires langchain-core to be installed. "
                "You can install it with `pip install langchain-core`."
            ) from e
        if config is None:
            config_ = ensure_config(
                cast(RunnableConfig, config) if isinstance(config, dict) else None
            )
        else:
            config_ = cast(RunnableConfig, config)

        if (
            (cb := config_.get("callbacks"))
            and isinstance(cb, (CallbackManager, AsyncCallbackManager))
            and cb.parent_run_id
            and (
                tracer := next(
                    (t for t in cb.handlers if isinstance(t, LangChainTracer)),
                    None,
                )
            )
        ):
            if (run := tracer.run_map.get(str(cb.parent_run_id))) and run.dotted_order:
                dotted_order = run.dotted_order
                kwargs["run_type"] = run.run_type
                kwargs["inputs"] = run.inputs
                kwargs["outputs"] = run.outputs
                kwargs["start_time"] = run.start_time
                kwargs["end_time"] = run.end_time
                kwargs["tags"] = sorted(set(run.tags or [] + kwargs.get("tags", [])))
                kwargs["name"] = run.name
                extra_ = kwargs.setdefault("extra", {})
                metadata_ = extra_.setdefault("metadata", {})
                metadata_.update(run.metadata)
            elif hasattr(tracer, "order_map") and cb.parent_run_id in tracer.order_map:
                dotted_order = tracer.order_map[cb.parent_run_id][1]
            else:
                return None
            kwargs["client"] = tracer.client
            kwargs["project_name"] = tracer.project_name
            return RunTree.from_dotted_order(dotted_order, **kwargs)
        return None

    @classmethod
    def from_headers(
        cls, headers: Mapping[Union[str, bytes], Union[str, bytes]], **kwargs: Any
    ) -> Optional[RunTree]:
        """Create a new 'parent' span from the provided headers.

        Extracts parent span information from the headers and creates a new span.
        Metadata and tags are extracted from the baggage header.
        The dotted order and trace id are extracted from the trace header.

        Returns:
            Optional[RunTree]: The new span or None if
                no parent span information is found.
        """
        init_args = kwargs.copy()

        langsmith_trace = cast(Optional[str], headers.get(LANGSMITH_DOTTED_ORDER))
        if not langsmith_trace:
            langsmith_trace_bytes = cast(
                Optional[bytes], headers.get(LANGSMITH_DOTTED_ORDER_BYTES)
            )
            if not langsmith_trace_bytes:
                return  # type: ignore[return-value]
            langsmith_trace = langsmith_trace_bytes.decode("utf-8")

        parent_dotted_order = langsmith_trace.strip()
        parsed_dotted_order = _parse_dotted_order(parent_dotted_order)
        trace_id = parsed_dotted_order[0][1]
        init_args["trace_id"] = trace_id
        init_args["id"] = parsed_dotted_order[-1][1]
        init_args["dotted_order"] = parent_dotted_order
        if len(parsed_dotted_order) >= 2:
            # Has a parent
            init_args["parent_run_id"] = parsed_dotted_order[-2][1]
        # All placeholders. We assume the source process
        # handles the life-cycle of the run.
        init_args["start_time"] = init_args.get("start_time") or datetime.now(
            timezone.utc
        )
        init_args["run_type"] = init_args.get("run_type") or "chain"
        init_args["name"] = init_args.get("name") or "parent"

        baggage = _Baggage.from_headers(headers)
        if baggage.metadata or baggage.tags:
            init_args["extra"] = init_args.setdefault("extra", {})
            init_args["extra"]["metadata"] = init_args["extra"].setdefault(
                "metadata", {}
            )
            metadata = {**baggage.metadata, **init_args["extra"]["metadata"]}
            init_args["extra"]["metadata"] = metadata
            tags = sorted(set(baggage.tags + init_args.get("tags", [])))
            init_args["tags"] = tags
            if baggage.project_name:
                init_args["project_name"] = baggage.project_name

        return RunTree(**init_args)

    def to_headers(self) -> dict[str, str]:
        """Return the RunTree as a dictionary of headers."""
        headers = {}
        if self.trace_id:
            headers[f"{LANGSMITH_DOTTED_ORDER}"] = self.dotted_order
        baggage = _Baggage(
            metadata=self.extra.get("metadata", {}),
            tags=self.tags,
            project_name=self.session_name,
        )
        headers["baggage"] = baggage.to_header()
        return headers

    def dict(self, **kwargs):
        """Backwards compatibility method for Pydantic's dict() method."""
        # Always exclude certain fields by default
        exclude = kwargs.get("exclude", set()) or set()
        if isinstance(exclude, (list, tuple)):
            exclude = set(exclude)
        exclude.update({"parent_run", "ls_client"})
        kwargs["exclude"] = exclude
        return self.model_dump(**kwargs)

    def json(self, **kwargs):
        """Backwards compatibility method for Pydantic's json() method."""
        import json

        return json.dumps(self.dict(**kwargs), default=str)

    def __repr__(self):
        """Return a string representation of the RunTree object."""
        return (
            f"RunTree(id={self.id}, name='{self.name}', "
            f"run_type='{self.run_type}', dotted_order='{self.dotted_order}')"
        )


class _Baggage:
    """Baggage header information."""

    def __init__(
        self,
        metadata: Optional[dict[str, str]] = None,
        tags: Optional[list[str]] = None,
        project_name: Optional[str] = None,
    ):
        """Initialize the Baggage object."""
        self.metadata = metadata or {}
        self.tags = tags or []
        self.project_name = project_name

    @classmethod
    def from_header(cls, header_value: Optional[str]) -> _Baggage:
        """Create a Baggage object from the given header value."""
        if not header_value:
            return cls()
        metadata = {}
        tags = []
        project_name = None
        try:
            for item in header_value.split(","):
                key, value = item.split("=", 1)
                if key == LANGSMITH_METADATA:
                    metadata = json.loads(urllib.parse.unquote(value))
                elif key == LANGSMITH_TAGS:
                    tags = urllib.parse.unquote(value).split(",")
                elif key == LANGSMITH_PROJECT:
                    project_name = urllib.parse.unquote(value)
        except Exception as e:
            logger.warning(f"Error parsing baggage header: {e}")

        return cls(metadata=metadata, tags=tags, project_name=project_name)

    @classmethod
    def from_headers(cls, headers: Mapping[Union[str, bytes], Any]) -> _Baggage:
        if "baggage" in headers:
            return cls.from_header(headers["baggage"])
        elif b"baggage" in headers:
            return cls.from_header(cast(bytes, headers[b"baggage"]).decode("utf-8"))
        else:
            return cls.from_header(None)

    def to_header(self) -> str:
        """Return the Baggage object as a header value."""
        items = []
        if self.metadata:
            serialized_metadata = _dumps_json(self.metadata)
            items.append(
                f"{LANGSMITH_PREFIX}metadata={urllib.parse.quote(serialized_metadata)}"
            )
        if self.tags:
            serialized_tags = ",".join(self.tags)
            items.append(
                f"{LANGSMITH_PREFIX}tags={urllib.parse.quote(serialized_tags)}"
            )
        if self.project_name:
            items.append(
                f"{LANGSMITH_PREFIX}project={urllib.parse.quote(self.project_name)}"
            )
        return ",".join(items)


def _parse_dotted_order(dotted_order: str) -> list[tuple[datetime, UUID]]:
    """Parse the dotted order string."""
    parts = dotted_order.split(".")
    return [
        (datetime.strptime(part[:-36], "%Y%m%dT%H%M%S%fZ"), UUID(part[-36:]))
        for part in parts
    ]


def _create_current_dotted_order(
    start_time: Optional[datetime], run_id: Optional[UUID]
) -> str:
    """Create the current dotted order."""
    st = start_time or datetime.now(timezone.utc)
    id_ = run_id or uuid4()
    return st.strftime("%Y%m%dT%H%M%S%fZ") + str(id_)


__all__ = ["RunTree", "RunTree"]
