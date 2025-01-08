use std::ptr::NonNull;

use pyo3::types::PyAnyMethods as _;

mod writer;

thread_local! {
    static ORJSON_DEFAULT: NonNull<pyo3_ffi::PyObject> = {
        pyo3::Python::with_gil(|py| {
            let module = match py.import("langsmith._internal._serde") {
                Ok(m) => m,
                Err(e) => {
                    let _ = py.import("langsmith").expect("failed to import `langsmith` package; please make sure `langsmith-pyo3` is only used via the `langsmith` package");
                    panic!("Failed to import `langsmith._internal._serde` even though `langsmith` can be imported. Did internal `langsmith` package structure change? Underlying error: {e}");
                }
            };

            let function = module.getattr("_serialize_json").expect("`_serialize_json` function not found").as_ptr();
            NonNull::new(function).expect("function was null, which shouldn't ever happen")
        })
    }
}

pub(crate) fn dumps(ptr: *mut pyo3_ffi::PyObject) -> Result<Vec<u8>, String> {
    let mut writer = writer::BufWriter::new();

    ORJSON_DEFAULT.with(|default| {
        let obj = orjson::PyObjectSerializer::new(
            ptr,
            orjson::SerializerState::new(Default::default()),
            Some(*default),
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
