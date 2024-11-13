# langsmith_pyo3

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

TODO: Move the `.github/workflows` CI workflow for testing the maturin build to the top level of the repo.
