import os
import statistics
import time
from pathlib import Path
from typing import Dict

from langsmith import Client
from langsmith.schemas import ExampleUpsertWithAttachments

WRITE_BATCH = 10000


def create_large_file(size: int, dir: str) -> str:
    """Create a large file for benchmarking purposes."""
    filename = f"large_file_{size}.txt"
    filepath = os.path.join(dir, filename)

    # delete the file if it exists
    print("Deleting existing file...")
    if os.path.exists(filepath):
        os.remove(filepath)

    print("Creating big file...")
    with open(filepath, "w") as f:
        curr_size = 0
        while curr_size < size:
            f.write("a" * (size - curr_size))
            curr_size += size - curr_size

    print("Done creating big file...")
    return filepath


DATASET_NAME = "upsert_big_file_to_dataset"


def benchmark_big_file_upload(
    size_bytes: int, num_examples: int, samples: int = 1
) -> Dict:
    """
    Benchmark run creation with specified parameters.
    Returns timing statistics.
    """
    multipart_timings = []

    for _ in range(samples):
        client = Client()

        if client.has_dataset(dataset_name=DATASET_NAME):
            client.delete_dataset(dataset_name=DATASET_NAME)

        dataset = client.create_dataset(
            DATASET_NAME,
            description="Test dataset for big file upload",
        )
        large_file = create_large_file(size_bytes, "/tmp")
        examples = [
            ExampleUpsertWithAttachments(
                dataset_id=dataset.id,
                inputs={"a": 1},
                outputs={"b": 2},
                attachments={
                    "bigfile": ("text/plain", Path(large_file)),
                },
            )
            for _ in range(num_examples)
        ]

        multipart_start = time.perf_counter()
        client.upsert_examples_multipart(upserts=examples)
        multipart_elapsed = time.perf_counter() - multipart_start

        multipart_timings.append(multipart_elapsed)

    return {
        "mean": statistics.mean(multipart_timings),
        "median": statistics.median(multipart_timings),
        "stdev": (
            statistics.stdev(multipart_timings) if len(multipart_timings) > 1 else 0
        ),
        "min": min(multipart_timings),
        "max": max(multipart_timings),
    }


size_bytes = 50000000
num_examples = 10


def main(size_bytes: int, num_examples: int = 1):
    """
    Run benchmarks with different combinations of parameters and report results.
    """
    results = benchmark_big_file_upload(size_bytes, num_examples)

    print(f"\nBenchmark Results for size {size_bytes} and {num_examples} examples:")
    print("-" * 30)
    print(f"{'Metric':<15} {'Result':>20}")
    print("-" * 30)

    metrics = ["mean", "median", "stdev", "min", "max"]
    for metric in metrics:
        print(f"{results[metric]:>20.4f}")

    print("-" * 30)
    print(f"{'Throughput':<15} {num_examples / results['mean']:>20.2f} ")
    print("(examples/second)")


if __name__ == "__main__":
    main(size_bytes, num_examples)
