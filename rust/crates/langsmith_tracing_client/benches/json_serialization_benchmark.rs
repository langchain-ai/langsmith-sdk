use rayon::prelude::*;
use serde_json::Value;
use criterion::{black_box, criterion_group, criterion_main, Criterion};

fn create_large_json(len: usize) -> Value {
    let large_array: Vec<Value> = (0..len)
        .map(|i| {
            serde_json::json!({
                "index": i,
                "data": format!("This is element number {}", i),
                "nested": {
                    "id": i,
                    "value": format!("Nested value for element {}", i),
                }
            })
        })
        .collect();

    serde_json::json!({
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

// Sequential processing
fn benchmark_sequential(data: &[Value]) -> Vec<Vec<u8>> {
    data.iter()
        .map(|json| serde_json::to_vec(json).expect("Failed to serialize JSON"))
        .collect()
}

// Parallel processing
fn benchmark_parallel(data: &[Value]) -> Vec<Vec<u8>> {
    data.par_iter()
        .map(|json| serde_json::to_vec(json).expect("Failed to serialize JSON"))
        .collect()
}

// into par iter
fn benchmark_into_par_iter(data: &[Value]) -> Vec<Vec<u8>> {
    let start = std::time::Instant::now();
    let meow = data.into_par_iter()
        .map(|json| serde_json::to_vec(&json).expect("Failed to serialize JSON"))
        .collect();
    println!("into_par_iter: {:?}", start.elapsed());
    meow
}

fn json_benchmark(c: &mut Criterion) {
    let num_json_objects = 2000;
    let json_length = 3000;
    let data: Vec<Value> = (0..num_json_objects)
        .map(|_| create_large_json(json_length))
        .collect();

    c.bench_function("sequential serialization", |b| {
        b.iter(|| benchmark_sequential(&data))
    });

    c.bench_function("parallel serialization", |b| {
        b.iter(|| benchmark_parallel(&data))
    });

    c.bench_function("into par iter serialization", |b| {
        b.iter(|| benchmark_into_par_iter(black_box(&data)))
    });
}

criterion_group! {
    name = benches;
    config = Criterion::default().sample_size(10);
    targets = json_benchmark
}
criterion_main!(benches);