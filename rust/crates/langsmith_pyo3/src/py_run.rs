use langsmith_tracing_client::client::{Attachment, RunIO, TimeValue};
use pyo3::{
    types::{PyAnyMethods as _, PyDateTime, PyMapping, PySequence, PyTuple},
    Bound, FromPyObject, PyAny, PyResult,
};

// TODO: consider interning all the strings here

// TODO: consider replacing `String` with `Box<str>`, and `Vec<T>` with `Box<[T]>`,
//       since none of them are growable and we can make them more compact in memory

#[derive(Debug)]
pub(crate) struct RunCreateExtended(langsmith_tracing_client::client::RunCreateExtended);

impl RunCreateExtended {
    #[inline]
    fn into_inner(self) -> langsmith_tracing_client::client::RunCreateExtended {
        self.0
    }
}

impl FromPyObject<'_> for RunCreateExtended {
    fn extract_bound(value: &Bound<'_, PyAny>) -> PyResult<Self> {
        let run_create = value.extract::<RunCreate>()?.into_inner();

        let attachments = {
            if let Ok(attachments_value) = value.get_item("attachments") {
                extract_attachments(&attachments_value)?
            } else {
                None
            }
        };

        let io = RunIO {
            inputs: extract_optional_value(&value.get_item("inputs")?)?,
            outputs: extract_optional_value(&value.get_item("outputs")?)?,
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

    for pair in mapping.iter()? {
        let pair_data = pair?;
        let tuple = pair_data.downcast_exact::<PyTuple>()?;

        let key_item = tuple.get_item(0)?;
        let key = key_item.extract::<&str>()?;

        // Each value in the attachments dict is a (mime_type, bytes) tuple.
        let value = tuple.get_item(1)?;
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
    fn into_inner(self) -> langsmith_tracing_client::client::RunCreate {
        self.0
    }
}

impl FromPyObject<'_> for RunCreate {
    fn extract_bound(value: &Bound<'_, PyAny>) -> PyResult<Self> {
        let common = RunCommon::extract_bound(value)?.into_inner();
        let name = value.get_item("name")?.extract::<String>()?;

        let start_time = extract_isoformat_time_value(value.get_item("start_time")?.downcast()?)?;

        let end_time = {
            let py_end_time = value.get_item("end_time")?;
            if py_end_time.is_none() {
                None
            } else {
                Some(extract_isoformat_time_value(py_end_time.downcast()?)?)
            }
        };

        let run_type = value.get_item("run_type")?.extract::<String>()?;
        let reference_example_id = value.get_item("key")?.extract::<Option<String>>()?;

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
    fn into_inner(self) -> langsmith_tracing_client::client::RunCommon {
        self.0
    }
}

impl FromPyObject<'_> for RunCommon {
    fn extract_bound(value: &Bound<'_, PyAny>) -> PyResult<Self> {
        let id = value.get_item("id")?.extract()?;
        let trace_id = value.get_item("trace_id")?.extract()?;

        let dotted_order = value.get_item("dotted_order")?.extract()?;
        let parent_run_id = value.get_item("parent_run_id")?.extract()?;

        let extra = extract_optional_value(&value.get_item("extra")?)?;

        let error = value.get_item("error")?.extract()?;

        let serialized = extract_optional_value(&value.get_item("serialized")?)?;
        let events = extract_optional_value(&value.get_item("events")?)?;
        let tags = extract_optional_value(&value.get_item("tags")?)?;

        let session_id = value.get_item("session_id")?.extract()?;
        let session_name = value.get_item("session_name")?.extract()?;

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

fn extract_isoformat_time_value(value: &Bound<'_, PyDateTime>) -> PyResult<TimeValue> {
    let string_value = value.call_method0("isoformat")?.extract::<String>()?;

    Ok(TimeValue::String(string_value))
}

// TODO: `Option<Value>` seems suspect as a type, since `Value` can be null already.
//       It might be unnecessarily large and slowing us down for no reason.
fn extract_optional_value(value: &Bound<'_, PyAny>) -> PyResult<Option<sonic_rs::Value>> {
    if value.is_none() {
        return Ok(None);
    }
    extract_value(value).map(Option::Some)
}

fn extract_value(value: &Bound<'_, PyAny>) -> PyResult<sonic_rs::Value> {
    if value.is_none() {
        Ok(sonic_rs::Value::new())
    } else if let Ok(number) = value.extract::<i64>() {
        Ok(number.into())
    } else if let Ok(number) = value.extract::<u64>() {
        Ok(number.into())
    } else if let Ok(float) = value.extract::<f64>() {
        Ok(sonic_rs::Value::new_f64(float).unwrap_or_default())
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

        for pair in mapping.iter()? {
            let pair_data = pair?;
            let tuple = pair_data.downcast_exact::<PyTuple>()?;

            // Sonic wants all object keys to be strings,
            // so we'll error on non-string dict keys.
            let key_item = tuple.get_item(0)?;
            let key = key_item.extract::<&str>()?;
            let value = extract_value(&tuple.get_item(1)?)?;
            dict.insert(key, value);
        }

        Ok(dict.into_value())
    } else {
        unreachable!("failed to convert python data {value} to sonic_rs::Value")
    }
}
