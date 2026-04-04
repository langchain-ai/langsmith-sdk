"""Tests for dataset commands."""

import json

from langsmith.cli.main import cli
from tests.unit_tests.cli.conftest import make_dataset, make_example


class TestDatasetList:
    def test_dataset_list_json(self, runner, mock_client):
        datasets = [make_dataset(name="ds-1"), make_dataset(name="ds-2")]
        mock_client.list_datasets.return_value = datasets

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "dataset",
                "list",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 2
        assert data[0]["name"] == "ds-1"

    def test_dataset_list_with_name_filter(self, runner, mock_client):
        mock_client.list_datasets.return_value = [make_dataset(name="eval-ds")]

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "dataset",
                "list",
                "--name-contains",
                "eval",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        call_kwargs = mock_client.list_datasets.call_args[1]
        assert call_kwargs["dataset_name_contains"] == "eval"

    def test_dataset_list_with_limit(self, runner, mock_client):
        mock_client.list_datasets.return_value = []

        runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "dataset",
                "list",
                "--limit",
                "5",
            ],
        )

        call_kwargs = mock_client.list_datasets.call_args[1]
        assert call_kwargs["limit"] == 5

    def test_dataset_list_pretty(self, runner, mock_client):
        datasets = [make_dataset(name="ds-pretty", description="A dataset")]
        mock_client.list_datasets.return_value = datasets

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "--format",
                "pretty",
                "dataset",
                "list",
            ],
        )

        assert result.exit_code == 0
        assert "ds-pretty" in result.output

    def test_dataset_list_to_file(self, runner, mock_client, tmp_path):
        datasets = [make_dataset(name="ds-1")]
        mock_client.list_datasets.return_value = datasets

        output_file = str(tmp_path / "datasets.json")
        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "dataset",
                "list",
                "-o",
                output_file,
            ],
        )

        assert result.exit_code == 0
        with open(output_file) as f:
            data = json.load(f)
        assert len(data) == 1


class TestDatasetGet:
    def test_dataset_get_by_name(self, runner, mock_client):
        ds = make_dataset(name="my-dataset", description="Test dataset")
        mock_client.read_dataset.return_value = ds

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "dataset",
                "get",
                "my-dataset",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "my-dataset"

    def test_dataset_get_by_uuid(self, runner, mock_client):
        import uuid

        ds_id = uuid.uuid4()
        ds = make_dataset(dataset_id=ds_id, name="uuid-dataset")
        mock_client.read_dataset.return_value = ds

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "dataset",
                "get",
                str(ds_id),
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "uuid-dataset"

    def test_dataset_get_pretty(self, runner, mock_client):
        ds = make_dataset(name="pretty-ds")
        mock_client.read_dataset.return_value = ds

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "--format",
                "pretty",
                "dataset",
                "get",
                "pretty-ds",
            ],
        )

        assert result.exit_code == 0

    def test_dataset_get_to_file(self, runner, mock_client, tmp_path):
        ds = make_dataset(name="filed-ds")
        mock_client.read_dataset.return_value = ds

        output_file = str(tmp_path / "ds.json")
        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "dataset",
                "get",
                "filed-ds",
                "-o",
                output_file,
            ],
        )

        assert result.exit_code == 0
        with open(output_file) as f:
            data = json.load(f)
        assert data["name"] == "filed-ds"


class TestDatasetCreate:
    def test_dataset_create(self, runner, mock_client):
        ds = make_dataset(name="new-ds")
        mock_client.create_dataset.return_value = ds

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "dataset",
                "create",
                "--name",
                "new-ds",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "created"
        assert data["name"] == "new-ds"

    def test_dataset_create_with_description(self, runner, mock_client):
        ds = make_dataset(name="new-ds", description="QA pairs")
        mock_client.create_dataset.return_value = ds

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "dataset",
                "create",
                "--name",
                "new-ds",
                "--description",
                "QA pairs",
            ],
        )

        assert result.exit_code == 0
        mock_client.create_dataset.assert_called_once_with(
            dataset_name="new-ds",
            description="QA pairs",
        )


