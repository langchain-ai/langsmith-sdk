use langsmith_tracing_client::client::run::{
    Attachment, RunCommon, RunCreate, RunCreateExtended, RunIO, RunUpdate, RunUpdateExtended,
    TimeValue,
};
use langsmith_tracing_client::client::tracing_client::{ClientConfig, TracingClient};
use reqwest::header::{HeaderMap, HeaderValue};
use std::fs::File;
use std::io::Write;
use tempfile::TempDir;
use tokio::time::Duration;
use uuid::Uuid;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let tmp_dir = TempDir::new().unwrap();
    let test_file_path = tmp_dir.path().join("test_file_create.txt");
    let mut test_file = File::create(&test_file_path).unwrap();
    writeln!(test_file, "Test file content for create").unwrap();

    let mut attachments = Vec::new();
    attachments.push(Attachment {
        ref_name: "attachment_1".to_string(),
        filename: "file1.txt".to_string(),
        data: Some(vec![1, 2, 3]),
        content_type: "application/octet-stream".to_string(),
    });
    attachments.push(Attachment {
        ref_name: "attachment_2".to_string(),
        filename: test_file_path.into_os_string().into_string().unwrap(),
        data: None, // this will cause the processor to read from disk
        content_type: "text/plain".to_string(),
    });

    let run_id = Uuid::new_v4().to_string();
    println!("Run ID: {}", run_id);

    let run_create = RunCreateExtended {
        run_create: RunCreate {
            common: RunCommon {
                id: String::from(&run_id),
                trace_id: String::from(&run_id),
                dotted_order: String::from("20241009T223747383001Z{}".to_string() + &run_id),
                parent_run_id: None,
                extra: Some(serde_json::json!({"extra_data": "value"})),
                error: None,
                serialized: None,
                events: Some(serde_json::json!([{ "event": "event_data" }])),
                tags: Some(serde_json::json!(["tag1", "tag2"])),
                session_id: None,
                session_name: Some("Rust Session Name".to_string()),
            },
            name: String::from("Rusty"),
            start_time: TimeValue::UnsignedInt(1728513467383),
            end_time: Some(TimeValue::UnsignedInt(1728513468236)),
            run_type: String::from("chain"),
            reference_example_id: None,
        },
        attachments: Some(attachments),
        io: RunIO {
            inputs: Some(serde_json::json!({"input": "value"})),
            outputs: Some(serde_json::json!({"output": "value"})),
        },
    };

    let mut attachments_two = Vec::new();
    attachments_two.push(Attachment {
        ref_name: "attachment_1".to_string(),
        filename: "file1.txt".to_string(),
        data: Some(vec![1, 2, 3]),
        content_type: "application/octet-stream".to_string(),
    });

    let run_id_two = Uuid::new_v4().to_string();
    println!("Run ID Two: {}", run_id_two);
    let run_create_two = RunCreateExtended {
        run_create: RunCreate {
            common: RunCommon {
                id: String::from(&run_id_two),
                trace_id: String::from(&run_id_two),
                dotted_order: String::from("20241009T223747383001Z{}".to_string() + &run_id_two),
                parent_run_id: None,
                extra: Some(serde_json::json!({"extra_data": "value"})),
                error: None,
                serialized: None,
                events: Some(serde_json::json!([{ "event": "event_data" }])),
                tags: Some(serde_json::json!(["tag1", "tag2"])),
                session_id: None,
                session_name: Some("Rust Session Name".to_string()),
            },
            name: String::from("Rusty two"),
            start_time: TimeValue::UnsignedInt(1728513467383),
            end_time: None,
            run_type: String::from("chain"),
            reference_example_id: None,
        },
        attachments: Some(attachments_two),
        io: RunIO {
            inputs: Some(serde_json::json!({"input": "value"})),
            outputs: None,
        },
    };

    let run_update_two = RunUpdateExtended {
        run_update: RunUpdate {
            common: RunCommon {
                id: String::from(&run_id_two),
                trace_id: String::from(&run_id_two),
                dotted_order: String::from("20241009T223747383001Z{}".to_string() + &run_id_two),
                parent_run_id: None,
                extra: Some(serde_json::json!({"extra_data": "value"})),
                error: None,
                serialized: None,
                events: None,
                tags: Some(serde_json::json!(["tag1", "tag2"])),
                session_id: None,
                session_name: Some("Rust Session Name".to_string()),
            },
            end_time: TimeValue::UnsignedInt(1728513468236),
        },
        io: RunIO {
            inputs: None,
            outputs: Some(serde_json::json!({"output": "value"})),
        },
        attachments: None,
    };

    let mut headers = HeaderMap::new();
    headers.insert("X-API-KEY", HeaderValue::from_static("test_key"));
    let config = ClientConfig {
        endpoint: String::from("http://localhost:1984"),
        queue_capacity: 10,
        batch_size: 5, // batch size is 5 to ensure shutdown flushes the queue
        batch_timeout: Duration::from_secs(1),
        headers: None,
    };

    let client = TracingClient::new(config).unwrap();
    client.submit_run_create(run_create).await.unwrap();
    client.submit_run_create(run_create_two).await.unwrap();
    client.submit_run_update(run_update_two).await.unwrap();

    client.shutdown().await.unwrap();
    Ok(())
}
