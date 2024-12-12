use std::collections::HashMap;
use std::sync::mpsc::{Receiver, Sender};
use std::sync::{mpsc, Arc, Mutex};
use std::time::{Duration, Instant};

use rayon::iter::{IntoParallelIterator, ParallelIterator};
use reqwest::blocking::multipart::{Form, Part};
use serde_json::to_vec;

use super::tracing_client::ClientConfig;
use crate::client::errors::TracingClientError;
use crate::client::run::{Attachment, QueuedRun};
use crate::client::run::{RunCreateExtended, RunUpdateExtended};

pub struct RunProcessor {
    receiver: Arc<Mutex<Receiver<QueuedRun>>>,
    drain_sender: Sender<()>,
    config: Arc<ClientConfig>,
    http_client: reqwest::blocking::Client,
}

impl RunProcessor {
    pub(crate) fn new(
        receiver: Arc<Mutex<Receiver<QueuedRun>>>,
        drain_sender: Sender<()>,
        config: Arc<ClientConfig>,
    ) -> Self {
        let http_client = reqwest::blocking::Client::new();

        Self { receiver, drain_sender, http_client, config }
    }

    pub(crate) fn run(&self) -> Result<(), TracingClientError> {
        let mut buffer = Vec::new();
        let batch_timeout = self.config.batch_timeout;
        let batch_size = self.config.batch_size;
        let mut last_send_time = Instant::now();

        loop {
            let queued_run = {
                let receiver = self.receiver.lock().unwrap();
                receiver.recv_timeout(Duration::from_millis(100))
            };

            match queued_run {
                Ok(queued_run) => match queued_run {
                    QueuedRun::Shutdown => {
                        if !buffer.is_empty() {
                            self.send_and_clear_buffer(&mut buffer)?;
                        }
                        break;
                    }
                    QueuedRun::Drain => {
                        if !buffer.is_empty() {
                            self.send_and_clear_buffer(&mut buffer)?;
                        }

                        self.drain_sender.send(()).expect("drain_sender should never fail");
                        break;
                    }
                    _ => {
                        buffer.push(queued_run);
                        if buffer.len() >= batch_size {
                            self.send_and_clear_buffer(&mut buffer)?;
                            last_send_time = Instant::now();
                        }
                    }
                },
                Err(mpsc::RecvTimeoutError::Timeout) => {
                    if !buffer.is_empty() && last_send_time.elapsed() >= batch_timeout {
                        self.send_and_clear_buffer(&mut buffer)?;
                        last_send_time = Instant::now();
                    }
                }
                Err(mpsc::RecvTimeoutError::Disconnected) => {
                    if !buffer.is_empty() {
                        self.send_and_clear_buffer(&mut buffer)?;
                    }
                    break;
                }
            }
        }

        Ok(())
    }

    fn send_and_clear_buffer(&self, buffer: &mut Vec<QueuedRun>) -> Result<(), TracingClientError> {
        if let Err(e) = self.send_batch(std::mem::take(buffer)) {
            // todo: retry logic?
            eprintln!("Error sending batch: {}", e);
        }
        Ok(())
    }

    // If we have a `QueuedRun::Create` and `QueuedRun::Update` for the same run ID in the batch,
    // combine the update data into the create so we can send just one operation instead of two.
    fn combine_batch_operations(batch: Vec<QueuedRun>) -> Vec<QueuedRun> {
        let mut output = Vec::with_capacity(batch.len());
        let mut id_to_index = HashMap::with_capacity(batch.len());

        for queued_run in batch {
            match queued_run {
                QueuedRun::Create(ref run_create_extended) => {
                    // Record the `Create` operation's ID and index,
                    // in case we need to modify it later.
                    let RunCreateExtended { run_create, .. } = run_create_extended;
                    let run_id = run_create.common.id.clone();
                    let index = output.len();
                    id_to_index.insert(run_id, index);
                    output.push(queued_run);
                }
                QueuedRun::Update(run_update_extended) => {
                    let run_id = run_update_extended.run_update.common.id.as_str();
                    if let Some(create_index) = id_to_index.get(run_id) {
                        // This `run_id` matches a `Create` in this batch.
                        // Merge the `Update` data into the `Create` and
                        // drop the separate `Update` operation from the batch.
                        let RunUpdateExtended { run_update, io, attachments } = run_update_extended;
                        let QueuedRun::Create(matching_create) = &mut output[*create_index] else {
                            panic!("index {create_index} did not point to a Create operation in {output:?}");
                        };
                        debug_assert_eq!(
                            run_update.common.id, matching_create.run_create.common.id,
                            "Create operation at index {create_index} did not have expected ID {}: {matching_create:?}",
                            run_update.common.id,
                        );

                        matching_create.run_create.common.merge(run_update.common);
                        matching_create.run_create.end_time = Some(run_update.end_time);
                        matching_create.io.merge(io);
                        if let Some(mut _existing_attachments) =
                            matching_create.attachments.as_mut()
                        {
                            unimplemented!("figure out how to merge attachments -- in Python they are a dict but here they are a Vec");
                        } else {
                            matching_create.attachments = attachments;
                        }
                    } else {
                        // No matching `Create` operations for this `Update`, add it as-is.
                        output.push(QueuedRun::Update(run_update_extended));
                    }
                }
                // Allow other operations to pass through unchanged.
                _ => output.push(queued_run),
            }
        }

        output
    }

