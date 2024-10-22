pub mod client;

use tokio::time::{sleep, Duration};

pub async fn minimal_test() {
    sleep(Duration::from_secs(1)).await;
}
