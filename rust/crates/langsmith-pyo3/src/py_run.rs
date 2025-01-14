use std::ffi::CStr;

use langsmith_tracing_client::client::{Attachment, RunIO, TimeValue};
use pyo3::{
    types::{
        PyAnyMethods as _, PyDateTime, PyMapping, PyMappingMethods, PySequence, PyString, PyTuple,
    },
    Bound, FromPyObject, PyAny, PyResult,
};

use crate::{errors::TracingClientError, serialization};

#[derive(Debug)]
pub struct RunCreateExtended(langsmith_tracing_client::client::RunCreateExtended);

impl RunCreateExtended {
    #[inline]
    pub(crate) fn into_inner(self) -> langsmith_tracing_client::client::RunCreateExtended {
        self.0
    }
}

impl FromPyObject<'_> for RunCreateExtended {
    fn extract_bound(value: &Bound<'_, PyAny>) -> PyResult<Self> {
        // Perform a runtime check that we've successfully located the `langsmith` Python code
        // used to transform Python objects which aren't natively serializeable by `orjson`.
        //
        // This assertion ensures that we won't later fail to serialize e.g. Pydantic objects.
        serialization::assert_orjson_default_is_present();

        let run_create = value.extract::<RunCreate>()?.into_inner();

        let attachments = {
            if let Ok(attachments_value) = value.get_item(pyo3::intern!(value.py(), "attachments"))
            {
                extract_attachments(&attachments_value)?
            } else {
                None
            }
        };

        let io = RunIO {
            inputs: serialize_optional_dict_value(value, pyo3::intern!(value.py(), "inputs"))?,
            outputs: serialize_optional_dict_value(value, pyo3::intern!(value.py(), "outputs"))?,
        };

        Ok(Self(langsmith_tracing_client::client::RunCreateExtended {
            run_create,
            io,
            attachments,
        }))
    }
}

#[derive(Debug)]
pub struct RunUpdateExtended(langsmith_tracing_client::client::RunUpdateExtended);

impl RunUpdateExtended {
    #[inline]
    pub(crate) fn into_inner(self) -> langsmith_tracing_client::client::RunUpdateExtended {
        self.0
    }
}

impl FromPyObject<'_> for RunUpdateExtended {
    fn extract_bound(value: &Bound<'_, PyAny>) -> PyResult<Self> {
        // Perform a runtime check that we've successfully located the `langsmith` Python code
        // used to transform Python objects which aren't natively serializeable by `orjson`.
        //
        // This assertion ensures that we won't later fail to serialize e.g. Pydantic objects.
        serialization::assert_orjson_default_is_present();

        let run_update = value.extract::<RunUpdate>()?.into_inner();

        // TODO: attachments are WIP at the moment, ignore them here for now.
        //
        // let attachments = {
        //     if let Ok(attachments_value) = value.get_item(pyo3::intern!(value.py(), "attachments"))
        //     {
        //         extract_attachments(&attachments_value)?
        //     } else {
        //         None
        //     }
        // };
        let attachments = None;

        let io = RunIO {
            inputs: serialize_optional_dict_value(value, pyo3::intern!(value.py(), "inputs"))?,
            outputs: serialize_optional_dict_value(value, pyo3::intern!(value.py(), "outputs"))?,
        };

        Ok(Self(langsmith_tracing_client::client::RunUpdateExtended {
            run_update,
            io,
            attachments,
        }))
    }
}

#[derive(Debug)]
pub(crate) struct RunCreate(langsmith_tracing_client::client::RunCreate);

impl RunCreate {
    #[inline]
    pub(crate) fn into_inner(self) -> langsmith_tracing_client::client::RunCreate {
        self.0
    }
}

