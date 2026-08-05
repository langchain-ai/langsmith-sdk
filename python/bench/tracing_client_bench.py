import statistics
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
from unittest.mock import Mock
from uuid import uuid4

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


def create_run_data(
    run_id: str, json_size: int, start_time: Optional[datetime] = None
) -> Dict:
    """Create a single run data object."""
    if start_time is None:
        start_time = datetime.now(timezone.utc)
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


def _stats(timings: list) -> Dict:
    return {
        "mean": statistics.mean(timings),
        "median": statistics.median(timings),
        "stdev": statistics.stdev(timings) if len(timings) > 1 else 0,
        "min": min(timings),
        "max": max(timings),
    }


def benchmark_run_creation(
    num_runs: int,
    json_size: int,
    samples: int = 1,
    *,
    patch: bool = False,
    exclude_inputs: bool = False,
) -> Dict:
    """
    Benchmark run creation (and optionally patching) with specified parameters.
    Returns timing statistics.

    Args:
        patch: Also benchmark a patch (update_run) phase for each created run.
        exclude_inputs: When patching, omit inputs from the patch (they were
            already sent on the create). Mirrors RunTree.patch(exclude_inputs=True).
    """
    timings: list = []
    patch_timings: list = []

    project_name = "__tracing_client_bench_python" + datetime.now().strftime(
        "%Y%m%dT%H%M%S"
    )

    for _ in range(samples):
        runs = [create_run_data(str(uuid4()), json_size) for i in range(num_runs)]

        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 202
        mock_response.text = "Accepted"
        mock_response.json.return_value = {"status": "success"}
        mock_session.request.return_value = mock_response
        client = Client(session=mock_session, api_key="xxx")

        start = time.perf_counter()
        for run in runs:
            client.create_run(**run, project_name=project_name)

        # wait for client.tracing_queue to be empty
        client.tracing_queue.join()

        timings.append(time.perf_counter() - start)

        if patch:
            patch_start = time.perf_counter()
            for run in runs:
                client.update_run(
                    run_id=run["id"],
                    trace_id=run["trace_id"],
                    dotted_order=run["dotted_order"],
                    outputs=run["outputs"],
                    end_time=datetime.now(timezone.utc),
                    inputs=None if exclude_inputs else run["inputs"],
                )
            client.tracing_queue.join()
            patch_timings.append(time.perf_counter() - patch_start)

    return {
        "create": _stats(timings),
        "patch": _stats(patch_timings) if patch else None,
    }


json_size = 3_000
num_runs = 1000


def _print_stats(label: str, num: int, stats: Dict, unit: str) -> None:
    print(f"\n{label}:")
    print(f"Mean time: {stats['mean']:.4f} seconds")
    print(f"Median time: {stats['median']:.4f} seconds")
    print(f"Std Dev: {stats['stdev']:.4f} seconds")
    print(f"Min time: {stats['min']:.4f} seconds")
    print(f"Max time: {stats['max']:.4f} seconds")
    print(f"Throughput: {num / stats['mean']:.2f} {unit}")


def main(
    json_size: int,
    num_runs: int,
    *,
    patch: bool = False,
    exclude_inputs: bool = False,
):
    """
    Run benchmarks with different combinations of parameters and report results.
    """

    results = benchmark_run_creation(
        num_runs=num_runs,
        json_size=json_size,
        patch=patch,
        exclude_inputs=exclude_inputs,
    )

    _print_stats(
        f"Create results for {num_runs} runs with JSON size {json_size}",
        num_runs,
        results["create"],
        "runs/second",
    )
    if results["patch"] is not None:
        _print_stats(
            f"Patch results (exclude_inputs={exclude_inputs})",
            num_runs,
            results["patch"],
            "patches/second",
        )


if __name__ == "__main__":
    # Create-only baseline (default behavior), then the patch phase both ways
    # to show the exclude_inputs optimization side by side.
    main(json_size, num_runs)
    main(json_size, num_runs, patch=True, exclude_inputs=False)
    main(json_size, num_runs, patch=True, exclude_inputs=True)
