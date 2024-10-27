import orjson
import timeit
from concurrent.futures import ThreadPoolExecutor, as_completed

def create_large_json(length):
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


def benchmark_sequential(data):
    return [orjson.dumps(json_obj) for json_obj in data]


def benchmark_parallel(data):
    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(orjson.dumps, json_obj) for json_obj in data]
        return [future.result() for future in as_completed(futures)]


def benchmark_with_map(data):
    with ThreadPoolExecutor() as executor:
        return list(executor.map(orjson.dumps, data))

def benchmark_no_return(data):
    for json_obj in data:
        orjson.dumps(json_obj)


num_json_objects = 100
json_length = 3000
data = [create_large_json(json_length) for _ in range(num_json_objects)]

print("Sequential serialization:")
print(timeit.timeit(lambda: benchmark_sequential(data), number=10))

print("Parallel serialization with ThreadPoolExecutor:")
print(timeit.timeit(lambda: benchmark_parallel(data), number=10))

print("Parallel serialization with map:")
print(timeit.timeit(lambda: benchmark_with_map(data), number=15))

print("Parallel serialization without return:")
print(timeit.timeit(lambda: benchmark_no_return(data), number=15))