impl FromPyObject<'_> for RunCreate {
    fn extract_bound(value: &Bound<'_, PyAny>) -> PyResult<Self> {
        let common = RunCommon::extract_bound(value)?.into_inner();
        let name = value.get_item(pyo3::intern!(value.py(), "name"))?.extract::<String>()?;

        let start_time =
            extract_time_value(&value.get_item(pyo3::intern!(value.py(), "start_time"))?)?;

        let end_time = {
            match value.get_item(pyo3::intern!(value.py(), "end_time")) {
                Ok(py_end_time) => {
                    if py_end_time.is_none() {
                        None
                    } else {
                        Some(extract_time_value(&py_end_time)?)
                    }
                }
                Err(_) => None,
            }
        };

        let run_type =
            value.get_item(pyo3::intern!(value.py(), "run_type"))?.extract::<String>()?;
        let reference_example_id = extract_string_like_or_none(
            get_optional_value_from_mapping(
                value,
                pyo3::intern!(value.py(), "reference_example_id"),
            )
            .as_ref(),
        )?;

        Ok(Self(langsmith_tracing_client::client::RunCreate {
            common,
            name,
            start_time,
            end_time,
            run_type,
            reference_example_id,
        }))
    }
}

#[derive(Debug)]
pub(crate) struct RunUpdate(langsmith_tracing_client::client::RunUpdate);

impl FromPyObject<'_> for RunUpdate {
    fn extract_bound(value: &Bound<'_, PyAny>) -> PyResult<Self> {
        let common = RunCommon::extract_bound(value)?.into_inner();

        let end_time = extract_time_value(&value.get_item(pyo3::intern!(value.py(), "end_time"))?)?;

        Ok(Self(langsmith_tracing_client::client::RunUpdate { common, end_time }))
    }
}

impl RunUpdate {
    #[inline]
    pub(crate) fn into_inner(self) -> langsmith_tracing_client::client::RunUpdate {
        self.0
    }
}

#[derive(Debug)]
pub(crate) struct RunCommon(langsmith_tracing_client::client::RunCommon);

impl RunCommon {
    #[inline]
    pub(crate) fn into_inner(self) -> langsmith_tracing_client::client::RunCommon {
        self.0
    }
}

impl FromPyObject<'_> for RunCommon {
    fn extract_bound(value: &Bound<'_, PyAny>) -> PyResult<Self> {
        let id = extract_string_like(&value.get_item(pyo3::intern!(value.py(), "id"))?)?;
        let trace_id =
            extract_string_like(&value.get_item(pyo3::intern!(value.py(), "trace_id"))?)?;

        let dotted_order = value.get_item(pyo3::intern!(value.py(), "dotted_order"))?.extract()?;
        let parent_run_id = extract_string_like_or_none(
            get_optional_value_from_mapping(value, pyo3::intern!(value.py(), "parent_run_id"))
                .as_ref(),
        )?;

        let extra = extract_optional_value_from_mapping(value, pyo3::intern!(value.py(), "extra"))?;

        let error = extract_string_like_or_none(
            get_optional_value_from_mapping(value, pyo3::intern!(value.py(), "error")).as_ref(),
        )?;

        let serialized =
            extract_optional_value_from_mapping(value, pyo3::intern!(value.py(), "serialized"))?;
        let events =
            extract_optional_value_from_mapping(value, pyo3::intern!(value.py(), "events"))?;
        let tags = extract_optional_value_from_mapping(value, pyo3::intern!(value.py(), "tags"))?;

        let session_id = extract_string_like_or_none(
            get_optional_value_from_mapping(value, pyo3::intern!(value.py(), "session_id"))
                .as_ref(),
        )?;
        let session_name = extract_string_like_or_none(
            get_optional_value_from_mapping(value, pyo3::intern!(value.py(), "session_name"))
                .as_ref(),
        )?;

        Ok(Self(langsmith_tracing_client::client::RunCommon {
            id,
            trace_id,
            dotted_order,
            parent_run_id,
            extra,
            error,
            serialized,
            events,
            tags,
            session_id,
            session_name,
        }))
    }
}

