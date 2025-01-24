use std::sync::Mutex;

use pyo3::{PyResult, Python};

// Python assumes it's the "only Python in the process",
// so embedding multiple Python interpreters in the same process will fail
// with obscure and difficult-to-debug errors.
//
// By default, `cargo test` runs tests on multiple threads.
// If multiple threads want to run a Python-related test,
// we have to make sure they don't attempt to initialize
// multiple Python interpreters concurrently.
//
// We use this mutex to coordinate creating Python interpreters.
static PYTHON_INTERPRETER: Mutex<()> = Mutex::new(());

pub(crate) fn with_python_interpreter<F>(inner: F) -> Result<(), String>
where
    F: for<'py> FnOnce(Python<'py>) -> PyResult<()>,
{
    let lock = PYTHON_INTERPRETER.lock().expect("lock was poisoned");

    // SAFETY:
    // - We have acquired the interpreter mutex.
    //   No other Python interpreters can be in existence.
    // - We do not return any Python-owned data, since we turn the `PyResult<()>`'s error case
    //   into a Rust string.
    let outcome = unsafe {
        pyo3::with_embedded_python_interpreter(move |py| {
            std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| -> Result<(), String> {
                let outcome = inner(py);
                outcome.map_err(|e| e.to_string())
            }))
        })
    };
    drop(lock);

    match outcome {
        Ok(r) => r,
        Err(panicked) => {
            // Running the closure caused a panic,
            // so resume panicking now that we've cleaned up Python.
            std::panic::resume_unwind(panicked)
        }
    }
}
