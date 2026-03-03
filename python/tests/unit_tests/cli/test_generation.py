"""Tests for generation.py - dataset generation from traces."""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from langsmith.cli.generation import (
    _load_json_file,
    _load_jsonl_file,
    _sort_traces,
    dict_to_obj,
    export_to_file,
    export_to_langsmith,
    extract_documents,
    extract_final_output,
    extract_from_messages,
    extract_tool_sequence,
    extract_trace_inputs,
    extract_trace_output,
    extract_value,
    find_retrieval_data,
    generate_dataset,
    get_node_io,
    load_traces_from_dir,
    load_traces_from_file,
)


# --- dict_to_obj ---

class TestDictToObj:
    def test_basic_conversion(self):
        obj = dict_to_obj({"name": "test", "value": 42})
        assert obj.name == "test"
        assert obj.value == 42

    def test_parses_start_time(self):
        obj = dict_to_obj({"start_time": "2024-01-15T10:30:00Z"})
        assert isinstance(obj.start_time, datetime)

    def test_parses_end_time(self):
        obj = dict_to_obj({"end_time": "2024-01-15T11:00:00+00:00"})
        assert isinstance(obj.end_time, datetime)

    def test_invalid_datetime_preserved(self):
        obj = dict_to_obj({"start_time": "not-a-date"})
        assert obj.start_time == "not-a-date"

    def test_non_string_datetime_preserved(self):
        obj = dict_to_obj({"start_time": 12345})
        assert obj.start_time == 12345


# --- File loading ---

class TestLoadJsonlFile:
    def test_loads_grouped_by_trace(self, tmp_path):
        filepath = tmp_path / "trace.jsonl"
        lines = [
            json.dumps({"run_id": "r1", "trace_id": "t1", "name": "root", "parent_run_id": None}),
            json.dumps({"run_id": "r2", "trace_id": "t1", "name": "child", "parent_run_id": "r1"}),
            json.dumps({"run_id": "r3", "trace_id": "t2", "name": "root2", "parent_run_id": None}),
        ]
        filepath.write_text("\n".join(lines))

        traces = _load_jsonl_file(str(filepath))
        assert len(traces) == 2

        t1_traces = [t for t in traces if t[0] == "t1"]
        assert len(t1_traces) == 1
        assert t1_traces[0][1].name == "root"
        assert len(t1_traces[0][2]) == 2

    def test_skips_blank_lines(self, tmp_path):
        filepath = tmp_path / "trace.jsonl"
        filepath.write_text('{"run_id": "r1", "trace_id": "t1", "name": "x"}\n\n\n')
        traces = _load_jsonl_file(str(filepath))
        assert len(traces) == 1

    def test_skips_invalid_json(self, tmp_path):
        filepath = tmp_path / "trace.jsonl"
        filepath.write_text('{"run_id": "r1", "trace_id": "t1"}\nnot json\n')
        traces = _load_jsonl_file(str(filepath))
        assert len(traces) == 1

    def test_root_detection_fallback(self, tmp_path):
        """When no run has parent_run_id=None, first run becomes root."""
        filepath = tmp_path / "trace.jsonl"
        lines = [
            json.dumps({"run_id": "r1", "trace_id": "t1", "parent_run_id": "r0"}),
            json.dumps({"run_id": "r2", "trace_id": "t1", "parent_run_id": "r0"}),
        ]
        filepath.write_text("\n".join(lines))
        traces = _load_jsonl_file(str(filepath))
        assert len(traces) == 1
        assert traces[0][1].run_id == "r1"


class TestLoadJsonFile:
    def test_loads_array_format(self, tmp_path):
        filepath = tmp_path / "data.json"
        data = [
            {"trace_id": "t1", "run_id": "r1", "name": "root", "parent_run_id": None},
        ]
        filepath.write_text(json.dumps(data))
        traces = _load_json_file(str(filepath))
        assert len(traces) == 1

    def test_loads_single_object(self, tmp_path):
        filepath = tmp_path / "data.json"
        filepath.write_text(json.dumps({"trace_id": "t1", "run_id": "r1"}))
        traces = _load_json_file(str(filepath))
        assert len(traces) == 1

    def test_loads_with_runs_field(self, tmp_path):
        filepath = tmp_path / "data.json"
        data = [{
            "trace_id": "t1",
            "runs": [
                {"run_id": "r1", "name": "root", "parent_run_id": None},
                {"run_id": "r2", "name": "child", "parent_run_id": "r1"},
            ],
        }]
        filepath.write_text(json.dumps(data))
        traces = _load_json_file(str(filepath))
        assert len(traces) == 1
        assert len(traces[0][2]) == 2

    def test_skips_non_dict_items(self, tmp_path):
        filepath = tmp_path / "data.json"
        filepath.write_text(json.dumps(["not a dict", {"trace_id": "t1"}]))
        traces = _load_json_file(str(filepath))
        assert len(traces) == 1


class TestLoadTracesFromDir:
    def test_loads_multiple_files(self, tmp_path):
        for i in range(3):
            f = tmp_path / f"trace_{i}.jsonl"
            f.write_text(json.dumps({"run_id": f"r{i}", "trace_id": f"t{i}", "name": f"run{i}"}) + "\n")

        traces = load_traces_from_dir(str(tmp_path))
        assert len(traces) == 3

    def test_ignores_non_jsonl_files(self, tmp_path):
        (tmp_path / "trace.jsonl").write_text(json.dumps({"run_id": "r1", "trace_id": "t1"}) + "\n")
        (tmp_path / "readme.txt").write_text("not a trace")

        traces = load_traces_from_dir(str(tmp_path))
        assert len(traces) == 1


