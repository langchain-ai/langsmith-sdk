use std::sync::Arc;

use pyo3::prelude::*;

use langsmith_tracing_client::client::blocking::{
    ClientConfig, TracingClient as RustTracingClient,
};
use langsmith_tracing_client::client::{
    Attachment, RunCommon, RunCreate, RunCreateExtended, RunIO, TimeValue,
};

#[pyclass]
pub struct TracingClient {
    client: Arc<RustTracingClient>,
}
