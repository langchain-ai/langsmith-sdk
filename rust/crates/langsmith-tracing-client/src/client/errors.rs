use thiserror::Error;

#[derive(Error, Debug)]
pub enum TracingClientError {
    #[error("Queue is full")]
    QueueFull,

    #[error("Serialization error: {0}")]
    SerializationError(#[from] serde_json::Error),

    #[error("HTTP error: {0}")]
    HttpError(reqwest::StatusCode),

    #[error("Request error: {0}")]
    RequestError(#[from] reqwest::Error),

    #[error("Channel send error")]
    ChannelSendError,

    #[error("Unexpected shutdown")]
    UnexpectedShutdown,

    #[error("IO error")]
    IoError(String),
}

impl From<std::io::Error> for TracingClientError {
    fn from(value: std::io::Error) -> Self {
        Self::IoError(value.to_string())
    }
}
