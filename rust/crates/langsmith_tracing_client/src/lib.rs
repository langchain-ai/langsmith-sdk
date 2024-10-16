use tokio::time::{sleep, Duration};

pub async fn minimal_test() {
    println!("Starting async task...");
    sleep(Duration::from_secs(1)).await;
    println!("Async task complete!");
}
