"""Unit tests for OTEL exporter and span processor."""

import json
import os
import threading
import time
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from langsmith._internal.otel._otel_exporter import (
    GEN_AI_RESPONSE_FINISH_REASONS,
    GEN_AI_TOOL_CALL_ID,
    GEN_AI_TOOL_NAME,
    OTELExporter,
)
from langsmith.integrations.otel import (
    otel_safe_attribute_value,
    set_langsmith_metadata_attribute,
)
from langsmith.integrations.otel.processor import OtelSpanProcessor


def test_cleanup_stale_spans():
    """Test cleanup of stale spans based on TTL."""
    with patch(
        "langsmith._internal.otel._otel_exporter._import_otel_exporter"
    ) as mock_import:
        mock_import.return_value = (MagicMock(),) * 8

        exporter = OTELExporter(span_ttl_seconds=1)

        # Add stale and fresh spans
        stale_span = MagicMock()
        fresh_span = MagicMock()
        stale_id = uuid.uuid4()
        fresh_id = uuid.uuid4()

        exporter._span_info.set(stale_id, stale_span, created_at=time.time() - 2)
        exporter._span_info.set(fresh_id, fresh_span, created_at=time.time())
        exporter._last_cleanup = 0.0  # Force cleanup

        exporter._cleanup_stale_spans()

        # Verify cleanup
        assert exporter._span_info.get(stale_id) is None
        assert exporter._span_info.get(fresh_id) is not None
        stale_span.end.assert_called_once()
        fresh_span.end.assert_not_called()


def test_cleanup_periodic_behavior():
    """Test cleanup only runs periodically."""
    with patch(
        "langsmith._internal.otel._otel_exporter._import_otel_exporter"
    ) as mock_import:
        mock_import.return_value = (MagicMock(),) * 8

        exporter = OTELExporter(span_ttl_seconds=1)
        stale_span = MagicMock()
        stale_id = uuid.uuid4()

        exporter._span_info.set(stale_id, stale_span, created_at=time.time() - 2)
        exporter._last_cleanup = time.time() - 5  # Recent cleanup

        exporter._cleanup_stale_spans()

        # Should not clean up due to periodic check
        assert exporter._span_info.get(stale_id) is not None
        stale_span.end.assert_not_called()


def test_cleanup_stale_spans_tolerates_concurrent_mutation():
    """Cleanup plus concurrent insert/delete from other batch workers must not
    raise ``RuntimeError: dictionary changed size during iteration`` or any
    ``KeyError``. The span info store locks all access and snapshots before
    iterating.
    """
    with patch(
        "langsmith._internal.otel._otel_exporter._import_otel_exporter"
    ) as mock_import:
        mock_import.return_value = (MagicMock(),) * 8

        exporter = OTELExporter(span_ttl_seconds=1)
        exporter._last_cleanup = 0.0  # Force cleanup

        errors: list = []
        stop = threading.Event()

        # Seed one stale span so cleanup has work to do.
        exporter._span_info.set(uuid.uuid4(), MagicMock(), created_at=time.time() - 2)

        def mutator():
            while not stop.is_set():
                sid = uuid.uuid4()
                try:
                    exporter._span_info.set(sid, MagicMock())
                    exporter._span_info.pop(sid)
                except Exception as e:  # noqa: BLE001
                    errors.append(e)

        threads = [threading.Thread(target=mutator) for _ in range(4)]
        for t in threads:
            t.start()
        try:
            deadline = time.time() + 1.0
            while time.time() < deadline:
                exporter._cleanup_stale_spans()
        finally:
            stop.set()
            for t in threads:
                t.join(timeout=2)

        assert not errors, f"concurrent access raised: {errors}"


@patch("langsmith.utils.get_env_var")
def test_env_var_ttl(mock_get_env_var):
    """Test TTL loading from environment variable with correct default."""
    with patch(
        "langsmith._internal.otel._otel_exporter._import_otel_exporter"
    ) as mock_import:
        mock_import.return_value = (MagicMock(),) * 8
        mock_get_env_var.return_value = "1800"

        exporter = OTELExporter()

        assert exporter._span_ttl_seconds == 1800
        mock_get_env_var.assert_any_call("OTEL_SPAN_TTL_SECONDS", default="3600")


def test_safe_attribute_value_preserves_primitives():
    """OTel-safe primitive values are returned unchanged."""
    for value in (True, b"bytes", 1, 1.5, "text"):
        safe_value = otel_safe_attribute_value(value)
        assert safe_value == value
        assert type(safe_value) is type(value)


class _Unserializable:
    def __repr__(self):
        return "unserializable"


def test_safe_attribute_value_serializes_structured_values():
    """Structured metadata values are converted to strings."""
    assert otel_safe_attribute_value(None) is None
    assert otel_safe_attribute_value({"nested": {"a": 1}}) == '{"nested":{"a":1}}'
    assert otel_safe_attribute_value(["a", 1]) == '["a",1]'
    assert (
        otel_safe_attribute_value({"bad": _Unserializable()})
        == "{'bad': unserializable}"
    )


