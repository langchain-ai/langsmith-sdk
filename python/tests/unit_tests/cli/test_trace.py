"""Tests for trace commands."""

import json
import os

from langsmith.cli.main import cli
from tests.unit_tests.cli.conftest import make_run


class TestTraceList:
    def test_trace_list_json(self, runner, mock_client):
        runs = [make_run(name="root-1"), make_run(name="root-2")]
        mock_client.list_runs.return_value = runs

        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "trace", "list",
            "--project", "test-project",
            "--limit", "10",
        ])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 2
        assert data[0]["name"] == "root-1"
        assert data[1]["name"] == "root-2"

    def test_trace_list_with_metadata(self, runner, mock_client):
        runs = [make_run(name="root", total_tokens=100, status="success")]
        mock_client.list_runs.return_value = runs

        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "trace", "list",
            "--project", "test-project",
            "--include-metadata",
        ])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["status"] == "success"
        assert data[0]["token_usage"]["total_tokens"] == 100

    def test_trace_list_with_io(self, runner, mock_client):
        runs = [make_run(inputs={"q": "hello"}, outputs={"a": "world"})]
        mock_client.list_runs.return_value = runs

        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "trace", "list",
            "--project", "test",
            "--include-io",
        ])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["inputs"]["q"] == "hello"
        assert data[0]["outputs"]["a"] == "world"

    def test_trace_list_full(self, runner, mock_client):
        runs = [make_run(inputs={"q": "hi"}, outputs={"a": "bye"}, total_tokens=50)]
        mock_client.list_runs.return_value = runs

        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "trace", "list",
            "--project", "test",
            "--full",
        ])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "inputs" in data[0]
        assert "status" in data[0]

    def test_trace_list_default_limit(self, runner, mock_client):
        mock_client.list_runs.return_value = []

        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "trace", "list",
            "--project", "test",
        ])

        assert result.exit_code == 0
        call_kwargs = mock_client.list_runs.call_args[1]
        assert call_kwargs.get("limit") == 20

    def test_trace_list_is_root_true(self, runner, mock_client):
        mock_client.list_runs.return_value = []

        runner.invoke(cli, [
            "--api-key", "test-key",
            "trace", "list",
            "--project", "test",
        ])

        call_kwargs = mock_client.list_runs.call_args[1]
        assert call_kwargs.get("is_root") is True

    def test_trace_list_show_hierarchy_json(self, runner, mock_client):
        root = make_run(name="root")
        child = make_run(name="child", parent_run_id=root.id, trace_id=root.trace_id)
        mock_client.list_runs.side_effect = [
            [root],  # Root query
            [root, child],  # Full trace query
        ]

        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "trace", "list",
            "--project", "test",
            "--show-hierarchy",
            "--limit", "1",
        ])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["run_count"] == 2

    def test_trace_list_show_hierarchy_pretty(self, runner, mock_client):
        root = make_run(name="root")
        child = make_run(name="child", parent_run_id=root.id, trace_id=root.trace_id)
        mock_client.list_runs.side_effect = [
            [root],
            [root, child],
        ]

        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "--format", "pretty",
            "trace", "list",
            "--project", "test",
            "--show-hierarchy",
            "--limit", "1",
        ])

        assert result.exit_code == 0

    def test_trace_list_to_file(self, runner, mock_client, tmp_path):
        runs = [make_run(name="root")]
        mock_client.list_runs.return_value = runs

        output_file = str(tmp_path / "traces.json")
        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "trace", "list",
            "--project", "test",
            "-o", output_file,
        ])

        assert result.exit_code == 0
        with open(output_file) as f:
            data = json.load(f)
        assert len(data) == 1

    def test_trace_list_pretty(self, runner, mock_client):
        runs = [make_run(name="my-trace", total_tokens=50)]
        mock_client.list_runs.return_value = runs

        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "--format", "pretty",
            "trace", "list",
            "--project", "test",
        ])

        assert result.exit_code == 0
        assert "my-trace" in result.output

    def test_trace_list_with_error_flag(self, runner, mock_client):
        mock_client.list_runs.return_value = []

        runner.invoke(cli, [
            "--api-key", "test-key",
            "trace", "list",
            "--project", "test",
            "--error",
        ])

        call_kwargs = mock_client.list_runs.call_args[1]
        assert call_kwargs.get("error") is True

    def test_trace_list_with_tags(self, runner, mock_client):
        mock_client.list_runs.return_value = []

        runner.invoke(cli, [
            "--api-key", "test-key",
            "trace", "list",
            "--project", "test",
            "--tags", "production,v2",
        ])

        call_kwargs = mock_client.list_runs.call_args[1]
        assert "filter" in call_kwargs
        assert "tags" in call_kwargs["filter"]

    def test_trace_list_with_name_filter(self, runner, mock_client):
        mock_client.list_runs.return_value = []

        runner.invoke(cli, [
            "--api-key", "test-key",
            "trace", "list",
            "--project", "test",
            "--name", "agent",
        ])

        call_kwargs = mock_client.list_runs.call_args[1]
        assert "filter" in call_kwargs
        assert "agent" in call_kwargs["filter"]

    def test_trace_list_with_min_latency(self, runner, mock_client):
        mock_client.list_runs.return_value = []

        runner.invoke(cli, [
            "--api-key", "test-key",
            "trace", "list",
            "--project", "test",
            "--min-latency", "2.5",
        ])

        call_kwargs = mock_client.list_runs.call_args[1]
        assert "filter" in call_kwargs
        assert "gte(latency, 2.5)" in call_kwargs["filter"]


