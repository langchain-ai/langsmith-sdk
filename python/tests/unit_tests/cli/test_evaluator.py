"""Tests for evaluator commands."""

import json
import textwrap
from unittest.mock import patch, MagicMock
from types import SimpleNamespace

from langsmith.cli.main import cli


class TestEvaluatorList:
    @patch("langsmith.cli.evaluator.requests")
    def test_evaluator_list_json(self, mock_requests, runner):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "id": "rule-1",
                "display_name": "accuracy",
                "sampling_rate": 1.0,
                "is_enabled": True,
                "dataset_id": "ds-1",
                "session_id": None,
            },
        ]
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "evaluator",
                "list",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["name"] == "accuracy"

    @patch("langsmith.cli.evaluator.requests")
    def test_evaluator_list_to_file(self, mock_requests, runner, tmp_path):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "id": "rule-1",
                "display_name": "eval1",
                "sampling_rate": 1.0,
                "is_enabled": True,
                "dataset_id": None,
                "session_id": None,
            },
        ]
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response

        output_file = str(tmp_path / "evals.json")
        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "evaluator",
                "list",
                "-o",
                output_file,
            ],
        )

        assert result.exit_code == 0
        with open(output_file) as f:
            data = json.load(f)
        assert len(data) == 1

    @patch("langsmith.cli.evaluator.requests")
    def test_evaluator_list_pretty(self, mock_requests, runner):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "id": "rule-1",
                "display_name": "accuracy",
                "sampling_rate": 1.0,
                "is_enabled": True,
                "dataset_id": "ds-1",
                "session_id": None,
            },
            {
                "id": "rule-2",
                "display_name": "latency",
                "sampling_rate": 0.5,
                "is_enabled": False,
                "dataset_id": None,
                "session_id": "proj-1",
            },
        ]
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "--format",
                "pretty",
                "evaluator",
                "list",
            ],
        )

        assert result.exit_code == 0
        assert "accuracy" in result.output

    @patch("langsmith.cli.evaluator.requests")
    def test_evaluator_list_pretty_no_target(self, mock_requests, runner):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "id": "rule-1",
                "display_name": "global-eval",
                "sampling_rate": 1.0,
                "is_enabled": True,
                "dataset_id": None,
                "session_id": None,
            },
        ]
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "--format",
                "pretty",
                "evaluator",
                "list",
            ],
        )

        assert result.exit_code == 0


