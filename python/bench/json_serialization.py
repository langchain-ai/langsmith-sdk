import statistics
import time
import zlib
from concurrent.futures import ThreadPoolExecutor

import orjson


def create_json_with_large_array(length):
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
            "version": 1.0,
        },
    }


def serialize_sequential(data):
    """Serialize data sequentially."""
    return [orjson.dumps(json_obj) for json_obj in data]


def serialize_parallel(data):
    """Serialize data in parallel using ThreadPoolExecutor."""
    with ThreadPoolExecutor() as executor:
        return list(executor.map(orjson.dumps, data))


def serialize_sequential_gz(data):
    """Serialize data sequentially and compress using zlib.

    With adjustable compression level."""
    compressed_data = []
    for json_obj in data:
        serialized = orjson.dumps(json_obj)
        compressed = zlib.compress(serialized, level=1)
        compressed_data.append(compressed)
    return compressed_data


def serialize_parallel_gz(data):
    """Serialize data in parallel with zlib.

    Using ThreadPoolExecutor and zlib with adjustable compression level."""

    def compress_item(json_obj):
        serialized = orjson.dumps(json_obj)
        return zlib.compress(serialized, level=1)

    with ThreadPoolExecutor() as executor:
        compressed_data = list(executor.map(compress_item, data))
    return compressed_data


def gzip_parallel(serialized_data):
    """Compress serialized data in parallel using ThreadPoolExecutor and zlib."""
    with ThreadPoolExecutor() as executor:
        return list(executor.map(zlib.compress, serialized_data))


def gzip_sequential(serialized_data):
    """Compress serialized data sequentially using zlib."""
    return [zlib.compress(serialized) for serialized in serialized_data]


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
    num_json_objects = 2000
    json_length = 5000

    data = [create_json_with_large_array(json_length) for _ in range(num_json_objects)]
    serialized_data = serialize_sequential(data)

    for func in [
        serialize_sequential,
        serialize_parallel,
        serialize_sequential_gz,
        serialize_parallel_gz,
        gzip_sequential,
        gzip_parallel,
    ]:
        # data = [
        #     create_json_with_large_strings(json_length)
        #     for _ in range(num_json_objects)
        # ]

        print(
            f"\nBenchmarking {func.__name__} with {num_json_objects} JSON objects "
            f"of length {json_length}..."
        )
        results_seq = (
            benchmark_serialization(data, func)
            if not func.__name__.startswith("gzip")
            else benchmark_serialization(serialized_data, func)
        )
        print(f"Mean time: {results_seq['mean']:.4f} seconds")
        print(f"Median time: {results_seq['median']:.4f} seconds")
        print(f"Std Dev: {results_seq['stdev']:.4f} seconds")
        print(f"Min time: {results_seq['min']:.4f} seconds")
        print(f"Max time: {results_seq['max']:.4f} seconds")


if __name__ == "__main__":
    main()