class TestTraceGet:
    def test_trace_get_json(self, runner, mock_client):
        runs = [make_run(name="step-1"), make_run(name="step-2")]
        mock_client.list_runs.return_value = runs

        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "trace", "get", "abc-trace-id",
            "--project", "test",
        ])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["trace_id"] == "abc-trace-id"
        assert data["run_count"] == 2

    def test_trace_get_pretty(self, runner, mock_client):
        runs = [make_run(name="root"), make_run(name="child")]
        mock_client.list_runs.return_value = runs

        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "--format", "pretty",
            "trace", "get", "abc-trace-id",
            "--project", "test",
        ])

        assert result.exit_code == 0

    def test_trace_get_full(self, runner, mock_client):
        runs = [make_run(inputs={"q": "hi"}, outputs={"a": "bye"}, total_tokens=10)]
        mock_client.list_runs.return_value = runs

        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "trace", "get", "abc-trace-id",
            "--project", "test",
            "--full",
        ])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "inputs" in data["runs"][0]
        assert "status" in data["runs"][0]

    def test_trace_get_to_file(self, runner, mock_client, tmp_path):
        runs = [make_run(name="run")]
        mock_client.list_runs.return_value = runs

        output_file = str(tmp_path / "trace.json")
        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "trace", "get", "abc-trace-id",
            "--project", "test",
            "-o", output_file,
        ])

        assert result.exit_code == 0
        with open(output_file) as f:
            data = json.load(f)
        assert data["trace_id"] == "abc-trace-id"


class TestTraceExport:
    def test_trace_export(self, runner, mock_client, tmp_path):
        root = make_run(name="root")
        child = make_run(name="child", parent_run_id=root.id, trace_id=root.trace_id)
        mock_client.list_runs.side_effect = [
            [root],  # Root query
            [root, child],  # Full trace query
        ]

        output_dir = str(tmp_path / "exports")

        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "trace", "export", output_dir,
            "--project", "test",
            "--limit", "1",
        ])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "exported"
        assert data["count"] == 1

    def test_trace_export_default_limit(self, runner, mock_client, tmp_path):
        mock_client.list_runs.return_value = []

        output_dir = str(tmp_path / "exports")

        runner.invoke(cli, [
            "--api-key", "test-key",
            "trace", "export", output_dir,
            "--project", "test",
        ])

        call_kwargs = mock_client.list_runs.call_args[1]
        assert call_kwargs.get("limit") == 10

    def test_trace_export_with_full(self, runner, mock_client, tmp_path):
        root = make_run(name="root", inputs={"q": "hi"}, outputs={"a": "bye"})
        mock_client.list_runs.side_effect = [
            [root],
            [root],
        ]

        output_dir = str(tmp_path / "exports")

        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "trace", "export", output_dir,
            "--project", "test",
            "--full",
            "--limit", "1",
        ])

        assert result.exit_code == 0
        # Check the exported JSONL file has IO fields
        files = os.listdir(output_dir)
        assert len(files) == 1
        with open(os.path.join(output_dir, files[0])) as f:
            line = json.loads(f.readline())
        assert "inputs" in line

    def test_trace_export_creates_directory(self, runner, mock_client, tmp_path):
        mock_client.list_runs.return_value = []

        output_dir = str(tmp_path / "new" / "nested" / "dir")

        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "trace", "export", output_dir,
            "--project", "test",
        ])

        assert result.exit_code == 0
        assert os.path.isdir(output_dir)
