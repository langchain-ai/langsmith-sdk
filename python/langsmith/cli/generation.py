"""Dataset generation logic - ported from generate_datasets.py.

Generates eval datasets from exported JSONL trace files.
"""

from __future__ import annotations

import csv
import json
import os
import random
from datetime import datetime
from types import SimpleNamespace


# Common field names for extraction
COMMON_INPUT_FIELDS = ["query", "input", "question", "message", "prompt", "text"]
COMMON_OUTPUT_FIELDS = ["answer", "output", "response", "result"]


def dict_to_obj(d: dict) -> SimpleNamespace:
    """Convert a dict to a SimpleNamespace object for attribute access."""
    obj = SimpleNamespace(**d)
    if hasattr(obj, "start_time") and isinstance(obj.start_time, str):
        try:
            obj.start_time = datetime.fromisoformat(obj.start_time.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass
    if hasattr(obj, "end_time") and isinstance(obj.end_time, str):
        try:
            obj.end_time = datetime.fromisoformat(obj.end_time.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass
    return obj


def load_traces_from_dir(input_dir: str, sort: str = "newest") -> list[tuple]:
    """Load traces from a directory of JSONL files.

    Returns list of (trace_id, root_run, all_runs) tuples.
    """
    traces = []

    for filename in os.listdir(input_dir):
        if not filename.endswith(".jsonl"):
            continue
        filepath = os.path.join(input_dir, filename)
        file_traces = _load_jsonl_file(filepath)
        traces.extend(file_traces)

    return _sort_traces(traces, sort)


def load_traces_from_file(input_file: str, sort: str = "newest") -> list[tuple]:
    """Load traces from a single JSONL file.

    Returns list of (trace_id, root_run, all_runs) tuples.
    """
    if input_file.endswith(".jsonl"):
        traces = _load_jsonl_file(input_file)
    elif input_file.endswith(".json"):
        traces = _load_json_file(input_file)
    else:
        return []

    return _sort_traces(traces, sort)


def _load_jsonl_file(filepath: str) -> list[tuple]:
    """Load traces from a JSONL file. Groups runs by trace_id."""
    trace_runs: dict[str, list[dict]] = {}

    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                run_data = json.loads(line)
                tid = run_data.get("trace_id", run_data.get("run_id", "unknown"))
                trace_runs.setdefault(str(tid), []).append(run_data)
            except json.JSONDecodeError:
                continue

    traces = []
    for tid, runs_data in trace_runs.items():
        runs = [dict_to_obj(r) for r in runs_data]
        root = None
        for r in runs:
            pid = getattr(r, "parent_run_id", None)
            if not pid:
                root = r
                break
        if root is None and runs:
            root = runs[0]
        if root is not None:
            traces.append((tid, root, runs))

    return traces


def _load_json_file(filepath: str) -> list[tuple]:
    """Load traces from a JSON file (legacy format)."""
    with open(filepath) as f:
        data = json.load(f)

    if isinstance(data, dict) and "trace_id" in data:
        data = [data]

    traces = []
    for item in data:
        if not isinstance(item, dict):
            continue
        tid = str(item.get("trace_id", "unknown"))
        runs_data = item.get("runs", [item])
        runs = [dict_to_obj(r) for r in runs_data]
        root = None
        for r in runs:
            pid = getattr(r, "parent_run_id", None)
            if not pid:
                root = r
                break
        if root is None and runs:
            root = runs[0]
        if root is not None:
            traces.append((tid, root, runs))

    return traces


def _sort_traces(traces: list[tuple], sort: str) -> list[tuple]:
    """Sort traces by the specified order."""
    if sort == "newest":
        traces.sort(key=lambda t: getattr(t[1], "start_time", "") or "", reverse=True)
    elif sort == "oldest":
        traces.sort(key=lambda t: getattr(t[1], "start_time", "") or "")
    elif sort == "alphabetical":
        traces.sort(key=lambda t: t[0])
    elif sort == "reverse-alphabetical":
        traces.sort(key=lambda t: t[0], reverse=True)
    return traces


# --- Extraction helpers ---

def extract_from_messages(messages: list, role: str | None = None) -> str | None:
    """Extract content from a messages array by role."""
    if not messages:
        return None

    if role in ("human", "user"):
        for msg in messages:
            if isinstance(msg, dict):
                msg_type = msg.get("type", msg.get("role", ""))
                if msg_type in ("human", "user"):
                    content = msg.get("content", "")
                    if isinstance(content, list):
                        parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
                        return " ".join(parts) if parts else str(content)
                    return str(content) if content else None
            elif isinstance(msg, str):
                return msg
    elif role in ("ai", "assistant"):
        for msg in reversed(messages):
            if isinstance(msg, dict):
                msg_type = msg.get("type", msg.get("role", ""))
                if msg_type in ("ai", "assistant"):
                    content = msg.get("content", "")
                    if content and str(content) != "None":
                        if isinstance(content, list):
                            parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
                            return " ".join(parts) if parts else str(content)
                        return str(content)
    else:
        if messages:
            last = messages[-1]
            if isinstance(last, dict):
                return str(last.get("content", ""))
            return str(last)

    return None


def extract_value(data: dict | None, fields: list[str] | None = None,
                  common_fields: list[str] | None = None,
                  message_role: str | None = None,
                  fallback_to_raw: bool = True) -> str | dict | None:
    """Extract a value from a dict using a priority chain."""
    if not data or not isinstance(data, dict):
        return None

    # 1. User-specified fields
    if fields:
        for field in fields:
            if field in data:
                val = data[field]
                if val is not None:
                    return val

    # 2. Messages extraction
    if "messages" in data and isinstance(data["messages"], list):
        result = extract_from_messages(data["messages"], message_role)
        if result:
            return result

    # 3. Common fields
    if common_fields:
        for field in common_fields:
            if field in data:
                val = data[field]
                if val is not None:
                    return val

    # 4. Fallback
    if fallback_to_raw:
        # Single string value dict
        values = [v for v in data.values() if v is not None]
        if len(values) == 1 and isinstance(values[0], str):
            return values[0]
        # First string value
        for v in values:
            if isinstance(v, str):
                return v
        # Return entire dict
        return data

    return None


def extract_trace_inputs(root, input_fields: list[str] | None = None,
                         as_dict: bool = False) -> str | dict | None:
    """Extract the primary input from a trace's root run."""
    inputs = getattr(root, "inputs", None)
    if not inputs:
        return None

    if input_fields:
        return extract_value(inputs, input_fields, COMMON_INPUT_FIELDS, "human")

    if as_dict:
        return inputs

    return extract_value(inputs, None, COMMON_INPUT_FIELDS, "human")


def extract_trace_output(root, output_fields: list[str] | None = None,
                         messages_only: bool = False) -> str | None:
    """Extract the primary output from a trace's root run."""
    outputs = getattr(root, "outputs", None)
    if not outputs:
        return None

    result = extract_value(
        outputs, output_fields,
        None if messages_only else COMMON_OUTPUT_FIELDS,
        "ai",
        fallback_to_raw=not messages_only,
    )

    if isinstance(result, dict):
        return json.dumps(result, default=str)
    return result


def extract_final_output(runs: list, output_fields: list[str] | None = None) -> str | None:
    """Search all runs newest-first for any run with matching outputs."""
    sorted_runs = sorted(runs, key=lambda r: getattr(r, "start_time", "") or "", reverse=True)
    for run in sorted_runs:
        outputs = getattr(run, "outputs", None)
        if outputs:
            result = extract_value(outputs, output_fields, COMMON_OUTPUT_FIELDS, "ai")
            if result:
                if isinstance(result, dict):
                    return json.dumps(result, default=str)
                return str(result)
    return None


def extract_tool_sequence(runs: list, depth: int | None = None) -> list[str]:
    """Extract the sequence of tool names from runs."""
    tool_runs = [r for r in runs if getattr(r, "run_type", "") == "tool"]
    tool_runs.sort(key=lambda r: getattr(r, "start_time", "") or "")

    if depth is not None:
        # Filter by hierarchy depth
        run_map = {str(getattr(r, "run_id", getattr(r, "id", ""))): r for r in runs}
        filtered = []
        for r in tool_runs:
            d = 0
            current = r
            while True:
                pid = getattr(current, "parent_run_id", None)
                if not pid or str(pid) not in run_map:
                    break
                current = run_map[str(pid)]
                d += 1
            if d <= depth:
                filtered.append(r)
        tool_runs = filtered

    return [getattr(r, "name", "unknown").lower() for r in tool_runs]


def get_node_io(runs: list, run_name: str | None = None) -> list[dict]:
    """Get input/output for runs matching a name."""
    matching = []
    for r in runs:
        if run_name and getattr(r, "name", "") != run_name:
            continue
        outputs = getattr(r, "outputs", None)
        if not outputs:
            continue
        matching.append(r)

    matching.sort(key=lambda r: getattr(r, "start_time", "") or "")

    results = []
    for r in matching:
        results.append({
            "node_name": getattr(r, "name", "unknown"),
            "inputs": getattr(r, "inputs", None),
            "outputs": getattr(r, "outputs", None),
            "run_id": str(getattr(r, "run_id", getattr(r, "id", ""))),
        })
    return results


def extract_documents(outputs: dict | list | None) -> list[str]:
    """Extract document text from LangChain retriever outputs."""
    if not outputs:
        return []

    docs = outputs
    if isinstance(outputs, dict):
        docs = outputs.get("documents", outputs.get("output", outputs))
    if not isinstance(docs, list):
        docs = [docs]

    chunks = []
    for doc in docs:
        if isinstance(doc, dict):
            text = doc.get("page_content", doc.get("content", doc.get("text")))
            if text:
                chunks.append(str(text))
            else:
                chunks.append(json.dumps(doc, default=str))
        elif isinstance(doc, str):
            chunks.append(doc)
        else:
            chunks.append(str(doc))
    return chunks


def find_retrieval_data(runs: list) -> dict:
    """Find retrieval data from retriever runs."""
    retriever_runs = [r for r in runs if getattr(r, "run_type", "") == "retriever"]
    retriever_runs.sort(key=lambda r: getattr(r, "start_time", "") or "")

    query = None
    all_chunks: list[str] = []

    if retriever_runs:
        # Query from first retriever's inputs
        first_inputs = getattr(retriever_runs[0], "inputs", {})
        if isinstance(first_inputs, dict):
            query = extract_value(first_inputs, None, COMMON_INPUT_FIELDS, "human")

        # Chunks from all retrievers
        for r in retriever_runs:
            outputs = getattr(r, "outputs", None)
            if outputs:
                all_chunks.extend(extract_documents(outputs))

    # Answer from final output
    answer = extract_final_output(runs)

    return {
        "query": str(query) if query else None,
        "retrieved_chunks": all_chunks,
        "answer": answer,
    }


# --- Generation ---

def generate_dataset(
    traces: list[tuple],
    dataset_type: str,
    run_name: str | None = None,
    depth: int | None = None,
    input_fields: list[str] | None = None,
    output_fields: list[str] | None = None,
    messages_only: bool = False,
    sample_per_trace: int | None = None,
) -> list[dict]:
    """Generate a dataset from traces."""
    dataset = []

    for trace_id, root, runs in traces:
        if dataset_type == "rag":
            retrieval = find_retrieval_data(runs)
            query = retrieval["query"]
            answer = retrieval["answer"]
            if not query or not answer:
                continue
            chunks_text = "\n\n".join(retrieval["retrieved_chunks"])
            cited = json.dumps(retrieval["retrieved_chunks"][:3], default=str)
            dataset.append({
                "trace_id": trace_id,
                "question": query,
                "retrieved_chunks": chunks_text,
                "answer": answer,
                "cited_chunks": cited,
            })

        elif dataset_type == "final_response":
            inputs = extract_trace_inputs(root, input_fields, as_dict=not input_fields)
            output = extract_trace_output(root, output_fields, messages_only)
            if not output:
                continue
            if isinstance(inputs, str):
                inputs = {"expected_input": inputs}
            dataset.append({
                "trace_id": trace_id,
                "inputs": inputs,
                "outputs": {"expected_response": output},
            })

        elif dataset_type == "single_step":
            node_results = get_node_io(runs, run_name)

            if sample_per_trace and len(node_results) > sample_per_trace:
                node_results = random.sample(node_results, sample_per_trace)

            for i, node in enumerate(node_results):
                dataset.append({
                    "trace_id": trace_id,
                    "run_id": node["run_id"],
                    "node_name": node["node_name"],
                    "occurrence": i + 1,
                    "inputs": node["inputs"],
                    "outputs": {"expected_output": node["outputs"]},
                })

        elif dataset_type == "trajectory":
            inputs = extract_trace_inputs(root, input_fields, as_dict=not input_fields)
            tools = extract_tool_sequence(runs, depth)
            if isinstance(inputs, str):
                inputs = {"expected_input": inputs}
            dataset.append({
                "trace_id": trace_id,
                "inputs": inputs,
                "outputs": {"expected_trajectory": tools},
            })

    return dataset


# --- Export ---

def export_to_file(dataset: list[dict], output_path: str) -> None:
    """Export a generated dataset to a file."""
    ext = os.path.splitext(output_path)[1].lower()

    if ext == ".csv":
        if not dataset:
            return
        all_keys = sorted(set().union(*(d.keys() for d in dataset)))
        with open(output_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=all_keys)
            writer.writeheader()
            for row in dataset:
                writer.writerow({k: json.dumps(v, default=str) if isinstance(v, (dict, list)) else v
                                 for k, v in row.items()})
    else:
        with open(output_path, "w") as f:
            json.dump(dataset, f, indent=2, default=str)


def export_to_langsmith(client, dataset: list[dict], dataset_name: str,
                        dataset_type: str) -> None:
    """Upload a generated dataset to LangSmith."""
    try:
        ds = client.create_dataset(dataset_name=dataset_name)
    except Exception:
        # Dataset already exists (duplicate name) — read the existing one
        ds = client.read_dataset(dataset_name=dataset_name)

    inputs_list = []
    outputs_list = []

    for ex in dataset:
        if dataset_type == "rag":
            inputs_list.append({
                "question": ex.get("question"),
                "retrieved_chunks": ex.get("retrieved_chunks"),
            })
            outputs_list.append({
                "answer": ex.get("answer"),
                "cited_chunks": ex.get("cited_chunks"),
            })
        else:
            inputs_list.append(ex.get("inputs", {}))
            outputs_list.append(ex.get("outputs", {}))

    client.create_examples(
        inputs=inputs_list,
        outputs=outputs_list,
        dataset_id=ds.id,
    )
