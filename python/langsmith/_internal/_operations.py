from __future__ import annotations

import itertools
import uuid
from typing import Literal, Optional, Union, cast

import orjson

from langsmith import schemas as ls_schemas
from langsmith._internal._multipart import MultipartPart, MultipartPartsAndContext
from langsmith._internal._serde import dumps_json as _dumps_json


class SerializedRunOperation:
    operation: Literal["post", "patch"]
    id: uuid.UUID
    trace_id: uuid.UUID

    # this is the whole object, minus the other fields which
    # are popped (inputs/outputs/events/attachments)
    _none: bytes

    inputs: Optional[bytes]
    outputs: Optional[bytes]
    events: Optional[bytes]
    attachments: Optional[ls_schemas.Attachments]

    __slots__ = (
        "operation",
        "id",
        "trace_id",
        "_none",
        "inputs",
        "outputs",
        "events",
        "attachments",
    )

    def __init__(
        self,
        operation: Literal["post", "patch"],
        id: uuid.UUID,
        trace_id: uuid.UUID,
        _none: bytes,
        inputs: Optional[bytes] = None,
        outputs: Optional[bytes] = None,
        events: Optional[bytes] = None,
        attachments: Optional[ls_schemas.Attachments] = None,
    ) -> None:
        self.operation = operation
        self.id = id
        self.trace_id = trace_id
        self._none = _none
        self.inputs = inputs
        self.outputs = outputs
        self.events = events
        self.attachments = attachments

    def __eq__(self, other: object) -> bool:
        return isinstance(other, SerializedRunOperation) and (
            self.operation,
            self.id,
            self.trace_id,
            self._none,
            self.inputs,
            self.outputs,
            self.events,
            self.attachments,
        ) == (
            other.operation,
            other.id,
            other.trace_id,
            other._none,
            other.inputs,
            other.outputs,
            other.events,
            other.attachments,
        )


class SerializedFeedbackOperation:
    id: uuid.UUID
    trace_id: uuid.UUID
    feedback: bytes

    __slots__ = ("id", "trace_id", "feedback")

    def __init__(self, id: uuid.UUID, trace_id: uuid.UUID, feedback: bytes) -> None:
        self.id = id
        self.trace_id = trace_id
        self.feedback = feedback

    def __eq__(self, other: object) -> bool:
        return isinstance(other, SerializedFeedbackOperation) and (
            self.id,
            self.trace_id,
            self.feedback,
        ) == (other.id, other.trace_id, other.feedback)


def serialize_feedback_dict(
    feedback: Union[ls_schemas.FeedbackCreate, dict],
) -> SerializedFeedbackOperation:
    if hasattr(feedback, "dict") and callable(getattr(feedback, "dict")):
        feedback_create: dict = feedback.dict()  # type: ignore
    else:
        feedback_create = cast(dict, feedback)
    if "id" not in feedback_create:
        feedback_create["id"] = uuid.uuid4()
    elif isinstance(feedback_create["id"], str):
        feedback_create["id"] = uuid.UUID(feedback_create["id"])
    if "trace_id" not in feedback_create:
        feedback_create["trace_id"] = uuid.uuid4()
    elif isinstance(feedback_create["trace_id"], str):
        feedback_create["trace_id"] = uuid.UUID(feedback_create["trace_id"])

    return SerializedFeedbackOperation(
        id=feedback_create["id"],
        trace_id=feedback_create["trace_id"],
        feedback=_dumps_json(feedback_create),
    )


def serialize_run_dict(
    operation: Literal["post", "patch"], payload: dict
) -> SerializedRunOperation:
    inputs = payload.pop("inputs", None)
    outputs = payload.pop("outputs", None)
    events = payload.pop("events", None)
    attachments = payload.pop("attachments", None)
    return SerializedRunOperation(
        operation=operation,
        id=payload["id"],
        trace_id=payload["trace_id"],
        _none=_dumps_json(payload),
        inputs=_dumps_json(inputs) if inputs is not None else None,
        outputs=_dumps_json(outputs) if outputs is not None else None,
        events=_dumps_json(events) if events is not None else None,
        attachments=attachments if attachments is not None else None,
    )


def combine_serialized_queue_operations(
    ops: list[Union[SerializedRunOperation, SerializedFeedbackOperation]],
) -> list[Union[SerializedRunOperation, SerializedFeedbackOperation]]:
    create_ops_by_id = {
        op.id: op
        for op in ops
        if isinstance(op, SerializedRunOperation) and op.operation == "post"
    }
    passthrough_ops: list[
        Union[SerializedRunOperation, SerializedFeedbackOperation]
    ] = []
    for op in ops:
        if isinstance(op, SerializedRunOperation):
            if op.operation == "post":
                continue

            # must be patch

            create_op = create_ops_by_id.get(op.id)
            if create_op is None:
                passthrough_ops.append(op)
                continue

            if op._none is not None and op._none != create_op._none:
                # TODO optimize this more - this would currently be slowest
                # for large payloads
                create_op_dict = orjson.loads(create_op._none)
                op_dict = {
                    k: v for k, v in orjson.loads(op._none).items() if v is not None
                }
                create_op_dict.update(op_dict)
                create_op._none = orjson.dumps(create_op_dict)

            if op.inputs is not None:
                create_op.inputs = op.inputs
            if op.outputs is not None:
                create_op.outputs = op.outputs
            if op.events is not None:
                create_op.events = op.events
            if op.attachments is not None:
                if create_op.attachments is None:
                    create_op.attachments = {}
                create_op.attachments.update(op.attachments)
        else:
            passthrough_ops.append(op)
    return list(itertools.chain(create_ops_by_id.values(), passthrough_ops))


def serialized_feedback_operation_to_multipart_parts_and_context(
    op: SerializedFeedbackOperation,
) -> MultipartPartsAndContext:
    return MultipartPartsAndContext(
        [
            (
                f"feedback.{op.id}",
                (
                    None,
                    op.feedback,
                    "application/json",
                    {"Content-Length": str(len(op.feedback))},
                ),
            )
        ],
        f"trace={op.trace_id},id={op.id}",
    )


def serialized_run_operation_to_multipart_parts_and_context(
    op: SerializedRunOperation,
) -> MultipartPartsAndContext:
    acc_parts: list[MultipartPart] = []

    # this is main object, minus inputs/outputs/events/attachments
    acc_parts.append(
        (
            f"{op.operation}.{op.id}",
            (
                None,
                op._none,
                "application/json",
                {"Content-Length": str(len(op._none))},
            ),
        )
    )
    for key, value in (
        ("inputs", op.inputs),
        ("outputs", op.outputs),
        ("events", op.events),
    ):
        if value is None:
            continue
        valb = value
        acc_parts.append(
            (
                f"{op.operation}.{op.id}.{key}",
                (
                    None,
                    valb,
                    "application/json",
                    {"Content-Length": str(len(valb))},
                ),
            ),
        )
    if op.attachments:
        for n, (content_type, valb) in op.attachments.items():
            acc_parts.append(
                (
                    f"attachment.{op.id}.{n}",
                    (
                        None,
                        valb,
                        content_type,
                        {"Content-Length": str(len(valb))},
                    ),
                )
            )
    return MultipartPartsAndContext(
        acc_parts,
        f"trace={op.trace_id},id={op.id}",
    )
