use crate::client::errors::TracingClientError;
use crate::client::run::{Attachment, EventType, QueuedRun, RunEventBytes};
use crate::client::run::{RunCreateExtended, RunUpdateExtended};
use crate::client::tracing_client_sync::ClientConfig;
use futures::stream::{FuturesUnordered, StreamExt};
use reqwest::blocking::multipart::{Form, Part};
use rayon::iter::{IntoParallelIterator, ParallelIterator};
use sonic_rs::{to_vec, to_value};
use std::sync::{mpsc, Arc, Mutex};
use std::sync::mpsc::Receiver;
use std::time::{Duration, Instant};

pub struct RunProcessor {
    receiver: Arc<Mutex<Receiver<QueuedRun>>>,
    http_client: reqwest::blocking::Client,
    config: ClientConfig,
}

impl RunProcessor {
    pub(crate) fn new(receiver: Arc<Mutex<Receiver<QueuedRun>>>, config: ClientConfig) -> Self {
        let http_client = reqwest::blocking::Client::new();

        Self {
            receiver,
            http_client,
            config,
        }
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

    fn send_and_clear_buffer(
        &self,
        buffer: &mut Vec<QueuedRun>,
    ) -> Result<(), TracingClientError> {
        if let Err(e) = self.send_batch(std::mem::take(buffer)) {
            // todo: retry logic?
            eprintln!("Error sending batch: {}", e);
        }
        Ok(())
    }

    fn send_batch(&self, batch: Vec<QueuedRun>) -> Result<(), TracingClientError> {
        //println!("Handling a batch of {} runs", batch.len());
        let start_send_batch = tokio::time::Instant::now();
        let mut json_data = Vec::new();
        let mut attachment_parts = Vec::new();

        let start_iter = Instant::now();
        for queued_run in batch {
            match queued_run {
                QueuedRun::Create(run_create_extended) => {
                    let RunCreateExtended {
                        run_create,
                        io,
                        attachments,
                    } = run_create_extended;
                    let run_id = run_create.common.id.clone();

                    // Collect JSON data
                    json_data.push((
                        format!("post.{}", run_id),
                        to_value(&run_create).unwrap(), // TODO: get rid of unwrap
                    ));

                    if let Some(inputs) = io.inputs {
                        json_data.push((format!("post.{}.inputs", run_id), inputs));
                    }

                    if let Some(outputs) = io.outputs {
                        json_data.push((format!("post.{}.outputs", run_id), outputs));
                    }

                    if let Some(attachments) = attachments {
                        for attachment in attachments {
                            let part_name = format!("attachment.{}.{}", run_id, attachment.ref_name);
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
                    let RunUpdateExtended {
                        run_update,
                        io,
                        attachments,
                    } = run_update_extended;
                    let run_id = run_update.common.id.clone();

                    // Collect JSON data
                    json_data.push((
                        format!("patch.{}", run_id),
                        to_value(&run_update).unwrap(), // TODO: get rid of unwrap
                    ));

                    if let Some(outputs) = io.outputs {
                        json_data.push((format!("patch.{}.outputs", run_id), outputs));
                    }

                    if let Some(attachments) = attachments {
                        for attachment in attachments {
                            let part_name = format!("attachment.{}.{}", run_id, attachment.ref_name);
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
                QueuedRun::Shutdown => {
                    return Err(TracingClientError::UnexpectedShutdown);
                }
            }
        }
        //println!("Iterating over batch took {:?}", start_iter.elapsed());

        let start = Instant::now();
        let json_parts = json_data
            .into_iter()
            .map(|(part_name, value)| {
                let data_bytes = to_vec(&value).unwrap(); // TODO: get rid of unwrap
                let part_size = data_bytes.len() as u64;
                let part = Part::bytes(data_bytes)
                    .mime_str(&format!("application/json; length={}", part_size))?;
                Ok::<(String, Part), TracingClientError>((part_name, part))
            })
            .collect::<Result<Vec<_>, TracingClientError>>()?;
        //println!("JSON processing took {:?}", start.elapsed());

        let mut form = Form::new();
        for (part_name, part) in json_parts.into_iter().chain(attachment_parts) {
            form = form.part(part_name, part);
        }

        // send the multipart POST request
        let response = self
            .http_client
            .post(format!("{}/runs/multipart", self.config.endpoint))
            .multipart(form)
            .headers(self.config.headers.clone().unwrap_or_default())
            .send()?;

        // println!("Sending batch took {:?}", start_send_batch.elapsed());
        if response.status().is_success() {
            Ok(())
        } else {
            Err(TracingClientError::HttpError(response.status()))
        }
    }

    fn create_attachment_part(
        &self,
        attachment: Attachment,
    ) -> Result<Part, TracingClientError> {
        let part = if let Some(data) = attachment.data {
            let part_size = data.len() as u64;
            Part::bytes(data)
                .file_name(attachment.filename)
                .mime_str(&format!(
                    "{}; length={}",
                    &attachment.content_type, part_size
                ))?
        } else {
            let file_path = std::path::Path::new(&attachment.filename);
            let metadata = std::fs::metadata(file_path).map_err(|e| {
                TracingClientError::IoError(format!("Failed to read file metadata: {}", e))
            })?;
            let file_size = metadata.len();
            let file = std::fs::File::open(file_path).map_err(|e| {
                TracingClientError::IoError(format!("Failed to open file: {}", e))
            })?;

            let file_name = file_path
                .file_name()
                .ok_or_else(|| {
                    TracingClientError::IoError("Failed to extract filename from path".to_string())
                })?
                .to_string_lossy()
                .into_owned();


            Part::reader_with_length(file, file_size)
                .file_name(file_name)
                .mime_str(&format!(
                    "{}; length={}",
                    &attachment.content_type, file_size
                ))?
        };

        Ok(part)
    }

}