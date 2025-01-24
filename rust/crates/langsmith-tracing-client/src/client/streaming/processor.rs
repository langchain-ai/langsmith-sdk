use std::{
    path::Path,
    sync::Arc,
    time::{Duration, Instant},
};

use crate::client::{run::QueuedRun, RunCreateExtended, RunUpdateExtended, TracingClientError};

use super::{multipart_writer::StreamingMultipart, ClientConfig};

pub struct RunProcessor {
    receiver: crossbeam_channel::Receiver<QueuedRun>,
    drain_sender: crossbeam_channel::Sender<()>,
    http_client: reqwest::blocking::Client,
    config: Arc<ClientConfig>,
    compression_workers: u32,
    multipart_stream: StreamingMultipart<zstd::stream::write::Encoder<'static, Vec<u8>>>,
}

impl RunProcessor {
    fn make_stream(
        compression_level: i32,
        n_workers: u32,
    ) -> StreamingMultipart<zstd::stream::write::Encoder<'static, Vec<u8>>> {
        // Unfortunately, the `reqwest` API doesn't seem to allow reusing this buffer
        // since `Into<Body>` requires `&'static [u8]` and can't take an arbitrary lifetime.
        let buffer = Vec::with_capacity(8192);

        let mut compressor = zstd::stream::write::Encoder::new(buffer, compression_level)
            .expect("failed to construct compressor");
        compressor.multithread(n_workers).expect("failed to enable multithreading in compressor");

