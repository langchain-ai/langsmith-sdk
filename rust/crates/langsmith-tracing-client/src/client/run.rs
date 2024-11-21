use serde::{Deserialize, Serialize};
use sonic_rs::Value;

// Map attachment ref to tuple of filename, optional bytes
#[derive(Debug)]
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
    pub inputs: Option<Vec<u8>>,
    pub outputs: Option<Vec<u8>>,
}

#[derive(Serialize, Deserialize, PartialEq, Debug)]
pub struct RunCommon {
    pub id: String,
    pub trace_id: String,
    pub dotted_order: String,
    pub parent_run_id: Option<String>,
    pub extra: Option<Value>,
    pub error: Option<String>,
    pub serialized: Option<Value>,
    pub events: Option<Value>,
    pub tags: Option<Value>,
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

#[derive(Debug)]
pub struct RunCreateExtended {
    pub run_create: RunCreate,
    pub io: RunIO,
    pub attachments: Option<Vec<Attachment>>,
}

#[derive(Debug)]
pub struct RunUpdateExtended {
    pub run_update: RunUpdate,
    pub io: RunIO,
    pub attachments: Option<Vec<Attachment>>,
}

#[derive(Debug)]
pub struct RunEventBytes {
    pub run_id: String,
    pub event_type: EventType,
    pub run_bytes: Vec<u8>,
    pub inputs_bytes: Option<Vec<u8>>,
    pub outputs_bytes: Option<Vec<u8>>,
    pub attachments: Option<Vec<Attachment>>,
}

#[derive(Debug)]
pub enum EventType {
    Create,
    Update,
}

#[derive(Debug)]
pub(crate) enum QueuedRun {
    Create(RunCreateExtended),
    Update(RunUpdateExtended),
    #[expect(dead_code)]
    RunBytes(RunEventBytes),
    Drain,
    Shutdown,
}
