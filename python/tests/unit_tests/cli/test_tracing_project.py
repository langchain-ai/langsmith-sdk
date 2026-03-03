"""Tests for tracing project commands."""

import json
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from langsmith.cli.main import cli


def _make_project(
    name="my-project",
    run_count=100,
    latency_p50=None,
    latency_p99=None,
    total_tokens=5000,
    total_cost=None,
    error_rate=0.02,
    last_run_start_time=None,
    description=None,
):
    return SimpleNamespace(
        id=uuid.uuid4(),
        name=name,
        description=description,
        run_count=run_count,
        latency_p50=latency_p50,
        latency_p99=latency_p99,
        total_tokens=total_tokens,
        total_cost=total_cost,
        error_rate=error_rate,
        last_run_start_time=last_run_start_time,
        start_time=datetime.now(timezone.utc),
        reference_dataset_id=None,
    )


class TestProjectList:
    def test_project_list_json(self, runner, mock_client):
        projects = [
            _make_project(name="app-prod"),
            _make_project(name="app-staging"),
        ]
        mock_client.list_projects.return_value = projects

        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "project", "list",
        ])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 2
        assert data[0]["name"] == "app-prod"
        assert data[1]["name"] == "app-staging"

    def test_project_list_passes_reference_free(self, runner, mock_client):
        mock_client.list_projects.return_value = []

        runner.invoke(cli, [
            "--api-key", "test-key",
            "project", "list",
        ])

        call_kwargs = mock_client.list_projects.call_args[1]
        assert call_kwargs["reference_free"] is True

    def test_project_list_default_limit(self, runner, mock_client):
        mock_client.list_projects.return_value = []

        runner.invoke(cli, [
            "--api-key", "test-key",
            "project", "list",
        ])

        call_kwargs = mock_client.list_projects.call_args[1]
        assert call_kwargs["limit"] == 20

    def test_project_list_custom_limit(self, runner, mock_client):
        mock_client.list_projects.return_value = []

        runner.invoke(cli, [
            "--api-key", "test-key",
            "project", "list",
            "--limit", "50",
        ])

        call_kwargs = mock_client.list_projects.call_args[1]
        assert call_kwargs["limit"] == 50

    def test_project_list_name_contains(self, runner, mock_client):
        mock_client.list_projects.return_value = []

        runner.invoke(cli, [
            "--api-key", "test-key",
            "project", "list",
            "--name-contains", "chatbot",
        ])

        call_kwargs = mock_client.list_projects.call_args[1]
        assert call_kwargs["name_contains"] == "chatbot"

    def test_project_list_name_contains_not_passed_when_omitted(self, runner, mock_client):
        mock_client.list_projects.return_value = []

        runner.invoke(cli, [
            "--api-key", "test-key",
            "project", "list",
        ])

        call_kwargs = mock_client.list_projects.call_args[1]
        assert "name_contains" not in call_kwargs

    def test_project_list_json_fields(self, runner, mock_client):
        projects = [
            _make_project(
                name="my-app",
                run_count=200,
                latency_p50=timedelta(seconds=1.5),
                latency_p99=timedelta(seconds=8.2),
                total_tokens=50000,
                error_rate=0.05,
            ),
        ]
        mock_client.list_projects.return_value = projects

        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "project", "list",
        ])

        assert result.exit_code == 0
        data = json.loads(result.output)
        entry = data[0]
        assert entry["name"] == "my-app"
        assert entry["run_count"] == 200
        assert entry["latency_p50"] == 1.5
        assert entry["latency_p99"] == 8.2
        assert entry["total_tokens"] == 50000
        assert entry["error_rate"] == 0.05
        assert "id" in entry
        assert "start_time" in entry

    def test_project_list_null_fields(self, runner, mock_client):
        projects = [
            _make_project(
                name="empty-project",
                run_count=None,
                latency_p50=None,
                latency_p99=None,
                total_tokens=None,
                total_cost=None,
                error_rate=None,
                last_run_start_time=None,
            ),
        ]
        mock_client.list_projects.return_value = projects

        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "project", "list",
        ])

        assert result.exit_code == 0
        data = json.loads(result.output)
        entry = data[0]
        assert entry["run_count"] is None
        assert entry["latency_p50"] is None
        assert entry["latency_p99"] is None
        assert entry["total_cost"] is None
        assert entry["error_rate"] is None
        assert entry["last_run_start_time"] is None

    def test_project_list_pretty(self, runner, mock_client):
        projects = [
            _make_project(
                name="pretty-app",
                latency_p50=timedelta(milliseconds=250),
                error_rate=0.1,
                last_run_start_time=datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc),
            ),
        ]
        mock_client.list_projects.return_value = projects

        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "--format", "pretty",
            "project", "list",
        ])

        assert result.exit_code == 0
        assert "pretty-app" in result.output
        assert "Tracing Projects" in result.output

    def test_project_list_to_file(self, runner, mock_client, tmp_path):
        projects = [_make_project(name="file-project")]
        mock_client.list_projects.return_value = projects

        output_file = str(tmp_path / "projects.json")
        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "project", "list",
            "-o", output_file,
        ])

        assert result.exit_code == 0
        with open(output_file) as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["name"] == "file-project"

    def test_project_list_total_cost_decimal(self, runner, mock_client):
        from decimal import Decimal
        projects = [
            _make_project(name="costly-app", total_cost=Decimal("12.345")),
        ]
        mock_client.list_projects.return_value = projects

        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "project", "list",
        ])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["total_cost"] == 12.345

    def test_project_list_empty(self, runner, mock_client):
        mock_client.list_projects.return_value = []

        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "project", "list",
        ])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == []
