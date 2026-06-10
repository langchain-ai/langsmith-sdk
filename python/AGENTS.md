# Instructions for code modifications in the Python SDK

This folder contains the Python version of the LangSmith SDK.

When modifying code in this library, **always** run the following commands from this directory before submitting a pull request:

```
make format
make lint
make tests
```

These commands format the code, run static analysis, and execute the test suite respectively.

To run a particular test file or pass custom pytest arguments, set the `TEST` environment variable. For example:

```bash
TEST=tests/unit_tests/test_client.py make tests
```

Any pytest options may be included inside the `TEST` variable.

## Notes

- The project uses `uv` for dependency management and the Makefile commands will automatically run inside the `uv` environment.
- `make tests` sets some environment variables (such as disabling network access) for reliability. If a test requires network access, adjust it accordingly.

## Conventions

### Constructing request URLs

Do not hardcode a leading `/v1` (or other `api_url`-dependent prefix) into request
paths. `LANGSMITH_ENDPOINT` may already include `/api/v1`, so a hardcoded
`/v1/...` produces a duplicated `/api/v1/v1/...` path and 404s.

For platform endpoints, build the path with the existing helpers so the `/v1`
prefix is only added when the configured `api_url` does not already end in `/v1`:

- `langsmith._internal._hub.platform_hub_path(api_url)` for hub (agent/skill) repos.
- `_platform_path(api_url, path)` / `_dataset_examples_path(api_url, dataset_id)`
  in `langsmith/client.py` for other platform paths.

When adding a new platform endpoint, follow the same pattern instead of inlining
`/v1/platform/...`.
