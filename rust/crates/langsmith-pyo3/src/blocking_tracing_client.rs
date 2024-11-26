use std::{sync::Arc, time::Duration};

use pyo3::prelude::*;

use langsmith_tracing_client::client::blocking::TracingClient as RustTracingClient;

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
        worker_threads: usize,
    ) -> PyResult<Self> {
        let config = langsmith_tracing_client::client::blocking::ClientConfig {
            endpoint,
            api_key,
            queue_capacity,
            batch_size,

            // TODO: check if this is fine
            batch_timeout: Duration::from_millis(batch_timeout_millis),

            headers: None, // TODO: support custom headers
            num_worker_threads: worker_threads,
        };

        let client = RustTracingClient::new(config)
            .map_err(|e| Python::with_gil(|py| into_py_err(py, e)))?;

        Ok(Self { client: Arc::from(client) })
    }

    // N.B.: We use `Py<Self>` so that we don't hold the GIL while running this method.
    //       `slf.get()` below is only valid if the `Self` type is `Sync` and `pyclass(frozen)`,
    //       which is enforced at compile-time.
    pub fn create_run(
        slf: &Bound<'_, Self>,
        run: super::py_run::RunCreateExtended,
    ) -> PyResult<()> {
        let unpacked = slf.get();
        Python::allow_threads(slf.py(), || unpacked.client.submit_run_create(run.into_inner()))
            .map_err(|e| into_py_err(slf.py(), e))
    }

    pub fn drain(slf: &Bound<'_, Self>) -> PyResult<()> {
        let unpacked = slf.get();
        Python::allow_threads(slf.py(), || unpacked.client.drain())
            .map_err(|e| into_py_err(slf.py(), e))
    }
}

fn into_py_err(py: Python<'_>, e: langsmith_tracing_client::client::TracingClientError) -> PyErr {
    crate::errors::TracingClientError::new_err(format!("{e}").into_py(py))
}