class TestLoadTracesFromFile:
    def test_loads_jsonl(self, tmp_path):
        f = tmp_path / "data.jsonl"
        f.write_text(json.dumps({"run_id": "r1", "trace_id": "t1"}) + "\n")
        traces = load_traces_from_file(str(f))
        assert len(traces) == 1

    def test_loads_json(self, tmp_path):
        f = tmp_path / "data.json"
        f.write_text(json.dumps([{"trace_id": "t1", "run_id": "r1"}]))
        traces = load_traces_from_file(str(f))
        assert len(traces) == 1

    def test_unsupported_extension(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text("a,b\n1,2\n")
        traces = load_traces_from_file(str(f))
        assert traces == []


class TestSortTraces:
    def _make_traces(self):
        t1 = ("t1", SimpleNamespace(start_time=datetime(2024, 1, 1, tzinfo=timezone.utc)), [])
        t2 = ("t2", SimpleNamespace(start_time=datetime(2024, 1, 3, tzinfo=timezone.utc)), [])
        t3 = ("t3", SimpleNamespace(start_time=datetime(2024, 1, 2, tzinfo=timezone.utc)), [])
        return [t1, t2, t3]

    def test_newest_first(self):
        traces = _sort_traces(self._make_traces(), "newest")
        assert [t[0] for t in traces] == ["t2", "t3", "t1"]

    def test_oldest_first(self):
        traces = _sort_traces(self._make_traces(), "oldest")
        assert [t[0] for t in traces] == ["t1", "t3", "t2"]

    def test_alphabetical(self):
        traces = _sort_traces(self._make_traces(), "alphabetical")
        assert [t[0] for t in traces] == ["t1", "t2", "t3"]

    def test_reverse_alphabetical(self):
        traces = _sort_traces(self._make_traces(), "reverse-alphabetical")
        assert [t[0] for t in traces] == ["t3", "t2", "t1"]


# --- Extraction helpers ---

class TestExtractFromMessages:
    def test_extract_human_message(self):
        messages = [
            {"type": "human", "content": "Hello, world!"},
            {"type": "ai", "content": "Hi there!"},
        ]
        assert extract_from_messages(messages, "human") == "Hello, world!"

    def test_extract_user_role(self):
        messages = [{"role": "user", "content": "What is LangSmith?"}]
        assert extract_from_messages(messages, "user") == "What is LangSmith?"

    def test_extract_ai_message(self):
        messages = [
            {"type": "human", "content": "Hello"},
            {"type": "ai", "content": "Hi there!"},
        ]
        assert extract_from_messages(messages, "ai") == "Hi there!"

    def test_extract_assistant_role(self):
        messages = [{"role": "assistant", "content": "Sure thing!"}]
        assert extract_from_messages(messages, "assistant") == "Sure thing!"

    def test_multipart_content(self):
        messages = [
            {"type": "human", "content": [{"type": "text", "text": "Part 1"}, {"type": "text", "text": "Part 2"}]},
        ]
        assert extract_from_messages(messages, "human") == "Part 1 Part 2"

    def test_no_matching_role(self):
        messages = [{"type": "ai", "content": "Only AI here"}]
        assert extract_from_messages(messages, "human") is None

    def test_empty_messages(self):
        assert extract_from_messages([], "human") is None
        assert extract_from_messages(None, "human") is None

    def test_no_role_returns_last(self):
        messages = [{"content": "first"}, {"content": "last"}]
        assert extract_from_messages(messages, None) == "last"

    def test_string_messages_for_human(self):
        messages = ["just a string"]
        assert extract_from_messages(messages, "human") == "just a string"

    def test_ai_skips_none_content(self):
        messages = [{"type": "ai", "content": "None"}, {"type": "ai", "content": "real answer"}]
        assert extract_from_messages(messages, "ai") == "real answer"


class TestExtractValue:
    def test_user_specified_fields(self):
        data = {"query": "hello", "other": "world"}
        assert extract_value(data, fields=["query"]) == "hello"

    def test_messages_extraction(self):
        data = {"messages": [{"type": "human", "content": "Hi"}]}
        assert extract_value(data, message_role="human") == "Hi"

    def test_common_fields(self):
        data = {"question": "What?"}
        assert extract_value(data, common_fields=["question"]) == "What?"

    def test_fallback_single_string(self):
        data = {"only_key": "only_value"}
        assert extract_value(data) == "only_value"

    def test_fallback_first_string(self):
        data = {"num": 42, "text": "hello", "more": "world"}
        assert extract_value(data) == "hello"

    def test_fallback_returns_dict(self):
        data = {"num": 42, "other_num": 100}
        assert extract_value(data) == data

    def test_no_fallback(self):
        data = {"num": 42}
        assert extract_value(data, fallback_to_raw=False) is None

    def test_none_data(self):
        assert extract_value(None) is None

    def test_non_dict_data(self):
        assert extract_value("not a dict") is None

    def test_priority_chain(self):
        data = {"query": "from_field", "messages": [{"type": "human", "content": "from_msg"}]}
        assert extract_value(data, fields=["query"], message_role="human") == "from_field"


class TestExtractTraceInputs:
    def test_basic_extraction(self):
        root = SimpleNamespace(inputs={"query": "hello"})
        assert extract_trace_inputs(root) == "hello"

    def test_with_input_fields(self):
        root = SimpleNamespace(inputs={"my_field": "value", "query": "other"})
        assert extract_trace_inputs(root, input_fields=["my_field"]) == "value"

    def test_no_inputs(self):
        root = SimpleNamespace(inputs=None)
        assert extract_trace_inputs(root) is None

    def test_as_dict(self):
        root = SimpleNamespace(inputs={"query": "hello", "context": "world"})
        result = extract_trace_inputs(root, as_dict=True)
        assert isinstance(result, dict)
        assert result["query"] == "hello"


class TestExtractTraceOutput:
    def test_basic_extraction(self):
        root = SimpleNamespace(outputs={"answer": "hello"})
        assert extract_trace_output(root) == "hello"

    def test_with_output_fields(self):
        root = SimpleNamespace(outputs={"my_output": "value"})
        assert extract_trace_output(root, output_fields=["my_output"]) == "value"

    def test_no_outputs(self):
        root = SimpleNamespace(outputs=None)
        assert extract_trace_output(root) is None

    def test_messages_only(self):
        root = SimpleNamespace(outputs={"messages": [{"type": "ai", "content": "AI says hi"}]})
        assert extract_trace_output(root, messages_only=True) == "AI says hi"

    def test_dict_output_serialized(self):
        root = SimpleNamespace(outputs={"nested": {"key": "val"}})
        result = extract_trace_output(root)
        assert isinstance(result, str)
        assert "key" in result


class TestExtractFinalOutput:
    def test_finds_output_from_newest_run(self):
        runs = [
            SimpleNamespace(outputs={"answer": "old"}, start_time=datetime(2024, 1, 1, tzinfo=timezone.utc)),
            SimpleNamespace(outputs={"answer": "new"}, start_time=datetime(2024, 1, 2, tzinfo=timezone.utc)),
        ]
        assert extract_final_output(runs) == "new"

    def test_skips_empty_outputs(self):
        runs = [
            SimpleNamespace(outputs=None, start_time=datetime(2024, 1, 2, tzinfo=timezone.utc)),
            SimpleNamespace(outputs={"answer": "found"}, start_time=datetime(2024, 1, 1, tzinfo=timezone.utc)),
        ]
        assert extract_final_output(runs) == "found"

    def test_no_outputs_returns_none(self):
        runs = [SimpleNamespace(outputs=None, start_time=datetime(2024, 1, 1, tzinfo=timezone.utc))]
        assert extract_final_output(runs) is None


class TestExtractToolSequence:
    def test_basic_sequence(self):
        runs = [
            SimpleNamespace(run_type="tool", name="Search", start_time=datetime(2024, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
                            run_id="r1", parent_run_id=None),
            SimpleNamespace(run_type="tool", name="Calculator", start_time=datetime(2024, 1, 1, 0, 0, 2, tzinfo=timezone.utc),
                            run_id="r2", parent_run_id=None),
            SimpleNamespace(run_type="llm", name="ChatOpenAI", start_time=datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                            run_id="r3", parent_run_id=None),
        ]
        tools = extract_tool_sequence(runs)
        assert tools == ["search", "calculator"]

    def test_empty_runs(self):
        assert extract_tool_sequence([]) == []

    def test_no_tool_runs(self):
        runs = [SimpleNamespace(run_type="llm", name="GPT", start_time="", run_id="r1")]
        assert extract_tool_sequence(runs) == []

    def test_depth_filter(self):
        runs = [
            SimpleNamespace(run_type="chain", name="root", start_time="2024-01-01T00:00:00Z",
                            run_id="r0", id="r0", parent_run_id=None),
            SimpleNamespace(run_type="tool", name="shallow_tool", start_time="2024-01-01T00:00:01Z",
                            run_id="r1", id="r1", parent_run_id="r0"),
            SimpleNamespace(run_type="tool", name="deep_tool", start_time="2024-01-01T00:00:02Z",
                            run_id="r2", id="r2", parent_run_id="r1"),
        ]
        tools = extract_tool_sequence(runs, depth=1)
        assert "shallow_tool" in tools


class TestGetNodeIO:
    def test_gets_all_nodes(self):
        runs = [
            SimpleNamespace(name="ChatOpenAI", inputs={"q": "hi"}, outputs={"a": "bye"},
                            start_time="2024-01-01", run_id="r1", id="r1"),
            SimpleNamespace(name="ChatOpenAI", inputs={"q": "foo"}, outputs={"a": "bar"},
                            start_time="2024-01-02", run_id="r2", id="r2"),
        ]
        results = get_node_io(runs, "ChatOpenAI")
        assert len(results) == 2
        assert results[0]["node_name"] == "ChatOpenAI"

    def test_filters_by_name(self):
        runs = [
            SimpleNamespace(name="ChatOpenAI", inputs={}, outputs={"a": "1"},
                            start_time="", run_id="r1", id="r1"),
            SimpleNamespace(name="OtherModel", inputs={}, outputs={"a": "2"},
                            start_time="", run_id="r2", id="r2"),
        ]
        results = get_node_io(runs, "ChatOpenAI")
        assert len(results) == 1

    def test_skips_no_outputs(self):
        runs = [
            SimpleNamespace(name="ChatOpenAI", inputs={}, outputs=None,
                            start_time="", run_id="r1", id="r1"),
        ]
        results = get_node_io(runs, "ChatOpenAI")
        assert len(results) == 0

    def test_no_name_filter(self):
        runs = [
            SimpleNamespace(name="A", inputs={}, outputs={"x": 1},
                            start_time="", run_id="r1", id="r1"),
            SimpleNamespace(name="B", inputs={}, outputs={"x": 2},
                            start_time="", run_id="r2", id="r2"),
        ]
        results = get_node_io(runs, None)
        assert len(results) == 2


class TestExtractDocuments:
    def test_dict_with_documents(self):
        outputs = {"documents": [{"page_content": "Hello"}, {"page_content": "World"}]}
        chunks = extract_documents(outputs)
        assert chunks == ["Hello", "World"]

    def test_list_of_strings(self):
        chunks = extract_documents(["chunk 1", "chunk 2"])
        assert chunks == ["chunk 1", "chunk 2"]

    def test_empty_outputs(self):
        assert extract_documents(None) == []
        assert extract_documents({}) == []

    def test_dict_fallback_to_content(self):
        outputs = {"documents": [{"content": "Hello"}]}
        chunks = extract_documents(outputs)
        assert chunks == ["Hello"]

    def test_dict_fallback_to_text(self):
        outputs = {"documents": [{"text": "Hello"}]}
        chunks = extract_documents(outputs)
        assert chunks == ["Hello"]

    def test_dict_no_text_field_serializes(self):
        outputs = {"documents": [{"other_field": "value"}]}
        chunks = extract_documents(outputs)
        assert len(chunks) == 1
        assert "other_field" in chunks[0]

    def test_non_dict_non_string_items(self):
        chunks = extract_documents([42, True])
        assert chunks == ["42", "True"]


class TestFindRetrievalData:
    def test_finds_retrieval_data(self):
        runs = [
            SimpleNamespace(
                run_type="retriever",
                inputs={"query": "What is LangSmith?"},
                outputs={"documents": [{"page_content": "LangSmith is..."}]},
                start_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ),
            SimpleNamespace(
                run_type="llm",
                inputs={"prompt": "Answer the question"},
                outputs={"answer": "LangSmith is a platform"},
                start_time=datetime(2024, 1, 2, tzinfo=timezone.utc),
            ),
        ]
        result = find_retrieval_data(runs)
        assert result["query"] == "What is LangSmith?"
        assert len(result["retrieved_chunks"]) == 1
        assert result["answer"] is not None

    def test_no_retrievers(self):
        runs = [
            SimpleNamespace(run_type="llm", inputs={}, outputs={"answer": "hi"},
                            start_time=datetime(2024, 1, 1, tzinfo=timezone.utc)),
        ]
        result = find_retrieval_data(runs)
        assert result["query"] is None
        assert result["retrieved_chunks"] == []

    def test_multiple_retrievers(self):
        runs = [
            SimpleNamespace(
                run_type="retriever",
                inputs={"query": "q1"},
                outputs={"documents": [{"page_content": "chunk1"}]},
                start_time=datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            ),
            SimpleNamespace(
                run_type="retriever",
                inputs={"query": "q2"},
                outputs={"documents": [{"page_content": "chunk2"}]},
                start_time=datetime(2024, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
            ),
        ]
        result = find_retrieval_data(runs)
        assert result["query"] == "q1"
        assert len(result["retrieved_chunks"]) == 2


# --- generate_dataset ---

_SENTINEL = object()


class TestGenerateDataset:
    def _make_trace(self, trace_id="t1", root_inputs=_SENTINEL, root_outputs=_SENTINEL,
                    extra_runs=None):
        root = SimpleNamespace(
            run_id="r1", id="r1", name="root", run_type="chain",
            parent_run_id=None,
            inputs={"query": "hello"} if root_inputs is _SENTINEL else root_inputs,
            outputs={"answer": "world"} if root_outputs is _SENTINEL else root_outputs,
            start_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        runs = [root] + (extra_runs or [])
        return (trace_id, root, runs)

    def test_final_response(self):
        traces = [self._make_trace()]
        dataset = generate_dataset(traces, "final_response")
        assert len(dataset) == 1
        assert dataset[0]["trace_id"] == "t1"
        assert dataset[0]["outputs"]["expected_response"] == "world"

    def test_final_response_no_output_skips(self):
        traces = [self._make_trace(root_inputs={"query": "hello"}, root_outputs=None)]
        dataset = generate_dataset(traces, "final_response")
        assert len(dataset) == 0

    def test_final_response_with_input_fields(self):
        traces = [self._make_trace(root_inputs={"my_input": "val"})]
        dataset = generate_dataset(traces, "final_response", input_fields=["my_input"])
        assert len(dataset) == 1
        assert dataset[0]["inputs"]["expected_input"] == "val"

    def test_single_step(self):
        node = SimpleNamespace(
            run_id="r2", id="r2", name="ChatOpenAI", run_type="llm",
            parent_run_id="r1", inputs={"prompt": "hi"},
            outputs={"text": "bye"}, start_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        traces = [self._make_trace(extra_runs=[node])]
        dataset = generate_dataset(traces, "single_step", run_name="ChatOpenAI")
        assert len(dataset) == 1
        assert dataset[0]["node_name"] == "ChatOpenAI"

    def test_single_step_sample_per_trace(self):
        nodes = [
            SimpleNamespace(
                run_id=f"r{i}", id=f"r{i}", name="Node", run_type="llm",
                parent_run_id="r1", inputs={"p": f"i{i}"},
                outputs={"t": f"o{i}"}, start_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
            )
            for i in range(10)
        ]
        traces = [self._make_trace(extra_runs=nodes)]
        dataset = generate_dataset(traces, "single_step", sample_per_trace=3)
        assert len(dataset) == 3

    def test_trajectory(self):
        tool1 = SimpleNamespace(
            run_id="r2", id="r2", name="Search", run_type="tool",
            parent_run_id="r1", inputs={}, outputs={},
            start_time=datetime(2024, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
        )
        tool2 = SimpleNamespace(
            run_id="r3", id="r3", name="Calculator", run_type="tool",
            parent_run_id="r1", inputs={}, outputs={},
            start_time=datetime(2024, 1, 1, 0, 0, 2, tzinfo=timezone.utc),
        )
        traces = [self._make_trace(extra_runs=[tool1, tool2])]
        dataset = generate_dataset(traces, "trajectory")
        assert len(dataset) == 1
        assert dataset[0]["outputs"]["expected_trajectory"] == ["search", "calculator"]

    def test_trajectory_with_depth(self):
        tool = SimpleNamespace(
            run_id="r2", id="r2", name="Tool", run_type="tool",
            parent_run_id="r1", inputs={}, outputs={},
            start_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        traces = [self._make_trace(extra_runs=[tool])]
        dataset = generate_dataset(traces, "trajectory", depth=1)
        assert len(dataset) == 1

    def test_rag(self):
        retriever = SimpleNamespace(
            run_id="r2", id="r2", name="Retriever", run_type="retriever",
            parent_run_id="r1",
            inputs={"query": "What is LangSmith?"},
            outputs={"documents": [{"page_content": "LangSmith is a platform."}]},
            start_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        llm = SimpleNamespace(
            run_id="r3", id="r3", name="LLM", run_type="llm",
            parent_run_id="r1", inputs={},
            outputs={"answer": "LangSmith is a platform for LLM observability."},
            start_time=datetime(2024, 1, 2, tzinfo=timezone.utc),
        )
        traces = [self._make_trace(extra_runs=[retriever, llm])]
        dataset = generate_dataset(traces, "rag")
        assert len(dataset) == 1
        assert dataset[0]["question"] == "What is LangSmith?"
        assert "LangSmith" in dataset[0]["answer"]

    def test_rag_no_retriever_skips(self):
        traces = [self._make_trace()]
        dataset = generate_dataset(traces, "rag")
        assert len(dataset) == 0


# --- Export ---

class TestExportToFile:
    def test_export_json(self, tmp_path):
        dataset = [{"trace_id": "t1", "inputs": {"q": "hello"}, "outputs": {"a": "world"}}]
        output_path = str(tmp_path / "output.json")
        export_to_file(dataset, output_path)

        with open(output_path) as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["trace_id"] == "t1"

    def test_export_csv(self, tmp_path):
        dataset = [
            {"trace_id": "t1", "question": "hello", "answer": "world"},
            {"trace_id": "t2", "question": "foo", "answer": "bar"},
        ]
        output_path = str(tmp_path / "output.csv")
        export_to_file(dataset, output_path)

        with open(output_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["question"] == "hello"

    def test_export_csv_empty(self, tmp_path):
        output_path = str(tmp_path / "output.csv")
        export_to_file([], output_path)
        assert not os.path.exists(output_path) or os.path.getsize(output_path) == 0

    def test_export_csv_complex_values(self, tmp_path):
        dataset = [{"data": {"nested": "value"}, "list": [1, 2, 3]}]
        output_path = str(tmp_path / "output.csv")
        export_to_file(dataset, output_path)

        with open(output_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 1


class TestExportToLangsmith:
    def test_creates_and_uploads(self):
        client = MagicMock()
        ds = SimpleNamespace(id="ds-123")
        client.create_dataset.return_value = ds

        dataset = [
            {"inputs": {"q": "hello"}, "outputs": {"a": "world"}},
            {"inputs": {"q": "foo"}, "outputs": {"a": "bar"}},
        ]
        export_to_langsmith(client, dataset, "test-dataset", "final_response")

        client.create_dataset.assert_called_once_with(dataset_name="test-dataset")
        client.create_examples.assert_called_once()
        call_kwargs = client.create_examples.call_args[1]
        assert len(call_kwargs["inputs"]) == 2
        assert call_kwargs["dataset_id"] == "ds-123"

    def test_uses_existing_dataset(self):
        client = MagicMock()
        client.create_dataset.side_effect = Exception("already exists")
        ds = SimpleNamespace(id="ds-existing")
        client.read_dataset.return_value = ds

        dataset = [{"inputs": {"q": "hello"}, "outputs": {"a": "world"}}]
        export_to_langsmith(client, dataset, "existing-ds", "final_response")

        client.read_dataset.assert_called_once_with(dataset_name="existing-ds")
        client.create_examples.assert_called_once()

    def test_rag_format(self):
        client = MagicMock()
        ds = SimpleNamespace(id="ds-123")
        client.create_dataset.return_value = ds

        dataset = [{"question": "q1", "retrieved_chunks": "chunk1", "answer": "a1", "cited_chunks": "c1"}]
        export_to_langsmith(client, dataset, "rag-ds", "rag")

        call_kwargs = client.create_examples.call_args[1]
        assert call_kwargs["inputs"][0]["question"] == "q1"
        assert call_kwargs["outputs"][0]["answer"] == "a1"
