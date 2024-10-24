use crate::client::errors::TracingClientError;
use crate::client::run::{Attachment, QueuedRun};
use crate::client::run::{RunCreateExtended, RunUpdateExtended};
use crate::client::tracing_client::ClientConfig;
use reqwest::multipart::{Form, Part};
use tokio::sync::mpsc::Receiver;
use tokio::time::{sleep, Instant};
use tokio_util::io::ReaderStream;
use futures::stream::{FuturesUnordered, StreamExt};
use tokio::task;

pub struct RunProcessor {
    receiver: Receiver<QueuedRun>,
    http_client: reqwest::Client,
    config: ClientConfig,
}

impl RunProcessor {
    pub(crate) fn new(receiver: Receiver<QueuedRun>, config: ClientConfig) -> Self {
        let http_client = reqwest::Client::new();

        Self {
            receiver,
            http_client,
            config,
        }
    }

    pub(crate) async fn run(mut self) -> Result<(), TracingClientError> {
        let mut buffer = Vec::new();
        let mut last_send_time = Instant::now();

        loop {
            tokio::select! {
                Some(queued_run) = self.receiver.recv() => {
                    match queued_run {
                        QueuedRun::Shutdown => {
                            // println!("shutdown signal received.");
                            if !buffer.is_empty() {
                                // println!("sending remaining buffer before shutdown.");
                                self.send_and_clear_buffer(&mut buffer).await?;
                            }
                            break;
                        },
                        _ => {
                            // println!("received a queued run.");
                            buffer.push(queued_run);
                            if buffer.len() >= self.config.batch_size {
                                // println!("batch size limit, sending batch.");
                                self.send_and_clear_buffer(&mut buffer).await?;
                                last_send_time = Instant::now();
                            }
                        }
                    }
                }
                _ = sleep(self.config.batch_timeout) => {
                    if !buffer.is_empty() && last_send_time.elapsed() >= self.config.batch_timeout {
                        // println!("batch timeout, sending batch.");
                        self.send_and_clear_buffer(&mut buffer).await?;
                        last_send_time = Instant::now();
                    }
                }
                else => {
                    // println!("channel closed.");
                    if !buffer.is_empty() {
                        // println!("sending remaining buffer.");
                        self.send_and_clear_buffer(&mut buffer).await?;
                    }
                    break;
                }
            }
        }
        // println!("exiting loop.");
        Ok(())
    }

    async fn send_and_clear_buffer(
        &self,
        buffer: &mut Vec<QueuedRun>,
    ) -> Result<(), TracingClientError> {
        if let Err(e) = self.send_batch(std::mem::take(buffer)).await {
            // todo: retry logic?
            eprintln!("Error sending batch: {}", e);
        }
        Ok(())
    }

    // async fn send_batch(&self, batch: Vec<QueuedRun>) -> Result<(), TracingClientError> {
    //     let mut form = Form::new();
    //     // git println!("Sending batch of {} runs", batch.len());
    //
    //     for queued_run in batch {
    //         match queued_run {
    //             QueuedRun::Create(run_create_extended) => {
    //                 self.consume_run_create(run_create_extended, &mut form)
    //                     .await?;
    //             }
    //             QueuedRun::Update(run_update_extended) => {
    //                 self.consume_run_update(run_update_extended, &mut form)
    //                     .await?;
    //             }
    //             QueuedRun::Shutdown => {
    //                 return Err(TracingClientError::UnexpectedShutdown);
    //             }
    //         }
    //     }
    //
    //     // Send the multipart POST request
    //     let response = self
    //         .http_client
    //         .post(format!("{}/runs/multipart", self.config.endpoint))
    //         .multipart(form)
    //         .headers(self.config.headers.clone().unwrap_or_default())
    //         .send()
    //         .await?;
    //
    //     if response.status().is_success() {
    //         Ok(())
    //     } else {
    //         Err(TracingClientError::HttpError(response.status()))
    //     }
    // }

    async fn consume_run_create(
        &self,
        run_create_extended: RunCreateExtended,
        form: &mut Form,
    ) -> Result<(), TracingClientError> {
        let RunCreateExtended {
            run_create,
            io,
            attachments,
        } = run_create_extended;
        let run_id = &run_create.common.id;

        // conditionally add the run_create and io parts to the form
        self.add_json_part_to_form(form, format!("post.{}", run_id), &run_create)?;

        if let Some(inputs) = io.inputs {
            self.add_json_part_to_form(form, format!("post.{}.inputs", run_id), &inputs)?;
        }

        if let Some(outputs) = io.outputs {
            self.add_json_part_to_form(form, format!("post.{}.outputs", run_id), &outputs)?;
        }

        if let Some(attachments) = attachments {
            for attachment in attachments {
                self.add_attachment_to_form(form, run_id, attachment)
                    .await?;
            }
        }

        Ok(())
    }

