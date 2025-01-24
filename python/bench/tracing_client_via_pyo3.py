import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from uuid import uuid4

from tracing_client_bench import create_run_data

from langsmith.client import Client


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
    if os.environ.get("LANGSMITH_USE_PYO3_CLIENT") is None:
        print(
            "LANGSMITH_USE_PYO3_CLIENT is not set, so this run will not use PyO3.\n"
            "  It will use only the pure Python code paths."
        )

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

    runs = [
        create_run_data(
            str(uuid4()), json_size, bench_start_time + timedelta(milliseconds=i * 2)
        )
        for i in range(num_runs)
    ]

    start = time.perf_counter()
    for run in runs:
        client.create_run(**run, project_name=project_name)
    end = time.perf_counter()

    # data = []
    # run = create_run_data(str(uuid4()), json_size, bench_start_time)
    # for i in range(num_runs):
    #     run_id = str(uuid4())
    #     start_time = bench_start_time + timedelta(milliseconds=i * 2)
    #     end_time = start_time + timedelta(milliseconds=1)
    #     dotted_order = f"{start_time.strftime('%Y%m%dT%H%M%S%fZ')}{run_id}"
    #     data.append((run_id, start_time, end_time, dotted_order))
    #
    # start = time.perf_counter()
    # for data_tuple in data:
    #     amend_run_data_in_place(run, *data_tuple)
    #     client.create_run(**run, project_name=project_name)
    # end = time.perf_counter()

    if client._pyo3_client:
        # Wait for the queue to drain.
        del client
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

    json_size = 3_000
    num_runs = 1000

    benchmark_run_creation(json_size, num_runs)


if __name__ == "__main__":
    main()
