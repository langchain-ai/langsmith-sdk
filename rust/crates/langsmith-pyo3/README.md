# langsmith-pyo3

Python bindings for LangSmith internals.

## Development

Requires a recent Rust build. `rustup upgrade stable` should do it.

Relies on `maturin`, `uvx`, and `cargo-nextest`.

To bootstrap, run:
```
cargo install --locked cargo-nextest
uv venv --seed
source .venv/bin/activate
pip install patchelf
```

To develop, run `uvx maturin develop` which will build and install the Rust code directly into the current virtualenv.

To build wheels, run `uvx maturin build`.

To make performance-optimized builds, append `--release` to either command.

To run install these bindings into another virtualenv (e.g. to run benchmarks),
activate that virtualenv, then `cd` to this directory and run `uvx maturin develop --release`.
When that command completes, the virtualenv will have an optimized build
of `langsmith-pyo3` installed.

### Testing

Do not run `cargo test`, *IT WILL NOT WORK*. You will get an inscrutable linker error like `undefined symbol: _Py_CheckFunctionResult` or `linker command failed with exit code 1`.

Instead, run: `cargo nextest run --no-default-features`

TL;DR on why:
- This package assumes it's compiled into a Python library, but Rust tests don't run a Python environment. That won't work.
- The `--no-default-features` flag is configured to include Python into the built code, which Rust tests will then run. (Full details [here](https://pyo3.rs/v0.13.2/faq#i-cant-run-cargo-test-im-having-linker-issues-like-symbol-not-found-or-undefined-reference-to-_pyexc_systemerror).)
- Rust tests run in parallel, but Python and `orjson` assume they own the entire process. That won't work.
- `cargo nextest` lets us run each test in its own process, satisfying Python's and `orjson`'s assumptions.
