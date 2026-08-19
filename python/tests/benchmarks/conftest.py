"""Benchmark-wide setup.

Every benchmark runs fully offline: the LangSmith client is always built with a
mocked `requests.Session`, and the environment is pinned so nothing depends on
the machine the benchmark runs on.
"""

import os

os.environ["LANGSMITH_API_KEY"] = "fake-api-key-for-benchmarks"
os.environ["LANGSMITH_ENDPOINT"] = "http://localhost:1984"
os.environ["LANGSMITH_TRACING"] = "false"
# Keep the wire format deterministic across benchmark runs.
os.environ["LANGSMITH_RUN_COMPRESSION_LEVEL"] = "1"
os.environ["LANGSMITH_RUN_COMPRESSION_THREADS"] = "0"
