# langsmith-pyo3

Python bindings for LangSmith internals.

## Development

Relies on `maturin` and `uvx`.

To bootstrap, run:
```
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
