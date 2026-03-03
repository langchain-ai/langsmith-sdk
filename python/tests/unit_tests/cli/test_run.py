"""Tests for run commands."""

import json

from langsmith.cli.main import cli
from tests.unit_tests.cli.conftest import make_run


class TestRunList:
    def test_run_list_json(self, runner, mock_client):
        runs = [make_run(name="llm-call", run_type="llm")]
        mock_client.list_runs.return_value = runs

        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "run", "list",
            "--project", "test",
            "--run-type", "llm",
        ])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["run_type"] == "llm"

    def test_run_list_default_limit(self, runner, mock_client):
        mock_client.list_runs.return_value = []

        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "run", "list",
            "--project", "test",
        ])

        assert result.exit_code == 0
        call_kwargs = mock_client.list_runs.call_args[1]
        assert call_kwargs.get("limit") == 50

    def test_run_list_with_metadata(self, runner, mock_client):
        runs = [make_run(name="llm-call", run_type="llm", total_tokens=200)]
        mock_client.list_runs.return_value = runs

        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "run", "list",
            "--project", "test",
            "--include-metadata",
        ])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["token_usage"]["total_tokens"] == 200

    def test_run_list_full(self, runner, mock_client):
        runs = [make_run(inputs={"q": "hi"}, outputs={"a": "bye"}, total_tokens=50)]
        mock_client.list_runs.return_value = runs

        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "run", "list",
            "--project", "test",
            "--full",
        ])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "inputs" in data[0]
        assert "status" in data[0]

    def test_run_list_pretty(self, runner, mock_client):
        runs = [make_run(name="pretty-run", run_type="llm")]
        mock_client.list_runs.return_value = runs

        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "--format", "pretty",
            "run", "list",
            "--project", "test",
        ])

        assert result.exit_code == 0
        assert "pretty-run" in result.output

    def test_run_list_to_file(self, runner, mock_client, tmp_path):
        runs = [make_run(name="run")]
        mock_client.list_runs.return_value = runs

        output_file = str(tmp_path / "runs.json")
        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "run", "list",
            "--project", "test",
            "-o", output_file,
        ])

        assert result.exit_code == 0
        with open(output_file) as f:
            data = json.load(f)
        assert len(data) == 1

    def test_run_list_with_run_type_filter(self, runner, mock_client):
        mock_client.list_runs.return_value = []

        runner.invoke(cli, [
            "--api-key", "test-key",
            "run", "list",
            "--project", "test",
            "--run-type", "tool",
        ])

        call_kwargs = mock_client.list_runs.call_args[1]
        assert call_kwargs.get("run_type") == "tool"

    def test_run_list_with_name_and_error(self, runner, mock_client):
        mock_client.list_runs.return_value = []

        runner.invoke(cli, [
            "--api-key", "test-key",
            "run", "list",
            "--project", "test",
            "--name", "ChatOpenAI",
            "--error",
        ])

        call_kwargs = mock_client.list_runs.call_args[1]
        assert call_kwargs.get("error") is True
        assert "ChatOpenAI" in call_kwargs.get("filter", "")


class TestRunGet:
    def test_run_get_json(self, runner, mock_client):
        run = make_run(name="my-run")
        mock_client.read_run.return_value = run

        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "run", "get", str(run.id),
        ])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "my-run"

    def test_run_get_with_io(self, runner, mock_client):
        run = make_run(inputs={"q": "hello"}, outputs={"a": "world"})
        mock_client.read_run.return_value = run

        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "run", "get", str(run.id),
            "--include-io",
        ])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["inputs"]["q"] == "hello"

    def test_run_get_full(self, runner, mock_client):
        run = make_run(inputs={"q": "hi"}, outputs={"a": "bye"}, total_tokens=10)
        mock_client.read_run.return_value = run

        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "run", "get", str(run.id),
            "--full",
        ])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "inputs" in data
        assert "status" in data

    def test_run_get_pretty(self, runner, mock_client):
        run = make_run(name="pretty-run")
        mock_client.read_run.return_value = run

        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "--format", "pretty",
            "run", "get", str(run.id),
        ])

        assert result.exit_code == 0

    def test_run_get_to_file(self, runner, mock_client, tmp_path):
        run = make_run(name="filed-run")
        mock_client.read_run.return_value = run

        output_file = str(tmp_path / "run.json")
        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "run", "get", str(run.id),
            "-o", output_file,
        ])

        assert result.exit_code == 0
        with open(output_file) as f:
            data = json.load(f)
        assert data["name"] == "filed-run"


class TestRunExport:
    def test_run_export(self, runner, mock_client, tmp_path):
        runs = [make_run(name="r1"), make_run(name="r2")]
        mock_client.list_runs.return_value = runs

        output_file = str(tmp_path / "runs.jsonl")

        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "run", "export", output_file,
            "--project", "test",
            "--limit", "10",
        ])

        assert result.exit_code == 0
        with open(output_file) as f:
            lines = f.read().strip().split("\n")
        assert len(lines) == 2

    def test_run_export_default_limit(self, runner, mock_client, tmp_path):
        mock_client.list_runs.return_value = []

        output_file = str(tmp_path / "runs.jsonl")

        runner.invoke(cli, [
            "--api-key", "test-key",
            "run", "export", output_file,
            "--project", "test",
        ])

        call_kwargs = mock_client.list_runs.call_args[1]
        assert call_kwargs.get("limit") == 100

    def test_run_export_with_full(self, runner, mock_client, tmp_path):
        runs = [make_run(name="r1", inputs={"q": "hi"}, outputs={"a": "bye"})]
        mock_client.list_runs.return_value = runs

        output_file = str(tmp_path / "runs.jsonl")

        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "run", "export", output_file,
            "--project", "test",
            "--full",
        ])

        assert result.exit_code == 0
        with open(output_file) as f:
            line = json.loads(f.readline())
        assert "inputs" in line
        assert "status" in line