class TestDatasetDelete:
    def test_dataset_delete_with_yes(self, runner, mock_client):
        ds = make_dataset(name="delete-me")
        mock_client.read_dataset.return_value = ds
        mock_client.delete_dataset.return_value = None

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "dataset",
                "delete",
                "delete-me",
                "--yes",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "deleted"


class TestDatasetExport:
    def test_dataset_export(self, runner, mock_client, tmp_path):
        ds = make_dataset(name="export-ds")
        mock_client.read_dataset.return_value = ds

        examples = [
            make_example(inputs={"q": "hello"}, outputs={"a": "world"}),
            make_example(inputs={"q": "foo"}, outputs={"a": "bar"}),
        ]
        mock_client.list_examples.return_value = examples

        output_file = str(tmp_path / "export.json")

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "dataset",
                "export",
                "export-ds",
                output_file,
            ],
        )

        assert result.exit_code == 0
        with open(output_file) as f:
            data = json.load(f)
        assert len(data) == 2

    def test_dataset_export_with_limit(self, runner, mock_client, tmp_path):
        ds = make_dataset(name="export-ds")
        mock_client.read_dataset.return_value = ds
        mock_client.list_examples.return_value = []

        output_file = str(tmp_path / "export.json")

        runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "dataset",
                "export",
                "export-ds",
                output_file,
                "--limit",
                "500",
            ],
        )

        call_kwargs = mock_client.list_examples.call_args[1]
        assert call_kwargs["limit"] == 500


class TestDatasetUpload:
    def test_dataset_upload(self, runner, mock_client, tmp_path):
        ds = make_dataset(name="upload-ds")
        mock_client.create_dataset.return_value = ds
        mock_client.create_examples.return_value = {"count": 2}

        input_file = str(tmp_path / "data.json")
        with open(input_file, "w") as f:
            json.dump(
                [
                    {"inputs": {"q": "hello"}, "outputs": {"a": "world"}},
                    {"inputs": {"q": "foo"}, "outputs": {"a": "bar"}},
                ],
                f,
            )

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "dataset",
                "upload",
                input_file,
                "--name",
                "upload-ds",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "uploaded"
        assert data["example_count"] == 2

    def test_dataset_upload_raw_dicts(self, runner, mock_client, tmp_path):
        """Upload file where items are raw dicts (no inputs/outputs wrapper)."""
        ds = make_dataset(name="raw-ds")
        mock_client.create_dataset.return_value = ds
        mock_client.create_examples.return_value = {"count": 1}

        input_file = str(tmp_path / "data.json")
        with open(input_file, "w") as f:
            json.dump([{"question": "hello", "answer": "world"}], f)

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "dataset",
                "upload",
                input_file,
                "--name",
                "raw-ds",
            ],
        )

        assert result.exit_code == 0
        call_kwargs = mock_client.create_examples.call_args[1]
        assert call_kwargs["inputs"][0] == {"question": "hello", "answer": "world"}
        assert call_kwargs["outputs"][0] is None

    def test_dataset_upload_single_object(self, runner, mock_client, tmp_path):
        """Upload file that is a single object, not an array."""
        ds = make_dataset(name="single-ds")
        mock_client.create_dataset.return_value = ds
        mock_client.create_examples.return_value = {"count": 1}

        input_file = str(tmp_path / "data.json")
        with open(input_file, "w") as f:
            json.dump({"inputs": {"q": "hi"}, "outputs": {"a": "bye"}}, f)

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "dataset",
                "upload",
                input_file,
                "--name",
                "single-ds",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["example_count"] == 1


