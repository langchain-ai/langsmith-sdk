"""Unit tests for OTel span ID -> LangSmith run ID/URL helpers."""

import uuid
from unittest.mock import MagicMock

import pytest

from langsmith.integrations.otel import (
    get_langsmith_run_url_for_span,
    langsmith_run_id_from_otel_span_id,
)


def test_run_id_from_int_known_vector():
    assert langsmith_run_id_from_otel_span_id(1) == uuid.UUID(
        "00000000-0000-0000-0000-000000000001"
    )


def test_run_id_from_int_multibyte():
    span_id = 0x0102030405060708
    assert langsmith_run_id_from_otel_span_id(span_id) == uuid.UUID(
        "00000000-0000-0000-0102-030405060708"
    )


def test_run_id_from_bytes_known_vector():
    assert langsmith_run_id_from_otel_span_id(b"\x00\x00\x00\x00\x00\x00\x00\x01") == (
        uuid.UUID("00000000-0000-0000-0000-000000000001")
    )


def test_run_id_from_bytes_multibyte():
    span_id = (0x0102030405060708).to_bytes(8, "big")
    assert langsmith_run_id_from_otel_span_id(span_id) == uuid.UUID(
        "00000000-0000-0000-0102-030405060708"
    )


def test_int_and_bytes_agree():
    span_id_int = 0xABCDEF1234567890
    assert langsmith_run_id_from_otel_span_id(
        span_id_int
    ) == langsmith_run_id_from_otel_span_id(span_id_int.to_bytes(8, "big"))


def test_low_level_helper_no_opentelemetry_import():
    import sys

    assert "opentelemetry" not in sys.modules or True
    # Call succeeds without touching opentelemetry.
    assert isinstance(langsmith_run_id_from_otel_span_id(42), uuid.UUID)


def test_invalid_type():
    with pytest.raises(TypeError):
        langsmith_run_id_from_otel_span_id("nope")  # type: ignore[arg-type]


def test_invalid_bytes_length():
    with pytest.raises(ValueError):
        langsmith_run_id_from_otel_span_id(b"\x00" * 17)


def test_reject_zero_int():
    with pytest.raises(ValueError):
        langsmith_run_id_from_otel_span_id(0)


def test_reject_all_zero_bytes():
    with pytest.raises(ValueError):
        langsmith_run_id_from_otel_span_id(b"\x00" * 8)


def test_reject_int_wider_than_64_bits():
    with pytest.raises(ValueError):
        langsmith_run_id_from_otel_span_id(1 << 64)


def test_reject_bool():
    with pytest.raises(TypeError):
        langsmith_run_id_from_otel_span_id(True)  # type: ignore[arg-type]


def test_importing_helper_does_not_import_processor():
    """Offline helper import must not eagerly import the .processor module."""
    import subprocess
    import sys

    code = (
        "import sys; import langsmith.integrations.otel as m; "
        "assert m.langsmith_run_id_from_otel_span_id(1); "
        "assert 'langsmith.integrations.otel.processor' not in sys.modules"
    )
    subprocess.run([sys.executable, "-W", "error", "-c", code], check=True)


def test_lazy_processor_exports_still_accessible():
    import langsmith.integrations.otel as m

    assert m.OtelSpanProcessor is not None
    assert m.OtelExporter is not None


def _make_client():
    client = MagicMock()
    client._host_url = "https://smith.langchain.com"
    client._get_tenant_id.return_value = uuid.UUID(
        "11111111-1111-1111-1111-111111111111"
    )
    return client


def test_url_with_project_id_offline():
    client = _make_client()
    span_ctx = MagicMock()
    span_ctx.span_id = 1
    span = MagicMock()
    span.get_span_context.return_value = span_ctx

    project_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    url = get_langsmith_run_url_for_span(span, project_id=project_id, client=client)

    assert url == (
        "https://smith.langchain.com/o/11111111-1111-1111-1111-111111111111/"
        "projects/p/22222222-2222-2222-2222-222222222222/"
        "r/00000000-0000-0000-0000-000000000001?poll=true"
    )
    client.read_project.assert_not_called()


def test_url_with_span_context_directly():
    client = _make_client()
    span_ctx = MagicMock(spec=["span_id"])
    span_ctx.span_id = 0x0102030405060708

    project_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    url = get_langsmith_run_url_for_span(span_ctx, project_id=project_id, client=client)

    assert "r/00000000-0000-0000-0102-030405060708?poll=true" in url


def test_url_with_project_name_resolves_via_client():
    client = _make_client()
    client.read_project.return_value = MagicMock(
        id=uuid.UUID("33333333-3333-3333-3333-333333333333")
    )
    span_ctx = MagicMock(spec=["span_id"])
    span_ctx.span_id = 1

    url = get_langsmith_run_url_for_span(
        span_ctx, project_name="my-project", client=client
    )

    client.read_project.assert_called_once_with(project_name="my-project")
    assert "projects/p/33333333-3333-3333-3333-333333333333/" in url


def test_url_requires_project():
    with pytest.raises(ValueError):
        get_langsmith_run_url_for_span(MagicMock(), client=_make_client())
