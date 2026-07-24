"""Unit tests for _v2_migration_utils — field mapping and .raw unwrapping."""

import datetime
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from langsmith._internal._v2_migration_utils import _v2_run_to_schema


def _make_v2_run(**kwargs):
    """Return a SimpleNamespace that quacks like the generated v2 Run model."""
    defaults = dict(
        id=str(uuid.uuid4()),
        name="test_run",
        run_type="CHAIN",
        start_time=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
        end_time=None,
        trace_id=str(uuid.uuid4()),
        project_id=str(uuid.uuid4()),
        parent_run_ids=[],
        dotted_order=None,
        reference_example_id=None,
        inputs={"x": 1},
        outputs=None,
        error=None,
        status="SUCCESS",
        tags=None,
        extra=None,
        events=None,
        feedback_stats=None,
        first_token_time=None,
        app_path=None,
        prompt_tokens=None,
        completion_tokens=None,
        total_tokens=None,
        prompt_cost=None,
        completion_cost=None,
        total_cost=None,
        prompt_token_details=None,
        completion_token_details=None,
        prompt_cost_details=None,
        completion_cost_details=None,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# run_type / status normalisation
# ---------------------------------------------------------------------------


def test_run_type_lowercased():
    result = _v2_run_to_schema(_make_v2_run(run_type="LLM"))
    assert result.run_type == "llm"


def test_run_type_chain_lowercased():
    result = _v2_run_to_schema(_make_v2_run(run_type="CHAIN"))
    assert result.run_type == "chain"


def test_status_lowercased():
    result = _v2_run_to_schema(_make_v2_run(status="ERROR"))
    assert result.status == "error"


# ---------------------------------------------------------------------------
# parent_run_id
# ---------------------------------------------------------------------------


def test_parent_run_id_set_to_last_ancestor():
    grandparent = str(uuid.uuid4())
    parent = str(uuid.uuid4())
    result = _v2_run_to_schema(_make_v2_run(parent_run_ids=[grandparent, parent]))
    assert result.parent_run_id == parent


def test_no_parent_run_id_when_root():
    result = _v2_run_to_schema(_make_v2_run(parent_run_ids=[]))
    assert result.parent_run_id is None


# ---------------------------------------------------------------------------
# tags / extra
# ---------------------------------------------------------------------------


def test_tags_passed_through():
    result = _v2_run_to_schema(_make_v2_run(tags=["production", "v2"]))
    assert result.tags == ["production", "v2"]


def test_extra_passed_through():
    extra = {"metadata": {"env": "prod"}, "raw_payload": True}
    result = _v2_run_to_schema(_make_v2_run(extra=extra))
    assert result.extra == extra


# ---------------------------------------------------------------------------
# events — each element is a Pydantic model; must call .model_dump()
# ---------------------------------------------------------------------------


def test_events_converted_via_model_dump():
    event = MagicMock()
    event.model_dump.return_value = {"name": "start", "time": "2024-01-01T00:00:00Z"}
    result = _v2_run_to_schema(_make_v2_run(events=[event]))
    assert result.events == [{"name": "start", "time": "2024-01-01T00:00:00Z"}]
    event.model_dump.assert_called_once()


def test_multiple_events_all_converted():
    e1, e2 = MagicMock(), MagicMock()
    e1.model_dump.return_value = {"name": "start"}
    e2.model_dump.return_value = {"name": "end"}
    result = _v2_run_to_schema(_make_v2_run(events=[e1, e2]))
    assert result.events == [{"name": "start"}, {"name": "end"}]


# ---------------------------------------------------------------------------
# feedback_stats — values are Pydantic models; must call .model_dump()
# ---------------------------------------------------------------------------


def test_feedback_stats_values_serialised():
    fs = MagicMock()
    fs.model_dump.return_value = {"avg": 0.8, "comments": ["great"]}
    result = _v2_run_to_schema(_make_v2_run(feedback_stats={"quality": fs}))
    assert result.feedback_stats == {"quality": {"avg": 0.8, "comments": ["great"]}}


def test_feedback_stats_multiple_keys():
    f1, f2 = MagicMock(), MagicMock()
    f1.model_dump.return_value = {"avg": 1.0}
    f2.model_dump.return_value = {"avg": None, "comments": ["ok"]}
    result = _v2_run_to_schema(
        _make_v2_run(feedback_stats={"score": f1, "notes": f2})
    )
    assert result.feedback_stats["score"] == {"avg": 1.0}
    assert result.feedback_stats["notes"] == {"avg": None, "comments": ["ok"]}


# ---------------------------------------------------------------------------
# token / cost scalars
# ---------------------------------------------------------------------------


def test_token_scalars_passed_through():
    result = _v2_run_to_schema(
        _make_v2_run(prompt_tokens=10, completion_tokens=20, total_tokens=30)
    )
    assert result.prompt_tokens == 10
    assert result.completion_tokens == 20
    assert result.total_tokens == 30


# ---------------------------------------------------------------------------
# token / cost detail maps — wrapped in .raw on the v2 wire; must unwrap
# ---------------------------------------------------------------------------


def test_prompt_token_details_raw_unwrapped():
    ptd = SimpleNamespace(raw={"cache_read": 5, "audio": 2})
    result = _v2_run_to_schema(_make_v2_run(prompt_token_details=ptd))
    assert result.prompt_token_details == {"cache_read": 5, "audio": 2}


def test_completion_token_details_raw_unwrapped():
    ctd = SimpleNamespace(raw={"reasoning": 8, "audio": 1})
    result = _v2_run_to_schema(_make_v2_run(completion_token_details=ctd))
    assert result.completion_token_details == {"reasoning": 8, "audio": 1}


def test_prompt_cost_details_raw_unwrapped():
    pcd = SimpleNamespace(raw={"cache_read": 1e-4, "cache_creation": 2e-4})
    result = _v2_run_to_schema(_make_v2_run(prompt_cost_details=pcd))
    assert set(result.prompt_cost_details.keys()) == {"cache_read", "cache_creation"}


def test_completion_cost_details_raw_unwrapped():
    ccd = SimpleNamespace(raw={"reasoning": 5e-4})
    result = _v2_run_to_schema(_make_v2_run(completion_cost_details=ccd))
    assert "reasoning" in result.completion_cost_details


def test_none_detail_stays_none():
    result = _v2_run_to_schema(_make_v2_run())
    assert result.prompt_token_details is None
    assert result.completion_token_details is None
    assert result.prompt_cost_details is None
    assert result.completion_cost_details is None


# ---------------------------------------------------------------------------
# first_token_time / app_path
# ---------------------------------------------------------------------------


def test_first_token_time_passed_through():
    t = datetime.datetime(2024, 6, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
    result = _v2_run_to_schema(_make_v2_run(first_token_time=t))
    assert result.first_token_time == t


def test_app_path_passed_through():
    path = "/o/my-org/projects/p/abc123/r/run-id"
    result = _v2_run_to_schema(_make_v2_run(app_path=path))
    assert result.app_path == path
