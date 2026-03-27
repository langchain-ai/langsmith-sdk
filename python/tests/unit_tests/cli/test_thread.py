"""Tests for thread commands."""

import json

from langsmith.cli.main import cli
from tests.unit_tests.cli.conftest import make_run


class TestThreadList:
    def test_thread_list_json(self, runner, mock_client):
        mock_client.list_threads.return_value = [
            {
                "thread_id": "thread-1",
                "runs": [make_run()],
                "count": 3,
                "min_start_time": "2024-01-01T00:00:00Z",
                "max_start_time": "2024-01-01T01:00:00Z",
            },
        ]

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "thread",
                "list",
                "--project",
                "test-project",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["thread_id"] == "thread-1"
        assert data[0]["run_count"] == 3

    def test_thread_list_with_limit(self, runner, mock_client):
        mock_client.list_threads.return_value = []

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "thread",
                "list",
                "--project",
                "test",
                "--limit",
                "5",
            ],
        )

        assert result.exit_code == 0
        call_kwargs = mock_client.list_threads.call_args[1]
        assert call_kwargs["limit"] == 5

    def test_thread_list_with_offset(self, runner, mock_client):
        mock_client.list_threads.return_value = []

        runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "thread",
                "list",
                "--project",
                "test",
                "--offset",
                "10",
            ],
        )

        call_kwargs = mock_client.list_threads.call_args[1]
        assert call_kwargs["offset"] == 10

    def test_thread_list_with_last_n_minutes(self, runner, mock_client):
        mock_client.list_threads.return_value = []

        runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "thread",
                "list",
                "--project",
                "test",
                "--last-n-minutes",
                "60",
            ],
        )

        call_kwargs = mock_client.list_threads.call_args[1]
        assert "start_time" in call_kwargs

    def test_thread_list_with_filter(self, runner, mock_client):
        mock_client.list_threads.return_value = []

        runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "thread",
                "list",
                "--project",
                "test",
                "--filter",
                'eq(status, "error")',
            ],
        )

        call_kwargs = mock_client.list_threads.call_args[1]
        assert call_kwargs["filter"] == 'eq(status, "error")'

    def test_thread_list_pretty(self, runner, mock_client):
        mock_client.list_threads.return_value = [
            {
                "thread_id": "thread-1",
                "count": 5,
                "min_start_time": "2024-01-01T00:00:00Z",
                "max_start_time": "2024-01-01T01:00:00Z",
            },
        ]

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "--format",
                "pretty",
                "thread",
                "list",
                "--project",
                "test",
            ],
        )

        assert result.exit_code == 0
        assert "thread-1" in result.output

    def test_thread_list_to_file(self, runner, mock_client, tmp_path):
        mock_client.list_threads.return_value = [
            {
                "thread_id": "thread-1",
                "count": 2,
                "min_start_time": None,
                "max_start_time": None,
            },
        ]

        output_file = str(tmp_path / "threads.json")
        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "thread",
                "list",
                "--project",
                "test",
                "-o",
                output_file,
            ],
        )

        assert result.exit_code == 0
        with open(output_file) as f:
            data = json.load(f)
        assert len(data) == 1

    def test_thread_list_project_required(self, runner, mock_client):
        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "thread",
                "list",
            ],
        )

        assert result.exit_code != 0


class TestThreadGet:
    def test_thread_get_json(self, runner, mock_client):
        runs = [make_run(name="turn-1"), make_run(name="turn-2")]
        mock_client.read_thread.return_value = iter(runs)

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "thread",
                "get",
                "thread-abc",
                "--project",
                "test",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["thread_id"] == "thread-abc"
        assert data["run_count"] == 2

    def test_thread_get_full(self, runner, mock_client):
        runs = [make_run(inputs={"q": "hi"}, outputs={"a": "bye"}, total_tokens=10)]
        mock_client.read_thread.return_value = iter(runs)

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "thread",
                "get",
                "thread-abc",
                "--project",
                "test",
                "--full",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "inputs" in data["runs"][0]
        assert "status" in data["runs"][0]

    def test_thread_get_pretty(self, runner, mock_client):
        runs = [make_run(name="turn-1")]
        mock_client.read_thread.return_value = iter(runs)

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "--format",
                "pretty",
                "thread",
                "get",
                "thread-abc",
                "--project",
                "test",
            ],
        )

        assert result.exit_code == 0

    def test_thread_get_to_file(self, runner, mock_client, tmp_path):
        runs = [make_run(name="turn-1")]
        mock_client.read_thread.return_value = iter(runs)

        output_file = str(tmp_path / "thread.json")
        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "thread",
                "get",
                "thread-abc",
                "--project",
                "test",
                "-o",
                output_file,
            ],
        )

        assert result.exit_code == 0
        with open(output_file) as f:
            data = json.load(f)
        assert data["thread_id"] == "thread-abc"

    def test_thread_get_with_limit(self, runner, mock_client):
        runs = [make_run(name="turn-1")]
        mock_client.read_thread.return_value = iter(runs)

        runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "thread",
                "get",
                "thread-abc",
                "--project",
                "test",
                "--limit",
                "3",
            ],
        )

        call_kwargs = mock_client.read_thread.call_args[1]
        assert call_kwargs["limit"] == 3

    def test_thread_get_project_required(self, runner, mock_client):
        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "thread",
                "get",
                "thread-abc",
            ],
        )

        assert result.exit_code != 0
