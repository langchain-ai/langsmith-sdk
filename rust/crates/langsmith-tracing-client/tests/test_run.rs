use langsmith_tracing_client::client::{RunCommon, RunCreate, RunUpdate, TimeValue};
use sonic_rs::{json, to_string, Value};

#[test]
fn test_run_common() {
    let run_common = RunCommon {
        id: String::from("fedcba98-7654-3210-fedc-ba9876543210"),
        trace_id: String::from("fedcba98-7654-3210-fedc-ba9876543210"),
        dotted_order: String::from("1.1"),
        parent_run_id: None,
        extra: Some(json!({"extra_data": "value"})),
        error: Some(String::from("error message")),
        serialized: Some(json!({"key": "value"})),
        events: Some(Value::from(vec![json!({"event": "event_data"})])),
        tags: None,
        session_id: Some("efghijkl-7654-3210-fedc-ba9876543210".to_string()),
        session_name: None,
    };

    let serialized = to_string(&run_common).unwrap();
    assert!(serialized.contains("\"dotted_order\":\"1.1\""));
}

#[test]
fn test_run_create_with_string_time() {
    let run_common = RunCommon {
        id: String::from("fedcba98-7654-3210-fedc-ba9876543210"),
        trace_id: String::from("fedcba98-7654-3210-fedc-ba9876543210"),
        dotted_order: String::from("1.1"),
        parent_run_id: None,
        extra: None,
        error: None,
        serialized: None,
        events: Some(Value::from(vec![json!({"event": "event_data"})])),
        tags: Some(json!({"tag": "value"})),
        session_id: None,
        session_name: Some("Session Name".to_string()),
    };

    let run_create = RunCreate {
        common: run_common,
        name: String::from("Run Name"),
        start_time: TimeValue::String("2024-10-16T12:00:00Z".to_string()),
        end_time: Some(TimeValue::String("2024-10-16T14:00:00Z".to_string())),
        run_type: String::from("test_run_type"),
        reference_example_id: None,
    };

    let serialized = to_string(&run_create).unwrap();
    assert!(serialized.contains("\"name\":\"Run Name\""));
    assert!(serialized.contains("\"start_time\":\"2024-10-16T12:00:00Z\""));
}

#[test]
fn test_run_create_with_timestamp() {
    let run_common = RunCommon {
        id: String::from("fedcba98-7654-3210-fedc-ba9876543210"),
        trace_id: String::from("fedcba98-7654-3210-fedc-ba9876543210"),
        dotted_order: String::from("1.1"),
        parent_run_id: None,
        extra: Some(json!({"extra_data": "value"})),
        error: None,
        serialized: Some(json!({"key": "value"})),
        events: None,
        tags: Some(json!({"tag": "value"})),
        session_id: None,
        session_name: None,
    };

    let run_create = RunCreate {
        common: run_common,
        name: String::from("Run Name"),
        start_time: TimeValue::UnsignedInt(1697462400000),
        end_time: Some(TimeValue::UnsignedInt(1697466000000)),
        run_type: String::from("test_run_type"),
        reference_example_id: None,
    };

    let serialized = to_string(&run_create).unwrap();
    assert!(serialized.contains("\"name\":\"Run Name\""));
    assert!(serialized.contains("\"start_time\":1697462400000"));
}

#[test]
fn test_run_update() {
    let run_common = RunCommon {
        id: String::from("fedcba98-7654-3210-fedc-ba9876543210"),
        trace_id: String::from("fedcba98-7654-3210-fedc-ba9876543210"),
        dotted_order: String::from("1.1"),
        parent_run_id: None,
        extra: None,
        error: None,
        serialized: None,
        events: None,
        tags: Some(json!({"tag": "value"})),
        session_id: None,
        session_name: None,
    };

    let run_update = RunUpdate {
        common: run_common,
        end_time: TimeValue::String("2024-10-16T14:00:00Z".to_string()),
    };

    let serialized = to_string(&run_update).unwrap();
    assert!(serialized.contains("\"dotted_order\":\"1.1\""));
    assert!(serialized.contains("\"end_time\":\"2024-10-16T14:00:00Z\""));
}
