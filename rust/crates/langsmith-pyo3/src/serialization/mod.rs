use std::ptr::NonNull;

use pyo3::types::PyAnyMethods as _;

mod writer;

thread_local! {
    static ORJSON_DEFAULT: Result<NonNull<pyo3_ffi::PyObject>, String> = {
        pyo3::Python::with_gil(|py| {
            let module = match py.import("langsmith._internal._serde") {
                Ok(m) => m,
                Err(e) => {
                    let _ = py.import("langsmith").map_err(|_| "failed to import `langsmith` package; please make sure `langsmith-pyo3` is only used via the `langsmith` package".to_string())?;
                    return Err(format!("Failed to import `langsmith._internal._serde` even though `langsmith` can be imported. Did internal `langsmith` package structure change? Underlying error: {e}"));
                }
            };

            let function = module.getattr("_serialize_json").map_err(|e| format!("`_serialize_json` function not found; underlying error: {e}"))?.as_ptr();
            Ok(NonNull::new(function).expect("function was null, which shouldn't ever happen"))
        })
    }
}

/// Perform a runtime check that we've successfully located the `langsmith` Python code
/// used to transform Python objects which aren't natively serializeable by `orjson`.
///
/// This assertion ensures that we won't later fail to serialize e.g. Pydantic objects.
///
/// The cost of this call is trivial: just one easily branch-predictable comparison on
/// an already-initialized thread-local.
pub(crate) fn assert_orjson_default_is_present() {
    ORJSON_DEFAULT.with(|res| {
        if let Err(e) = res {
            panic!("{e}");
        }
    })
}

pub(crate) fn dumps(ptr: *mut pyo3_ffi::PyObject) -> Result<Vec<u8>, String> {
    let mut writer = writer::BufWriter::new();

    ORJSON_DEFAULT.with(|default| {
        let obj = orjson::PyObjectSerializer::new(
            ptr,
            orjson::SerializerState::new(Default::default()),
            default.as_ref().cloned().ok(),
        );

        let res = orjson::to_writer(&mut writer, &obj);
        match res {
            Ok(_) => Ok(writer.finish()),
            Err(err) => {
                // Make sure we drop the allocated buffer.
                let _ = writer.into_inner();
                Err(err.to_string())
            }
        }
    })
}
