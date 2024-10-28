import time
import statistics
from concurrent.futures import ThreadPoolExecutor
import threading
import orjson


def create_json_with_large_array(length):
    """Create a large JSON object for benchmarking purposes."""
    large_array = [
        {
            "index": i,
            "data": f"This is element number {i}",
            "nested": {
                "id": i,
                "value": f"Nested value for element {i}"
            }
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
            "version": 1.0
        }
    }


def create_json_with_large_strings(length: int) -> dict:
    large_string = "a" * length  # Create a large string of repeated 'a' characters

    return {
        "name": "Huge JSON",
        "description": "This is a very large JSON object for benchmarking purposes.",
        "key1": large_string,
        "key2": large_string,
        "key3": large_string,
        "metadata": {
            "created_at": "2024-10-22T19:00:00Z",
            "author": "Python Program",
            "version": 1.0
        }
    }



def serialize_sequential(data):
    """Serialize data sequentially."""
    return [orjson.dumps(json_obj) for json_obj in data]


def serialize_parallel(data):
    """Serialize data in parallel using ThreadPoolExecutor."""
    with ThreadPoolExecutor() as executor:
        return list(executor.map(orjson.dumps, data))


def benchmark_serialization(data, func, samples=10):
    """Benchmark a serialization function with multiple samples."""
    timings = []
    for _ in range(samples):
        start = time.perf_counter()
        func(data)
        elapsed = time.perf_counter() - start
        timings.append(elapsed)

    return {
        "mean": statistics.mean(timings),
        "median": statistics.median(timings),
        "stdev": statistics.stdev(timings) if len(timings) > 1 else 0,
        "min": min(timings),
        "max": max(timings),
    }


def main():
    num_json_objects = 300
    json_length = 5000
    data = [create_json_with_large_array(json_length) for _ in range(num_json_objects)]
    # data = [create_json_with_large_strings(json_length) for _ in range(num_json_objects)]

    # Sequential Benchmark
    results_seq = benchmark_serialization(data, serialize_sequential)
    print("\nSequential Serialization Results:")
    print(f"Mean time: {results_seq['mean']:.4f} seconds")
    print(f"Median time: {results_seq['median']:.4f} seconds")
    print(f"Std Dev: {results_seq['stdev']:.4f} seconds")
    print(f"Min time: {results_seq['min']:.4f} seconds")
    print(f"Max time: {results_seq['max']:.4f} seconds")

    # Parallel Benchmark with ThreadPoolExecutor
    results_par = benchmark_serialization(data, serialize_parallel)
    print("\nParallel Serialization (ThreadPoolExecutor) Results:")
    print(f"Mean time: {results_par['mean']:.4f} seconds")
    print(f"Median time: {results_par['median']:.4f} seconds")
    print(f"Std Dev: {results_par['stdev']:.4f} seconds")
    print(f"Min time: {results_par['min']:.4f} seconds")
    print(f"Max time: {results_par['max']:.4f} seconds")


if __name__ == "__main__":
    main()
