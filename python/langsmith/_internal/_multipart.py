from __future__ import annotations

from dataclasses import dataclass
from typing import (
    Dict,
    Iterable,
    List,
    Tuple,
)

from langsmith import schemas as ls_schemas
from langsmith._internal._serde import dumps_json as _dumps_json

MultipartPart = Tuple[str, Tuple[None, bytes, str, Dict[str, str]]]


@dataclass(order=True)
class MultipartPartsAndContext:
    parts: list[MultipartPart]
    context: str


@dataclass
class SerializedRun:
    _none: bytes
    inputs: bytes
    outputs: bytes
    events: bytes
    feedback: bytes
    attachments: ls_schemas.Attachments
    _context: str


def convert_to_multipart_parts_and_context(
    create_dicts: list[dict],
    update_dicts: list[dict],
    feedback_dicts: list[dict],
    *,
    all_attachments: Dict,
) -> MultipartPartsAndContext:
    acc_context: List[str] = []
    acc_parts: list[MultipartPart] = []
    for event, payloads in (
        ("post", create_dicts),
        ("patch", update_dicts),
        ("feedback", feedback_dicts),
    ):
        for payload in payloads:
            # collect fields to be sent as separate parts
            fields = [
                ("inputs", payload.pop("inputs", None)),
                ("outputs", payload.pop("outputs", None)),
                ("events", payload.pop("events", None)),
                ("feedback", payload.pop("feedback", None)),
            ]
            # encode the main run payload
            payloadb = _dumps_json(payload)
            acc_parts.append(
                (
                    f"{event}.{payload['id']}",
                    (
                        None,
                        payloadb,
                        "application/json",
                        {"Content-Length": str(len(payloadb))},
                    ),
                )
            )
            # encode the fields we collected
            for key, value in fields:
                if value is None:
                    continue
                valb = _dumps_json(value)
                acc_parts.append(
                    (
                        f"{event}.{payload['id']}.{key}",
                        (
                            None,
                            valb,
                            "application/json",
                            {"Content-Length": str(len(valb))},
                        ),
                    ),
                )
            # encode the attachments
            if attachments := all_attachments.pop(payload["id"], None):
                for n, (content_type, valb) in attachments.items():
                    acc_parts.append(
                        (
                            f"attachment.{payload['id']}.{n}",
                            (
                                None,
                                valb,
                                content_type,
                                {"Content-Length": str(len(valb))},
                            ),
                        )
                    )
            # compute context
            acc_context.append(
                f"trace={payload.get('trace_id')},id={payload.get('id')}"
            )
    _context = "; ".join(acc_context)
    return MultipartPartsAndContext(acc_parts, _context)


def join_multipart_parts_and_context(
    parts_and_contexts: Iterable[MultipartPartsAndContext],
) -> MultipartPartsAndContext:
    acc_parts: list[MultipartPart] = []
    acc_context: list[str] = []
    for parts_and_context in parts_and_contexts:
        acc_parts.extend(parts_and_context.parts)
        acc_context.append(parts_and_context.context)
    return MultipartPartsAndContext(acc_parts, "; ".join(acc_context))
