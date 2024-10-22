use crate::client::errors::TracingClientError;
use crate::client::run::{Attachment, QueuedRun};
use crate::client::run::{RunCreateExtended, RunUpdateExtended};
use crate::client::tracing_client::ClientConfig;
use reqwest::multipart::{Form, Part};
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
        Ok(())
    }

    async fn send_batch(&self, batch: Vec<QueuedRun>) -> Result<(), TracingClientError> {
        let mut form = Form::new();

        for queued_run in batch {
            match queued_run {
                QueuedRun::Create(run_create_extended) => {
                    self.consume_run_create(run_create_extended, &mut form)
                        .await?;
                }
                QueuedRun::Update(run_update_extended) => {
                    self.consume_run_update(run_update_extended, &mut form)
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

        self.add_json_part_to_form(form, format!("post.{}", run_id), &run_create)?;
        self.add_json_part_to_form(form, format!("post.{}.inputs", run_id), &io.inputs)?;
        self.add_json_part_to_form(form, format!("post.{}.outputs", run_id), &io.outputs)?;

        for attachment in attachments {
            self.add_attachment_to_form(form, "post", run_id, attachment)
                .await?;
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
        self.add_json_part_to_form(form, format!("patch.{}.outputs", run_id), &io.outputs)?;

        for attachment in attachments {
            self.add_attachment_to_form(form, "patch", run_id, attachment)
                .await?;
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
        prefix: &str,
        run_id: &str,
        attachment: Attachment,
    ) -> Result<(), TracingClientError> {
        let part_name = format!("{}.{}.attachments.{}", prefix, run_id, attachment.ref_name);
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
}
