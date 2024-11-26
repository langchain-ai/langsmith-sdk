use std::sync::mpsc::{self, Receiver, Sender};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;

use reqwest::header::{HeaderMap, HeaderValue};

use super::processor::RunProcessor;
use crate::client::errors::TracingClientError;
use crate::client::run::{QueuedRun, RunEventBytes};
use crate::client::run::{RunCreateExtended, RunUpdateExtended};

#[derive(Clone)]
pub struct ClientConfig {
    pub endpoint: String,
    pub api_key: String,
    pub queue_capacity: usize,
    pub batch_size: usize,
    pub batch_timeout: Duration,
    pub headers: Option<HeaderMap>,
    pub num_worker_threads: usize,
}

pub struct TracingClient {
    sender: Sender<QueuedRun>,
    drain: Mutex<Receiver<()>>,
    handles: Vec<thread::JoinHandle<()>>, // Handles to worker threads
}

impl TracingClient {
    pub fn new(mut config: ClientConfig) -> Result<Self, TracingClientError> {
        let (sender, receiver) = mpsc::channel::<QueuedRun>();
        let (drain_sender, drain_receiver) = mpsc::channel::<()>();
        let receiver = Arc::new(Mutex::new(receiver));

        // Ensure our headers include the API key.
        config.headers.get_or_insert_with(Default::default).append(
            "X-API-KEY",
            HeaderValue::from_str(&config.api_key).expect("failed to convert API key into header"),
        );

        // We're going to share the config across threads.
        // It's immutable from this point onward, so Arc it for efficiency.
        let config = Arc::from(config);

        let mut handles = Vec::new();

        for _ in 0..config.num_worker_threads {
            let worker_receiver = Arc::clone(&receiver);
            let worker_config = Arc::clone(&config);
            let cloned_drain_sender = drain_sender.clone();

            let handle = thread::spawn(move || {
                let processor =
                    RunProcessor::new(worker_receiver, cloned_drain_sender, worker_config);
                processor.run().expect("run failed");
            });

            handles.push(handle);
        }

        Ok(Self { sender, drain: drain_receiver.into(), handles })
    }

    pub fn submit_run_create(&self, run: RunCreateExtended) -> Result<(), TracingClientError> {
        let queued_run = QueuedRun::Create(run);

        self.sender.send(queued_run).map_err(|_| TracingClientError::QueueFull)
    }

    // Similar methods for submit_run_update and submit_run_bytes

    pub fn submit_run_bytes(&self, run_bytes: RunEventBytes) -> Result<(), TracingClientError> {
        let queued_run = QueuedRun::RunBytes(run_bytes);

        self.sender.send(queued_run).map_err(|_| TracingClientError::QueueFull)
    }

    pub fn submit_run_update(&self, run: RunUpdateExtended) -> Result<(), TracingClientError> {
        let queued_run = QueuedRun::Update(run);

        self.sender.send(queued_run).map_err(|_| TracingClientError::QueueFull)
    }

    pub fn drain(&self) -> Result<(), TracingClientError> {
        for _ in &self.handles {
            self.sender.send(QueuedRun::Drain).map_err(|_| TracingClientError::QueueFull)?;
        }

        let drain_guard = self.drain.lock().expect("locking failed");
        for _ in &self.handles {
            drain_guard.recv().expect("failed to receive drained message");
        }
        drop(drain_guard);

        Ok(())
    }

    pub fn shutdown(self) -> Result<(), TracingClientError> {
        // Send a Shutdown message to each worker thread
        for _ in &self.handles {
            self.sender.send(QueuedRun::Shutdown).map_err(|_| TracingClientError::QueueFull)?;
        }

        // Wait for all worker threads to finish
        for handle in self.handles {
            handle.join().unwrap();
        }

        Ok(())
    }
}
