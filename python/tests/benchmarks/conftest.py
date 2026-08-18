"""Shared fixtures for the CodSpeed benchmark suite.

The benchmarks never touch the network: every client is built on top of a mocked
session that immediately returns an "accepted" response, so what is measured is
purely the SDK work (serialization, batching, multipart encoding, compression).
"""

import os
from unittest.mock import Mock

import pytest

from langsmith.client import Client

# Make sure nothing in the SDK tries to pick up an ambient configuration, and that
# the measured work is deterministic: tracing is on (otherwise `@traceable` is a
# no-op) and trace compression happens inline instead of on a worker thread.
os.environ["LANGSMITH_API_KEY"] = "fake-api-key"
os.environ["LANGSMITH_TRACING"] = "true"
os.environ["LANGSMITH_RUN_COMPRESSION_THREADS"] = "0"
os.environ.pop("LANGSMITH_ENDPOINT", None)
os.environ.pop("LANGSMITH_PROJECT", None)


def make_mock_session() -> Mock:
    """Build a session that accepts every request without doing any I/O."""
    session = Mock()
    response = Mock()
    response.status_code = 202
    response.text = "Accepted"
    response.json.return_value = {"status": "success"}
    session.request.return_value = response
    return session


@pytest.fixture
def client() -> Client:
    """A client with background batching disabled (runs are sent inline)."""
    return Client(
        api_url="https://api.smith.langchain.com",
        api_key="fake-api-key",
        session=make_mock_session(),
        auto_batch_tracing=False,
        info={
            "version": "0.1.0",
            "batch_ingest_config": {"use_multipart_endpoint": True},
        },
    )
