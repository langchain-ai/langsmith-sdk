use criterion::{black_box, criterion_group, criterion_main, BatchSize, BenchmarkId, Criterion};
use langsmith_tracing_client::client::run::{
    Attachment, RunCommon, RunCreate, RunCreateExtended, RunIO, TimeValue,
};
use langsmith_tracing_client::client::tracing_client::{ClientConfig, TracingClient};
use mockito::Server;
use std::time::Duration;
use tokio::runtime::Runtime;

fn create_mock_client_config(server_url: &str, batch_size: usize) -> ClientConfig {
    ClientConfig {
        endpoint: server_url.to_string(),
        queue_capacity: 1_000_000,
        batch_size,
        batch_timeout: Duration::from_secs(1),
        headers: Default::default(),
    }
}

fn create_run_create(
    attachments: Option<Vec<Attachment>>,
    inputs: Option<serde_json::Value>,
    outputs: Option<serde_json::Value>,
) -> RunCreateExtended {
    RunCreateExtended {
        run_create: RunCreate {
            common: RunCommon {
                id: String::from("test_id"),
                trace_id: String::from("trace_id"),
                dotted_order: String::from("1.1"),
                parent_run_id: None,
                extra: Some(serde_json::json!({"extra_data": "value"})),
                error: None,
                serialized: Some(serde_json::json!({"key": "value"})),
                events: Some(serde_json::json!([{ "event": "event_data" }])),
                tags: Some(serde_json::json!(["tag1", "tag2"])),
                session_id: None,
                session_name: Some("Session Name".to_string()),
            },
            name: String::from("Run Name"),
            start_time: TimeValue::UnsignedInt(1697462400000),
            end_time: Some(TimeValue::UnsignedInt(1697466000000)),
            run_type: String::from("chain"),
            reference_example_id: None,
        },
        attachments,
        io: RunIO { inputs, outputs },
    }
}

fn create_large_json(len: usize) -> serde_json::Value {
    let large_array: Vec<serde_json::Value> = (0..len)
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
fn bench_run_create(c: &mut Criterion) {
    let rt = Runtime::new().unwrap();
    let server = rt.block_on(async {
        let mut server = Server::new_async().await;
        server
            .mock("POST", "/runs/multipart")
            .with_status(202)
            .create_async()
            .await;
        server
    });

    let mut group = c.benchmark_group("run_create");
    for batch_size in vec![50] {
        for json_len in vec![1_000, 5_000] {
            for num_runs in vec![500, 1_000] {
                group.bench_with_input(
                    BenchmarkId::new(
                        "run_create",
                        format!("batch_{}_json_{}_runs_{}", batch_size, json_len, num_runs),
                    ),
                    &(batch_size, json_len, num_runs),
                    |b, &(batch_size, json_len, num_runs)| {
                        b.to_async(&rt).iter_batched(
                            || {
                                let runs: Vec<RunCreateExtended> = (0..num_runs)
                                    .map(|i| {
                                        let mut run = create_run_create(
                                            None,
                                            Some(create_large_json(json_len)),
                                            Some(create_large_json(json_len)),
                                        );
                                        run.run_create.common.id = format!("test_id_{}", i);
                                        run
                                    })
                                    .collect();
                                let client_config =
                                    create_mock_client_config(&server.url(), batch_size);
                                let client = TracingClient::new(client_config).unwrap();
                                (client, runs)
                            },
                            |(client, runs)| async {
                                for run in runs {
                                    client.submit_run_create(black_box(run)).await.unwrap();
                                }
                                // shutdown the client to flush the queue
                                client.shutdown().await.unwrap();
                            },
                            BatchSize::LargeInput,
                        );
                    },
                );
            }
        }
    }
    group.finish();
}

fn bench_run_create_iter_custom(c: &mut Criterion) {
    let rt = Runtime::new().unwrap();
    let server = rt.block_on(async {
        let mut server = Server::new_async().await;
        server
            .mock("POST", "/runs/multipart")
            .with_status(202)
            .create_async()
            .await;
        server
    });

    let mut group = c.benchmark_group("run_create_custom_iter");
    let server_url = server.url();
    for batch_size in vec![50] {
        for json_len in vec![1_000, 5_000] {
            for num_runs in vec![500, 1_000] {
                group.bench_function(
                    BenchmarkId::new(
                        "run_create",
                        format!("batch_{}_json_{}_runs_{}", batch_size, json_len, num_runs),
                    ),
                    |b| {
                        b.to_async(&rt).iter_custom(|iters| {
                            let mut elapsed_time = Duration::default();
                            let server_url = server_url.clone();
                            async move {
                                println!("Iterations: {}", iters);
                                for _ in 0..iters {
                                    let runs: Vec<RunCreateExtended> = (0..num_runs)
                                        .map(|i| {
                                            let mut run = create_run_create(
                                                None,
                                                Some(create_large_json(json_len)),
                                                Some(create_large_json(json_len)),
                                            );
                                            run.run_create.common.id = format!("test_id_{}", i);
                                            run
                                        })
                                        .collect();
                                    let client_config =
                                        create_mock_client_config(&server_url, batch_size);
                                    let client = TracingClient::new(client_config).unwrap();

                                    let start = std::time::Instant::now();
                                    for run in runs {
                                        client.submit_run_create(black_box(run)).await.unwrap();
                                    }
                                    // shutdown the client to flush the queue
                                    client.shutdown().await.unwrap();
                                    println!("Elapsed time inner loop: {:?}", start.elapsed());
                                    elapsed_time += start.elapsed();
                                }
                                println!("Elapsed time: {:?}", elapsed_time);
                                elapsed_time
                            }
                        })
                    },
                );
            }
        }
    }
    group.finish();
}

criterion_group! {
    name = benches;
    config = Criterion::default().sample_size(10);
    targets = bench_run_create_iter_custom, bench_run_create
}

criterion_main!(benches);