class TestEvaluatorUpload:
    @patch("langsmith.cli.evaluator.requests")
    def test_upload_to_dataset(self, mock_requests, runner, mock_client, tmp_path):
        # Create eval file
        eval_file = tmp_path / "evals.py"
        eval_file.write_text(
            textwrap.dedent("""\
            def check_accuracy(run, example):
                return {"score": 1.0}
        """)
        )

        # Mock dataset resolution
        ds = SimpleNamespace(id="ds-123")
        mock_client.read_dataset.return_value = ds

        # Mock POST response
        post_response = MagicMock()
        post_response.json.return_value = {"id": "rule-new"}
        post_response.raise_for_status.return_value = None
        mock_requests.post.return_value = post_response

        # Mock GET (for _find_evaluator check)
        get_response = MagicMock()
        get_response.json.return_value = []
        get_response.raise_for_status.return_value = None
        mock_requests.get.return_value = get_response

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "evaluator",
                "upload",
                str(eval_file),
                "--name",
                "accuracy",
                "--function",
                "check_accuracy",
                "--dataset",
                "my-eval-set",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "uploaded"
        assert data["name"] == "accuracy"
        assert data["target"] == "dataset"

    @patch("langsmith.cli.evaluator.requests")
    def test_upload_to_project(self, mock_requests, runner, mock_client, tmp_path):
        eval_file = tmp_path / "evals.py"
        eval_file.write_text(
            textwrap.dedent("""\
            def check_latency(run):
                return {"score": 1.0 if run.latency < 5 else 0.0}
        """)
        )

        mock_client.list_projects.return_value = [
            SimpleNamespace(name="my-app", id="proj-123"),
        ]

        post_response = MagicMock()
        post_response.json.return_value = {"id": "rule-new"}
        post_response.raise_for_status.return_value = None
        mock_requests.post.return_value = post_response

        get_response = MagicMock()
        get_response.json.return_value = []
        get_response.raise_for_status.return_value = None
        mock_requests.get.return_value = get_response

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "evaluator",
                "upload",
                str(eval_file),
                "--name",
                "latency-check",
                "--function",
                "check_latency",
                "--project",
                "my-app",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "uploaded"
        assert data["target"] == "project"

    @patch("langsmith.cli.evaluator.requests")
    def test_upload_no_target_errors(
        self, mock_requests, runner, mock_client, tmp_path
    ):
        eval_file = tmp_path / "evals.py"
        eval_file.write_text("def my_eval(run): return {}\n")

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "evaluator",
                "upload",
                str(eval_file),
                "--name",
                "test",
                "--function",
                "my_eval",
            ],
        )

        # Should error because neither --dataset nor --project specified
        assert "Must specify --dataset or --project" in result.output

    @patch("langsmith.cli.evaluator.requests")
    def test_upload_function_not_found(
        self, mock_requests, runner, mock_client, tmp_path
    ):
        eval_file = tmp_path / "evals.py"
        eval_file.write_text("def other_func(run): return {}\n")

        ds = SimpleNamespace(id="ds-123")
        mock_client.read_dataset.return_value = ds

        get_response = MagicMock()
        get_response.json.return_value = []
        get_response.raise_for_status.return_value = None
        mock_requests.get.return_value = get_response

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "evaluator",
                "upload",
                str(eval_file),
                "--name",
                "test",
                "--function",
                "nonexistent",
                "--dataset",
                "my-ds",
            ],
        )

        assert "not found" in result.output

    @patch("langsmith.cli.evaluator.requests")
    def test_upload_replace_existing(
        self, mock_requests, runner, mock_client, tmp_path
    ):
        eval_file = tmp_path / "evals.py"
        eval_file.write_text(
            textwrap.dedent("""\
            def check_v2(run, example):
                return {"score": 0.5}
        """)
        )

        ds = SimpleNamespace(id="ds-123")
        mock_client.read_dataset.return_value = ds

        # Mock GET returns existing evaluator
        get_response = MagicMock()
        get_response.json.return_value = [
            {"id": "rule-old", "display_name": "accuracy", "dataset_id": "ds-123"},
        ]
        get_response.raise_for_status.return_value = None
        mock_requests.get.return_value = get_response

        # Mock DELETE
        delete_response = MagicMock()
        delete_response.raise_for_status.return_value = None
        mock_requests.delete.return_value = delete_response

        # Mock POST
        post_response = MagicMock()
        post_response.json.return_value = {"id": "rule-new"}
        post_response.raise_for_status.return_value = None
        mock_requests.post.return_value = post_response

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "evaluator",
                "upload",
                str(eval_file),
                "--name",
                "accuracy",
                "--function",
                "check_v2",
                "--dataset",
                "my-ds",
                "--replace",
                "--yes",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "uploaded"
        mock_requests.delete.assert_called_once()

    @patch("langsmith.cli.evaluator.requests")
    def test_upload_existing_no_replace_warns(
        self, mock_requests, runner, mock_client, tmp_path
    ):
        eval_file = tmp_path / "evals.py"
        eval_file.write_text("def my_eval(run, example): return {}\n")

        ds = SimpleNamespace(id="ds-123")
        mock_client.read_dataset.return_value = ds

        get_response = MagicMock()
        get_response.json.return_value = [
            {"id": "rule-existing", "display_name": "test", "dataset_id": "ds-123"},
        ]
        get_response.raise_for_status.return_value = None
        mock_requests.get.return_value = get_response

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "evaluator",
                "upload",
                str(eval_file),
                "--name",
                "test",
                "--function",
                "my_eval",
                "--dataset",
                "my-ds",
            ],
        )

        assert "already exists" in result.output

    @patch("langsmith.cli.evaluator.requests")
    def test_upload_project_not_found(
        self, mock_requests, runner, mock_client, tmp_path
    ):
        eval_file = tmp_path / "evals.py"
        eval_file.write_text("def my_eval(run): return {}\n")

        mock_client.list_projects.return_value = []

        get_response = MagicMock()
        get_response.json.return_value = []
        get_response.raise_for_status.return_value = None
        mock_requests.get.return_value = get_response

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "evaluator",
                "upload",
                str(eval_file),
                "--name",
                "test",
                "--function",
                "my_eval",
                "--project",
                "nonexistent-project",
            ],
        )

        assert "not found" in result.output

    @patch("langsmith.cli.evaluator.requests")
    def test_upload_sampling_rate(self, mock_requests, runner, mock_client, tmp_path):
        eval_file = tmp_path / "evals.py"
        eval_file.write_text(
            textwrap.dedent("""\
            def my_eval(run, example):
                return {"score": 1.0}
        """)
        )

        ds = SimpleNamespace(id="ds-123")
        mock_client.read_dataset.return_value = ds

        get_response = MagicMock()
        get_response.json.return_value = []
        get_response.raise_for_status.return_value = None
        mock_requests.get.return_value = get_response

        post_response = MagicMock()
        post_response.json.return_value = {"id": "rule-new"}
        post_response.raise_for_status.return_value = None
        mock_requests.post.return_value = post_response

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "evaluator",
                "upload",
                str(eval_file),
                "--name",
                "test",
                "--function",
                "my_eval",
                "--dataset",
                "my-ds",
                "--sampling-rate",
                "0.5",
            ],
        )

        assert result.exit_code == 0
        call_kwargs = mock_requests.post.call_args
        payload = call_kwargs[1]["json"]
        assert payload["sampling_rate"] == 0.5