class TestDatasetViewFile:
    def test_view_json_file(self, runner, tmp_path):
        file_path = str(tmp_path / "data.json")
        with open(file_path, "w") as f:
            json.dump([{"inputs": {"q": "hello"}, "outputs": {"a": "world"}}], f)

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "dataset",
                "view-file",
                file_path,
            ],
        )

        assert result.exit_code == 0
        # Output has header lines (stderr) mixed in; find the JSON array
        output = result.output
        json_start = output.index("[")
        data = json.loads(output[json_start:])
        assert len(data) == 1

    def test_view_csv_file(self, runner, tmp_path):
        file_path = str(tmp_path / "data.csv")
        with open(file_path, "w") as f:
            f.write("question,answer\nhello,world\n")

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "dataset",
                "view-file",
                file_path,
            ],
        )

        assert result.exit_code == 0
        output = result.output
        json_start = output.index("[")
        data = json.loads(output[json_start:])
        assert len(data) == 1

    def test_view_json_with_limit(self, runner, tmp_path):
        file_path = str(tmp_path / "data.json")
        with open(file_path, "w") as f:
            json.dump([{"q": f"q{i}"} for i in range(10)], f)

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "dataset",
                "view-file",
                file_path,
                "--limit",
                "3",
            ],
        )

        assert result.exit_code == 0
        output = result.output
        json_start = output.index("[")
        data = json.loads(output[json_start:])
        assert len(data) == 3

    def test_view_pretty_json(self, runner, tmp_path):
        file_path = str(tmp_path / "data.json")
        with open(file_path, "w") as f:
            json.dump([{"inputs": {"q": "hello"}, "outputs": {"a": "world"}}], f)

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "--format",
                "pretty",
                "dataset",
                "view-file",
                file_path,
            ],
        )

        assert result.exit_code == 0

    def test_view_pretty_csv(self, runner, tmp_path):
        file_path = str(tmp_path / "data.csv")
        with open(file_path, "w") as f:
            f.write("question,answer\nhello,world\n")

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "--format",
                "pretty",
                "dataset",
                "view-file",
                file_path,
            ],
        )

        assert result.exit_code == 0

    def test_view_unsupported_file(self, runner, tmp_path):
        file_path = str(tmp_path / "data.txt")
        with open(file_path, "w") as f:
            f.write("hello")

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "dataset",
                "view-file",
                file_path,
            ],
        )

        assert "Unsupported" in result.output


class TestDatasetStructure:
    def test_structure_json(self, runner, tmp_path):
        file_path = str(tmp_path / "data.json")
        with open(file_path, "w") as f:
            json.dump(
                [
                    {"inputs": {"q": "a"}, "outputs": {"a": "b"}},
                    {"inputs": {"q": "c"}},
                ],
                f,
            )

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "dataset",
                "structure",
                file_path,
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["format"] == "json"
        assert data["example_count"] == 2
        assert "inputs" in data["field_coverage"]

    def test_structure_csv(self, runner, tmp_path):
        file_path = str(tmp_path / "data.csv")
        with open(file_path, "w") as f:
            f.write("question,answer\nhello,world\nfoo,bar\n")

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "dataset",
                "structure",
                file_path,
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["format"] == "csv"
        assert data["row_count"] == 2
        assert "question" in data["column_coverage"]

    def test_structure_unsupported_file(self, runner, tmp_path):
        file_path = str(tmp_path / "data.txt")
        with open(file_path, "w") as f:
            f.write("hello")

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "dataset",
                "structure",
                file_path,
            ],
        )

        assert "Unsupported" in result.output


