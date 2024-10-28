use rayon::prelude::*;
// use serde_json::Value;
use sonic_rs::Value;
use criterion::{black_box, criterion_group, criterion_main, Criterion};

fn create_json_with_large_array(len: usize) -> Value {
    let large_array: Vec<Value> = (0..len)
        .map(|i| {
            sonic_rs::json!({
                "index": i,
                "data": format!("This is element number {}", i),
                "nested": {
                    "id": i,
                    "value": format!("Nested value for element {}", i),
                }
            })
        })
        .collect();

    sonic_rs::json!({
        "name": "Huge JSON",
        "description": "This is a very large JSON object for benchmarking purposes.",
        "array": large_array,
        "metadata": {
            "created_at": "2024-10-22T19:00:00Z",
            "author": "Rust Program",
            "version": 1.0
        }
    })
}

fn create_json_with_large_strings(len: usize) -> Value {
    let large_string = "a".repeat(len);
    sonic_rs::json!({
        "name": "Huge JSON",
        "description": "This is a very large JSON object for benchmarking purposes.",
        "key1": large_string.clone(),
        "key2": large_string.clone(),
        "key3": large_string.clone(),
        "metadata": {
            "created_at": "2024-10-22T19:00:00Z",
            "author": "Rust Program",
            "version": 1.0
        }
    })
}

// Sequential processing
fn benchmark_sequential(data: &[Value]) -> Vec<Vec<u8>> {
    data.iter()
        .map(|json| sonic_rs::to_vec(json).expect("Failed to serialize JSON"))
        .collect()
}

// Parallel processing
fn benchmark_parallel(data: &[Value]) -> Vec<Vec<u8>> {
    data.par_iter()
        .map(|json| sonic_rs::to_vec(json).expect("Failed to serialize JSON"))
        .collect()
}

// into par iter
fn benchmark_into_par_iter(data: &[Value]) -> Vec<Vec<u8>> {
    data.into_par_iter()
        .map(|json| sonic_rs::to_vec(&json).expect("Failed to serialize JSON"))
        .collect()
}

fn json_benchmark_large_array(c: &mut Criterion) {
    let num_json_objects = 300;
    let json_length = 3000;
    let data: Vec<Value> = (0..num_json_objects)
        .map(|_| create_json_with_large_array(json_length))
        .collect();

    let mut group = c.benchmark_group("json_benchmark_large_array");
    group.bench_function("sequential serialization", |b|
        b.iter_with_large_drop(|| benchmark_sequential(&data))
    );
    group.bench_function("parallel serialization", |b|
        b.iter_with_large_drop(|| benchmark_parallel(&data))
    );
    group.bench_function("into par iter serialization", |b|
        b.iter_with_large_drop(|| benchmark_into_par_iter(&data))
    );
}

fn json_benchmark_large_strings(c: &mut Criterion) {
    let num_json_objects = 100;
    let json_length = 100_000;
    let data: Vec<Value> = (0..num_json_objects)
        .map(|_| create_json_with_large_strings(json_length))
        .collect();

    let mut group = c.benchmark_group("json_benchmark_large_strings");
    group.bench_function("sequential serialization", |b|
        b.iter_with_large_drop(|| benchmark_sequential(&data))
    );
    group.bench_function("parallel serialization", |b|
        b.iter_with_large_drop(|| benchmark_parallel(&data))
    );
    group.bench_function("into par iter serialization", |b|
        b.iter_with_large_drop(|| benchmark_into_par_iter(&data))
    );
}

criterion_group! {
    name = benches;
    config = Criterion::default().sample_size(10);
    targets = json_benchmark_large_array, json_benchmark_large_strings
}
criterion_main!(benches);

// fn main() {
// }