class TestEvaluatorDelete:
    @patch("langsmith.cli.evaluator.requests")
    def test_evaluator_delete_with_yes(self, mock_requests, runner):
        # Mock GET for listing rules
        list_response = MagicMock()
        list_response.json.return_value = [
            {"id": "rule-1", "display_name": "test-eval"},
        ]
        list_response.raise_for_status.return_value = None

        # Mock DELETE
        delete_response = MagicMock()
        delete_response.raise_for_status.return_value = None

        mock_requests.get.return_value = list_response
        mock_requests.delete.return_value = delete_response

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "evaluator",
                "delete",
                "test-eval",
                "--yes",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "deleted"

    @patch("langsmith.cli.evaluator.requests")
    def test_evaluator_delete_not_found(self, mock_requests, runner):
        list_response = MagicMock()
        list_response.json.return_value = []
        list_response.raise_for_status.return_value = None
        mock_requests.get.return_value = list_response

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "evaluator",
                "delete",
                "nonexistent",
                "--yes",
            ],
        )

        # Should print error to stderr
        assert "not found" in result.output or result.exit_code == 0

    @patch("langsmith.cli.evaluator.requests")
    def test_evaluator_delete_multiple_matching(self, mock_requests, runner):
        list_response = MagicMock()
        list_response.json.return_value = [
            {"id": "rule-1", "display_name": "dup-eval"},
            {"id": "rule-2", "display_name": "dup-eval"},
        ]
        list_response.raise_for_status.return_value = None

        delete_response = MagicMock()
        delete_response.raise_for_status.return_value = None

        mock_requests.get.return_value = list_response
        mock_requests.delete.return_value = delete_response

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "evaluator",
                "delete",
                "dup-eval",
                "--yes",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 2
        assert mock_requests.delete.call_count == 2