def test_set_langsmith_metadata_attribute_sets_safe_values():
    """Metadata helper sets converted attributes and skips None."""
    span = MagicMock()

    set_langsmith_metadata_attribute(span, "extra", {"a": 1})
    set_langsmith_metadata_attribute(span, "empty", None)

    span.set_attribute.assert_called_once_with("langsmith.metadata.extra", '{"a":1}')


@patch(
    "langsmith.integrations.otel.processor.OtelExporter",
    return_value=MagicMock(),
)
@patch(
    "langsmith.integrations.otel.processor.OTEL_AVAILABLE",
    True,
)
def test_set_metadata_propagates_to_spans(mock_exporter_cls):
    """Test that set_metadata propagates attributes to every span on_start."""
    mock_inner_processor = MagicMock()
    processor = OtelSpanProcessor(
        api_key="test", project="test", SpanProcessor=lambda _: mock_inner_processor
    )

    processor.set_metadata(
        {"thread_id": "t-123", "session_id": "s-456", "extra": {"a": 1}}
    )

    span = MagicMock()
    processor.on_start(span, parent_context=None)

    span.set_attribute.assert_any_call("langsmith.metadata.thread_id", "t-123")
    span.set_attribute.assert_any_call("langsmith.metadata.session_id", "s-456")
    span.set_attribute.assert_any_call("langsmith.metadata.extra", '{"a":1}')
    mock_inner_processor.on_start.assert_called_once_with(span, None)


# --- Tests for get_otlp_tracer_provider ---


def _make_mock_otel_imports():
    """Build mock return value for _import_otel_client."""
    MockExporter = MagicMock(name="OTLPSpanExporter")
    MockSERVICE_NAME = "service.name"
    MockResource = MagicMock(name="Resource")
    MockTracerProvider = MagicMock(name="TracerProvider")
    MockBatchSpanProcessor = MagicMock(name="BatchSpanProcessor")
    return (
        MockExporter,
        MockSERVICE_NAME,
        MockResource,
        MockTracerProvider,
        MockBatchSpanProcessor,
    )


def _make_exporter() -> OTELExporter:
    with patch(
        "langsmith._internal.otel._otel_exporter._import_otel_exporter",
        return_value=(MagicMock(),) * 8,
    ):
        return OTELExporter()


def _attributes_for_outputs(outputs: dict) -> dict:
    span = MagicMock()
    op = SimpleNamespace(
        id=uuid.uuid4(),
        inputs=None,
        outputs=json.dumps(outputs).encode(),
    )
    _make_exporter()._set_io_attributes(span, op)
    return {call.args[0]: call.args[1] for call in span.set_attribute.call_args_list}


def test_finish_reasons_preserve_all_openai_choices_as_a_list():
    attrs = _attributes_for_outputs(
        {
            "choices": [
                {"finish_reason": "stop"},
                {"finish_reason": "length"},
            ]
        }
    )

    assert attrs[GEN_AI_RESPONSE_FINISH_REASONS] == ["stop", "length"]


def test_finish_reasons_support_anthropic_and_gemini_shapes():
    assert _attributes_for_outputs({"stop_reason": "tool_use"})[
        GEN_AI_RESPONSE_FINISH_REASONS
    ] == ["tool_use"]
    assert _attributes_for_outputs({"finish_reason": "STOP"})[
        GEN_AI_RESPONSE_FINISH_REASONS
    ] == ["STOP"]


def test_choices_finish_reasons_take_precedence_over_top_level_reason():
    attrs = _attributes_for_outputs(
        {
            "choices": [{"finish_reason": "stop"}],
            "stop_reason": "tool_use",
            "finish_reason": "STOP",
        }
    )

    assert attrs[GEN_AI_RESPONSE_FINISH_REASONS] == ["stop"]


def test_missing_finish_reason_is_omitted_and_commas_are_not_split():
    assert GEN_AI_RESPONSE_FINISH_REASONS not in _attributes_for_outputs(
        {"content": "hello"}
    )
    assert _attributes_for_outputs({"stop_reason": "provider,custom"})[
        GEN_AI_RESPONSE_FINISH_REASONS
    ] == ["provider,custom"]


def test_tool_attributes_use_run_name_and_tool_call_metadata():
    span = MagicMock()
    op = SimpleNamespace(id=uuid.uuid4(), inputs=None, outputs=None, operation="post")
    _make_exporter()._set_span_attributes(
        span,
        {
            "run_type": "tool",
            "name": "Bash",
            "extra": {"metadata": {"tool_call_id": "toolu_123"}},
        },
        op,
    )

    calls = {call.args[0]: call.args[1] for call in span.set_attribute.call_args_list}
    assert calls[GEN_AI_TOOL_NAME] == "Bash"
    assert calls[GEN_AI_TOOL_CALL_ID] == "toolu_123"