fn extract_attachments(value: &Bound<'_, PyAny>) -> PyResult<Option<Vec<Attachment>>> {
    if value.is_none() {
        return Ok(None);
    }

    let mapping = value.downcast::<PyMapping>()?;

    let size = mapping.len()?;
    if size == 0 {
        return Ok(None);
    }

    let mut attachments = Vec::with_capacity(size);

    for result in mapping.items()?.iter()? {
        let key_value_pair = result?;

        let key_item = key_value_pair.get_item(0)?;
        let key = key_item.extract::<&str>()?;

        // Each value in the attachments dict is a (mime_type, bytes) tuple.
        let value = key_value_pair.get_item(1)?;
        let value_tuple = value.downcast_exact::<PyTuple>()?;
        let mime_type_value = value_tuple.get_item(0)?;
        let bytes_value = value_tuple.get_item(1)?;

        attachments.push(Attachment {
            // TODO: It's unclear whether the key in the attachments dict is
            //       the `filename`` or the `ref_name`, and where the other one is coming from.
            ref_name: key.to_string(),
            filename: key.to_string(),
            data: bytes_value.extract()?,
            content_type: mime_type_value.extract()?,
        });
    }

    Ok(Some(attachments))
}

/// Get an optional string from a Python `None`, string, or string-like object such as a UUID value.
fn extract_string_like_or_none(value: Option<&Bound<'_, PyAny>>) -> PyResult<Option<String>> {
    match value {
        None => Ok(None),
        Some(val) if val.is_none() => Ok(None),
        Some(val) => extract_string_like(val).map(Option::Some),
    }
}

/// Get a string from a Python string or string-like object, such as a UUID value.
fn extract_string_like(value: &Bound<'_, PyAny>) -> PyResult<String> {
    match value.extract::<String>() {
        Ok(s) => Ok(s),
        Err(e) => {
            // PyO3 doesn't have a Rust-native representation of Python's UUID object yet.
            // However, orjson supports serializing UUID objects, so the easiest way to get
            // a Rust string from a Python UUID object is to serialize the UUID to a JSON string
            // and then parse out the string.
            let Ok(buffer) = serialization::dumps(value.as_ptr()) else {
                // orjson failed to deserialize the object. The fact that orjson is involved
                // is an internal implementation detail, so return the original error instead.
                // It looks like this:
                // `'SomeType' object cannot be converted to 'PyString'`
                return Err(e);
            };

            let content = CStr::from_bytes_until_nul(&buffer)
                .expect("not a valid C string, this should never happen")
                .to_str()
                .expect("not a valid UTF-8 string, this should never happen");

            // orjson serialized buffers are null-terminated, so strip the trailing
            // If the remaining value didn't start or end with a quote, it wasn't string-like.
            // It might have been a number, dict, or list -- none of those are legal here.
            // Raise the original error again, for the same reason as above.
            let string_content =
                content.strip_prefix('"').and_then(|s| s.strip_suffix('"')).ok_or(e)?.to_string();
            Ok(string_content)
        }
    }
}

fn extract_time_value(value: &Bound<'_, PyAny>) -> PyResult<TimeValue> {
    if let Ok(string) = value.extract::<String>() {
        return Ok(TimeValue::String(string));
    }

    let datetime = value.downcast::<PyDateTime>()?;
    let isoformat =
        datetime.call_method0(pyo3::intern!(value.py(), "isoformat"))?.extract::<String>()?;
    Ok(TimeValue::String(isoformat))
}

fn get_optional_value_from_mapping<'py>(
    mapping: &Bound<'py, PyAny>,
    key: &Bound<'py, PyString>,
) -> Option<Bound<'py, PyAny>> {
    mapping.get_item(key).ok()
}

fn serialize_optional_dict_value(
    mapping: &Bound<'_, PyAny>,
    key: &Bound<'_, PyString>,
) -> PyResult<Option<Vec<u8>>> {
    match mapping.get_item(key) {
        Ok(value) => {
            if value.is_none() {
                return Ok(None);
            }
            serialization::dumps(value.as_ptr())
                .map(Option::Some)
                .map_err(TracingClientError::new_err)
        }
        Err(_) => Ok(None),
    }
}

