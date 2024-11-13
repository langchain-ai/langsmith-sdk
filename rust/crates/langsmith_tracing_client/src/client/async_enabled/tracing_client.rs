use std::time::Duration;

use reqwest::header::HeaderMap;
use tokio::sync::mpsc::{self, Sender};
use tokio::task::JoinHandle;

use super::processor::RunProcessor;
use crate::client::errors::TracingClientError;
use crate::client::run::{QueuedRun, RunEventBytes};
use crate::client::run::{RunCreateExtended, RunUpdateExtended};

pub struct ClientConfig {
    pub endpoint: String,
    pub queue_capacity: usize,
    pub batch_size: usize,
    pub batch_timeout: Duration,
    pub headers: Option<HeaderMap>,
}

pub struct TracingClient {
    sender: Sender<QueuedRun>,
    handle: JoinHandle<Result<(), TracingClientError>>,
}

impl TracingClient {
    pub fn new(config: ClientConfig) -> Result<Self, TracingClientError> {
        let (sender, receiver) = mpsc::channel(config.queue_capacity);

        let processor = RunProcessor::new(receiver, config);

        let handle = tokio::spawn(async move {
            let result = processor.run().await;
            if let Err(e) = &result {
                eprintln!("RunProcessor exited with error: {}", e);
            }
            result
        });

        Ok(Self { sender, handle })
    }

    pub async fn submit_run_create(
        &self,
        run: RunCreateExtended,
    ) -> Result<(), TracingClientError> {
        let queued_run = QueuedRun::Create(run);

        self.sender.send(queued_run).await.map_err(|_| TracingClientError::QueueFull)
    }

    pub async fn submit_run_update(
        &self,
        run: RunUpdateExtended,
    ) -> Result<(), TracingClientError> {
        let queued_run = QueuedRun::Update(run);

        self.sender.send(queued_run).await.map_err(|_| TracingClientError::QueueFull)
    }

    pub async fn submit_run_bytes(&self, run: RunEventBytes) -> Result<(), TracingClientError> {
        let queued_run = QueuedRun::RunBytes(run);

        self.sender.send(queued_run).await.map_err(|_| TracingClientError::QueueFull)
    }

    pub async fn shutdown(self) -> Result<(), TracingClientError> {
        self.sender.send(QueuedRun::Shutdown).await.map_err(|_| TracingClientError::QueueFull)?;

        self.handle.await.unwrap()
    }
}
