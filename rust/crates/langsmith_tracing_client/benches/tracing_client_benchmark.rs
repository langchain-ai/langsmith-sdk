use criterion::{black_box, criterion_group, criterion_main, BatchSize, Criterion};
use tokio::runtime::Runtime;
use std::time::Duration;
use langsmith_tracing_client::client::tracing_client::{ClientConfig, TracingClient};
use langsmith_tracing_client::client::run::{RunCreateExtended, RunCreate, RunIO, Attachment, TimeValue, RunCommon};
use mockito::{ Server};

fn create_mock_client_config(server_url: &str) -> ClientConfig {
    ClientConfig {
        endpoint: server_url.to_string(),
        queue_capacity: 10000,
        batch_size: 50,
        batch_timeout: Duration::from_secs(1),
        headers: Default::default(),
    }
}

fn create_run_create(attachments: Option<Vec<Attachment>>, inputs: Option<serde_json::Value>, outputs: Option<serde_json::Value>) -> RunCreateExtended {
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
        io: RunIO {
            inputs,
            outputs,
        },
    }
}

fn create_large_json() -> serde_json::Value {
    let large_array: Vec<serde_json::Value> = (0..1_000)
        .map(|i| serde_json::json!({
            "index": i,
            "data": format!("This is element number {}", i),
            "nested": {
                "id": i,
                "value": format!("Nested value for element {}", i),
            }
        }))
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

fn bench_single_request_without_attachments(c: &mut Criterion) {
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

    let client_config = create_mock_client_config(&server.url());
    let client = rt.block_on(async {
        TracingClient::new(client_config).unwrap()
    });

    c.bench_function("simple run create", |b| {
        b.to_async(&rt).iter_batched(
            || create_run_create(None, Some(serde_json::json!({"input": "value"})), Some(serde_json::json!({"output": "value"}))),
            |run_create| async {
                client.submit_run_create(black_box(run_create)).await.unwrap()
            },
            BatchSize::SmallInput,
        );
    });

    c.bench_function("run create with large i/o", |b| {
        b.to_async(&rt).iter_batched(
            || create_run_create(None, Some(create_large_json()), Some(create_large_json())),
            |run_create| async {
                client.submit_run_create(black_box(run_create)).await.unwrap()
            },
            BatchSize::LargeInput,
        );
    });

    rt.block_on(async {
        client.shutdown().await.unwrap();
    });
}

fn bench_shutdown_large_buffer(c: &mut Criterion) {
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

    let num_runs = 1000;

    c.bench_function("client shutdown with large buffer", |b| {
        b.to_async(&rt).iter_batched(
            || {
                let runs: Vec<RunCreateExtended> = (0..num_runs)
                    .map(|i| {
                        let mut run = create_run_create(None, Some(create_large_json()), Some(create_large_json()));
                        run.run_create.common.id = format!("test_id_{}", i);
                        run
                    })
                    .collect();
                let client_config = create_mock_client_config(&server.url());
                let client = TracingClient::new(client_config).unwrap();
                (client, runs)
            },
            |(client, runs)| async {
                for run in runs {
                    client.submit_run_create(run).await.unwrap();
                }
                client.shutdown().await.unwrap();
            },
            BatchSize::LargeInput,
        );
    });
}

//criterion_group!(benches, bench_single_request_without_attachments);
//criterion_group!(benches, bench_shutdown_large_buffer);
criterion_group!{
    name = benches;
    config = Criterion::default().sample_size(10);
    targets = bench_shutdown_large_buffer
}

criterion_main!(benches);