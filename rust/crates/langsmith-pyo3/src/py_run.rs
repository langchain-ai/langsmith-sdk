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
        let reference_example_id =
            extract_optional_mapping_key(value, pyo3::intern!(value.py(), "reference_example_id"))?;

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
pub(crate) struct RunCommon(langsmith_tracing_client::client::RunCommon);

impl RunCommon {
    #[inline]
    pub(crate) fn into_inner(self) -> langsmith_tracing_client::client::RunCommon {
        self.0
    }
}

impl FromPyObject<'_> for RunCommon {
    fn extract_bound(value: &Bound<'_, PyAny>) -> PyResult<Self> {
        let id = value.get_item(pyo3::intern!(value.py(), "id"))?.extract()?;
        let trace_id = value.get_item(pyo3::intern!(value.py(), "trace_id"))?.extract()?;

        let dotted_order = value.get_item(pyo3::intern!(value.py(), "dotted_order"))?.extract()?;
        let parent_run_id =
            extract_optional_mapping_key(value, pyo3::intern!(value.py(), "parent_run_id"))?;

        let extra = extract_optional_value_from_mapping(value, pyo3::intern!(value.py(), "extra"))?;

        let error = extract_optional_mapping_key(value, pyo3::intern!(value.py(), "error"))?;

        let serialized =
            extract_optional_value_from_mapping(value, pyo3::intern!(value.py(), "serialized"))?;
        let events =
            extract_optional_value_from_mapping(value, pyo3::intern!(value.py(), "events"))?;
        let tags = extract_optional_value_from_mapping(value, pyo3::intern!(value.py(), "tags"))?;

        let session_id =
            extract_optional_mapping_key(value, pyo3::intern!(value.py(), "session_id"))?;
        let session_name =
            extract_optional_mapping_key(value, pyo3::intern!(value.py(), "session_name"))?;

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

fn extract_optional_mapping_key<'py, T: FromPyObject<'py>>(
    mapping: &Bound<'py, PyAny>,
    key: &Bound<'py, PyString>,
) -> PyResult<Option<T>> {
    match mapping.get_item(key) {
        Ok(x) => Ok(Some(x.extract()?)),
        Err(_) => Ok(None),
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
) -> PyResult<Option<sonic_rs::Value>> {
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

fn extract_value(value: &Bound<'_, PyAny>) -> PyResult<sonic_rs::Value> {
    if value.is_none() {
        Ok(sonic_rs::Value::new())
    } else if let Ok(number) = value.extract::<i64>() {
        Ok(number.into())
    } else if let Ok(number) = value.extract::<u64>() {
        Ok(number.into())
    } else if let Ok(float) = value.extract::<f64>() {
        Ok(sonic_rs::Number::try_from(float).map(sonic_rs::Value::from).unwrap_or_default())
    } else if let Ok(string) = value.extract::<&str>() {
        Ok(string.into())
    } else if let Ok(bool) = value.extract::<bool>() {
        Ok(bool.into())
    } else if let Ok(sequence) = value.downcast::<PySequence>() {
        let mut array = sonic_rs::Array::with_capacity(sequence.len()?);

        for elem in sequence.iter()? {
            array.push(extract_value(&elem?)?);
        }

        Ok(array.into_value())
    } else if let Ok(mapping) = value.downcast::<PyMapping>() {
        let mut dict = sonic_rs::Object::with_capacity(mapping.len()?);

        for result in mapping.items()?.iter()? {
            let key_value_pair = result?;

            // Sonic wants all object keys to be strings,
            // so we'll error on non-string dict keys.
            let key_item = key_value_pair.get_item(0)?;
            let value = extract_value(&key_value_pair.get_item(1)?)?;

            // sonic_rs 0.3.14 doesn't allow `K: ?Sized` for the `&K` key,
            // so we can't extract `&str` and have to get a `String` instead.
            let key = key_item.extract::<String>()?;
            dict.insert(&key, value);
        }

        Ok(dict.into_value())
    } else {
        unreachable!("failed to convert python data {value} to sonic_rs::Value")
    }
}
