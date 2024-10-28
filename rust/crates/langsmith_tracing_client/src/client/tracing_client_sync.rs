use std::sync::mpsc::{self, Sender, Receiver};
use std::thread;
use crate::client::errors::TracingClientError;
use crate::client::processor_sync::RunProcessor;
use crate::client::run::{QueuedRun, RunEventBytes};
use crate::client::run::{RunCreateExtended, RunUpdateExtended};
use reqwest::header::HeaderMap;
use std::time::Duration;
use std::sync::{Arc, Mutex};

#[derive(Clone)]
pub struct ClientConfig {
    pub endpoint: String,
    pub queue_capacity: usize,
    pub batch_size: usize,
    pub batch_timeout: Duration,
    pub headers: Option<HeaderMap>,
    pub num_worker_threads: usize,
}

pub struct TracingClient {
    sender: Sender<QueuedRun>,
    handles: Vec<thread::JoinHandle<()>>, // Handles to worker threads
}

impl TracingClient {
    pub fn new(config: ClientConfig) -> Result<Self, TracingClientError> {
        let (sender, receiver) = mpsc::channel::<QueuedRun>();
        let receiver = Arc::new(Mutex::new(receiver));

        let mut handles = Vec::new();

        for _ in 0..config.num_worker_threads {
            let worker_receiver = Arc::clone(&receiver);
            let worker_config = config.clone();

            let handle = thread::spawn(move || {
                let processor = RunProcessor::new(worker_receiver, worker_config);
                processor.run();
            });

            handles.push(handle);
        }

        Ok(Self { sender, handles })
    }

    pub fn submit_run_create(
        &self,
        run: RunCreateExtended,
    ) -> Result<(), TracingClientError> {
        let queued_run = QueuedRun::Create(run);

        self.sender
            .send(queued_run)
            .map_err(|_| TracingClientError::QueueFull)
    }

    // Similar methods for submit_run_update and submit_run_bytes

    pub fn submit_run_bytes(
        &self,
        run_bytes: RunEventBytes,
    ) -> Result<(), TracingClientError> {
        let queued_run = QueuedRun::RunBytes(run_bytes);

        self.sender
            .send(queued_run)
            .map_err(|_| TracingClientError::QueueFull)
    }

    pub fn submit_run_update(
        &self,
        run: RunUpdateExtended,
    ) -> Result<(), TracingClientError> {
        let queued_run = QueuedRun::Update(run);

        self.sender
            .send(queued_run)
            .map_err(|_| TracingClientError::QueueFull)
    }

    pub fn shutdown(self) -> Result<(), TracingClientError> {
        // Send a Shutdown message to each worker thread
        for _ in &self.handles {
            self.sender
                .send(QueuedRun::Shutdown)
                .map_err(|_| TracingClientError::QueueFull)?;
        }

        // Wait for all worker threads to finish
        for handle in self.handles {
            handle.join().unwrap();
        }

        Ok(())
    }
}