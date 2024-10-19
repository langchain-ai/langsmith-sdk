use langsmith_tracing_client::client::run::{
    RunCommon, RunCreate, RunCreateWithAttachments, RunUpdate, RunUpdateWithAttachments, TimeValue,
};
use langsmith_tracing_client::client::tracing_client::{ClientConfig, TracingClient};
use mockito::{Matcher, Server};
use std::collections::HashMap;
use std::time::Duration;
use serde::de::Unexpected::Option;

#[tokio::test]
async fn test_tracing_client_submit_run_create() {
    let mut server = Server::new_async().await;
    let m = server
        .mock("POST", "/")
        .match_header(
            "content-type",
            Matcher::Regex(r"multipart/form-data.*".to_string()),
        )
        .match_body(Matcher::AllOf(vec![
            Matcher::Regex("post\\.test_id".to_string()),
            Matcher::Regex("post\\.test_id\\.inputs".to_string()),
            Matcher::Regex("post\\.test_id\\.outputs".to_string()),
            Matcher::Regex("post\\.test_id\\.attachments\\.attachment_1".to_string()),
            Matcher::Regex("post\\.test_id\\.attachments\\.attachment_2".to_string()),
        ]))
        .with_status(200)
        .create_async()
        .await;

    let config = ClientConfig {
        endpoint: server.url(),
        queue_capacity: 10,
        batch_size: 5,  // batch size is 5 to ensure shutdown flushes the queue
        batch_timeout: Duration::from_secs(1),
    };

    let client = TracingClient::new(config).unwrap();

    let mut attachments = HashMap::new();
    attachments.insert(
        "attachment_1".to_string(),
        ("file1.txt".to_string(), vec![1, 2, 3]),
    );
    attachments.insert(
        "attachment_2".to_string(),
        ("file2.txt".to_string(), vec![4, 5, 6]),
    );

    let run_create = RunCreateWithAttachments {
        run_create: RunCreate {
            common: RunCommon {
                id: String::from("test_id"),
                trace_id: String::from("trace_id"),
                dotted_order: String::from("1.1"),
                parent_run_id: None,
                extra: serde_json::json!({"extra_data": "value"}),
                error: None,
                serialized: serde_json::json!({"key": "value"}),
                inputs: serde_json::json!({"input": "value"}),
                events: serde_json::json!([{ "event": "event_data" }]),
                tags: serde_json::json!({"tag": "value"}),
                session_id: None,
                session_name: Some("Session Name".to_string()),
            },
            name: String::from("Run Name"),
            start_time: TimeValue::UnsignedInt(1697462400000),
            end_time: Some(TimeValue::UnsignedInt(1697466000000)),
            outputs: serde_json::json!({"output_key": "output_value"}),
            run_type: String::from("test_run_type"),
            reference_example_id: None,
        },
        attachments,
    };

    client.submit_run_create(run_create).await.unwrap();

    // shutdown the client to ensure all messages are processed
    client.shutdown().await.unwrap();
    m.assert_async().await;
}

// now test run update
#[tokio::test]
async fn test_tracing_client_submit_run_update() {
    let mut server = Server::new_async().await;
    let m = server
        .mock("POST", "/")
        .match_header(
            "content-type",
            Matcher::Regex(r"multipart/form-data.*".to_string()),
        )
        .match_body(Matcher::AllOf(vec![
            Matcher::Regex("patch\\.test_id".to_string()),
            Matcher::Regex("patch\\.test_id\\.outputs".to_string()),
            Matcher::Regex("patch\\.test_id\\.attachments\\.attachment_1".to_string()),
            Matcher::Regex("patch\\.test_id\\.attachments\\.attachment_2".to_string()),
        ]))
        .with_status(200)
        .create_async()
        .await;

    let config = ClientConfig {
        endpoint: server.url(),
        queue_capacity: 10,
        batch_size: 1, // batch size is 1 to ensure each message is sent immediately
        batch_timeout: Duration::from_secs(1),
    };

    let client = TracingClient::new(config).unwrap();

    let mut attachments = HashMap::new();
    attachments.insert(
        "attachment_1".to_string(),
        ("file1.txt".to_string(), vec![1, 2, 3]),
    );
    attachments.insert(
        "attachment_2".to_string(),
        ("file2.txt".to_string(), vec![4, 5, 6]),
    );

    let run_update = RunUpdateWithAttachments {
        run_update: RunUpdate {
            common: RunCommon {
                id: String::from("test_id"),
                trace_id: String::from("trace_id"),
                dotted_order: String::from("1.1"),
                parent_run_id: None,
                extra: serde_json::json!({"extra_data": "value"}),
                error: None,
                serialized: serde_json::json!({"key": "value"}),
                inputs: serde_json::json!({"input": "value"}),
                events: serde_json::json!([{ "event": "event_data" }]),
                tags: serde_json::json!({"tag": "value"}),
                session_name: Some("Session Name".to_string()),
                session_id: None,
            },
            end_time: TimeValue::UnsignedInt(1697462400000),
            outputs: Some(serde_json::json!({"output_key": "output_value"})),
        },
        attachments,
    };

    client.submit_run_update(run_update).await.unwrap();

    // shutdown the client to ensure all messages are processed
    client.shutdown().await.unwrap();
    m.assert_async().await;
}
