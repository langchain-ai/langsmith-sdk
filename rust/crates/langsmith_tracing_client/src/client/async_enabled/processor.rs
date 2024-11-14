use futures::stream::{FuturesUnordered, StreamExt};
use rayon::iter::{IntoParallelIterator, ParallelIterator};
use reqwest::multipart::{Form, Part};
use sonic_rs::to_vec;
use tokio::sync::mpsc::Receiver;
use tokio::task;
use tokio::time::{sleep, Instant};
use tokio_util::io::ReaderStream;

use super::tracing_client::ClientConfig;
use crate::client::errors::TracingClientError;
use crate::client::run::{Attachment, EventType, QueuedRun, RunEventBytes};
use crate::client::run::{RunCreateExtended, RunUpdateExtended};

pub struct RunProcessor {
    receiver: Receiver<QueuedRun>,
    http_client: reqwest::Client,
    config: ClientConfig,
}

impl RunProcessor {
    pub(crate) fn new(receiver: Receiver<QueuedRun>, config: ClientConfig) -> Self {
        let http_client = reqwest::Client::new();

        Self { receiver, http_client, config }
    }

    pub(crate) async fn run(mut self) -> Result<(), TracingClientError> {
        let mut buffer = Vec::new();
        let mut last_send_time = Instant::now();

        loop {
            tokio::select! {
                Some(queued_run) = self.receiver.recv() => {
                    match queued_run {
                        QueuedRun::Shutdown => {
                            println!("shutdown signal received.");
                            if !buffer.is_empty() {
                                println!("sending remaining buffer before shutdown.");
                                self.send_and_clear_buffer(&mut buffer).await?;
                            }
                            break;
                        },
                        _ => {
                            // println!("received a queued run.");
                            buffer.push(queued_run);
                            if buffer.len() >= self.config.batch_size {
                                println!("batch size limit, sending batch.");
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
    //     // println!("Sending batch of {} runs", batch.len());
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
    //             QueuedRun::RunBytes(run_event_bytes) => {
    //                 self.consume_run_bytes(run_event_bytes, &mut form).await?;
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

    #[expect(dead_code)]
    async fn consume_run_create(
        &self,
        run_create_extended: RunCreateExtended,
        form: &mut Form,
    ) -> Result<(), TracingClientError> {
        let RunCreateExtended { run_create, io, attachments } = run_create_extended;
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
                self.add_attachment_to_form(form, run_id, attachment).await?;
            }
        }

        Ok(())
    }

    #[expect(dead_code)]
    async fn consume_run_update(
        &self,
        run_update_extended: RunUpdateExtended,
        form: &mut Form,
    ) -> Result<(), TracingClientError> {
        let RunUpdateExtended { run_update, io, attachments } = run_update_extended;
        let run_id = &run_update.common.id;

        self.add_json_part_to_form(form, format!("patch.{}", run_id), &run_update)?;

        if let Some(outputs) = io.outputs {
            self.add_json_part_to_form(form, format!("patch.{}.outputs", run_id), &outputs)?;
        }

        if let Some(attachments) = attachments {
            for attachment in attachments {
                self.add_attachment_to_form(form, run_id, attachment).await?;
            }
        }

        Ok(())
    }

    #[expect(dead_code)]
    async fn consume_run_bytes(
        &self,
        run_event_bytes: RunEventBytes,
        form: &mut Form,
    ) -> Result<(), TracingClientError> {
        let RunEventBytes {
            run_id,
            event_type,
            run_bytes,
            inputs_bytes,
            outputs_bytes,
            attachments,
        } = run_event_bytes;

        let event_type_str = match event_type {
            EventType::Create => "post",
            EventType::Update => "patch",
        };

        let part_size = run_bytes.len() as u64;
        *form = std::mem::take(form).part(
            format!("{}.{}", event_type_str, run_id),
            Part::bytes(run_bytes).mime_str(&format!("application/json; length={}", part_size))?,
        );

        if let Some(inputs_bytes) = inputs_bytes {
            let part_size = inputs_bytes.len() as u64;
            *form = std::mem::take(form).part(
                format!("{}.{}.inputs", event_type_str, run_id),
                Part::bytes(inputs_bytes)
                    .mime_str(&format!("application/json; length={}", part_size))?,
            );
        }

        if let Some(outputs_bytes) = outputs_bytes {
            let part_size = outputs_bytes.len() as u64;
            *form = std::mem::take(form).part(
                format!("{}.{}.outputs", event_type_str, run_id),
                Part::bytes(outputs_bytes)
                    .mime_str(&format!("application/json; length={}", part_size))?,
            );
        }

        if let Some(attachments) = attachments {
            for attachment in attachments {
                self.add_attachment_to_form(form, &run_id, attachment).await?;
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
        let data_bytes = to_vec(data).unwrap(); // TODO: get rid of unwrap
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
                    .mime_str(&format!("{}; length={}", &attachment.content_type, part_size))?,
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
                .mime_str(&format!("{}; length={}", &attachment.content_type, file_size))?;

            *form = std::mem::take(form).part(part_name, part);
        }
        Ok(())
    }

    #[expect(unused_variables)]
    async fn send_batch(&self, batch: Vec<QueuedRun>) -> Result<(), TracingClientError> {
        let start_send_batch = Instant::now();
        let mut json_data = Vec::new();
        let mut attachment_futures = Vec::new();

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

                    if let Some(inputs) = io.inputs {
                        json_data.push((format!("post.{}.inputs", run_id), inputs));
                    }

                    if let Some(outputs) = io.outputs {
                        json_data.push((format!("post.{}.outputs", run_id), outputs));
                    }

                    if let Some(attachments) = attachments {
                        for attachment in attachments {
                            attachment_futures.push((
                                format!("attachment.{}.{}", run_id, attachment.ref_name),
                                self.create_attachment_part(attachment),
                            ));
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

                    if let Some(outputs) = io.outputs {
                        json_data.push((format!("patch.{}.outputs", run_id), outputs));
                    }

                    if let Some(attachments) = attachments {
                        for attachment in attachments {
                            attachment_futures.push((
                                format!("attachment.{}.{}", run_id, attachment.ref_name),
                                self.create_attachment_part(attachment),
                            ));
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

        // println!("Batch processing took {:?}", start_send_batch.elapsed());
        // process JSON serialization in a blocking thread with Rayon parallel iterator
        let start = Instant::now();
        let json_parts = task::spawn_blocking(move || {
            println!("Parallel processing a batch of {} runs", json_data.len());
            let start_time_in_parallel = Instant::now();
            json_data
                .into_par_iter()
                .map(|(part_name, data_bytes)| {
                    let part_size = data_bytes.len() as u64;
                    let part = Part::bytes(data_bytes)
                        .mime_str(&format!("application/json; length={}", part_size))?;
                    Ok::<(String, Part), TracingClientError>((part_name, part))
                })
                .collect::<Result<Vec<_>, TracingClientError>>()
        })
        .await
        .unwrap()?; // TODO: get rid of unwrap
        println!("JSON processing took {:?}", start.elapsed());

        // process attachments asynchronously
        let attachment_parts_results = FuturesUnordered::from_iter(
            attachment_futures.into_iter().map(|(part_name, future)| async {
                let part = future.await?;
                Ok((part_name, part))
            }),
        )
        .collect::<Vec<Result<(String, Part), TracingClientError>>>()
        .await;
        let mut attachment_parts = Vec::new();
        for result in attachment_parts_results {
            match result {
                Ok((part_name, part)) => {
                    attachment_parts.push((part_name, part));
                }
                Err(e) => {
                    eprintln!("Error processing attachment: {}", e);
                }
            }
        }

        // assemble form
        let mut form = Form::new();
        for (part_name, part) in json_parts.into_iter().chain(attachment_parts) {
            form = form.part(part_name, part);
        }

        // println!("Assembling form took {:?}", start.elapsed());

        // send the multipart POST request
        let start_send_batch = std::time::Instant::now();
        let response = self
            .http_client
            .post(format!("{}/runs/multipart", self.config.endpoint))
            .multipart(form)
            .headers(self.config.headers.clone().unwrap_or_default())
            .send()
            .await?;
        println!("Sending batch took {:?}", start_send_batch.elapsed());

        // println!("Sending batch took {:?}", start_send_batch.elapsed());
        if response.status().is_success() {
            Ok(())
        } else {
            Err(TracingClientError::HttpError(response.status()))
        }
    }

    async fn create_attachment_part(
        &self,
        attachment: Attachment,
    ) -> Result<Part, TracingClientError> {
        let part = if let Some(data) = attachment.data {
            let part_size = data.len() as u64;
            Part::bytes(data)
                .file_name(attachment.filename)
                .mime_str(&format!("{}; length={}", &attachment.content_type, part_size))?
        } else {
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

            let file_name = file_path
                .file_name()
                .ok_or_else(|| {
                    TracingClientError::IoError("Failed to extract filename from path".to_string())
                })?
                .to_string_lossy()
                .into_owned();

            Part::stream_with_length(body, file_size)
                .file_name(file_name)
                .mime_str(&format!("{}; length={}", &attachment.content_type, file_size))?
        };

        Ok(part)
    }
}