class TestDatasetGenerate:
    def test_generate_final_response(self, runner, mock_client, tmp_path):
        # Create input JSONL file
        input_file = str(tmp_path / "traces.jsonl")
        with open(input_file, "w") as f:
            f.write(
                json.dumps(
                    {
                        "run_id": "r1",
                        "trace_id": "t1",
                        "name": "root",
                        "run_type": "chain",
                        "parent_run_id": None,
                        "inputs": {"query": "hello"},
                        "outputs": {"answer": "world"},
                        "start_time": "2024-01-01T00:00:00Z",
                    }
                )
                + "\n"
            )

        output_file = str(tmp_path / "eval.json")

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "dataset",
                "generate",
                "-i",
                input_file,
                "-o",
                output_file,
                "--type",
                "final_response",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "generated"
        assert data["count"] == 1

        with open(output_file) as f:
            dataset = json.load(f)
        assert len(dataset) == 1

    def test_generate_from_directory(self, runner, mock_client, tmp_path):
        input_dir = tmp_path / "traces"
        input_dir.mkdir()

        trace_file = input_dir / "trace.jsonl"
        trace_file.write_text(
            json.dumps(
                {
                    "run_id": "r1",
                    "trace_id": "t1",
                    "name": "root",
                    "run_type": "chain",
                    "parent_run_id": None,
                    "inputs": {"query": "q1"},
                    "outputs": {"answer": "a1"},
                    "start_time": "2024-01-01T00:00:00Z",
                }
            )
            + "\n"
        )

        output_file = str(tmp_path / "eval.json")

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "dataset",
                "generate",
                "-i",
                str(input_dir),
                "-o",
                output_file,
                "--type",
                "final_response",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 1

    def test_generate_no_traces_error(self, runner, mock_client, tmp_path):
        input_dir = tmp_path / "empty"
        input_dir.mkdir()

        output_file = str(tmp_path / "eval.json")

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "dataset",
                "generate",
                "-i",
                str(input_dir),
                "-o",
                output_file,
                "--type",
                "final_response",
            ],
        )

        assert "No traces found" in result.output

    def test_generate_file_exists_no_replace(self, runner, mock_client, tmp_path):
        input_file = str(tmp_path / "traces.jsonl")
        with open(input_file, "w") as f:
            f.write(
                json.dumps(
                    {
                        "run_id": "r1",
                        "trace_id": "t1",
                        "name": "root",
                        "run_type": "chain",
                        "parent_run_id": None,
                        "inputs": {"query": "q"},
                        "outputs": {"answer": "a"},
                        "start_time": "2024-01-01T00:00:00Z",
                    }
                )
                + "\n"
            )

        output_file = str(tmp_path / "eval.json")
        with open(output_file, "w") as f:
            f.write("existing content")

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "dataset",
                "generate",
                "-i",
                input_file,
                "-o",
                output_file,
                "--type",
                "final_response",
            ],
        )

        assert "exists" in result.output

    def test_generate_with_replace(self, runner, mock_client, tmp_path):
        input_file = str(tmp_path / "traces.jsonl")
        with open(input_file, "w") as f:
            f.write(
                json.dumps(
                    {
                        "run_id": "r1",
                        "trace_id": "t1",
                        "name": "root",
                        "run_type": "chain",
                        "parent_run_id": None,
                        "inputs": {"query": "q"},
                        "outputs": {"answer": "a"},
                        "start_time": "2024-01-01T00:00:00Z",
                    }
                )
                + "\n"
            )

        output_file = str(tmp_path / "eval.json")
        with open(output_file, "w") as f:
            f.write("existing content")

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "dataset",
                "generate",
                "-i",
                input_file,
                "-o",
                output_file,
                "--type",
                "final_response",
                "--replace",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "generated"

    def test_generate_with_upload(self, runner, mock_client, tmp_path):
        from types import SimpleNamespace

        input_file = str(tmp_path / "traces.jsonl")
        with open(input_file, "w") as f:
            f.write(
                json.dumps(
                    {
                        "run_id": "r1",
                        "trace_id": "t1",
                        "name": "root",
                        "run_type": "chain",
                        "parent_run_id": None,
                        "inputs": {"query": "q"},
                        "outputs": {"answer": "a"},
                        "start_time": "2024-01-01T00:00:00Z",
                    }
                )
                + "\n"
            )

        output_file = str(tmp_path / "eval.json")

        ds = SimpleNamespace(id="ds-123")
        mock_client.create_dataset.return_value = ds

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "dataset",
                "generate",
                "-i",
                input_file,
                "-o",
                output_file,
                "--type",
                "final_response",
                "--upload",
                "my-eval-set",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["uploaded_to"] == "my-eval-set"
        mock_client.create_examples.assert_called_once()

    def test_generate_rag_type(self, runner, mock_client, tmp_path):
        input_file = str(tmp_path / "traces.jsonl")
        with open(input_file, "w") as f:
            f.write(
                json.dumps(
                    {
                        "run_id": "r1",
                        "trace_id": "t1",
                        "name": "root",
                        "run_type": "chain",
                        "parent_run_id": None,
                        "inputs": {"query": "what is LangSmith"},
                        "outputs": {},
                        "start_time": "2024-01-01T00:00:00Z",
                    }
                )
                + "\n"
            )
            f.write(
                json.dumps(
                    {
                        "run_id": "r2",
                        "trace_id": "t1",
                        "name": "retriever",
                        "run_type": "retriever",
                        "parent_run_id": "r1",
                        "inputs": {"query": "what is LangSmith"},
                        "outputs": {"documents": [{"page_content": "LangSmith is..."}]},
                        "start_time": "2024-01-01T00:00:01Z",
                    }
                )
                + "\n"
            )
            f.write(
                json.dumps(
                    {
                        "run_id": "r3",
                        "trace_id": "t1",
                        "name": "llm",
                        "run_type": "llm",
                        "parent_run_id": "r1",
                        "inputs": {},
                        "outputs": {"answer": "LangSmith is a platform"},
                        "start_time": "2024-01-01T00:00:02Z",
                    }
                )
                + "\n"
            )

        output_file = str(tmp_path / "eval.json")

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "dataset",
                "generate",
                "-i",
                input_file,
                "-o",
                output_file,
                "--type",
                "rag",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["type"] == "rag"

    def test_generate_with_input_output_fields(self, runner, mock_client, tmp_path):
        input_file = str(tmp_path / "traces.jsonl")
        with open(input_file, "w") as f:
            f.write(
                json.dumps(
                    {
                        "run_id": "r1",
                        "trace_id": "t1",
                        "name": "root",
                        "run_type": "chain",
                        "parent_run_id": None,
                        "inputs": {"my_query": "hello"},
                        "outputs": {"my_answer": "world"},
                        "start_time": "2024-01-01T00:00:00Z",
                    }
                )
                + "\n"
            )

        output_file = str(tmp_path / "eval.json")

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "dataset",
                "generate",
                "-i",
                input_file,
                "-o",
                output_file,
                "--type",
                "final_response",
                "--input-fields",
                "my_query",
                "--output-fields",
                "my_answer",
            ],
        )

        assert result.exit_code == 0
        with open(output_file) as f:
            dataset = json.load(f)
        assert len(dataset) == 1

    def test_generate_trajectory_type(self, runner, mock_client, tmp_path):
        input_file = str(tmp_path / "traces.jsonl")
        with open(input_file, "w") as f:
            f.write(
                json.dumps(
                    {
                        "run_id": "r1",
                        "trace_id": "t1",
                        "name": "root",
                        "run_type": "chain",
                        "parent_run_id": None,
                        "inputs": {"query": "find info"},
                        "outputs": {},
                        "start_time": "2024-01-01T00:00:00Z",
                    }
                )
                + "\n"
            )
            f.write(
                json.dumps(
                    {
                        "run_id": "r2",
                        "trace_id": "t1",
                        "name": "Search",
                        "run_type": "tool",
                        "parent_run_id": "r1",
                        "inputs": {},
                        "outputs": {},
                        "start_time": "2024-01-01T00:00:01Z",
                    }
                )
                + "\n"
            )

        output_file = str(tmp_path / "eval.json")

        result = runner.invoke(
            cli,
            [
                "--api-key",
                "test-key",
                "dataset",
                "generate",
                "-i",
                input_file,
                "-o",
                output_file,
                "--type",
                "trajectory",
            ],
        )

        assert result.exit_code == 0
        with open(output_file) as f:
            dataset = json.load(f)
        assert dataset[0]["outputs"]["expected_trajectory"] == ["search"]
