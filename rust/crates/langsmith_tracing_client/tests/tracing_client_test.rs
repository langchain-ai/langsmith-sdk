use langsmith_tracing_client::client::run::{
    Attachment, RunCommon, RunCreate, RunCreateExtended, RunIO, RunUpdate, RunUpdateExtended,
    TimeValue,
};
use langsmith_tracing_client::client::tracing_client::{ClientConfig, TracingClient};
use mockito::{Matcher, Server};
use std::collections::HashMap;
use std::fs::File;
use std::time::Duration;
// use tokio::io::AsyncWriteExt;
use multipart::server::Multipart;
use std::io::{self, Read, Write};
use std::sync::{Arc, Mutex};
use tempfile::TempDir;

#[derive(Debug)]
struct MultipartField {
    name: String,
    content_type: Option<String>,
    filename: Option<String>,
    data: String,
}

fn handle_request(body: Vec<u8>, content_type_str: String) -> Vec<MultipartField> {
    assert!(content_type_str.starts_with("multipart/form-data"));

    let boundary = content_type_str.split("boundary=").nth(1).unwrap();
    let mut mp = Multipart::with_body(body.as_slice(), boundary);

    let mut fields = Vec::new();

    while let Some(mut field) = mp.read_entry().unwrap() {
        let field_name = field.headers.name.to_string();
        let field_content_type = field.headers.content_type.map(|ct| ct.to_string());
        let field_filename = field.headers.filename.map(String::from);

        let mut content = String::new();
        field.data.read_to_string(&mut content).unwrap();

        let multipart_field = MultipartField {
            name: field_name,
            content_type: field_content_type,
            filename: field_filename,
            data: content,
        };

        fields.push(multipart_field);
    }

    fields
}

