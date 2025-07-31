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
