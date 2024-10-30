from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Dict, Iterable, List, Literal, Optional, Tuple, Union, cast

from langsmith import schemas as ls_schemas
from langsmith._internal._serde import dumps_json as _dumps_json

MultipartPart = Tuple[str, Tuple[None, bytes, str, Dict[str, str]]]


@dataclass
class MultipartPartsAndContext:
    parts: list[MultipartPart]
    context: str


@dataclass
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


@dataclass
class SerializedFeedbackOperation:
    id: uuid.UUID
    trace_id: uuid.UUID
    feedback: bytes


def serialize_feedback_dict(
    feedback: Union[ls_schemas.Feedback, dict]
) -> SerializedFeedbackOperation:
    if hasattr(feedback, "dict") and callable(getattr(feedback, "dict")):
        feedback_create: dict = feedback.dict()  # type: ignore
    else:
        feedback_create = cast(dict, feedback)
    if "id" not in feedback_create:
        feedback_create["id"] = uuid.uuid4()
    elif isinstance(feedback_create["id"], str):
        feedback_create["id"] = uuid.UUID(feedback_create["id"])

    return SerializedFeedbackOperation(
        id=feedback_create["id"],
        trace_id=feedback_create.get("trace_id"),
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


# def convert_to_multipart_parts_and_context(
#     create_dicts: list[dict],
#     update_dicts: list[dict],
#     feedback_dicts: list[dict],
#     *,
#     all_attachments: Dict,
# ) -> MultipartPartsAndContext:
#     acc_context: List[str] = []
#     acc_parts: list[MultipartPart] = []
#     for event, payloads in (
#         ("post", create_dicts),
#         ("patch", update_dicts),
#         ("feedback", feedback_dicts),
#     ):
#         for payload in payloads:
#             # collect fields to be sent as separate parts
#             fields = [
#                 ("inputs", payload.pop("inputs", None)),
#                 ("outputs", payload.pop("outputs", None)),
#                 ("events", payload.pop("events", None)),
#                 ("feedback", payload.pop("feedback", None)),
#             ]
#             # encode the main run payload
#             payloadb = _dumps_json(payload)
#             acc_parts.append(
#                 (
#                     f"{event}.{payload['id']}",
#                     (
#                         None,
#                         payloadb,
#                         "application/json",
#                         {"Content-Length": str(len(payloadb))},
#                     ),
#                 )
#             )
#             # encode the fields we collected
#             for key, value in fields:
#                 if value is None:
#                     continue
#                 valb = _dumps_json(value)
#                 acc_parts.append(
#                     (
#                         f"{event}.{payload['id']}.{key}",
#                         (
#                             None,
#                             valb,
#                             "application/json",
#                             {"Content-Length": str(len(valb))},
#                         ),
#                     ),
#                 )
#             # encode the attachments
#             if attachments := all_attachments.pop(payload["id"], None):
#                 for n, (content_type, valb) in attachments.items():
#                     acc_parts.append(
#                         (
#                             f"attachment.{payload['id']}.{n}",
#                             (
#                                 None,
#                                 valb,
#                                 content_type,
#                                 {"Content-Length": str(len(valb))},
#                             ),
#                         )
#                     )
#             # compute context
#             acc_context.append(
#                 f"trace={payload.get('trace_id')},id={payload.get('id')}"
#             )
#     _context = "; ".join(acc_context)
#     return MultipartPartsAndContext(acc_parts, _context)


def join_multipart_parts_and_context(
    parts_and_contexts: Iterable[MultipartPartsAndContext],
) -> MultipartPartsAndContext:
    acc_parts: list[MultipartPart] = []
    acc_context: list[str] = []
    for parts_and_context in parts_and_contexts:
        acc_parts.extend(parts_and_context.parts)
        acc_context.append(parts_and_context.context)
    return MultipartPartsAndContext(acc_parts, "; ".join(acc_context))
