use pyo3::{
    create_exception,
    types::{PyModule, PyModuleMethods},
    Bound, PyResult, Python,
};

pub(super) fn register(py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("TracingClientError", py.get_type_bound::<TracingClientError>())?;

    Ok(())
}

create_exception!(langsmith_pyo3, TracingClientError, pyo3::exceptions::PyException);
