use tokio::sync::mpsc::{self, Sender};
use std::time::Duration;
use crate::client::run::QueuedRun;
use crate::client::errors::TracingClientError;
use crate::client::run::{RunCreateWithAttachments, RunUpdateWithAttachments};
use crate::client::processor::RunProcessor;

pub struct ClientConfig {
    pub endpoint: String,
    pub queue_capacity: usize,
    pub batch_size: usize,
    pub batch_timeout: Duration,
}

pub struct TracingClient {
    sender: Sender<QueuedRun>,
}

impl TracingClient {
    pub fn new(config: ClientConfig) -> Result<Self, TracingClientError> {
        let (sender, receiver) = mpsc::channel(config.queue_capacity);

        let processor = RunProcessor::new(receiver, config);
        tokio::spawn(async move {
            if let Err(e) = processor.run().await {
                eprintln!("RunProcessor exited with error: {}", e);
            }
        });

        Ok(Self { sender })
    }

    pub async fn submit_run_create(
        &self,
        run: RunCreateWithAttachments,
    ) -> Result<(), TracingClientError> {
        let queued_run = QueuedRun::Create(run);

        // Send the run to the async queue
        self.sender
            .send(queued_run)
            .await
            .map_err(|_| TracingClientError::QueueFull)
    }

    pub async fn submit_run_update(
        &self,
        run: RunUpdateWithAttachments,
    ) -> Result<(), TracingClientError> {
        let queued_run = QueuedRun::Update(run);

        // Send the run to the async queue
        self.sender
            .send(queued_run)
            .await
            .map_err(|_| TracingClientError::QueueFull)
    }
}
