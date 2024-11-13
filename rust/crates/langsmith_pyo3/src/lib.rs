use pyo3::{
    pymodule,
    types::{PyModule, PyModuleMethods},
    Bound, PyResult, Python,
};

mod blocking_tracing_client;
mod py_run;

#[pymodule]
fn langsmith_pyo3(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<blocking_tracing_client::TracingClient>()?;
    Ok(())
}
