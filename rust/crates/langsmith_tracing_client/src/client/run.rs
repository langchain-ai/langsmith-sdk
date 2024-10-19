use serde::{Deserialize, Serialize};
use std::collections::HashMap;

// Map attachment ref to tuple of filename, optional bytes
pub struct Attachment {
    pub filename: String,
    pub data: Option<Vec<u8>>,
    pub content_type: String,
}

// Must support both string (Py) and unsigned int (JS)
#[derive(Serialize, Deserialize)]
#[serde(untagged)]
pub enum TimeValue {
    String(String),
    UnsignedInt(u64),
}

#[derive(Serialize, Deserialize)]
pub struct RunCommon {
    pub id: String,
    pub trace_id: String,
    pub dotted_order: String,
    pub parent_run_id: Option<String>,
    pub extra: serde_json::Value,
    pub error: Option<String>,
    pub serialized: serde_json::Value,
    pub inputs: serde_json::Value,
    pub events: serde_json::Value,
    pub tags: serde_json::Value,
    pub session_id: Option<String>,
    pub session_name: Option<String>,
}

#[derive(Serialize, Deserialize)]
pub struct RunCreate {
    pub common: RunCommon,
    pub name: String,
    pub start_time: TimeValue,
    pub end_time: Option<TimeValue>,
    pub outputs: serde_json::Value,
    pub run_type: String,
    pub reference_example_id: Option<String>,
}

#[derive(Serialize, Deserialize)]
pub struct RunUpdate {
    pub common: RunCommon,
    pub end_time: TimeValue,
    pub outputs: Option<serde_json::Value>,
}

pub struct RunCreateWithAttachments {
    pub run_create: RunCreate,
    pub attachments: HashMap<String, Attachment>,
}

pub struct RunUpdateWithAttachments {
    pub run_update: RunUpdate,
    pub attachments: HashMap<String, Attachment>,
}

pub enum QueuedRun {
    Create(RunCreateWithAttachments),
    Update(RunUpdateWithAttachments),
    Shutdown,
}
