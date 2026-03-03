"""Tests for output.py - JSON, JSONL, table, tree formatting."""

import json
import os
import tempfile
import uuid

from langsmith.cli.output import (
    output_json,
    output_jsonl,
    output_table,
    output_tree,
    print_output,
    print_runs_table,
)
from tests.unit_tests.cli.conftest import make_run


class TestOutputJson:
    def test_json_to_stdout(self, capsys):
        output_json({"key": "value"})
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["key"] == "value"

    def test_json_to_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
        try:
            output_json({"key": "value"}, path)
            with open(path) as f:
                data = json.load(f)
            assert data["key"] == "value"
        finally:
            os.unlink(path)

    def test_json_list(self, capsys):
        output_json([1, 2, 3])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data == [1, 2, 3]

    def test_json_file_writes_status_to_stderr(self, capsys):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
        try:
            output_json({"key": "value"}, path)
            captured = capsys.readouterr()
            assert "written" in captured.err
            assert path in captured.err
        finally:
            os.unlink(path)


class TestOutputJsonl:
    def test_jsonl_to_stdout(self, capsys):
        output_jsonl([{"a": 1}, {"b": 2}])
        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0]) == {"a": 1}
        assert json.loads(lines[1]) == {"b": 2}

    def test_jsonl_to_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            output_jsonl([{"a": 1}, {"b": 2}], path)
            with open(path) as f:
                lines = f.read().strip().split("\n")
            assert len(lines) == 2
        finally:
            os.unlink(path)

    def test_jsonl_empty_list(self, capsys):
        output_jsonl([])
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_jsonl_file_writes_status_to_stderr(self, capsys):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            output_jsonl([{"a": 1}], path)
            captured = capsys.readouterr()
            assert "written" in captured.err
            assert "count" in captured.err
        finally:
            os.unlink(path)


class TestOutputTable:
    def test_renders_table(self, capsys):
        output_table(["Name", "Value"], [["foo", "bar"], ["baz", "qux"]], title="Test")
        captured = capsys.readouterr()
        assert "foo" in captured.out
        assert "bar" in captured.out

    def test_handles_none_values(self, capsys):
        output_table(["Col"], [[None]])
        captured = capsys.readouterr()
        assert captured.out  # Should not crash

    def test_empty_rows(self, capsys):
        output_table(["Col1", "Col2"], [])
        captured = capsys.readouterr()
        assert "Col1" in captured.out


class TestOutputTree:
    def test_renders_tree(self, capsys):
        root_id = uuid.uuid4()
        child_id = uuid.uuid4()
        root = make_run(run_id=root_id, name="root", run_type="chain")
        child = make_run(run_id=child_id, name="child", run_type="llm", parent_run_id=root_id)
        output_tree([root, child])
        captured = capsys.readouterr()
        assert "root" in captured.out

    def test_empty_runs(self, capsys):
        output_tree([])
        captured = capsys.readouterr()
        assert "No runs found" in captured.out

    def test_tree_with_root_id(self, capsys):
        root_id = uuid.uuid4()
        root = make_run(run_id=root_id, name="specific-root", run_type="chain")
        output_tree([root], root_id=str(root_id))
        captured = capsys.readouterr()
        assert "specific-root" in captured.out

    def test_tree_error_child_highlighted(self, capsys):
        root_id = uuid.uuid4()
        child_id = uuid.uuid4()
        root = make_run(run_id=root_id, name="root", run_type="chain")
        child = make_run(run_id=child_id, name="error-child", run_type="llm",
                         parent_run_id=root_id, error="something broke")
        output_tree([root, child])
        captured = capsys.readouterr()
        assert "error-child" in captured.out


class TestPrintRunsTable:
    def test_basic_table(self, capsys):
        runs = [make_run(name="run-1"), make_run(name="run-2")]
        print_runs_table(runs)
        captured = capsys.readouterr()
        assert "run-1" in captured.out
        assert "run-2" in captured.out

    def test_with_metadata(self, capsys):
        runs = [make_run(name="my-run", total_tokens=100, status="success")]
        print_runs_table(runs, include_metadata=True)
        captured = capsys.readouterr()
        assert "my-run" in captured.out
        assert "100" in captured.out

    def test_with_title(self, capsys):
        runs = [make_run(name="titled-run")]
        print_runs_table(runs, title="My Table")
        captured = capsys.readouterr()
        assert "My Table" in captured.out

    def test_empty_runs(self, capsys):
        print_runs_table([])
        capsys.readouterr()
        # Should not crash, just print empty table


class TestPrintOutput:
    def test_json_mode(self, capsys):
        print_output({"key": "value"}, "json")
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["key"] == "value"

    def test_json_to_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
        try:
            print_output({"key": "value"}, "json", path)
            with open(path) as f:
                data = json.load(f)
            assert data["key"] == "value"
        finally:
            os.unlink(path)

    def test_pretty_mode(self, capsys):
        print_output({"key": "value"}, "pretty")
        captured = capsys.readouterr()
        assert "key" in captured.out

    def test_pretty_to_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
        try:
            print_output({"key": "value"}, "pretty", path)
            with open(path) as f:
                data = json.load(f)
            assert data["key"] == "value"
        finally:
            os.unlink(path)
