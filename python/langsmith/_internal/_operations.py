from __future__ import annotations

import io
import itertools
import logging
import uuid
from typing import Iterator, Literal, Optional, Sequence, Union, cast

import zstandard as zstd

from langsmith import schemas as ls_schemas
from langsmith._internal import _orjson
from langsmith._internal._multipart import MultipartPart, MultipartPartsAndContext
from langsmith._internal._serde import dumps_json as _dumps_json

logger = logging.getLogger(__name__)

BOUNDARY = uuid.uuid4().hex
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
                create_op_dict = _orjson.loads(create_op._none)
                op_dict = {
                    k: v for k, v in _orjson.loads(op._none).items() if v is not None
                }
                create_op_dict.update(op_dict)
                create_op._none = _orjson.dumps(create_op_dict)

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
            if "." in n:
                logger.warning(
                    f"Skipping logging of attachment '{n}' "
                    f"for run {op.id}:"
                    " Invalid attachment name.  Attachment names must not contain"
                    " periods ('.'). Please rename the attachment and try again."
                )
                continue

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


def combine_multipart_parts_and_context_for_compression(
    parts_and_contexts: Sequence[MultipartPartsAndContext],
) -> MultipartPartsAndContext:
    """Combine multiple MultipartPartsAndContext objects for streaming compression.
    
    Args:
        parts_and_contexts: Sequence of MultipartPartsAndContext objects to combine
        
    Returns:
        Combined MultipartPartsAndContext with all parts and contexts
    """
    all_parts = []
    contexts = []
    
    for pc in parts_and_contexts:
        all_parts.extend(pc.parts)
        contexts.append(pc.context)
        
    return MultipartPartsAndContext(
        all_parts,
        ";".join(contexts)
    )

class StreamingMultipartCompressor:
    """Incrementally compress multipart form data from multiple traces."""

    def __init__(
        self,
        *,
        compression_level: int = 3,
        blocksize: int = 65536,
        boundary: str = BOUNDARY,
    ):
        self.compressor = zstd.ZstdCompressor(level=compression_level)
        self.buffer = io.BytesIO()
        self.blocksize = blocksize
        self.boundary = boundary

    def _yield_and_reset_buffer(self) -> Iterator[bytes]:
        # Yield the current compressed data and reset the buffer.
        compressed_data = self.buffer.getvalue()
        if compressed_data:
            yield compressed_data
            self.buffer.seek(0)
            self.buffer.truncate()

    def _process_bytes(
        self,
        compressor: zstd.ZstdCompressionWriter,
        data: Union[bytes, bytearray],
    ) -> Iterator[bytes]:
        with memoryview(data) as view:
            for i in range(0, len(view), self.blocksize):
                chunk = view[i:i + self.blocksize]
                compressor.write(chunk)
                yield from self._yield_and_reset_buffer()

    def compress_multipart_stream(
        self,
        parts_and_contexts: MultipartPartsAndContext,
    ) -> Iterator[bytes]:
        # Create a streaming compressor context
        compressor = self.compressor.stream_writer(self.buffer)

        try:
            for part_name, (filename, data, content_type, headers) in (
                parts_and_contexts.parts
            ):
                # Write part headers
                part_header = (
                    f'--{self.boundary}\r\n'
                    f'Content-Disposition: form-data; name="{part_name}"'
                )
                if filename:
                    part_header += f'; filename="{filename}"'
                part_header += f'\r\nContent-Type: {content_type}\r\n'

                for header_name, header_value in headers.items():
                    part_header += f'{header_name}: {header_value}\r\n'

                part_header += '\r\n'
                compressor.write(part_header.encode())
                # Yield compressed data to keep memory footprint small
                yield from self._yield_and_reset_buffer()

                # Write part data in chunks
                if isinstance(data, (bytes, bytearray)):
                    yield from self._process_bytes(compressor, data)
                else:
                    # Handle other data types
                    compressor.write(str(data).encode())
                    yield from self._yield_and_reset_buffer()

                # End of this part
                compressor.write(b'\r\n')
                yield from self._yield_and_reset_buffer()

            # Write final boundary
            compressor.write(f'--{self.boundary}--\r\n'.encode())
            yield from self._yield_and_reset_buffer()

        finally:
            # Close the compressor to flush any remaining data
            compressor.close()
            # Yield any final compressed data
            yield from self._yield_and_reset_buffer()
            # Close the buffer
            self.buffer.close()

    def compress_operations(
        self,
        ops: Sequence[SerializedRunOperation],
        *,
        batch_size: Optional[int] = None,
    ) -> Iterator[bytes]:
        """Compress a sequence of operations into multipart form data.
        
        Args:
            ops: Sequence of operations to compress
            batch_size: Optional batch size for processing operations
            
        Yields:
            Compressed chunks of the multipart form data
        """
        def chunk_ops(ops: Sequence[SerializedRunOperation], 
                     size: Optional[int] = None,
                     ) -> Iterator[Sequence[SerializedRunOperation]]:
            if size is None:
                yield ops
                return
            
            for i in range(0, len(ops), size):
                yield ops[i:i + size]

        def get_multipart_parts(
            batch: Sequence[SerializedRunOperation]
        ) -> MultipartPartsAndContext:
            parts_and_contexts = []
            for op in batch:
                parts_and_contexts.append(
                    serialized_run_operation_to_multipart_parts_and_context(op)
                )
            return combine_multipart_parts_and_context_for_compression(
                parts_and_contexts
            )

        # Process operations in batches
        for batch in chunk_ops(ops, batch_size):
            multipart_data = get_multipart_parts(batch)
            yield from self.compress_multipart_stream(multipart_data)
