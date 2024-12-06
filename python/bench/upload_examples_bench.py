import statistics
import time
from typing import Dict
from uuid import uuid4

from langsmith import Client
from langsmith.schemas import DataType, ExampleUpsertWithAttachments


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
        "name": "Huge JSON" + str(uuid4()),
        "description": "This is a very large JSON object for benchmarking purposes.",
        "array": large_array,
        "metadata": {
            "created_at": "2024-10-22T19:00:00Z",
            "author": "Python Program",
            "version": 1.0,
        },
    }


def create_example_data(dataset_id: str, json_size: int) -> Dict:
    """Create a single example data object."""
    return ExampleUpsertWithAttachments(
        **{
            "dataset_id": dataset_id,
            "inputs": create_large_json(json_size),
            "outputs": create_large_json(json_size),
        }
    )


DATASET_NAME = "upsert_llm_evaluator_benchmark_dataset"


def benchmark_example_uploading(
    num_examples: int, json_size: int, samples: int = 1
) -> Dict:
    """
    Benchmark run creation with specified parameters.
    Returns timing statistics.
    """
    multipart_timings, old_timings = [], []

    for _ in range(samples):
        client = Client()

        if client.has_dataset(dataset_name=DATASET_NAME):
            client.delete_dataset(dataset_name=DATASET_NAME)

        dataset = client.create_dataset(
            DATASET_NAME,
            description="Test dataset for multipart example upload",
            data_type=DataType.kv,
        )
        examples = [
            create_example_data(dataset.id, json_size) for i in range(num_examples)
        ]

        # Old method
        old_start = time.perf_counter()
        # inputs = [e.inputs for e in examples]
        # outputs = [e.outputs for e in examples]
        # # the create_examples endpoint fails above 20mb
        # # so this will crash with json_size > ~100
        # client.create_examples(inputs=inputs, outputs=outputs, dataset_id=dataset.id)
        old_elapsed = time.perf_counter() - old_start

        # New method
        multipart_start = time.perf_counter()
        client.upsert_examples_multipart(upserts=examples)
        multipart_elapsed = time.perf_counter() - multipart_start

        multipart_timings.append(multipart_elapsed)
        old_timings.append(old_elapsed)

    return {
        "old": {
            "mean": statistics.mean(old_timings),
            "median": statistics.median(old_timings),
            "stdev": statistics.stdev(old_timings) if len(old_timings) > 1 else 0,
            "min": min(old_timings),
            "max": max(old_timings),
        },
        "new": {
            "mean": statistics.mean(multipart_timings),
            "median": statistics.median(multipart_timings),
            "stdev": (
                statistics.stdev(multipart_timings) if len(multipart_timings) > 1 else 0
            ),
            "min": min(multipart_timings),
            "max": max(multipart_timings),
        },
    }


json_size = 1000
num_examples = 1000


def main(json_size: int, num_examples: int):
    """
    Run benchmarks with different combinations of parameters and report results.
    """
    results = benchmark_example_uploading(
        num_examples=num_examples, json_size=json_size
    )

    print(
        f"\nBenchmark Results for {num_examples} examples with JSON size {json_size}:"
    )
    print("-" * 60)
    print(f"{'Metric':<15} {'Old Method':>20} {'New Method':>20}")
    print("-" * 60)

    metrics = ["mean", "median", "stdev", "min", "max"]
    for metric in metrics:
        print(
            f"{metric:<15} {results['old'][metric]:>20.4f} "
            f"{results['new'][metric]:>20.4f}"
        )

    print("-" * 60)
    print(
        f"{'Throughput':<15} {num_examples / results['old']['mean']:>20.2f} "
        f"{num_examples / results['new']['mean']:>20.2f}"
    )
    print("(examples/second)")


if __name__ == "__main__":
    main(json_size, num_examples)