    async fn consume_run_update(
        &self,
        run_update_extended: RunUpdateExtended,
        form: &mut Form,
    ) -> Result<(), TracingClientError> {
        let RunUpdateExtended {
            run_update,
            io,
            attachments,
        } = run_update_extended;
        let run_id = &run_update.common.id;

        self.add_json_part_to_form(form, format!("patch.{}", run_id), &run_update)?;

        if let Some(outputs) = io.outputs {
            self.add_json_part_to_form(form, format!("patch.{}.outputs", run_id), &outputs)?;
        }

        if let Some(attachments) = attachments {
            for attachment in attachments {
                self.add_attachment_to_form(form, run_id, attachment)
                    .await?;
            }
        }

        Ok(())
    }

    fn add_json_part_to_form(
        &self,
        form: &mut Form,
        part_name: String,
        data: &impl serde::Serialize,
    ) -> Result<(), TracingClientError> {
        let data_bytes = serde_json::to_vec(data)?;
        let part_size = data_bytes.len() as u64;
        *form = std::mem::take(form).part(
            part_name,
            Part::bytes(data_bytes).mime_str(&format!("application/json; length={}", part_size))?,
        );
        Ok(())
    }

    async fn add_attachment_to_form(
        &self,
        form: &mut Form,
        run_id: &str,
        attachment: Attachment,
    ) -> Result<(), TracingClientError> {
        let part_name = format!("attachment.{}.{}", run_id, attachment.ref_name);
        if let Some(data) = attachment.data {
            let part_size = data.len() as u64;
            *form = std::mem::take(form).part(
                part_name,
                Part::bytes(data)
                    .file_name(attachment.filename)
                    .mime_str(&format!(
                        "{}; length={}",
                        &attachment.content_type, part_size
                    ))?,
            );
        } else {
            // stream the file from disk to avoid loading the entire file into memory
            let file_path = std::path::Path::new(&attachment.filename);
            let metadata = tokio::fs::metadata(file_path).await.map_err(|e| {
                TracingClientError::IoError(format!("Failed to read file metadata: {}", e))
            })?;
            let file_size = metadata.len();
            let file = tokio::fs::File::open(file_path)
                .await
                .map_err(|e| TracingClientError::IoError(format!("Failed to open file: {}", e)))?;
            let stream = ReaderStream::new(file);
            let body = reqwest::Body::wrap_stream(stream);

            // extract filename from path
            let file_name = file_path
                .file_name()
                .ok_or_else(|| {
                    TracingClientError::IoError("Failed to extract filename from path".to_string())
                })?
                .to_string_lossy()
                .into_owned();

            let part = Part::stream_with_length(body, file_size)
                .file_name(file_name)
                .mime_str(&format!(
                    "{}; length={}",
                    &attachment.content_type, file_size
                ))?;

            *form = std::mem::take(form).part(part_name, part);
        }
        Ok(())
    }

    async fn send_batch(&self, batch: Vec<QueuedRun>) -> Result<(), TracingClientError> {
        let mut form = Form::new();

        // Use FuturesUnordered to process the batch concurrently
        let futures = batch.into_iter().map(|queued_run| async {
            let parts = match queued_run {
                QueuedRun::Create(run_create_extended) => {
                    self.process_run_create(run_create_extended).await?
                }
                QueuedRun::Update(run_update_extended) => {
                    self.process_run_update(run_update_extended).await?
                }
                QueuedRun::Shutdown => return Err(TracingClientError::UnexpectedShutdown),
            };
            Ok::<_, TracingClientError>(parts)
        });

        // Collect all parts from concurrent processing
        let results = FuturesUnordered::from_iter(futures)
            .collect::<Vec<Result<Vec<(String, Part)>, TracingClientError>>>()
            .await;

        // Assemble the form with all collected parts
        for result in results {
            match result {
                Ok(parts) => {
                    for (part_name, part) in parts {
                        form = form.part(part_name, part);
                    }
                }
                Err(e) => {
                    eprintln!("Error processing queued run: {}", e);
                    // Handle errors as needed, possibly retry or abort
                }
            }
        }

        // Send the multipart POST request
        let response = self
            .http_client
            .post(format!("{}/runs/multipart", self.config.endpoint))
            .multipart(form)
            .headers(self.config.headers.clone().unwrap_or_default())
            .send()
            .await?;

        if response.status().is_success() {
            Ok(())
        } else {
            Err(TracingClientError::HttpError(response.status()))
        }
    }

