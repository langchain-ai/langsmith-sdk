import datetime
import statistics
import time
from typing import Dict
from unittest.mock import Mock
from uuid import uuid4

import pytest

from langsmith_pyo3 import BlockingTracingClient
from tracing_client_bench import create_run_data


def benchmark_run_creation(num_runs: int, json_size: int, samples: int = 1) -> Dict:
    """
    Benchmark run creation with specified parameters.
    Returns timing statistics.
    """
    timings = []

    for _ in range(samples):
        print("creating data")
        runs = [create_run_data(str(uuid4()), json_size) for i in range(num_runs)]

        # We need to add "start_time" manually since
        # it isn't added on the Rust side right now.
        for run in runs:
            run["start_time"] = datetime.datetime.now(datetime.timezone.utc)

        endpoint = "http://localhost:1234/FILL_ME_IN"
        queue_capacity = 1_000_000
        batch_size = 100
        batch_timeout_millis = 1000
        worker_threads = 1

        print("initializing client")
        client = BlockingTracingClient(
            endpoint,
            queue_capacity,
            batch_size,
            batch_timeout_millis,
            worker_threads,
        )

        print("beginning runs")
        start = time.perf_counter()
        for run in runs:
            client.create_run(run)

        # wait for client queues to be empty
        client.drain()
        elapsed = time.perf_counter() - start

        print(f"runs complete: {elapsed:.3f}s")

        timings.append(elapsed)

    return {
        "mean": statistics.mean(timings),
        "median": statistics.median(timings),
        "stdev": statistics.stdev(timings) if len(timings) > 1 else 0,
        "min": min(timings),
        "max": max(timings),
    }


json_size = 3_000
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
