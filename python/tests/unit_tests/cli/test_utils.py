"""Tests for utils.py - extract_run, calc_duration, format_duration, etc."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

from langsmith.cli.utils import (
    _serialize,
    calc_duration,
    extract_run,
    format_duration,
    get_trace_id,
)
from tests.unit_tests.cli.conftest import make_run


class TestCalcDuration:
    def test_normal_duration(self):
        run = make_run(
            start_time=datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2024, 1, 1, 0, 0, 2, tzinfo=timezone.utc),
        )
        assert calc_duration(run) == 2000

    def test_sub_second_duration(self):
        start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        end = start + timedelta(milliseconds=150)
        run = make_run(start_time=start, end_time=end)
        assert calc_duration(run) == 150

    def test_no_start_time(self):
        run = SimpleNamespace(start_time=None, end_time=datetime.now(timezone.utc))
        assert calc_duration(run) is None

    def test_no_end_time(self):
        run = SimpleNamespace(start_time=datetime.now(timezone.utc), end_time=None)
        assert calc_duration(run) is None

    def test_both_none(self):
        run = SimpleNamespace(start_time=None, end_time=None)
        assert calc_duration(run) is None


class TestFormatDuration:
    def test_none(self):
        assert format_duration(None) == "N/A"

    def test_milliseconds(self):
        assert format_duration(500) == "500ms"

    def test_zero(self):
        assert format_duration(0) == "0ms"

    def test_exactly_one_second(self):
        assert format_duration(1000) == "1.00s"

    def test_seconds(self):
        assert format_duration(2500) == "2.50s"

    def test_large_duration(self):
        assert format_duration(65000) == "65.00s"

    def test_boundary_999ms(self):
        assert format_duration(999) == "999ms"


class TestGetTraceId:
    def test_with_trace_id(self):
        run = make_run(trace_id=uuid.UUID("12345678-1234-1234-1234-123456789abc"))
        assert get_trace_id(run) == "12345678-1234-1234-1234-123456789abc"

    def test_no_trace_id_falls_back_to_run_id(self):
        rid = uuid.UUID("abcdef01-abcd-abcd-abcd-abcdef012345")
        run = SimpleNamespace(id=rid, trace_id=None)
        assert get_trace_id(run) == str(rid)

    def test_missing_trace_id_attr(self):
        rid = uuid.UUID("abcdef01-abcd-abcd-abcd-abcdef012345")
        run = SimpleNamespace(id=rid)
        assert get_trace_id(run) == str(rid)


class TestSerialize:
    def test_none(self):
        assert _serialize(None) is None

    def test_decimal(self):
        assert _serialize(Decimal("3.14")) == 3.14

    def test_dict(self):
        result = _serialize({"a": Decimal("1.5"), "b": None})
        assert result == {"a": 1.5, "b": None}

    def test_list(self):
        result = _serialize([Decimal("1"), Decimal("2")])
        assert result == [1.0, 2.0]

    def test_tuple(self):
        result = _serialize((Decimal("1"), "hello"))
        assert result == [1.0, "hello"]

    def test_nested(self):
        result = _serialize({"nested": [{"val": Decimal("42")}]})
        assert result == {"nested": [{"val": 42.0}]}

    def test_passthrough_string(self):
        assert _serialize("hello") == "hello"

    def test_passthrough_int(self):
        assert _serialize(42) == 42


class TestExtractRun:
    def test_base_fields(self):
        run = make_run(name="my-run", run_type="llm")
        result = extract_run(run)

        assert result["run_id"] == str(run.id)
        assert result["trace_id"] == str(run.trace_id)
        assert result["name"] == "my-run"
        assert result["run_type"] == "llm"
        assert result["parent_run_id"] is None
        assert result["start_time"] is not None
        assert result["end_time"] is not None
        # Base fields should NOT include metadata or IO
        assert "status" not in result
        assert "inputs" not in result

    def test_base_with_parent_run_id(self):
        pid = uuid.uuid4()
        run = make_run(parent_run_id=pid)
        result = extract_run(run)
        assert result["parent_run_id"] == str(pid)

    def test_include_metadata(self):
        run = make_run(
            status="success",
            total_tokens=100,
            prompt_tokens=60,
            completion_tokens=40,
            prompt_cost=Decimal("0.001"),
            completion_cost=Decimal("0.002"),
            total_cost=Decimal("0.003"),
            tags=["production", "v2"],
            extra={"metadata": {"model": "gpt-4"}},
        )
        result = extract_run(run, include_metadata=True)

        assert result["status"] == "success"
        assert result["duration_ms"] is not None
        assert result["token_usage"]["total_tokens"] == 100
        assert result["token_usage"]["prompt_tokens"] == 60
        assert result["token_usage"]["completion_tokens"] == 40
        assert result["costs"]["prompt_cost"] == 0.001
        assert result["costs"]["completion_cost"] == 0.002
        assert result["costs"]["total_cost"] == 0.003
        assert result["tags"] == ["production", "v2"]
        assert result["custom_metadata"] == {"model": "gpt-4"}

    def test_include_metadata_no_tokens(self):
        run = make_run()
        result = extract_run(run, include_metadata=True)
        assert result["token_usage"] is None
        assert result["costs"] is None

    def test_include_metadata_no_tags(self):
        run = make_run(tags=[])
        result = extract_run(run, include_metadata=True)
        assert result["tags"] is None

    def test_include_io(self):
        run = make_run(
            inputs={"query": "hello"},
            outputs={"response": "world"},
            error="something went wrong",
        )
        result = extract_run(run, include_io=True)

        assert result["inputs"] == {"query": "hello"}
        assert result["outputs"] == {"response": "world"}
        assert result["error"] == "something went wrong"

    def test_include_io_empty_inputs(self):
        run = make_run(inputs={}, outputs={})
        result = extract_run(run, include_io=True)
        assert result["inputs"] is None
        assert result["outputs"] is None

    def test_full_run(self):
        run = make_run(
            inputs={"q": "hi"},
            outputs={"a": "bye"},
            total_tokens=50,
            status="success",
        )
        result = extract_run(run, include_metadata=True, include_io=True)

        # All sections present
        assert "status" in result
        assert "inputs" in result
        assert "run_id" in result

    def test_metadata_with_no_extra(self):
        run = make_run()
        run.extra = None
        result = extract_run(run, include_metadata=True)
        assert result["custom_metadata"] == {}

    def test_metadata_with_extra_not_dict(self):
        run = make_run()
        run.extra = "not a dict"
        result = extract_run(run, include_metadata=True)
        assert result["custom_metadata"] == {}

    def test_io_serialize_decimal(self):
        run = make_run(inputs={"cost": Decimal("1.5")}, outputs={"score": Decimal("0.9")})
        result = extract_run(run, include_io=True)
        assert result["inputs"]["cost"] == 1.5
        assert result["outputs"]["score"] == 0.9