#[tokio::test]
async fn test_tracing_client_submit_run_create() {
    let mut server = Server::new_async().await;
    let captured_request: Arc<Mutex<(Vec<u8>, String)>> =
        Arc::new(Mutex::new((Vec::new(), String::new())));
    let captured_request_clone = Arc::clone(&captured_request);

    let m = server
        .mock("POST", "/")
        .expect(1)
        .with_status(200)
        .with_body_from_request(move |req| {
            let mut request = captured_request_clone.lock().unwrap();
            request.0 = req.body().unwrap().to_vec();
            let content_type_headers = req.header("content-type");
            let content_type_str: String = content_type_headers
                .iter()
                .filter_map(|h| h.to_str().ok())
                .collect::<Vec<&str>>()
                .join(", ");
            request.1 = content_type_str;
            vec![] // return empty response body
        })
        .create_async()
        .await;

    let config = ClientConfig {
        endpoint: server.url(),
        queue_capacity: 10,
        batch_size: 5, // batch size is 5 to ensure shutdown flushes the queue
        batch_timeout: Duration::from_secs(1),
    };

    let client = TracingClient::new(config).unwrap();

    // Write a test file to disk for streaming
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

    let run_create = RunCreateExtended {
        run_create: RunCreate {
            common: RunCommon {
                id: String::from("test_id"),
                trace_id: String::from("trace_id"),
                dotted_order: String::from("1.1"),
                parent_run_id: None,
                extra: Some(serde_json::json!({"extra_data": "value"})),
                error: None,
                serialized: Some(serde_json::json!({"key": "value"})),
                events: serde_json::json!([{ "event": "event_data" }]),
                tags: serde_json::json!([{"tag": "value"}]),
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
            inputs: serde_json::json!({"input": "value"}),
            outputs: Some(serde_json::json!({"output": "value"})),
        },
    };

    client.submit_run_create(run_create).await.unwrap();

    // shutdown the client to ensure all messages are processed
    client.shutdown().await.unwrap();
    m.assert_async().await;

    let req = captured_request.lock().unwrap().clone();
    let fields = handle_request(req.0, req.1);

    assert_eq!(fields.len(), 5);

    // assert run fields
    assert_eq!(fields[0].name, "post.test_id");
    assert_eq!(fields[0].content_type, Some("application/json".to_string()));
    assert_eq!(fields[0].filename, None);
    let received_run: serde_json::Value = serde_json::from_str(&fields[0].data).unwrap();
    assert_eq!(received_run["id"], "test_id");
    assert_eq!(received_run["trace_id"], "trace_id");
    assert_eq!(received_run["dotted_order"], "1.1");
    assert_eq!(received_run["parent_run_id"], serde_json::Value::Null);
    assert_eq!(
        received_run["extra"],
        serde_json::json!({"extra_data": "value"})
    );
    assert_eq!(received_run["error"], serde_json::Value::Null);
    assert_eq!(
        received_run["serialized"],
        serde_json::json!({"key": "value"})
    );
    assert_eq!(
        received_run["events"],
        serde_json::json!([{ "event": "event_data" }])
    );
    assert_eq!(received_run["tags"], serde_json::json!([{"tag": "value"}]));
    assert_eq!(received_run["session_name"], "Session Name");
    assert_eq!(received_run["session_id"], serde_json::Value::Null);
    assert_eq!(received_run["name"], "Run Name");
    assert_eq!(received_run["start_time"], 1697462400000i64);
    assert_eq!(received_run["end_time"], 1697466000000i64);
    assert_eq!(received_run["run_type"], "chain");
    assert_eq!(
        received_run["reference_example_id"],
        serde_json::Value::Null
    );

    // assert inputs fields
    assert_eq!(fields[1].name, "post.test_id.inputs");
    assert_eq!(fields[1].content_type, Some("application/json".to_string()));
    assert_eq!(fields[1].filename, None);
    let received_inputs: serde_json::Value = serde_json::from_str(&fields[1].data).unwrap();
    assert_eq!(received_inputs, serde_json::json!({"input": "value"}));

    // assert outputs fields
    assert_eq!(fields[2].name, "post.test_id.outputs");
    assert_eq!(fields[2].content_type, Some("application/json".to_string()));
    assert_eq!(fields[2].filename, None);
    let received_outputs: serde_json::Value = serde_json::from_str(&fields[2].data).unwrap();
    assert_eq!(received_outputs, serde_json::json!({"output": "value"}));

    // assert attachment_1 fields
    assert_eq!(fields[3].name, "post.test_id.attachments.attachment_1");
    assert_eq!(
        fields[3].content_type,
        Some("application/octet-stream".to_string())
    );
    assert_eq!(fields[3].filename, Some("file1.txt".to_string()));
    assert_eq!(fields[3].data, "\u{1}\u{2}\u{3}");

    // assert attachment_2 fields
    assert_eq!(fields[4].name, "post.test_id.attachments.attachment_2");
    assert_eq!(fields[4].content_type, Some("text/plain".to_string()));
    assert_eq!(fields[4].filename, Some("test_file_create.txt".to_string()));
    assert_eq!(fields[4].data, "Test file content for create\n");
}

// #[tokio::test]
// async fn test_tracing_client_submit_run_update() {
//     let mut server = Server::new_async().await;
//     let m = server
//         .mock("POST", "/")
//         .match_header(
//             "content-type",
//             Matcher::Regex(r"multipart/form-data.*".to_string()),
//         )
//         .match_body(Matcher::AllOf(vec![
//             Matcher::Regex("patch\\.test_id".to_string()),
//             Matcher::Regex("patch\\.test_id\\.outputs".to_string()),
//             Matcher::Regex("patch\\.test_id\\.attachments\\.attachment_1".to_string()),
//             Matcher::Regex("patch\\.test_id\\.attachments\\.attachment_2".to_string()),
//         ]))
//         .with_status(200)
//         .create_async()
//         .await;
//
//     let config = ClientConfig {
//         endpoint: server.url(),
//         queue_capacity: 10,
//         batch_size: 1, // batch size is 1 to ensure each message is sent immediately
//         batch_timeout: Duration::from_secs(1),
//     };
//
//     let client = TracingClient::new(config).unwrap();
//
//     // Write a test file to disk for streaming
//     let test_file_path = "test_file_update.txt";
//     let mut test_file = File::create(test_file_path).await.unwrap();
//     test_file
//         .write_all(b"Test file content for update")
//         .await
//         .unwrap();
//
//     let mut attachments = HashMap::new();
//     attachments.insert(
//         "attachment_1".to_string(),
//         Attachment {
//             filename: "file1.txt".to_string(),
//             data: Some(vec![1, 2, 3]),
//             content_type: "application/octet-stream".to_string(),
//         },
//     );
//     attachments.insert(
//         "attachment_2".to_string(),
//         Attachment {
//             filename: test_file_path.to_string(),
//             data: None, // This will cause the code to read from disk
//             content_type: "text/plain".to_string(),
//         },
//     );
//
//     let run_update = RunUpdateWithAttachments {
//         run_update: RunUpdate {
//             common: RunCommon {
//                 id: String::from("test_id"),
//                 trace_id: String::from("trace_id"),
//                 dotted_order: String::from("1.1"),
//                 parent_run_id: None,
//                 extra: serde_json::json!({"extra_data": "value"}),
//                 error: None,
//                 serialized: serde_json::json!({"key": "value"}),
//                 inputs: serde_json::json!({"input": "value"}),
//                 events: serde_json::json!([{ "event": "event_data" }]),
//                 tags: serde_json::json!({"tag": "value"}),
//                 session_name: Some("Session Name".to_string()),
//                 session_id: None,
//             },
//             end_time: TimeValue::UnsignedInt(1697462400000),
//             outputs: Some(serde_json::json!({"output_key": "output_value"})),
//         },
//         attachments,
//     };
//
//     client.submit_run_update(run_update).await.unwrap();
//
//     // shutdown the client to ensure all messages are processed
//     client.shutdown().await.unwrap();
//     m.assert_async().await;
// }