    async fn process_run_create(
        &self,
        run_create_extended: RunCreateExtended,
    ) -> Result<Vec<(String, Part)>, TracingClientError> {
        let RunCreateExtended {
            run_create,
            io,
            attachments,
        } = run_create_extended;
        let run_id = &run_create.common.id;

        let mut parts = Vec::new();

        // Process run_create
        parts.push(
            self.create_json_part(format!("post.{}", run_id), &run_create)
                .await?,
        );

        // Process inputs and outputs if available
        if let Some(inputs) = io.inputs {
            parts.push(
                self.create_json_part(format!("post.{}.inputs", run_id), &inputs)
                    .await?,
            );
        }

        if let Some(outputs) = io.outputs {
            parts.push(
                self.create_json_part(format!("post.{}.outputs", run_id), &outputs)
                    .await?,
            );
        }

        // Process attachments if any
        if let Some(attachments) = attachments {
            for attachment in attachments {
                parts.push(
                    self.create_attachment_part(run_id, attachment)
                        .await?,
                );
            }
        }

        Ok(parts)
    }

    async fn process_run_update(
        &self,
        run_update_extended: RunUpdateExtended,
    ) -> Result<Vec<(String, Part)>, TracingClientError> {
        let RunUpdateExtended {
            run_update,
            io,
            attachments,
        } = run_update_extended;
        let run_id = &run_update.common.id;

        let mut parts = Vec::new();

        // Process run_update
        parts.push(
            self.create_json_part(format!("patch.{}", run_id), &run_update)
                .await?,
        );

        // Process outputs if available
        if let Some(outputs) = io.outputs {
            parts.push(
                self.create_json_part(format!("patch.{}.outputs", run_id), &outputs)
                    .await?,
            );
        }

        // Process attachments if any
        if let Some(attachments) = attachments {
            for attachment in attachments {
                parts.push(
                    self.create_attachment_part(&run_id, attachment)
                        .await?,
                );
            }
        }

        Ok(parts)
    }

    async fn create_json_part(
        &self,
        part_name: String,
        data: &impl serde::Serialize,
    ) -> Result<(String, Part), TracingClientError> {
        // TODO Offload serialization to a blocking thread?
        let data_bytes = serde_json::to_vec(data)?;
        let part_size = data_bytes.len() as u64;
        let part = Part::bytes(data_bytes)
            .mime_str(&format!("application/json; length={}", part_size))?;
        Ok((part_name, part))
    }

    async fn create_attachment_part(
        &self,
        run_id: &str,
        attachment: Attachment,
    ) -> Result<(String, Part), TracingClientError> {
        let part_name = format!("attachment.{}.{}", run_id, attachment.ref_name);

        let part = if let Some(data) = attachment.data {
            let part_size = data.len() as u64;
            Part::bytes(data)
                .file_name(attachment.filename)
                .mime_str(&format!("{}; length={}", &attachment.content_type, part_size))?
        } else {
            // Stream the file from disk
            let file_path = std::path::Path::new(&attachment.filename);
            let metadata = tokio::fs::metadata(file_path).await.map_err(|e| {
                TracingClientError::IoError(format!("Failed to read file metadata: {}", e))
            })?;
            let file_size = metadata.len();
            let file = tokio::fs::File::open(file_path).await.map_err(|e| {
                TracingClientError::IoError(format!("Failed to open file: {}", e))
            })?;
            let stream = ReaderStream::new(file);
            let body = reqwest::Body::wrap_stream(stream);

            let file_name = file_path
                .file_name()
                .ok_or_else(|| {
                    TracingClientError::IoError("Failed to extract filename from path".to_string())
                })?
                .to_string_lossy()
                .into_owned();

            Part::stream_with_length(body, file_size)
                .file_name(file_name)
                .mime_str(&format!(
                    "{}; length={}",
                    &attachment.content_type, file_size
                ))?
        };

        Ok((part_name, part))
    }
}
