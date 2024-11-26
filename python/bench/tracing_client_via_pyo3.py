from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from uuid import uuid4
import time
import os

from langsmith.client import Client


def create_large_json(length: int) -> Dict:
    """Create a large JSON object for benchmarking purposes."""
    large_array = [
        {
            "index": i,
            "data": f"This is element number {i}",
            "nested": {"id": i, "value": f"Nested value for element {i}"},
        }
        for i in range(length)
    ]

    return {
        "name": "Huge JSON",
        "description": "This is a very large JSON object for benchmarking purposes.",
        "array": large_array,
        "metadata": {
            "created_at": "2024-10-22T19:00:00Z",
            "author": "Python Program",
            "version": 1.0,
        },
    }


def create_run_data(run_id: str, start_time: datetime, json_size: int) -> Dict:
    """Create a single run data object."""

    end_time = start_time + timedelta(milliseconds=1)

    dotted_order = f"{start_time.strftime('%Y%m%dT%H%M%S%fZ')}{run_id}"

    return {
        "name": "Run Name",
        "id": run_id,
        "run_type": "chain",
        "inputs": create_large_json(json_size),
        "outputs": create_large_json(json_size),
        "extra": {"extra_data": "value"},
        "trace_id": run_id,
        "dotted_order": dotted_order,
        "tags": ["tag1", "tag2"],
        "session_name": "Session Name",
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
    }


def amend_run_data_in_place(
    run: Dict[str, Any],
    run_id: str,
    start_time: str,
    end_time: str,
    dotted_order: str,
):
    run["id"] = run_id
    run["trace_id"] = run_id
    run["dotted_order"] = dotted_order
    run["start_time"] = start_time
    run["end_time"] = end_time


def benchmark_run_creation(json_size, num_runs) -> None:
    """Benchmark the creation of runs."""
    os.environ["LANGSMITH_USE_PYO3_CLIENT"] = "1"
    api_key = os.environ["LANGSMITH_API_KEY"]

    if not api_key:
        raise Exception("No API key configured")

    client = Client(
        api_url="https://beta.api.smith.langchain.com",
        api_key=api_key,
    )

    project_name = "__tracing_client_bench_pyo3_" + datetime.now().strftime(
        "%Y%m%dT%H%M%S"
    )

    bench_start_time = datetime.now(timezone.utc)
    run = create_run_data(str(uuid4()), bench_start_time, json_size)

    data = []
    for i in range(num_runs):
        run_id = str(uuid4())
        start_time = bench_start_time + timedelta(milliseconds=i * 2)
        end_time = start_time + timedelta(milliseconds=1)
        dotted_order = f"{start_time.strftime('%Y%m%dT%H%M%S%fZ')}{run_id}"
        data.append((run_id, start_time, end_time, dotted_order))

    start = time.perf_counter()
    for data_tuple in data:
        amend_run_data_in_place(run, *data_tuple)
        client.create_run(**run, project_name=project_name)
    end = time.perf_counter()

    if client._pyo3_client:
        # Wait for the queue to drain.
        client._pyo3_client.drain()
    else:
        client.tracing_queue.join()

    total = time.perf_counter() - start
    just_create_run = end - start
    queue_drain_time = total - just_create_run

    throughput = num_runs / just_create_run
    throughput_including_drain = num_runs / total
    print(f"Made {num_runs} create_run() calls in {just_create_run:.2f}s")
    print(f"Spent {queue_drain_time:.2f} waiting for the queue to drain")
    print(f"Total time: {num_runs} runs in {total:.2f}s")
    print(f"Throughput:               {throughput:.2f} req/s")
    print(f"Throughput (incl. drain): {throughput_including_drain:.2f} req/s")


def main():
    """
    Run benchmarks with different combinations of parameters and report results.
    """

    json_size = 7_500
    num_runs = 1000

    benchmark_run_creation(json_size, num_runs)


if __name__ == "__main__":
    main()
