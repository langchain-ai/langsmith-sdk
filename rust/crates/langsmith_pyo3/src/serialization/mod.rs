mod writer;

pub(crate) fn dumps(ptr: *mut pyo3_ffi::PyObject) -> Result<Vec<u8>, String> {
    let mut writer = writer::BufWriter::new();

    let obj = orjson::PyObjectSerializer::new(
        ptr,
        orjson::SerializerState::new(Default::default()),
        None,
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
}
