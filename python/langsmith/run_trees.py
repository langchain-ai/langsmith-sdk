"""Schemas for the LangSmith API."""
# mypy: disable-error-code="valid-type,attr-defined,union-attr,index,arg-type"

from __future__ import annotations

import contextvars
import functools
import json
import logging
import sys
import threading
import urllib.parse
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, Optional, Union, cast
from uuid import NAMESPACE_DNS, UUID, uuid5

from typing_extensions import TypedDict

import langsmith._internal._context as _context
from langsmith import schemas as ls_schemas
from langsmith import utils
from langsmith.client import ID_TYPE, RUN_TYPE_T, Client, _dumps_json, _ensure_uuid
from langsmith.uuid import uuid7_from_datetime

logger = logging.getLogger(__name__)


class WriteReplica(TypedDict, total=False):
    api_url: Optional[str]
    api_key: Optional[str]
    project_name: Optional[str]
    updates: Optional[dict]


LANGSMITH_PREFIX = "langsmith-"
LANGSMITH_DOTTED_ORDER = sys.intern(f"{LANGSMITH_PREFIX}trace")
LANGSMITH_DOTTED_ORDER_BYTES = LANGSMITH_DOTTED_ORDER.encode("utf-8")
LANGSMITH_METADATA = sys.intern(f"{LANGSMITH_PREFIX}metadata")
LANGSMITH_TAGS = sys.intern(f"{LANGSMITH_PREFIX}tags")
LANGSMITH_PROJECT = sys.intern(f"{LANGSMITH_PREFIX}project")
LANGSMITH_REPLICAS = sys.intern(f"{LANGSMITH_PREFIX}replicas")
OVERRIDE_OUTPUTS = sys.intern("__omit_auto_outputs")
NOT_PROVIDED = cast(None, object())
_LOCK = threading.Lock()

# Context variables
_REPLICAS = contextvars.ContextVar[Optional[Sequence[WriteReplica]]](
    "_REPLICAS", default=None
)

_DISTRIBUTED_PARENT_ID = contextvars.ContextVar[Optional[str]](
    "_DISTRIBUTED_PARENT_ID", default=None
)

_SENTINEL = cast(None, object())

TIMESTAMP_LENGTH = 36


# Note, this is called directly by langchain. Do not remove.
def get_cached_client(**init_kwargs: Any) -> Client:
    global _CLIENT
    if _CLIENT is None:
        with _LOCK:
            if _CLIENT is None:
                _CLIENT = Client(**init_kwargs)
    return _CLIENT


def configure(
    client: Optional[Client] = _SENTINEL,
    enabled: Optional[bool] = _SENTINEL,
    project_name: Optional[str] = _SENTINEL,
    tags: Optional[list[str]] = _SENTINEL,
    metadata: Optional[dict[str, Any]] = _SENTINEL,
):
    """Configure global LangSmith tracing context.

    This function allows you to set global configuration options for LangSmith
    tracing that will be applied to all subsequent traced operations. It modifies
    context variables that control tracing behavior across your application.

    Do this once at startup to configure the global settings in code.

    If, instead, you wish to only configure tracing for a single invocation,
    use the `tracing_context` context manager instead.

    Args:
        client: A LangSmith Client instance to use for all tracing operations.

            If provided, this client will be used instead of creating new clients.

            Pass `None` to explicitly clear the global client.
        enabled: Whether tracing is enabled.

            Can be:

            - `True`: Enable tracing and send data to LangSmith
            - `False`: Disable tracing completely
            - `'local'`: Enable tracing but only store data locally
            - `None`: Clear the setting (falls back to environment variables)
        project_name: The LangSmith project name where traces will be sent.

            This determines which project dashboard will display your traces.

            Pass `None` to explicitly clear the project name.
        tags: A list of tags to be applied to all traced runs.

            Tags are useful for filtering and organizing runs in the LangSmith UI.

            Pass `None` to explicitly clear all global tags.
        metadata: A dictionary of metadata to attach to all traced runs.

            Metadata can store any additional context about your runs.

            Pass `None` to explicitly clear all global metadata.

    Examples:
        Basic configuration:
        >>> import langsmith as ls
        >>> # Enable tracing with a specific project
        >>> ls.configure(enabled=True, project_name="my-project")

        Set global trace masking:
        >>> def hide_keys(data):
        ...     if not data:
        ...         return {}
        ...     return {k: v for k, v in data.items() if k not in ["key1", "key2"]}
        >>> ls.configure(
        ...     client=ls.Client(
        ...         hide_inputs=hide_keys,
        ...         hide_outputs=hide_keys,
        ...     )
        ... )

        Adding global tags and metadata:
        >>> ls.configure(
        ...     tags=["production", "v1.0"],
        ...     metadata={"environment": "prod", "version": "1.0.0"},
        ... )

        Disabling tracing:
        >>> ls.configure(enabled=False)
    """
    global _CLIENT
    with _LOCK:
        if client is not _SENTINEL:
            _CLIENT = client
        if enabled is not _SENTINEL:
            _context._TRACING_ENABLED.set(enabled)
            _context._GLOBAL_TRACING_ENABLED = enabled
        if project_name is not _SENTINEL:
            _context._PROJECT_NAME.set(project_name)
            _context._GLOBAL_PROJECT_NAME = project_name
        if tags is not _SENTINEL:
            _context._TAGS.set(tags)
            _context._GLOBAL_TAGS = tags
        if metadata is not _SENTINEL:
            _context._METADATA.set(metadata)
            _context._GLOBAL_METADATA = metadata


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


