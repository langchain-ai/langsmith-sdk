"""Tests for experiment commands."""

import json
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
import uuid

from langsmith.cli.main import cli


class TestExperimentList:
    def test_experiment_list_json(self, runner, mock_client):
        projects = [
            SimpleNamespace(
                id=uuid.uuid4(),
                name="exp-1",
                reference_dataset_id=uuid.uuid4(),
                run_count=10,
                feedback_stats={"accuracy": 0.9},
            ),
        ]
        mock_client.list_projects.return_value = projects

        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "experiment", "list",
        ])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["name"] == "exp-1"

    def test_experiment_list_with_dataset_filter(self, runner, mock_client):
        from tests.unit_tests.cli.conftest import make_dataset
        ds = make_dataset(name="eval-ds")
        mock_client.read_dataset.return_value = ds
        mock_client.list_projects.return_value = []

        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "experiment", "list",
            "--dataset", "eval-ds",
        ])

        assert result.exit_code == 0
        call_kwargs = mock_client.list_projects.call_args[1]
        assert call_kwargs["reference_dataset_id"] == ds.id

    def test_experiment_list_with_limit(self, runner, mock_client):
        mock_client.list_projects.return_value = []

        runner.invoke(cli, [
            "--api-key", "test-key",
            "experiment", "list",
            "--limit", "5",
        ])

        call_kwargs = mock_client.list_projects.call_args[1]
        assert call_kwargs["limit"] == 5

    def test_experiment_list_pretty(self, runner, mock_client):
        projects = [
            SimpleNamespace(
                id=uuid.uuid4(),
                name="exp-pretty",
                reference_dataset_id=uuid.uuid4(),
                run_count=5,
            ),
        ]
        mock_client.list_projects.return_value = projects

        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "--format", "pretty",
            "experiment", "list",
        ])

        assert result.exit_code == 0
        assert "exp-pretty" in result.output

    def test_experiment_list_to_file(self, runner, mock_client, tmp_path):
        projects = [
            SimpleNamespace(
                id=uuid.uuid4(),
                name="exp-1",
                reference_dataset_id=uuid.uuid4(),
                run_count=10,
                feedback_stats={"accuracy": 0.9},
            ),
        ]
        mock_client.list_projects.return_value = projects

        output_file = str(tmp_path / "experiments.json")
        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "experiment", "list",
            "-o", output_file,
        ])

        assert result.exit_code == 0
        with open(output_file) as f:
            data = json.load(f)
        assert len(data) == 1

    def test_experiment_list_no_reference_dataset(self, runner, mock_client):
        projects = [
            SimpleNamespace(
                id=uuid.uuid4(),
                name="exp-no-ref",
                reference_dataset_id=None,
                run_count=3,
            ),
        ]
        mock_client.list_projects.return_value = projects

        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "experiment", "list",
        ])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["reference_dataset_id"] is None


class TestExperimentGet:
    def test_experiment_get_json(self, runner, mock_client):
        mock_client.get_experiment_results.return_value = {
            "feedback_stats": {"accuracy": 0.95},
            "run_stats": {"run_count": 50, "error_rate": 0.02},
            "examples_with_runs": [],
        }

        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "experiment", "get", "my-experiment",
        ])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "my-experiment"
        assert data["feedback_stats"]["accuracy"] == 0.95

    def test_experiment_get_pretty(self, runner, mock_client):
        mock_client.get_experiment_results.return_value = {
            "feedback_stats": {"accuracy": 0.95},
            "run_stats": {},
            "examples_with_runs": [],
        }

        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "--format", "pretty",
            "experiment", "get", "my-experiment",
        ])

        assert result.exit_code == 0

    def test_experiment_get_to_file(self, runner, mock_client, tmp_path):
        mock_client.get_experiment_results.return_value = {
            "feedback_stats": {"accuracy": 0.95},
            "run_stats": {},
            "examples_with_runs": [],
        }

        output_file = str(tmp_path / "experiment.json")
        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "experiment", "get", "my-experiment",
            "-o", output_file,
        ])

        assert result.exit_code == 0
        with open(output_file) as f:
            data = json.load(f)
        assert data["name"] == "my-experiment"

    def test_experiment_get_with_timedelta_stats(self, runner, mock_client):
        mock_client.get_experiment_results.return_value = {
            "feedback_stats": {"accuracy": 0.95},
            "run_stats": {
                "avg_latency": timedelta(seconds=2.5),
                "total_tokens": 1000,
            },
            "examples_with_runs": [],
        }

        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "experiment", "get", "my-experiment",
        ])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["run_stats"]["avg_latency"] == 2.5

    def test_experiment_get_fallback_to_test_results(self, runner, mock_client):
        mock_client.get_experiment_results.side_effect = Exception("not supported")

        mock_df = MagicMock()
        mock_df.to_dict.return_value = [{"example_id": "e1", "score": 0.9}]
        mock_client.get_test_results.return_value = mock_df

        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "experiment", "get", "fallback-experiment",
        ])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "fallback-experiment"
        assert data["result_count"] == 1

    def test_experiment_get_both_fail(self, runner, mock_client):
        mock_client.get_experiment_results.side_effect = Exception("fail 1")
        mock_client.get_test_results.side_effect = Exception("fail 2")

        result = runner.invoke(cli, [
            "--api-key", "test-key",
            "experiment", "get", "bad-experiment",
        ])

        # Should output error
        assert "fail 2" in result.output