// TODO: `Option<Value>` seems suspect as a type, since `Value` can be null already.
//       It might be unnecessarily large and slowing us down for no reason.
fn extract_optional_value_from_mapping(
    mapping: &Bound<'_, PyAny>,
    key: &Bound<'_, PyString>,
) -> PyResult<Option<serde_json::Value>> {
    match mapping.get_item(key) {
        Ok(value) => {
            if value.is_none() {
                return Ok(None);
            }
            extract_value(&value).map(Option::Some)
        }
        Err(_) => Ok(None),
    }
}

fn extract_value(value: &Bound<'_, PyAny>) -> PyResult<serde_json::Value> {
    if value.is_none() {
        Ok(serde_json::Value::Null)
    } else if let Ok(number) = value.extract::<i64>() {
        Ok(number.into())
    } else if let Ok(number) = value.extract::<u64>() {
        Ok(number.into())
    } else if let Ok(float) = value.extract::<f64>() {
        Ok(serde_json::Number::from_f64(float).map(serde_json::Value::from).unwrap_or_default())
    } else if let Ok(string) = value.extract::<&str>() {
        Ok(string.into())
    } else if let Ok(bool) = value.extract::<bool>() {
        Ok(bool.into())
    } else if let Ok(sequence) = value.downcast::<PySequence>() {
        let mut array = Vec::with_capacity(sequence.len()?);

        for elem in sequence.iter()? {
            array.push(extract_value(&elem?)?);
        }

        Ok(serde_json::Value::Array(array))
    } else if let Ok(mapping) = value.downcast::<PyMapping>() {
        let mut dict = serde_json::Map::with_capacity(mapping.len()?);

        for result in mapping.items()?.iter()? {
            let key_value_pair = result?;

            let key_item = key_value_pair.get_item(0)?;
            let value = extract_value(&key_value_pair.get_item(1)?)?;

            // We error on non-string-like keys here.
            let key = extract_string_like(&key_item)?;
            dict.insert(key, value);
        }

        Ok(dict.into())
    } else if let Ok(string_like) = extract_string_like(value) {
        // This allows us to support Python `UUID` objects by serializing them to strings.
        Ok(string_like.into())
    } else {
        unreachable!("failed to convert python data {value} to sonic_rs::Value")
    }
}

#[cfg(test)]
mod tests {
    use crate::test_infra::with_python_interpreter;
    use pyo3::{prelude::*, types::PyDict};

    #[pyfunction]
    fn extract_uuid(uuid_value: &Bound<'_, PyAny>, string_value: &str) {
        let extracted = super::extract_string_like(uuid_value).expect("extraction failed");
        assert_eq!(extracted.as_str(), string_value);
    }

    #[test]
    fn test_uuid_value_extraction() {
        fn inner(py: Python<'_>) -> PyResult<()> {
            // This call only works correctly "the first time".
            // We use `cargo-nextest` to ensure we run each test in its own process.
            // Otherwise, tests will suffer unpredictable errors.
            orjson::init_typerefs();

            // Create a new test module.
            let test_module = PyModule::new_bound(py, "test_module")?;
            test_module.add_function(pyo3::wrap_pyfunction!(extract_uuid, &test_module)?)?;

            // Get `sys.modules`, then insert our module into it.
            let sys = PyModule::import_bound(py, "sys")?;
            let py_modules: Bound<'_, PyDict> = sys.getattr("modules")?.downcast_into()?;
            py_modules.set_item("test_module", test_module)?;

            // Now we can import and run our python code.
            let python_code = "\
import uuid
import test_module

uuid_to_test = uuid.uuid4()

test_module.extract_uuid(uuid_to_test, str(uuid_to_test))
            ";
            Python::run_bound(py, python_code, None, None)?;

            Ok(())
        }

        with_python_interpreter(inner).expect("encountered an unexpected error")
    }

    /// Just to ensure that running multiple tests works fine.
    /// If Python or orjson are initialized more than once per process,
    /// either this test or another test will fail.
    #[test]
    fn other_test() {
        test_uuid_value_extraction();
    }
}