def test_tool_attributes_are_optional_and_tool_only():
    span = MagicMock()
    op = SimpleNamespace(id=uuid.uuid4(), inputs=None, outputs=None, operation="post")
    _make_exporter()._set_span_attributes(
        span,
        {"run_type": "tool", "name": "Bash", "extra": {"metadata": {}}},
        op,
    )
    _make_exporter()._set_span_attributes(
        span,
        {
            "run_type": "llm",
            "name": "model",
            "extra": {"metadata": {"tool_call_id": "toolu_123"}},
        },
        op,
    )

    keys = [call.args[0] for call in span.set_attribute.call_args_list]
    assert GEN_AI_TOOL_NAME in keys
    assert GEN_AI_TOOL_CALL_ID not in keys


@patch("langsmith._internal.otel._otel_client._import_otel_client")
@patch("langsmith._internal.otel._otel_client.ls_utils")
def test_get_otlp_tracer_provider_does_not_mutate_env(mock_utils, mock_import):
    """Env vars must not be written by get_otlp_tracer_provider."""
    mock_import.return_value = _make_mock_otel_imports()
    mock_utils.get_api_url.return_value = "https://api.smith.langchain.com"
    mock_utils.get_api_key.return_value = "lsv2_pt_test123"
    mock_utils.get_tracer_project.return_value = "my-project"

    # Snapshot env before
    env_before = dict(os.environ)

    from langsmith._internal.otel._otel_client import get_otlp_tracer_provider

    get_otlp_tracer_provider()

    # These specific keys must not have been added
    assert "OTEL_EXPORTER_OTLP_ENDPOINT" not in os.environ
    assert "OTEL_EXPORTER_OTLP_HEADERS" not in os.environ

    # Restore env (safety)
    os.environ.clear()
    os.environ.update(env_before)


@patch("langsmith._internal.otel._otel_client._import_otel_client")
@patch("langsmith._internal.otel._otel_client.ls_utils")
def test_get_otlp_tracer_provider_passes_defaults_to_exporter(mock_utils, mock_import):
    """Default endpoint and headers are passed directly to OTLPSpanExporter."""
    mocks = _make_mock_otel_imports()
    mock_import.return_value = mocks
    MockExporter = mocks[0]

    mock_utils.get_api_url.return_value = "https://api.smith.langchain.com"
    mock_utils.get_api_key.return_value = "lsv2_pt_test123"
    mock_utils.get_tracer_project.return_value = "my-project"

    from langsmith._internal.otel._otel_client import get_otlp_tracer_provider

    get_otlp_tracer_provider()

    MockExporter.assert_called_once_with(
        endpoint="https://api.smith.langchain.com/otel",
        headers={"x-api-key": "lsv2_pt_test123", "Langsmith-Project": "my-project"},
    )


@patch("langsmith._internal.otel._otel_client._import_otel_client")
@patch("langsmith._internal.otel._otel_client.ls_utils")
def test_get_otlp_tracer_provider_honors_env_overrides(mock_utils, mock_import):
    """User-set OTEL env vars are read and passed through to the exporter."""
    mocks = _make_mock_otel_imports()
    mock_import.return_value = mocks
    MockExporter = mocks[0]

    env_patch = {
        "OTEL_EXPORTER_OTLP_ENDPOINT": "https://custom-collector:4318",
        "OTEL_EXPORTER_OTLP_HEADERS": "Authorization=Bearer custom-token",
    }

    from langsmith._internal.otel._otel_client import get_otlp_tracer_provider

    with patch.dict(os.environ, env_patch):
        get_otlp_tracer_provider()

    MockExporter.assert_called_once_with(
        endpoint="https://custom-collector:4318",
        headers={"Authorization": "Bearer custom-token"},
    )
    # LangSmith utils should NOT have been called for key/endpoint
    mock_utils.get_api_key.assert_not_called()
    mock_utils.get_api_url.assert_not_called()


@patch("langsmith._internal.otel._otel_client._import_otel_client")
@patch("langsmith._internal.otel._otel_client.ls_utils")
def test_get_otlp_tracer_provider_no_project(mock_utils, mock_import):
    """When no project is configured, headers contain only the API key."""
    mocks = _make_mock_otel_imports()
    mock_import.return_value = mocks
    MockExporter = mocks[0]

    mock_utils.get_api_url.return_value = "https://api.smith.langchain.com"
    mock_utils.get_api_key.return_value = "lsv2_pt_test123"
    mock_utils.get_tracer_project.return_value = None

    from langsmith._internal.otel._otel_client import get_otlp_tracer_provider

    get_otlp_tracer_provider()

    MockExporter.assert_called_once_with(
        endpoint="https://api.smith.langchain.com/otel",
        headers={"x-api-key": "lsv2_pt_test123"},
    )
