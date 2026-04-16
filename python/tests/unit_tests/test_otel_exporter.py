"""Unit tests for OTEL exporter and span processor."""

import os
import time
import uuid
from unittest.mock import MagicMock, patch

from langsmith._internal.otel._otel_exporter import OTELExporter
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

        exporter._span_info[stale_id] = {
            "span": stale_span,
            "created_at": time.time() - 2,
        }
        exporter._span_info[fresh_id] = {"span": fresh_span, "created_at": time.time()}
        exporter._last_cleanup = 0.0  # Force cleanup

        exporter._cleanup_stale_spans()

        # Verify cleanup
        assert stale_id not in exporter._span_info
        assert fresh_id in exporter._span_info
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

        exporter._span_info[stale_id] = {
            "span": stale_span,
            "created_at": time.time() - 2,
        }
        exporter._last_cleanup = time.time() - 5  # Recent cleanup

        exporter._cleanup_stale_spans()

        # Should not clean up due to periodic check
        assert stale_id in exporter._span_info
        stale_span.end.assert_not_called()


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

    processor.set_metadata({"thread_id": "t-123", "session_id": "s-456"})

    span = MagicMock()
    processor.on_start(span, parent_context=None)

    span.set_attribute.assert_any_call("langsmith.metadata.thread_id", "t-123")
    span.set_attribute.assert_any_call("langsmith.metadata.session_id", "s-456")
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
