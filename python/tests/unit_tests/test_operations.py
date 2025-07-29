import logging
import uuid

from langsmith._internal import _orjson
from langsmith._internal._operations import (
    SerializedFeedbackOperation,
    SerializedRunOperation,
    combine_serialized_queue_operations,
    serialized_run_operation_to_multipart_parts_and_context,
)


def test_combine_serialized_queue_operations():
    # Arrange
    serialized_run_operations = [
        SerializedRunOperation(
            operation="post",
            id="id1",
            trace_id="trace_id1",
            _none=_orjson.dumps({"a": 1}),
            inputs="inputs1",
            outputs="outputs1",
            events="events1",
            attachments=None,
        ),
        SerializedRunOperation(
            operation="patch",
            id="id1",
            trace_id="trace_id1",
            _none=_orjson.dumps({"b": "2"}),
            inputs="inputs1-patched",
            outputs="outputs1-patched",
            events="events1",
            attachments=None,
        ),
        SerializedFeedbackOperation(
            id="id2",
            trace_id="trace_id2",
            feedback="feedback2",
        ),
        SerializedRunOperation(
            operation="post",
            id="id3",
            trace_id="trace_id3",
            _none="none3",
            inputs="inputs3",
            outputs="outputs3",
            events="events3",
            attachments=None,
        ),
        SerializedRunOperation(
            operation="patch",
            id="id4",
            trace_id="trace_id4",
            _none="none4",
            inputs="inputs4-patched",
            outputs="outputs4-patched",
            events="events4",
            attachments=None,
        ),
        SerializedRunOperation(
            operation="post",
            id="id5",
            trace_id="trace_id5",
            _none="none5",
            inputs="inputs5",
            outputs=None,
            events="events5",
            attachments=None,
        ),
        SerializedRunOperation(
            operation="patch",
            id="id5",
            trace_id="trace_id5",
            _none=None,
            inputs=None,
            outputs="outputs5-patched",
            events=None,
            attachments=None,
        ),
    ]

    # Act
    result = combine_serialized_queue_operations(serialized_run_operations)

    # Assert
    assert result == [
        # merged 1+2
        SerializedRunOperation(
            operation="post",
            id="id1",
            trace_id="trace_id1",
            _none=_orjson.dumps({"a": 1, "b": "2"}),
            inputs="inputs1-patched",
            outputs="outputs1-patched",
            events="events1",
            attachments=None,
        ),
        # 4 passthrough
        serialized_run_operations[3],
        # merged 6+7
        SerializedRunOperation(
            operation="post",
            id="id5",
            trace_id="trace_id5",
            _none="none5",
            inputs="inputs5",
            outputs="outputs5-patched",
            events="events5",
            attachments=None,
        ),
        # 3,5 are passthrough in that order
        serialized_run_operations[2],
        serialized_run_operations[4],
    ]


def test_serialized_run_operation_missing_file(tmp_path, caplog) -> None:
    caplog.set_level(logging.WARNING)
    op = SerializedRunOperation(
        operation="post",
        id=uuid.uuid4(),
        trace_id=uuid.uuid4(),
        _none=_orjson.dumps({"foo": 1}),
        inputs=None,
        outputs=None,
        events=None,
        attachments={
            "missing": ("text/plain", tmp_path / "does-not-exist.txt"),
            "ok": ("text/plain", b"data"),
        },
    )

    with caplog.at_level(logging.WARNING):
        (
            parts_and_context,
            opened,
        ) = serialized_run_operation_to_multipart_parts_and_context(op)

    assert "Attachment file not found" in caplog.text
    part_names = [p[0] for p in parts_and_context.parts]
    assert f"attachment.{op.id}.ok" in part_names
    assert f"attachment.{op.id}.missing" not in part_names
    assert not opened
