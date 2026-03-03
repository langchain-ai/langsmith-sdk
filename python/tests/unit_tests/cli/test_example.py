"""Tests for example commands."""

import json

from langsmith.cli.main import cli
from tests.unit_tests.cli.conftest import make_dataset, make_example


class TestExampleList:
    def test_example_list_json(self, runner, mock_client):
        ds = make_dataset(name="test-ds")
        mock_client.read_dataset.return_value = ds

        examples = [
            make_example(inputs={"q": "hello"}, outputs={"a": "world"}),
            make_example(inputs={"q": "foo"}, outputs={"a": "bar"}),
        ]
        mock_client.list_examples.return_value = examples

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "example",
                "list",
                "--dataset",
                "test-ds",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 2
        assert data[0]["inputs"]["q"] == "hello"

    def test_example_list_with_split(self, runner, mock_client):
        ds = make_dataset()
        mock_client.read_dataset.return_value = ds
        mock_client.list_examples.return_value = [make_example(split="train")]

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "example",
                "list",
                "--dataset",
                "test-ds",
                "--split",
                "train",
            ],
        )

        assert result.exit_code == 0
        mock_client.list_examples.assert_called_once()
        call_kwargs = mock_client.list_examples.call_args[1]
        assert call_kwargs["splits"] == ["train"]

    def test_example_list_with_limit(self, runner, mock_client):
        ds = make_dataset()
        mock_client.read_dataset.return_value = ds
        mock_client.list_examples.return_value = []

        runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "example",
                "list",
                "--dataset",
                "test-ds",
                "--limit",
                "100",
            ],
        )

        call_kwargs = mock_client.list_examples.call_args[1]
        assert call_kwargs["limit"] == 100

    def test_example_list_with_offset(self, runner, mock_client):
        ds = make_dataset()
        mock_client.read_dataset.return_value = ds
        mock_client.list_examples.return_value = []

        runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "example",
                "list",
                "--dataset",
                "test-ds",
                "--offset",
                "20",
            ],
        )

        call_kwargs = mock_client.list_examples.call_args[1]
        assert call_kwargs["offset"] == 20

    def test_example_list_pretty(self, runner, mock_client):
        ds = make_dataset(name="pretty-ds")
        mock_client.read_dataset.return_value = ds
        mock_client.list_examples.return_value = [
            make_example(inputs={"q": "hello"}, outputs={"a": "world"}),
        ]

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "--format",
                "pretty",
                "example",
                "list",
                "--dataset",
                "pretty-ds",
            ],
        )

        assert result.exit_code == 0

    def test_example_list_to_file(self, runner, mock_client, tmp_path):
        ds = make_dataset()
        mock_client.read_dataset.return_value = ds
        mock_client.list_examples.return_value = [make_example()]

        output_file = str(tmp_path / "examples.json")
        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "example",
                "list",
                "--dataset",
                "test-ds",
                "-o",
                output_file,
            ],
        )

        assert result.exit_code == 0
        with open(output_file) as f:
            data = json.load(f)
        assert len(data) == 1

    def test_example_list_dataset_required(self, runner, mock_client):
        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "example",
                "list",
            ],
        )

        assert result.exit_code != 0


class TestExampleCreate:
    def test_example_create(self, runner, mock_client):
        ex = make_example(inputs={"q": "test"}, outputs={"a": "result"})
        mock_client.create_example.return_value = ex

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "example",
                "create",
                "--dataset",
                "test-ds",
                "--inputs",
                '{"q": "test"}',
                "--outputs",
                '{"a": "result"}',
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "created"

    def test_example_create_inputs_only(self, runner, mock_client):
        ex = make_example(inputs={"q": "test"}, outputs=None)
        mock_client.create_example.return_value = ex

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "example",
                "create",
                "--dataset",
                "test-ds",
                "--inputs",
                '{"q": "test"}',
            ],
        )

        assert result.exit_code == 0
        call_kwargs = mock_client.create_example.call_args[1]
        assert call_kwargs["outputs"] is None

    def test_example_create_with_metadata_and_split(self, runner, mock_client):
        ex = make_example(inputs={"q": "test"}, outputs={"a": "result"}, split="test")
        mock_client.create_example.return_value = ex

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "example",
                "create",
                "--dataset",
                "test-ds",
                "--inputs",
                '{"q": "test"}',
                "--outputs",
                '{"a": "result"}',
                "--metadata",
                '{"source": "manual"}',
                "--split",
                "test",
            ],
        )

        assert result.exit_code == 0
        call_kwargs = mock_client.create_example.call_args[1]
        assert call_kwargs["metadata"] == {"source": "manual"}
        assert call_kwargs["split"] == "test"


class TestExampleDelete:
    def test_example_delete_with_yes(self, runner, mock_client):
        mock_client.delete_example.return_value = None

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "example",
                "delete",
                "abc-123",
                "--yes",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "deleted"
