use tokio::sync::mpsc::{Receiver};
use tokio::time::{sleep, Instant};
use reqwest::multipart::{Form, Part};
use serde_json::Value;
use crate::client::run::{QueuedRun};
use crate::client::errors::TracingClientError;
use crate::client::tracing_client::ClientConfig;
use crate::client::run::{RunCreateWithAttachments, RunUpdateWithAttachments};

pub(crate) struct RunProcessor {
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
                    buffer.push(queued_run);
                    if buffer.len() >= self.config.batch_size {
                        self.send_and_clear_buffer(&mut buffer).await?;
                        last_send_time = Instant::now();
                    }
                }
                _ = sleep(self.config.batch_timeout) => {
                    if !buffer.is_empty() && last_send_time.elapsed() >= self.config.batch_timeout {
                        self.send_and_clear_buffer(&mut buffer).await?;
                        last_send_time = Instant::now();
                    }
                }
                else => {
                    // Channel closed
                    if !buffer.is_empty() {
                        self.send_and_clear_buffer(&mut buffer).await?;
                    }
                    break;
                }
            }
        }
        Ok(())
    }

    async fn send_and_clear_buffer(&self, buffer: &mut Vec<QueuedRun>) -> Result<(), TracingClientError> {
        if let Err(e) = self.send_batch(buffer).await {
            // Handle error (e.g., log and retry logic)
            eprintln!("Error sending batch: {}", e);
            // Decide whether to drop the buffer or retry
        }
        buffer.clear();
        Ok(())
    }

    async fn send_batch(&self, batch: &[QueuedRun]) -> Result<(), TracingClientError> {
        let mut form = Form::new();

        for queued_run in batch {
            match queued_run {
                QueuedRun::Create(run_create_with_attachments) => {
                    self.add_run_create_to_form(run_create_with_attachments, &mut form)?;
                }
                QueuedRun::Update(run_update_with_attachments) => {
                    self.add_run_update_to_form(run_update_with_attachments, &mut form)?;
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

    fn add_run_create_to_form(
        &self,
        run_with_attachments: &RunCreateWithAttachments,
        form: &mut Form,
    ) -> Result<(), TracingClientError> {
        let run = &run_with_attachments.run_create;
        let run_id = &run.common.id;

        // Serialize the run
        let mut run_json = serde_json::to_value(run)?;
        let inputs = run_json
            .as_object_mut()
            .and_then(|obj| obj.remove("inputs"))
            .unwrap_or(Value::Null);
        let outputs = run_json
            .as_object_mut()
            .and_then(|obj| obj.remove("outputs"))
            .unwrap_or(Value::Null);

        // Add the main run data
        *form = std::mem::take(form).part(
            format!("post.{}", run_id),
            Part::text(run_json.to_string()).mime_str("application/json")?,
        );

        // Add inputs
        *form = std::mem::take(form).part(
            format!("post.{}.inputs", run_id),
            Part::text(inputs.to_string()).mime_str("application/json")?,
        );

        // Add outputs
        *form = std::mem::take(form).part(
            format!("post.{}.outputs", run_id),
            Part::text(outputs.to_string()).mime_str("application/json")?,
        );

        // Add attachments
        for (ref_name, (filename, data)) in &run_with_attachments.attachments {
            *form = std::mem::take(form).part(
                format!("post.{}.attachments.{}", run_id, ref_name),
                Part::bytes(data.clone())
                    .file_name(filename.clone())
                    .mime_str("application/octet-stream")?,
            );
        }

        Ok(())
    }

    fn add_run_update_to_form(
        &self,
        run_with_attachments: &RunUpdateWithAttachments,
        form: &mut Form,
    ) -> Result<(), TracingClientError> {
        let run = &run_with_attachments.run_update;
        let run_id = &run.common.id;

        // Serialize the run
        let mut run_json = serde_json::to_value(run)?;
        let outputs = run_json
            .as_object_mut()
            .and_then(|obj| obj.remove("outputs"))
            .unwrap_or(Value::Null);

        // Add the main run data
        *form = std::mem::take(form).part(
            format!("patch.{}", run_id),
            Part::text(run_json.to_string()).mime_str("application/json")?,
        );

        // Add outputs if present
        if !outputs.is_null() {
            *form = std::mem::take(form).part(
                format!("patch.{}.outputs", run_id),
                Part::text(outputs.to_string()).mime_str("application/json")?,
            );
        }

        // Add attachments
        for (ref_name, (filename, data)) in &run_with_attachments.attachments {
            *form = std::mem::take(form).part(
                format!("patch.{}.attachments.{}", run_id, ref_name),
                Part::bytes(data.clone())
                    .file_name(filename.clone())
                    .mime_str("application/octet-stream")?,
            );
        }

        Ok(())
    }
}
