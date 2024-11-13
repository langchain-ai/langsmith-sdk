use pyo3::{pymodule, types::PyModule, Bound, PyResult, Python};

mod blocking_tracing_client;
mod errors;
mod py_run;

#[pymodule]
fn langsmith_pyo3(py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    blocking_tracing_client::register(py, m)?;
    errors::register(py, m)?;
    Ok(())
}
