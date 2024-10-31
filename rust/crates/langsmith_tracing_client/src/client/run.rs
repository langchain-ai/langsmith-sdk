use serde::{Deserialize, Serialize};

// Map attachment ref to tuple of filename, optional bytes
pub struct Attachment {
    pub ref_name: String,
    pub filename: String,
    pub data: Option<Vec<u8>>,
    pub content_type: String,
}

// Must support both string (Py) and unsigned int (JS)
#[derive(Serialize, Deserialize, PartialEq, Debug)]
#[serde(untagged)]
pub enum TimeValue {
    String(String),
    UnsignedInt(u64),
}

#[derive(PartialEq, Debug)]
pub struct RunIO {
    pub inputs: Option<serde_json::Value>,
    pub outputs: Option<serde_json::Value>,
}

#[derive(Serialize, Deserialize, PartialEq, Debug)]
pub struct RunCommon {
    pub id: String,
    pub trace_id: String,
    pub dotted_order: String,
    pub parent_run_id: Option<String>,
    pub extra: Option<serde_json::Value>,
    pub error: Option<String>,
    pub serialized: Option<serde_json::Value>,
    pub events: Option<serde_json::Value>,
    pub tags: Option<serde_json::Value>,
    pub session_id: Option<String>,
    pub session_name: Option<String>,
}

#[derive(Serialize, Deserialize, PartialEq, Debug)]
pub struct RunCreate {
    #[serde(flatten)]
    pub common: RunCommon,
    pub name: String,
    pub start_time: TimeValue,
    pub end_time: Option<TimeValue>,
    pub run_type: String,
    pub reference_example_id: Option<String>,
}

#[derive(Serialize, Deserialize, PartialEq, Debug)]
pub struct RunUpdate {
    #[serde(flatten)]
    pub common: RunCommon,
    pub end_time: TimeValue,
}

pub struct RunCreateExtended {
    pub run_create: RunCreate,
    pub io: RunIO,
    pub attachments: Option<Vec<Attachment>>,
}

pub struct RunUpdateExtended {
    pub run_update: RunUpdate,
    pub io: RunIO,
    pub attachments: Option<Vec<Attachment>>,
}

pub struct RunEventBytes {
    pub run_id: String,
    pub event_type: EventType,
    pub run_bytes: Vec<u8>,
    pub inputs_bytes: Option<Vec<u8>>,
    pub outputs_bytes: Option<Vec<u8>>,
    pub attachments: Option<Vec<Attachment>>,
}

pub enum EventType {
    Create,
    Update,
}

pub(crate) enum QueuedRun {
    Create(RunCreateExtended),
    Update(RunUpdateExtended),
    RunBytes(RunEventBytes),
    Shutdown,
}