        StreamingMultipart::new(compressor)
    }

    pub(crate) fn new(
        receiver: crossbeam_channel::Receiver<QueuedRun>,
        drain_sender: crossbeam_channel::Sender<()>,
        config: Arc<ClientConfig>,
    ) -> Self {
        let http_client = reqwest::blocking::Client::new();

        // We want to use as many threads as available cores to compress data.
        // However, we have to be mindful of special values in the zstd library:
        // - A setting of `0` here means "use the current thread only."
        // - A setting of `1` means "use a separate thread, but only one."
        //
        // `1` isn't a useful setting for us, so turn `1` into `0` while
        // keeping higher numbers the same.
        let compression_workers = match std::thread::available_parallelism() {
            Ok(num) => {
                if num.get() == 1 {
                    0
                } else {
                    num.get() as u32
                }
            }
            Err(_) => {
                // We failed to query the available number of cores.
                // Use only the current single thread, to be safe.
                0
            }
        };

        let multipart_stream = Self::make_stream(config.compression_level, compression_workers);

        Self { receiver, drain_sender, http_client, config, compression_workers, multipart_stream }
    }

    pub(crate) fn run(&mut self) -> Result<(), TracingClientError> {
        let mut last_send_time = Instant::now();

        loop {
            let queued_run = { self.receiver.recv_timeout(Duration::from_millis(100)) };

            match queued_run {
                Ok(queued_run) => match queued_run {
                    QueuedRun::Shutdown => {
                        self.send_pending_data()?;
                        break;
                    }
                    QueuedRun::Drain => {
                        self.send_pending_data()?;
                        self.drain_sender.send(()).expect("drain_sender should never fail");
                        break;
                    }
                    _ => {
                        self.process_new_data(queued_run)?;
                        if self.multipart_stream.get_ref().get_ref().len()
                            >= self.config.send_at_batch_size
                        {
                            self.send_pending_data()?;
                            last_send_time = Instant::now();
                        }
                    }
                },
                Err(crossbeam_channel::RecvTimeoutError::Timeout) => {
                    if self.multipart_stream.is_empty()
                        && last_send_time.elapsed() >= self.config.send_at_batch_time
                    {
                        self.send_pending_data()?;
                        last_send_time = Instant::now();
                    }
                }
                Err(crossbeam_channel::RecvTimeoutError::Disconnected) => {
                    // The sending part of the channel was dropped, so no further data is incoming.
                    self.send_pending_data()?;
                    break;
                }
            }
        }

        Ok(())
    }

    fn send_pending_data(&mut self) -> Result<(), TracingClientError> {
        if self.multipart_stream.is_empty() {
            return Ok(());
        }

        // Start a new compression stream for future payload data, and replace the current one.
        let next_stream =
            Self::make_stream(self.config.compression_level, self.compression_workers);
        let compressed_stream = std::mem::replace(&mut self.multipart_stream, next_stream);

        let content_type =
            format!("multipart/form-data; boundary={}", compressed_stream.boundary());
        let compressed_payload = compressed_stream.finish()?.finish()?;

        let response = self
            .http_client
            .post(format!("{}/runs/multipart", self.config.endpoint))
            .headers(self.config.headers.as_ref().cloned().unwrap_or_default())
            .header(http::header::CONTENT_TYPE, content_type)
            .header(http::header::CONTENT_ENCODING, "zstd")
            .body(compressed_payload)
            .send()?;

        if response.status().is_success() {
            Ok(())
        } else {
            let status = response.status();
            Err(TracingClientError::HttpError(status))
        }
    }

    fn process_new_data(&mut self, queued_run: QueuedRun) -> Result<(), TracingClientError> {
        match queued_run {
            QueuedRun::Create(run_create_extended) => {
                let RunCreateExtended { run_create, io, attachments } = run_create_extended;
                let run_id = run_create.common.id.clone();

                // Collect JSON data.
                let part_name = format!("post.{}", run_id);
                let serialized = serde_json::to_vec(&run_create).expect("serialization_failed");
                self.multipart_stream.json_part(&part_name, &serialized)?;

                // Ensure that pre-formatted JSON data represented as bytes
                // doesn't end in trailing null bytes, since they are unnecessary
                // in HTTP multipart requests.
                if let Some(mut inputs) = io.inputs {
                    if inputs.last() == Some(&0) {
                        inputs.pop().expect("popping trailing null byte failed");
                    }
                    let part_name = format!("post.{}.inputs", run_id);
                    self.multipart_stream.json_part(&part_name, &inputs)?;
                }
                if let Some(mut outputs) = io.outputs {
                    if outputs.last() == Some(&0) {
                        outputs.pop().expect("popping trailing null byte failed");
                    }
                    let part_name = format!("post.{}.outputs", run_id);
                    self.multipart_stream.json_part(&part_name, &outputs)?;
                }

                if let Some(attachments) = attachments {
                    for attachment in attachments {
                        let part_name = format!("attachment.{}.{}", run_id, attachment.ref_name);
                        if let Some(data) = attachment.data {
                            self.multipart_stream.file_part_from_bytes(
                                &part_name,
                                &attachment.ref_name,
                                &attachment.content_type,
                                &data,
                            )?;
                        } else {
                            self.multipart_stream.file_part_from_path(
                                &part_name,
                                &attachment.ref_name,
                                &attachment.content_type,
                                Path::new(&attachment.filename),
                            )?;
                        }
                    }
                }

                Ok(())
            }
            QueuedRun::Update(run_update_extended) => {
                let RunUpdateExtended { run_update, io, attachments } = run_update_extended;
                let run_id = run_update.common.id.clone();

                // Collect JSON data.
                let part_name = format!("patch.{}", run_id);
                let serialized = serde_json::to_vec(&run_update).expect("serialization_failed");
                self.multipart_stream.json_part(&part_name, &serialized)?;

                // Ensure that pre-formatted JSON data represented as bytes
                // doesn't end in trailing null bytes, since they are unnecessary
                // in HTTP multipart requests.
                if let Some(mut outputs) = io.outputs {
                    if outputs.last() == Some(&0) {
                        outputs.pop().expect("popping trailing null byte failed");
                    }

                    let part_name = format!("patch.{}.outputs", run_id);
                    self.multipart_stream.json_part(&part_name, &outputs)?;
                }

                if let Some(attachments) = attachments {
                    for attachment in attachments {
                        let part_name = format!("attachment.{}.{}", run_id, attachment.ref_name);
                        if let Some(data) = attachment.data {
                            self.multipart_stream.file_part_from_bytes(
                                &part_name,
                                &attachment.ref_name,
                                &attachment.content_type,
                                &data,
                            )?;
                        } else {
                            self.multipart_stream.file_part_from_path(
                                &part_name,
                                &attachment.ref_name,
                                &attachment.content_type,
                                Path::new(&attachment.filename),
                            )?;
                        }
                    }
                }

                Ok(())
            }
            QueuedRun::Drain => {
                unreachable!("drain message that wasn't handled earlier");
            }
            QueuedRun::Shutdown => Err(TracingClientError::UnexpectedShutdown),
        }
    }
}
