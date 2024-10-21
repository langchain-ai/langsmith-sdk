use crate::client::errors::TracingClientError;
use crate::client::run::QueuedRun;
use crate::client::run::{RunCreateExtended, RunUpdateExtended};
use crate::client::tracing_client::ClientConfig;
use reqwest::multipart::{Form, Part};
use serde_json::Value;
use tokio::sync::mpsc::Receiver;
use tokio::time::{sleep, Instant};
use tokio_util::io::ReaderStream;

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
                            println!("shutdown signal received.");
                            if !buffer.is_empty() {
                                println!("sending remaining buffer before shutdown.");
                                self.send_and_clear_buffer(&mut buffer).await?;
                            }
                            break;
                        },
                        _ => {
                            println!("received a queued run.");
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
                        println!("batch timeout, sending batch.");
                        self.send_and_clear_buffer(&mut buffer).await?;
                        last_send_time = Instant::now();
                    }
                }
                else => {
                    println!("channel closed.");
                    if !buffer.is_empty() {
                        println!("sending remaining buffer.");
                        self.send_and_clear_buffer(&mut buffer).await?;
                    }
                    break;
                }
            }
        }
        println!("exiting loop.");
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
        buffer.clear();
        Ok(())
    }

    async fn send_batch(&self, batch: Vec<QueuedRun>) -> Result<(), TracingClientError> {
        let mut form = Form::new();

        for queued_run in batch {
            match queued_run {
                QueuedRun::Create(run_create_extended) => {
                    self.add_run_create_to_form(run_create_extended, &mut form)
                        .await?;
                }
                QueuedRun::Update(run_update_extended) => {
                    self.add_run_update_to_form(run_update_extended, &mut form)
                        .await?;
                }
                QueuedRun::Shutdown => {
                    return Err(TracingClientError::UnexpectedShutdown);
                }
            }
        }

        // Send the multipart POST request
        let response = self
            .http_client
            .post(&self.config.endpoint)
            .multipart(form)
            .send()
            .await?;

        if response.status().is_success() {
            Ok(())
        } else {
            Err(TracingClientError::HttpError(response.status()))
        }
    }

    async fn add_run_create_to_form(
        &self,
        run_create_extended: RunCreateExtended,
        form: &mut Form,
    ) -> Result<(), TracingClientError> {
        let run = run_create_extended.run_create;
        let run_id = &run.common.id;
        let inputs = run_create_extended.io.inputs;
        let outputs = run_create_extended.io.outputs;

        let inputs_bytes = serde_json::to_vec(&inputs)?;
        let outputs_bytes = serde_json::to_vec(&outputs)?;
        let run_bytes = serde_json::to_vec(&run)?;

        *form = std::mem::take(form).part(
            format!("post.{}", run_id),
            Part::bytes(run_bytes).mime_str("application/json")?,
        );

        *form = std::mem::take(form).part(
            format!("post.{}.inputs", run_id),
            Part::bytes(inputs_bytes).mime_str("application/json")?,
        );

        *form = std::mem::take(form).part(
            format!("post.{}.outputs", run_id),
            Part::bytes(outputs_bytes).mime_str("application/json")?,
        );

        for attachment in run_create_extended.attachments {
            let ref_name = attachment.ref_name;
            let filename = attachment.filename;
            let data = attachment.data;
            let content_type = attachment.content_type;

            let part_name = format!("post.{}.attachments.{}", run_id, ref_name);
            if let Some(data) = data {
                *form = std::mem::take(form).part(
                    part_name,
                    Part::bytes(data)
                        .file_name(filename)
                        .mime_str(&content_type)?,
                );
            } else {
                // read the file from disk and stream it to avoid loading the entire file into memory
                let file_path = std::path::Path::new(&filename);
                let metadata = tokio::fs::metadata(file_path).await.map_err(|e| {
                    TracingClientError::IoError(format!("Failed to read file metadata: {}", e))
                })?;
                let file_size = metadata.len();
                let file = tokio::fs::File::open(file_path).await.map_err(|e| {
                    TracingClientError::IoError(format!("Failed to open file: {}", e))
                })?;
                let stream = ReaderStream::new(file);
                let body = reqwest::Body::wrap_stream(stream);

                // Extract just the last component of the file path
                let file_name = file_path
                    .file_name()
                    .ok_or_else(|| {
                        TracingClientError::IoError(
                            "Failed to extract filename from path".to_string(),
                        )
                    })?
                    .to_string_lossy();

                let part = Part::stream_with_length(body, file_size)
                    .file_name(file_name.into_owned())
                    .mime_str(&content_type)?;

                *form = std::mem::take(form).part(part_name, part);
            }
        }

        Ok(())
    }

    async fn add_run_update_to_form(
        &self,
        run_with_attachments: RunUpdateExtended,
        form: &mut Form,
    ) -> Result<(), TracingClientError> {
        let run = &run_with_attachments.run_update;
        let run_id = &run.common.id;

        let mut run_json = serde_json::to_value(run)?;
        let outputs = run_json
            .as_object_mut()
            .and_then(|obj| obj.remove("outputs"))
            .unwrap_or(Value::Null);

        *form = std::mem::take(form).part(
            format!("patch.{}", run_id),
            Part::text(run_json.to_string()).mime_str("application/json")?,
        );

        if !outputs.is_null() {
            *form = std::mem::take(form).part(
                format!("patch.{}.outputs", run_id),
                Part::text(outputs.to_string()).mime_str("application/json")?,
            );
        }

        for attachment in &run_with_attachments.attachments {
            let ref_name = &attachment.ref_name;
            let filename = &attachment.filename;
            let data = &attachment.data;
            let content_type = &attachment.content_type;

            let part_name = format!("patch.{}.attachments.{}", run_id, ref_name);
            if let Some(data) = data {
                *form = std::mem::take(form).part(
                    part_name,
                    Part::bytes(data.clone())
                        .file_name(filename.clone())
                        .mime_str(content_type)?,
                );
            } else {
                // read the file from disk and stream it to avoid loading the entire file into memory
                let file_path = std::path::Path::new(filename);
                let metadata = tokio::fs::metadata(file_path).await.map_err(|e| {
                    TracingClientError::IoError(format!("Failed to read file metadata: {}", e))
                })?;
                let file_size = metadata.len();
                let file = tokio::fs::File::open(file_path).await.map_err(|e| {
                    TracingClientError::IoError(format!("Failed to open file: {}", e))
                })?;
                let stream = ReaderStream::new(file);
                let body = reqwest::Body::wrap_stream(stream);

                // extract just the last component of the file path
                let file_name = file_path
                    .file_name()
                    .ok_or_else(|| {
                        TracingClientError::IoError(
                            "Failed to extract filename from path".to_string(),
                        )
                    })?
                    .to_string_lossy()
                    .to_string();

                println!("file_name: {:?}", file_name);

                let part = Part::stream_with_length(body, file_size)
                    .file_name(file_name)
                    .mime_str(content_type)?;

                *form = std::mem::take(form).part(part_name, part);
            }
        }

        Ok(())
    }
}