class RunTree:
    """Run Schema with back-references for posting runs."""

    __slots__ = (
        # From RunBase
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
        # RunTree-specific
        "parent_run",
        "parent_dotted_order",
        "child_runs",
        "session_name",
        "session_id",
        "ls_client",
        "dotted_order",
        "trace_id",
        "dangerously_allow_filesystem",
        "replicas",
        # Private
        "_extensions",
    )

    # Type annotations for mypy (required for __slots__)
    id: UUID
    name: str
    start_time: datetime
    run_type: str
    end_time: Optional[datetime]
    extra: dict[str, Any]  # Always set to {} in __init__ if None
    error: Optional[str]
    serialized: Optional[dict[str, Any]]
    events: list[dict[str, Any]]
    inputs: dict[str, Any]
    outputs: Optional[dict[str, Any]]
    reference_example_id: Optional[UUID]
    parent_run_id: Optional[UUID]
    tags: Optional[list[str]]
    attachments: Any
    parent_run: Optional[RunTree]
    parent_dotted_order: Optional[str]
    child_runs: list[RunTree]
    session_name: str
    session_id: Optional[UUID]
    ls_client: Optional[Any]
    dotted_order: str
    trace_id: UUID
    dangerously_allow_filesystem: Optional[bool]
    replicas: Optional[Sequence[WriteReplica]]
    _extensions: dict[str, Any]

    def __init__(
        self,
        name: str = "Unnamed",
        run_type: str = "chain",
        *,
        id: Optional[UUID] = None,
        start_time: Optional[datetime] = None,
        parent_run: Optional[RunTree] = None,
        parent_dotted_order: Optional[str] = None,
        child_runs: Optional[list[RunTree]] = None,
        session_name: Optional[str] = None,
        session_id: Optional[UUID] = None,
        extra: Optional[dict] = None,
        tags: Optional[list[str]] = None,
        events: Optional[list[dict]] = None,
        ls_client: Optional[Any] = None,
        dotted_order: str = "",
        trace_id: Optional[UUID] = None,
        dangerously_allow_filesystem: Optional[bool] = False,
        replicas: Optional[Sequence[WriteReplica]] = None,
        # Support aliases
        client: Optional[Any] = None,
        _client: Optional[Any] = None,
        project_name: Optional[str] = None,
        project_id: Optional[UUID] = None,
        # Other RunBase fields
        end_time: Optional[datetime] = None,
        error: Optional[str] = None,
        serialized: Optional[dict] = None,
        inputs: Optional[dict] = None,
        outputs: Optional[dict] = None,
        reference_example_id: Optional[UUID] = None,
        parent_run_id: Optional[UUID] = None,
        attachments: Optional[Any] = None,
        **kwargs: Any,
    ):
        """Initialize the RunTree."""
        # Initialize _extensions first
        object.__setattr__(self, "_extensions", {})

        # Handle aliases
        ls_client = ls_client or client or _client
        session_name = (
            session_name or project_name or utils.get_tracer_project() or "default"
        )
        session_id = session_id or project_id

        # Infer name from serialized if needed
        if not name or name == "Unnamed":
            if serialized is not None:
                if "name" in serialized:
                    name = serialized["name"]
                elif "id" in serialized:
                    name = serialized["id"][-1]
            if not name:
                name = "Unnamed"

        # Handle parent_run
        if parent_run is not None:
            parent_run_id = parent_run.id
            parent_dotted_order = parent_run.dotted_order

        # Generate ID if not provided
        if id is None:
            if start_time is not None:
                id = uuid7_from_datetime(start_time)
            else:
                start_time = datetime.now(timezone.utc)
                id = uuid7_from_datetime(start_time)
        elif start_time is None:
            start_time = datetime.now(timezone.utc)

        # Handle trace_id
        if trace_id is None:
            if parent_run is not None:
                trace_id = parent_run.trace_id
            else:
                trace_id = id

        # Handle defaults
        if extra is None:
            extra = {}
        if events is None:
            events = []
        if tags is None:
            tags = []
        if outputs is None:
            outputs = {}
        if attachments is None:
            attachments = {}
        if inputs is None:
            inputs = {}
        if child_runs is None:
            child_runs = []
        if replicas is None:
            replicas = _REPLICAS.get()
        replicas = _ensure_write_replicas(replicas)

        # Ensure dotted_order
        if not dotted_order or not dotted_order.strip():
            current_dotted_order = _create_current_dotted_order(start_time, id)
            if parent_dotted_order is not None:
                dotted_order = parent_dotted_order + "." + current_dotted_order
            else:
                dotted_order = current_dotted_order

        # Set all fields using object.__setattr__ to bypass __setattr__
        object.__setattr__(self, "id", id)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "run_type", run_type)
        object.__setattr__(self, "start_time", start_time)
        object.__setattr__(self, "end_time", end_time)
        object.__setattr__(self, "extra", extra)
        object.__setattr__(self, "error", error)
        object.__setattr__(self, "serialized", serialized)
        object.__setattr__(self, "events", events)
        object.__setattr__(self, "inputs", inputs)
        object.__setattr__(self, "outputs", outputs)
        object.__setattr__(self, "reference_example_id", reference_example_id)
        object.__setattr__(self, "parent_run_id", parent_run_id)
        object.__setattr__(self, "tags", tags)
        object.__setattr__(self, "attachments", attachments)
        object.__setattr__(self, "parent_run", parent_run)
        object.__setattr__(self, "parent_dotted_order", parent_dotted_order)
        object.__setattr__(self, "child_runs", child_runs)
        object.__setattr__(self, "session_name", session_name)
        object.__setattr__(self, "session_id", session_id)
        object.__setattr__(self, "ls_client", ls_client)
        object.__setattr__(self, "dotted_order", dotted_order)
        object.__setattr__(self, "trace_id", trace_id)
        object.__setattr__(
            self, "dangerously_allow_filesystem", dangerously_allow_filesystem
        )
        object.__setattr__(self, "replicas", replicas)

        # Store any remaining unknown fields in _extensions
        for key, value in kwargs.items():
            self._extensions[key] = value

    def __getattr__(self, name: str) -> Any:
        """Fall back to _extensions for unknown attributes."""
        if name.startswith("_"):
            raise AttributeError(
                f"'{self.__class__.__name__}' object has no attribute '{name}'"
            )
        try:
            extensions = object.__getattribute__(self, "_extensions")
            return extensions[name]
        except KeyError:
            raise AttributeError(
                f"'{self.__class__.__name__}' object has no attribute '{name}'"
            )

    def __setattr__(self, name: str, value: Any) -> None:
        """Handle setting attributes, with special handling for _client."""
        # For backwards compat
        if name == "_client":
            object.__setattr__(self, "ls_client", value)
        elif name in self.__slots__:
            object.__setattr__(self, name, value)
        else:
            # Route unknown fields to _extensions
            try:
                extensions = object.__getattribute__(self, "_extensions")
            except AttributeError:
                object.__setattr__(self, "_extensions", {})
                extensions = object.__getattribute__(self, "_extensions")
            extensions[name] = value

    def model_dump(
        self,
        *,
        exclude_none: bool = False,
        exclude: Optional[set] = None,
        mode: str = "python",
    ) -> dict[str, Any]:
        """Convert to dict, including extensions."""
        result = {}
        exclude = exclude or set()
        # Fields to always exclude
        always_exclude = {
            "parent_run",
            "parent_dotted_order",
            "ls_client",
            "_extensions",
        }

        # Add all __slots__ fields (except excluded ones)
        for slot in self.__slots__:
            if slot.startswith("_") or slot in exclude or slot in always_exclude:
                continue
            value = getattr(self, slot, None)
            if exclude_none and value is None:
                continue
            result[slot] = value

        # Add extensions
        extensions = object.__getattribute__(self, "_extensions")
        for key, value in extensions.items():
            if key not in exclude:
                if not exclude_none or value is not None:
                    result[key] = value

        return result

    def dict(
        self,
        *,
        exclude_none: bool = False,
        exclude: Optional[set] = None,
    ) -> dict[str, Any]:
        """Convert to dict (pydantic v1 compatibility)."""
        return self.model_dump(exclude_none=exclude_none, exclude=exclude)

    @property
    def metadata(self) -> dict[str, Any]:
        """Retrieve the metadata (if any)."""
        if self.extra is None:
            object.__setattr__(self, "extra", {})
        assert self.extra is not None  # for mypy
        return self.extra.setdefault("metadata", {})

    @property
    def revision_id(self) -> Optional[UUID]:
        """Retrieve the revision ID (if any)."""
        return self.metadata.get("revision_id")

    @property
    def latency(self) -> Optional[float]:
        """Latency in seconds."""
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time).total_seconds()

    def __repr__(self):
        """Return a string representation of the RunTree object."""
        return (
            f"RunTree(id={self.id}, name='{self.name}', "
            f"run_type='{self.run_type}', dotted_order='{self.dotted_order}')"
        )

    @classmethod
    def construct(cls, **kwargs: Any) -> RunTree:
        """Construct a RunTree without validation (Pydantic compatibility)."""
        return cls(**kwargs)

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
        this will also override the default behavior of `LangChainTracer`.

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
            outputs: A dictionary containing the outputs to be added.
        """
        if self.outputs is None:
            self.outputs = {}
        self.outputs.update(outputs)

    def add_inputs(self, inputs: dict[str, Any]) -> None:
        """Upsert the given inputs into the run.

        Args:
            inputs: A dictionary containing the inputs to be added.
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
            events: The event(s) to be added. It can be a single event, a sequence
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
        # Ensure child start_time is never earlier than parent start_time
        # to prevent timestamp ordering violations in dotted_order
        if start_time is not None and self.start_time is not None:
            if start_time < self.start_time:
                logger.debug(
                    f"Adjusting child run '{name}' start_time from {start_time} "
                    f"to {self.start_time} to maintain timestamp ordering with "
                    f"parent '{self.name}'"
                )
            start_time = max(start_time, self.start_time)

        serialized_ = serialized or {"name": name}
        run = RunTree(
            name=name,
            id=_ensure_uuid(run_id),
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
            project_name=self.session_name,
            replicas=self.replicas,
            ls_client=self.ls_client,
            tags=tags,
            attachments=attachments or {},  # type: ignore
            dangerously_allow_filesystem=self.dangerously_allow_filesystem,
        )

        return run

    def _get_dicts_safe(self) -> dict[str, Any]:
        # Things like generators cannot be copied
        self_dict = self.model_dump(
            exclude={"child_runs", "inputs", "outputs"}, exclude_none=True
        )
        if self.inputs is not None:
            # shallow copy. deep copying will occur in the client
            inputs_ = {}
            attachments = self_dict.get("attachments", {})
            for k, v in self.inputs.items():
                if isinstance(v, ls_schemas.Attachment):
                    attachments[k] = v
                else:
                    inputs_[k] = v
            self_dict["inputs"] = inputs_
            if attachments:
                self_dict["attachments"] = attachments
        if self.outputs is not None:
            # shallow copy; deep copying will occur in the client
            self_dict["outputs"] = self.outputs.copy()
        return self_dict

    def _slice_parent_id(self, parent_id: str, run_dict: dict[str, Any]) -> None:
        """Slice the parent id from dotted order.

        Additionally check if the current run is a child of the parent. If so, update
        the parent_run_id to None, and set the trace id to the new root id after
        parent_id.
        """
        if dotted_order := run_dict.get("dotted_order"):
            segs = dotted_order.split(".")
            start_idx = None
            parent_id = str(parent_id)
            # TODO(angus): potentially use binary search to find the index
            for idx, part in enumerate(segs):
                seg_id = part[-TIMESTAMP_LENGTH:]
                if str(seg_id) == parent_id:
                    start_idx = idx
                    break
            if start_idx is not None:
                # Trim segments to start after parent_id (exclusive)
                trimmed_segs = segs[start_idx + 1 :]
                # Rebuild dotted_order
                run_dict["dotted_order"] = ".".join(trimmed_segs)
                if trimmed_segs:
                    run_dict["trace_id"] = UUID(trimmed_segs[0][-TIMESTAMP_LENGTH:])
                else:
                    run_dict["trace_id"] = run_dict["id"]
        if str(run_dict.get("parent_run_id")) == parent_id:
            # We've found the new root node.
            run_dict.pop("parent_run_id", None)

    def _remap_for_project(
        self, project_name: str, updates: Optional[dict] = None
    ) -> dict[str, Any]:
        """Rewrites ids/dotted_order for a given project with optional updates."""
        run_dict = self._get_dicts_safe()
        if project_name == self.session_name:
            return run_dict

        if updates and updates.get("reroot", False):
            distributed_parent_id = _DISTRIBUTED_PARENT_ID.get()
            if distributed_parent_id:
                self._slice_parent_id(distributed_parent_id, run_dict)

        old_id = run_dict["id"]
        new_id = uuid5(NAMESPACE_DNS, f"{old_id}:{project_name}")
        # trace id
        old_trace = run_dict.get("trace_id")
        if old_trace:
            new_trace = uuid5(NAMESPACE_DNS, f"{old_trace}:{project_name}")
        else:
            new_trace = None
        # parent id
        parent = run_dict.get("parent_run_id")
        if parent:
            new_parent = uuid5(NAMESPACE_DNS, f"{parent}:{project_name}")
        else:
            new_parent = None
        # dotted order
        if run_dict.get("dotted_order"):
            segs = run_dict["dotted_order"].split(".")
            rebuilt = []
            for part in segs[:-1]:
                repl = uuid5(
                    NAMESPACE_DNS, f"{part[-TIMESTAMP_LENGTH:]}:{project_name}"
                )
                rebuilt.append(part[:-TIMESTAMP_LENGTH] + str(repl))
            rebuilt.append(segs[-1][:-TIMESTAMP_LENGTH] + str(new_id))
            dotted = ".".join(rebuilt)
        else:
            dotted = None
        dup = utils.deepish_copy(run_dict)
        dup.update(
            {
                "id": new_id,
                "trace_id": new_trace,
                "parent_run_id": new_parent,
                "dotted_order": dotted,
                "session_name": project_name,
            }
        )
        if updates:
            dup.update(updates)
        return dup

    def post(self, exclude_child_runs: bool = True) -> None:
        """Post the run tree to the API asynchronously."""
        if self.replicas:
            for replica in self.replicas:
                project_name = replica.get("project_name") or self.session_name
                updates = replica.get("updates")
                run_dict = self._remap_for_project(project_name, updates)
                self.client.create_run(
                    **run_dict,
                    api_key=replica.get("api_key"),
                    api_url=replica.get("api_url"),
                )
        else:
            kwargs = self._get_dicts_safe()
            self.client.create_run(**kwargs)
        if self.attachments:
            keys = [str(name) for name in self.attachments]
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

    def patch(self, *, exclude_inputs: bool = False) -> None:
        """Patch the run tree to the API in a background thread.

        Args:
            exclude_inputs: Whether to exclude inputs from the patch request.
        """
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
        if self.replicas:
            for replica in self.replicas:
                project_name = replica.get("project_name") or self.session_name
                updates = replica.get("updates")
                run_dict = self._remap_for_project(project_name, updates)
                self.client.update_run(
                    name=run_dict["name"],
                    run_id=run_dict["id"],
                    run_type=run_dict.get("run_type"),
                    start_time=run_dict.get("start_time"),
                    inputs=None if exclude_inputs else run_dict["inputs"],
                    outputs=run_dict["outputs"],
                    error=run_dict.get("error"),
                    parent_run_id=run_dict.get("parent_run_id"),
                    session_name=run_dict.get("session_name"),
                    reference_example_id=run_dict.get("reference_example_id"),
                    end_time=run_dict.get("end_time"),
                    dotted_order=run_dict.get("dotted_order"),
                    trace_id=run_dict.get("trace_id"),
                    events=run_dict.get("events"),
                    tags=run_dict.get("tags"),
                    extra=run_dict.get("extra"),
                    attachments=attachments,
                    api_key=replica.get("api_key"),
                    api_url=replica.get("api_url"),
                )
        else:
            self.client.update_run(
                name=self.name,
                run_id=self.id,
                run_type=cast(RUN_TYPE_T, self.run_type),
                start_time=self.start_time,
                inputs=(
                    None
                    if exclude_inputs
                    else (self.inputs.copy() if self.inputs else None)
                ),
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
        """Wait for all `_futures` to complete."""
        pass

    def get_url(self) -> str:
        """Return the URL of the run."""
        return self.client.get_run_url(run=self)  # type: ignore[arg-type]  # RunTree not RunBase

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

        Requires `langchain` to be installed.

        Returns:
            The new span or `None` if no parent span information is found.
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
            The new span or `None` if no parent span information is found.
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
        if baggage.replicas:
            init_args["replicas"] = baggage.replicas

        run_tree = RunTree(**init_args)

        # Set the distributed parent ID to this run's ID for rerooting
        _DISTRIBUTED_PARENT_ID.set(str(run_tree.id))

        return run_tree

    def to_headers(self) -> dict[str, str]:
        """Return the `RunTree` as a dictionary of headers."""
        headers = {}
        if self.trace_id:
            headers[f"{LANGSMITH_DOTTED_ORDER}"] = self.dotted_order
        baggage = _Baggage(
            metadata=self.extra.get("metadata", {}),
            tags=self.tags,
            project_name=self.session_name,
            replicas=self.replicas,
        )
        headers["baggage"] = baggage.to_header()
        return headers


class _Baggage:
    """Baggage header information."""

    def __init__(
        self,
        metadata: Optional[dict[str, str]] = None,
        tags: Optional[list[str]] = None,
        project_name: Optional[str] = None,
        replicas: Optional[Sequence[WriteReplica]] = None,
    ):
        """Initialize the Baggage object."""
        self.metadata = metadata or {}
        self.tags = tags or []
        self.project_name = project_name
        self.replicas = replicas or []

    @classmethod
    def from_header(cls, header_value: Optional[str]) -> _Baggage:
        """Create a Baggage object from the given header value."""
        if not header_value:
            return cls()
        metadata = {}
        tags = []
        project_name = None
        replicas: Optional[list[WriteReplica]] = None
        try:
            for item in header_value.split(","):
                key, value = item.split("=", 1)
                if key == LANGSMITH_METADATA:
                    metadata = json.loads(urllib.parse.unquote(value))
                elif key == LANGSMITH_TAGS:
                    tags = urllib.parse.unquote(value).split(",")
                elif key == LANGSMITH_PROJECT:
                    project_name = urllib.parse.unquote(value)
                elif key == LANGSMITH_REPLICAS:
                    replicas_data = json.loads(urllib.parse.unquote(value))
                    parsed_replicas: list[WriteReplica] = []
                    for replica_item in replicas_data:
                        if (
                            isinstance(replica_item, (tuple, list))
                            and len(replica_item) == 2
                        ):
                            # Convert legacy format to WriteReplica
                            parsed_replicas.append(
                                WriteReplica(
                                    api_url=None,
                                    api_key=None,
                                    project_name=str(replica_item[0]),
                                    updates=replica_item[1],
                                )
                            )
                        elif isinstance(replica_item, dict):
                            # New WriteReplica format: preserve as dict
                            parsed_replicas.append(cast(WriteReplica, replica_item))
                        else:
                            logger.warning(
                                f"Unknown replica format in baggage: {replica_item}"
                            )
                            continue
                    replicas = parsed_replicas
        except Exception as e:
            logger.warning(f"Error parsing baggage header: {e}")

        return cls(
            metadata=metadata, tags=tags, project_name=project_name, replicas=replicas
        )

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
        if self.replicas:
            serialized_replicas = _dumps_json(self.replicas)
            items.append(
                f"{LANGSMITH_PREFIX}replicas={urllib.parse.quote(serialized_replicas)}"
            )
        return ",".join(items)


@functools.lru_cache(maxsize=1)
def _parse_write_replicas_from_env_var(env_var: Optional[str]) -> list[WriteReplica]:
    """Parse write replicas from LANGSMITH_RUNS_ENDPOINTS environment variable value.

    Supports array format [{"api_url": "x", "api_key": "y"}] and object format
    {"url": "key"}.
    """
    if not env_var:
        return []

    try:
        parsed = json.loads(env_var)

        if isinstance(parsed, list):
            replicas = []
            for item in parsed:
                if not isinstance(item, dict):
                    logger.warning(
                        f"Invalid item type in LANGSMITH_RUNS_ENDPOINTS: "
                        f"expected dict, got {type(item).__name__}"
                    )
                    continue

                api_url = item.get("api_url")
                api_key = item.get("api_key")

                if not isinstance(api_url, str):
                    logger.warning(
                        f"Invalid api_url type in LANGSMITH_RUNS_ENDPOINTS: "
                        f"expected string, got {type(api_url).__name__}"
                    )
                    continue

                if not isinstance(api_key, str):
                    logger.warning(
                        f"Invalid api_key type in LANGSMITH_RUNS_ENDPOINTS: "
                        f"expected string, got {type(api_key).__name__}"
                    )
                    continue

                replicas.append(
                    WriteReplica(
                        api_url=api_url.rstrip("/"),
                        api_key=api_key,
                        project_name=None,
                        updates=None,
                    )
                )
            return replicas
        elif isinstance(parsed, dict):
            _check_endpoint_env_unset(parsed)

            replicas = []
            for url, key in parsed.items():
                url = url.rstrip("/")

                if isinstance(key, str):
                    replicas.append(
                        WriteReplica(
                            api_url=url,
                            api_key=key,
                            project_name=None,
                            updates=None,
                        )
                    )
                else:
                    logger.warning(
                        f"Invalid value type in LANGSMITH_RUNS_ENDPOINTS for URL "
                        f"{url}: "
                        f"expected string, got {type(key).__name__}"
                    )
                    continue
            return replicas
        else:
            logger.warning(
                f"Invalid LANGSMITH_RUNS_ENDPOINTS – must be valid JSON list of "
                "objects with api_url and api_key properties, or object mapping "
                f"url->apiKey, got {type(parsed).__name__}"
            )
            return []
    except utils.LangSmithUserError:
        raise
    except Exception as e:
        logger.warning(
            "Invalid LANGSMITH_RUNS_ENDPOINTS – must be valid JSON list of "
            f"objects with api_url and api_key properties, or object mapping"
            f" url->apiKey: {e}"
        )
        return []


def _get_write_replicas_from_env() -> list[WriteReplica]:
    """Get write replicas from LANGSMITH_RUNS_ENDPOINTS environment variable."""
    env_var = utils.get_env_var("RUNS_ENDPOINTS")

    return _parse_write_replicas_from_env_var(env_var)


def _check_endpoint_env_unset(parsed: dict[str, str]) -> None:
    """Check if endpoint environment variables conflict with runs endpoints."""
    import os

    if parsed and (os.getenv("LANGSMITH_ENDPOINT") or os.getenv("LANGCHAIN_ENDPOINT")):
        raise utils.LangSmithUserError(
            "You cannot provide both LANGSMITH_ENDPOINT / LANGCHAIN_ENDPOINT "
            "and LANGSMITH_RUNS_ENDPOINTS."
        )


def _ensure_write_replicas(
    replicas: Optional[Sequence[WriteReplica]],
) -> list[WriteReplica]:
    """Convert replicas to WriteReplica format."""
    if replicas is None:
        return _get_write_replicas_from_env()

    # All replicas should now be WriteReplica dicts
    return list(replicas)


def _parse_dotted_order(dotted_order: str) -> list[tuple[datetime, UUID]]:
    """Parse the dotted order string."""
    parts = dotted_order.split(".")
    return [
        (
            datetime.strptime(part[:-TIMESTAMP_LENGTH], "%Y%m%dT%H%M%S%fZ"),
            UUID(part[-TIMESTAMP_LENGTH:]),
        )
        for part in parts
    ]


_CLIENT: Optional[Client] = _context._GLOBAL_CLIENT
__all__ = ["RunTree", "RunTree"]


def _create_current_dotted_order(
    start_time: Optional[datetime], run_id: Optional[UUID]
) -> str:
    """Create the current dotted order."""
    st = start_time or datetime.now(timezone.utc)
    id_ = run_id or uuid7_from_datetime(st)
    return st.strftime("%Y%m%dT%H%M%S%fZ") + str(id_)
