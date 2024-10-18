use langsmith_tracing_client::minimal_test;
use tokio::runtime::Runtime;

#[test]
fn test_tokio_runtime() {
    let rt = Runtime::new().unwrap();
    rt.block_on(async {
        minimal_test().await;
    });
}
