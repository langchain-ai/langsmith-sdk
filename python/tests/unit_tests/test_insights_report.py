"""Unit tests for Insights report helpers and client.get_insights_report."""

from __future__ import annotations

from typing import Any, Dict, List
from uuid import UUID

from langsmith import schemas as ls_schemas
from langsmith.client import Client


class _DummyResponse:
    def __init__(self, payload: Dict[str, Any]) -> None:
        self._payload = payload

    def json(self) -> Dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        """Match the API used by raise_for_status_with_text."""
        return None


class _DummyClient(Client):
    def __init__(self, responses: List[Dict[str, Any]]) -> None:  # type: ignore[no-untyped-def]
        self._responses = responses
        self._calls: List[Dict[str, Any]] = []

    def request_with_retries(  # type: ignore[override]
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> _DummyResponse:
        self._calls.append({"method": method, "path": path, "kwargs": kwargs})
        return _DummyResponse(self._responses[len(self._calls) - 1])


def _make_report_payload() -> Dict[str, Any]:
    return {
        "id": "11111111-1111-1111-1111-111111111111",
        "name": "test-report",
        "status": "success",
        "start_time": "2026-02-12T22:14:48.648851+00:00",
        "end_time": "2026-02-12T23:14:48.648851+00:00",
        "created_at": "2026-02-12T23:14:48.649882+00:00",
        "metadata": {
            "report": {
                "title": "Test title",
                "key_points": [],
                "highlighted_traces": [],
            }
        },
        "shape": {"cluster-a": 2},
        "error": None,
        "config_id": "22222222-2222-2222-2222-222222222222",
        "clusters": [
            {
                "id": "33333333-3333-3333-3333-333333333333",
                "parent_id": None,
                "level": 0,
                "name": "cluster-a",
                "description": "Cluster A",
                "parent_name": None,
                "num_runs": 2,
                "stats": {"run_count": 2},
            }
        ],
        "report": {
            "key_points": [],
            "title": "Test title",
            "highlighted_traces": [],
            "created_at": "2026-02-12T23:15:26.092278+00:00",
        },
    }


def _make_runs_page_payload(offset: int, has_next: bool) -> Dict[str, Any]:
    runs = [
        {"id": f"run-{offset}-1"},
        {"id": f"run-{offset}-2"},
    ]
    return {
        "runs": runs,
        "offset": offset + 2 if has_next else None,
    }


def test_get_insights_report_basic_metadata() -> None:
    payload = _make_report_payload()
    client = _DummyClient([payload])

    result = client.get_insights_report(
        id=UUID(int=1), project_id=UUID(int=2), include_runs=False
    )

    assert isinstance(result, ls_schemas.InsightsReportResult)
    assert result.id == payload["id"]
    assert result.name == payload["name"]
    assert result.status == "success"
    assert result.shape == {"cluster-a": 2}
    assert len(result.clusters) == 1
    assert result.report is not None
    assert result.report.title == "Test title"

    cluster = result.clusters["cluster-a"]
    assert cluster.name == "cluster-a"
    assert cluster.num_runs == 2


def test_get_insights_report_with_runs_and_cluster_load_traces() -> None:
    report_payload = _make_report_payload()
    runs_page_1 = _make_runs_page_payload(offset=0, has_next=True)
    runs_page_2 = _make_runs_page_payload(offset=2, has_next=False)

    # get_insights_report uses 3 responses; load_traces() uses 2 more
    client = _DummyClient(
        [report_payload, runs_page_1, runs_page_2, runs_page_1, runs_page_2]
    )

    result = client.get_insights_report(
        id="job-id", project_id="project-id", include_runs=True
    )

    assert len(result.runs) == 4

    cluster = result.clusters["cluster-a"]
    traces = cluster.load_traces()
    assert len(traces) == 4

    assert client._calls[0]["path"] == "/sessions/project-id/insights/job-id"
    # Calls 1–2: get_insights_report (no cluster_id); 3–4: load_traces (with cluster_id)
    run_calls_with_cluster = [
        c for c in client._calls[1:] if c["kwargs"].get("params", {}).get("cluster_id")
    ]
    assert len(run_calls_with_cluster) == 2
    for call in run_calls_with_cluster:
        assert "/insights/job-id/runs" in call["path"]
        assert call["kwargs"]["params"]["cluster_id"] == str(cluster.id)