    #[expect(unused_variables)]
    fn send_batch(&self, batch: Vec<QueuedRun>) -> Result<(), TracingClientError> {
        //println!("Handling a batch of {} runs", batch.len());
        let start_send_batch = tokio::time::Instant::now();
        let mut json_data = Vec::new();
        let mut attachment_parts = Vec::new();

        let batch = Self::combine_batch_operations(batch);

        let start_iter = Instant::now();
        for queued_run in batch {
            match queued_run {
                QueuedRun::Create(run_create_extended) => {
                    let RunCreateExtended { run_create, io, attachments } = run_create_extended;
                    let run_id = run_create.common.id.clone();

                    // Collect JSON data
                    json_data.push((
                        format!("post.{}", run_id),
                        to_vec(&run_create).unwrap(), // TODO: get rid of unwrap
                    ));

                    // Ensure that pre-formatted JSON data represented as bytes
                    // doesn't end in trailing null bytes, since we'll be pasting it verbatim
                    // into an HTTP multipart request which carries an explicit length header.
                    if let Some(mut inputs) = io.inputs {
                        if inputs.last() == Some(&0) {
                            inputs.pop().expect("popping trailing null byte failed");
                        }
                        json_data.push((format!("post.{}.inputs", run_id), inputs));
                    }
                    if let Some(mut outputs) = io.outputs {
                        if outputs.last() == Some(&0) {
                            outputs.pop().expect("popping trailing null byte failed");
                        }
                        json_data.push((format!("post.{}.outputs", run_id), outputs));
                    }

                    if let Some(attachments) = attachments {
                        for attachment in attachments {
                            let part_name =
                                format!("attachment.{}.{}", run_id, attachment.ref_name);
                            match self.create_attachment_part(attachment) {
                                Ok(part) => {
                                    attachment_parts.push((part_name, part));
                                }
                                Err(e) => {
                                    eprintln!("Error processing attachment: {}", e);
                                }
                            }
                        }
                    }
                }
                QueuedRun::Update(run_update_extended) => {
                    let RunUpdateExtended { run_update, io, attachments } = run_update_extended;
                    let run_id = run_update.common.id.clone();

                    // Collect JSON data
                    json_data.push((
                        format!("patch.{}", run_id),
                        to_vec(&run_update).unwrap(), // TODO: get rid of unwrap
                    ));

                    // Ensure that pre-formatted JSON data represented as bytes
                    // doesn't end in trailing null bytes, since we'll be pasting it verbatim
                    // into an HTTP multipart request which carries an explicit length header.
                    if let Some(mut outputs) = io.outputs {
                        if outputs.last() == Some(&0) {
                            outputs.pop().expect("popping trailing null byte failed");
                        }
                        json_data.push((format!("patch.{}.outputs", run_id), outputs));
                    }

                    if let Some(attachments) = attachments {
                        for attachment in attachments {
                            let part_name =
                                format!("attachment.{}.{}", run_id, attachment.ref_name);
                            match self.create_attachment_part(attachment) {
                                Ok(part) => {
                                    attachment_parts.push((part_name, part));
                                }
                                Err(e) => {
                                    eprintln!("Error processing attachment: {}", e);
                                }
                            }
                        }
                    }
                }
                QueuedRun::RunBytes(_) => {
                    // TODO: fix this
                    return Err(TracingClientError::UnexpectedShutdown);
                }
                QueuedRun::Drain => {
                    unreachable!("drain message in batch");
                }
                QueuedRun::Shutdown => {
                    return Err(TracingClientError::UnexpectedShutdown);
                }
            }
        }
        //println!("Iterating over batch took {:?}", start_iter.elapsed());

        let start = Instant::now();
        let json_parts = json_data
            .into_par_iter()
            .map(|(part_name, data_bytes)| {
                let part_size = data_bytes.len() as u64;
                let part = Part::bytes(data_bytes)
                    .mime_str(&format!("application/json; length={}", part_size))?;
                Ok::<(String, Part), TracingClientError>((part_name, part))
            })
            .collect::<Result<Vec<_>, TracingClientError>>()?;
        // println!("JSON processing took {:?}", start.elapsed());

        let mut form = Form::new();
        for (part_name, part) in json_parts.into_iter().chain(attachment_parts) {
            form = form.part(part_name, part);
        }

        // send the multipart POST request
        let start_send_batch = Instant::now();
        let response = self
            .http_client
            .post(format!("{}/runs/multipart", self.config.endpoint))
            .multipart(form)
            .headers(self.config.headers.as_ref().cloned().unwrap_or_default())
            .send()?;
        // println!("Sending batch took {:?}", start_send_batch.elapsed());

        if response.status().is_success() {
            Ok(())
        } else {
            Err(TracingClientError::HttpError(response.status()))
        }
    }

    fn create_attachment_part(&self, attachment: Attachment) -> Result<Part, TracingClientError> {
        let part = if let Some(data) = attachment.data {
            let part_size = data.len() as u64;
            Part::bytes(data)
                .file_name(attachment.filename)
                .mime_str(&format!("{}; length={}", &attachment.content_type, part_size))?
        } else {
            let file_path = std::path::Path::new(&attachment.filename);
            let metadata = std::fs::metadata(file_path).map_err(|e| {
                TracingClientError::IoError(format!("Failed to read file metadata: {}", e))
            })?;
            let file_size = metadata.len();
            let file = std::fs::File::open(file_path)
                .map_err(|e| TracingClientError::IoError(format!("Failed to open file: {}", e)))?;

            let file_name = file_path
                .file_name()
                .ok_or_else(|| {
                    TracingClientError::IoError("Failed to extract filename from path".to_string())
                })?
                .to_string_lossy()
                .into_owned();

            Part::reader_with_length(file, file_size)
                .file_name(file_name)
                .mime_str(&format!("{}; length={}", &attachment.content_type, file_size))?
        };

        Ok(part)
    }
}
