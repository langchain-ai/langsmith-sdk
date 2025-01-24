use criterion::{criterion_group, criterion_main, BenchmarkId, Criterion};
use langsmith_tracing_client::client::{
    Attachment, ClientConfig as BlockingClientConfig, RunCommon, RunCreate, RunCreateExtended,
    RunIO, TimeValue, TracingClient as BlockingTracingClient,
};
use mockito::Server;
use serde_json::{json, Value};
use std::time::Duration;

fn create_mock_client_config_sync(server_url: &str, batch_size: usize) -> BlockingClientConfig {
    BlockingClientConfig {
        endpoint: server_url.to_string(),
        api_key: "anything".into(),
        queue_capacity: 1_000_000,
        send_at_batch_size: batch_size,
        send_at_batch_time: Duration::from_secs(1),
        headers: Default::default(),
        compression_level: 1,
    }
}

fn create_run_create(
    attachments: Option<Vec<Attachment>>,
    inputs: Option<Value>,
    outputs: Option<Value>,
) -> RunCreateExtended {
    RunCreateExtended {
        run_create: RunCreate {
            common: RunCommon {
                id: String::from("test_id"),
                trace_id: String::from("trace_id"),
                dotted_order: String::from("1.1"),
                parent_run_id: None,
                extra: Some(json!({"extra_data": "value"})),
                error: None,
                serialized: Some(json!({"key": "value"})),
                events: Some(json!([{ "event": "event_data" }])),
                tags: Some(json!(["tag1", "tag2"])),
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
            inputs: inputs.map(|i| serde_json::to_vec(&i).unwrap()),
            outputs: outputs.map(|i| serde_json::to_vec(&i).unwrap()),
        },
    }
}

fn create_large_json(len: usize) -> Value {
    let large_array: Vec<Value> = (0..len)
        .map(|i| {
            json!({
                "index": i,
                "data": format!("This is element number {}", i),
                "nested": {
                    "id": i,
                    "value": format!("Nested value for element {}", i),
                }
            })
        })
        .collect();

    json!({
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

#[expect(unused_variables, clippy::single_element_loop)]
fn bench_run_create_sync_iter_custom(c: &mut Criterion) {
    let server = {
        let mut server = Server::new();
        server.mock("POST", "/runs/multipart").with_status(202).create();
        server
    };

    let mut group = c.benchmark_group("run_create_custom_iter");
    let server_url = server.url();
    for batch_size in [100] {
        for json_len in [5_000] {
            for num_runs in [1_000] {
                group.bench_function(
                    BenchmarkId::new(
                        "run_create_sync",
                        format!("batch_{}_json_{}_runs_{}", batch_size, json_len, num_runs),
                    ),
                    |b| {
                        b.iter_custom(|iters| {
                            let mut elapsed_time = Duration::default();
                            let server_url = server_url.clone();
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
                                    create_mock_client_config_sync(&server_url, batch_size);
                                let client = BlockingTracingClient::new(client_config).unwrap();

                                let start = std::time::Instant::now();
                                for run in runs {
                                    std::hint::black_box(
                                        client.submit_run_create(std::hint::black_box(run)),
                                    )
                                    .unwrap();
                                }

                                // shutdown the client to flush the queue
                                let start_shutdown = std::time::Instant::now();
                                std::hint::black_box(client.shutdown()).unwrap();
                                // println!("Elapsed time for shutdown: {:?}", start_shutdown.elapsed());
                                elapsed_time += start.elapsed();
                                println!("Elapsed time: {:?}", elapsed_time);
                            }
                            elapsed_time
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
    targets = bench_run_create_sync_iter_custom
}

criterion_main!(benches);
