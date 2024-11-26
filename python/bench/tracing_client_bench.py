import statistics
import time
from typing import Dict
from unittest.mock import Mock
from uuid import uuid4
from datetime import datetime, timezone

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


def create_run_data(run_id: str, inputs: Dict, outputs: Dict) -> Dict:
    """Create a single run data object."""
    start_time = datetime.now(timezone.utc)
    end_time = datetime.now(timezone.utc)
    dotted_order = f"{start_time.strftime('%Y%m%dT%H%M%S%fZ')}{run_id}"

    return {
        "name": "Run Name",
        "id": run_id,
        "run_type": "chain",
        "inputs": inputs,
        "outputs": outputs,
        "extra": {"extra_data": "value"},
        "trace_id": run_id,
        "dotted_order": dotted_order,
        "tags": ["tag1", "tag2"],
        "session_name": "Session Name",
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
    }


def benchmark_run_creation(num_runs: int, json_size: int, samples: int = 1) -> Dict:
    """
    Benchmark run creation with specified parameters.
    Returns timing statistics.
    """
    timings = []

    for _ in range(samples):
        print("Creating runs...")
        inputs, outputs = create_large_json(json_size), create_large_json(json_size)
        runs = [create_run_data(str(uuid4()), inputs, outputs) for _ in range(num_runs)]
        print("Runs created.")

        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 202
        mock_response.text = "Accepted"
        mock_response.json.return_value = {"status": "success"}
        mock_session.request.return_value = mock_response
        client = Client(session=mock_session, api_key="xxx")

        start = time.perf_counter()
        for run in runs:
            client.create_run(**run)

        # wait for client.tracing_queue to be empty
        client.tracing_queue.join()

        elapsed = time.perf_counter() - start

        timings.append(elapsed)

    return {
        "mean": statistics.mean(timings),
        "median": statistics.median(timings),
        "stdev": statistics.stdev(timings) if len(timings) > 1 else 0,
        "min": min(timings),
        "max": max(timings),
    }


json_size = 5_000
num_runs = 1000

def main(json_size: int, num_runs: int):
    """
    Run benchmarks with different combinations of parameters and report results.
    """

    results = benchmark_run_creation(num_runs=num_runs, json_size=json_size)

    print(f"\nBenchmark Results for {num_runs} runs with JSON size {json_size}:")
    print(f"Mean time: {results['mean']:.4f} seconds")
    print(f"Median time: {results['median']:.4f} seconds")
    print(f"Std Dev: {results['stdev']:.4f} seconds")
    print(f"Min time: {results['min']:.4f} seconds")
    print(f"Max time: {results['max']:.4f} seconds")
    print(f"Throughput: {num_runs / results['mean']:.2f} runs/second")


if __name__ == "__main__":
    main(json_size, num_runs)
