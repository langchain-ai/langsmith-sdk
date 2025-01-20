use std::{sync::Arc, time::Duration};

use pyo3::prelude::*;

use langsmith_tracing_client::client::{
    ClientConfig as RustClientConfig, TracingClient as RustTracingClient,
};

pub(super) fn register(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<BlockingTracingClient>()?;
    Ok(())
}

// `frozen` here means "immutable from Python". Rust-side mutation is allowed.
// Since this type is also `Sync`, that means we can operate on `BlockingTracingClient` values
// without holding the Python GIL.
#[pyclass(frozen)]
pub struct BlockingTracingClient {
    client: Arc<RustTracingClient>,
}

#[pymethods]
impl BlockingTracingClient {
    #[new]
    pub fn new(
        endpoint: String,
        api_key: String,
        queue_capacity: usize,
        batch_size: usize,
        batch_timeout_millis: u64,
        compression_level: i32,
    ) -> PyResult<Self> {
        let config = RustClientConfig {
            endpoint,
            api_key,
            queue_capacity,
            send_at_batch_size: batch_size,
            send_at_batch_time: Duration::from_millis(batch_timeout_millis),
            compression_level,
            headers: None, // TODO: support custom headers
        };

        let client = RustTracingClient::new(config)
            .map_err(|e| Python::with_gil(|py| into_py_err(py, e)))?;

        Ok(Self { client: Arc::from(client) })
    }

    // N.B.: `slf.get()` below is only valid if the `Self` type is `Sync` and `pyclass(frozen)`,
    //       which is enforced at compile-time.
    pub fn create_run(
        slf: &Bound<'_, Self>,
        run: super::py_run::RunCreateExtended,
    ) -> PyResult<()> {
        let unpacked = slf.get();
        Python::allow_threads(slf.py(), || unpacked.client.submit_run_create(run.into_inner()))
            .map_err(|e| into_py_err(slf.py(), e))
    }

    // N.B.: `slf.get()` below is only valid if the `Self` type is `Sync` and `pyclass(frozen)`,
    //       which is enforced at compile-time.
    pub fn update_run(
        slf: &Bound<'_, Self>,
        run: super::py_run::RunUpdateExtended,
    ) -> PyResult<()> {
        let unpacked = slf.get();
        Python::allow_threads(slf.py(), || unpacked.client.submit_run_update(run.into_inner()))
            .map_err(|e| into_py_err(slf.py(), e))
    }
}

fn into_py_err(py: Python<'_>, e: langsmith_tracing_client::client::TracingClientError) -> PyErr {
    crate::errors::TracingClientError::new_err(format!("{e}").into_py(py))
}

impl Drop for BlockingTracingClient {
    fn drop(&mut self) {
        if Arc::strong_count(&self.client) == 1 {
            // This is the only copy of the client in Python,
            // so let it drain its in-progress requests before proceeding.
            // This runs when Python runs GC on the client, such as when the application is exiting.
            self.client.drain().expect("draining failed");
        }
    }
}
