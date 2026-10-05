"""Unit tests for Insights report helpers and client.get_insights_report."""

from __future__ import annotations

from typing import Any, Dict, List
from uuid import UUID

import pytest

from langsmith import schemas as ls_schemas
from langsmith.client import Client


class _DummyResponse:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def json(self) -> Any:
        return self._payload

    def raise_for_status(self) -> None:
        """Match the API used by raise_for_status_with_text."""
        return None


class _DummyClient(Client):
    def __init__(self, responses: List[Any]) -> None:  # type: ignore[no-untyped-def]
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


def test_insights_report_link_uses_insights_tab() -> None:
    report = ls_schemas.InsightsReport(
        id="11111111-1111-1111-1111-111111111111",
        name="test-report",
        status="success",
        project_id="22222222-2222-2222-2222-222222222222",
        host_url="https://smith.langchain.com",
        tenant_id="33333333-3333-3333-3333-333333333333",
    )

    expected_link = (
        "https://smith.langchain.com/o/"
        "33333333-3333-3333-3333-333333333333/projects/p/"
        "22222222-2222-2222-2222-222222222222?"
        "tab=3&clusterJobId=11111111-1111-1111-1111-111111111111"
    )
    assert report.link == expected_link


def test_insights_report_repr_html_escapes_name_and_link() -> None:
    report = ls_schemas.InsightsReport(
        id="job-id",
        name='bad\');</a><script>alert("x")</script>',
        status="success",
        project_id="project-id",
        host_url='https://smith.langchain.com/" onclick="alert(1)',
        tenant_id="tenant-id",
    )

    expected_href = (
        "https://smith.langchain.com/&quot; onclick=&quot;alert(1)/o/tenant-id/"
        "projects/p/project-id?tab=3&amp;clusterJobId=job-id"
    )
    expected_name = (
        "bad&#x27;);&lt;/a&gt;&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;"
    )
    assert report._repr_html_() == (
        f'<a href="{expected_href}", target="_blank" rel="noopener">'
        f"InsightsReport('{expected_name}')</a>"
    )


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


class _GenerateInsightsClient(_DummyClient):
    """_DummyClient plus the attributes generate_insights reads off a real Client."""

    _TENANT_ID = "44444444-4444-4444-4444-444444444444"

    def _get_tenant_id(self) -> str:  # type: ignore[override]
        return self._TENANT_ID

    @property
    def _host_url(self) -> str:  # type: ignore[override]
        return "https://smith.langchain.com"


def _make_secrets_payload() -> List[Dict[str, str]]:
    return [{"key": "OPENAI_API_KEY"}]


def _make_job_payload() -> Dict[str, Any]:
    return {
        "id": "11111111-1111-1111-1111-111111111111",
        "name": "test-report",
        "status": "queued",
        "error": None,
    }


def _make_project_payload(project_id: str) -> Dict[str, Any]:
    return {
        "id": project_id,
        "name": "my-agent",
        "tenant_id": _GenerateInsightsClient._TENANT_ID,
        "reference_dataset_id": None,
    }


def test_generate_insights_over_existing_project_id() -> None:
    project_id = "55555555-5555-5555-5555-555555555555"
    client = _GenerateInsightsClient([_make_secrets_payload(), _make_job_payload()])

    report = client.generate_insights(
        project_id=project_id,
        name="Conversation Topics",
        instructions="What do users ask about?",
        last_n_hours=24,
        filter="eq(is_root, true)",
        sample=0.1,
    )

    assert isinstance(report, ls_schemas.InsightsReport)
    assert str(report.project_id) == project_id
    assert f"clusterJobId={report.id}" in report.link

    create_call = client._calls[1]
    assert create_call["method"] == "POST"
    assert create_call["path"] == f"/sessions/{project_id}/insights"

    body = create_call["kwargs"]["json"]
    assert body["last_n_hours"] == 24
    assert body["filter"] == "eq(is_root, true)"
    assert body["sample"] == 0.1
    # Unset run-selection keys are omitted so the server applies its defaults.
    assert "start_time" not in body
    assert "end_time" not in body
    assert (
        body["user_context"]["What would you like to learn about your agent?"]
        == "What do users ask about?"
    )


def test_generate_insights_resolves_project_name() -> None:
    project_id = "55555555-5555-5555-5555-555555555555"
    client = _GenerateInsightsClient(
        [
            _make_secrets_payload(),
            [_make_project_payload(project_id)],
            _make_job_payload(),
        ]
    )

    client.generate_insights(project_name="my-agent")

    read_call = client._calls[1]
    assert read_call["path"] == "/sessions"
    assert read_call["kwargs"]["params"]["name"] == "my-agent"
    assert client._calls[2]["path"] == f"/sessions/{project_id}/insights"


def test_generate_insights_passes_trace_structure() -> None:
    client = _GenerateInsightsClient([_make_secrets_payload(), _make_job_payload()])

    client.generate_insights(
        project_id="55555555-5555-5555-5555-555555555555",
        trace_structure="Look at outputs.answer.",
    )

    body = client._calls[1]["kwargs"]["json"]
    assert (
        body["user_context"]["How are your agent traces structured?"]
        == "Look at outputs.answer."
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"project_id": "p", "project_name": "my-agent"},
        {"chat_histories": [], "project_name": "my-agent"},
    ],
)
def test_generate_insights_requires_exactly_one_source(kwargs: Dict[str, Any]) -> None:
    client = _GenerateInsightsClient([])

    with pytest.raises(ValueError, match="Exactly one argument"):
        client.generate_insights(**kwargs)

    assert client._calls == []


def test_generate_insights_rejects_run_selection_with_chat_histories() -> None:
    client = _GenerateInsightsClient([])

    with pytest.raises(ValueError, match="cannot be used with 'chat_histories'"):
        client.generate_insights(chat_histories=[], last_n_hours=24)

    assert client._calls == []
