"""Unit tests for OTELExporter cleanup functionality."""

import time
import uuid
from unittest.mock import MagicMock, patch

from langsmith._internal.otel._otel_exporter import OTELExporter


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
        mock_get_env_var.assert_called_with("OTEL_SPAN_TTL_SECONDS", default="3600")
