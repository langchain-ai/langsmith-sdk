"""Test utilities in the LangSmith server."""
from langsmith.cli.main import _dumps_yaml


def test__dumps_yaml() -> None:
    d = {
        "region": "us",
        "tunnels": {"langchain": {"addr": "langchain-backend:8000", "proto": "http"}},
        "version": "2",
    }
    expected = """region: us
tunnels:
  langchain:
    addr: langchain-backend:8000
    proto: http
version: 2"""
    result = _dumps_yaml(d)
    assert result == expected
    expected += "\nauthtoken: 123"
    d["authtoken"] = "123"
    result = _dumps_yaml(d)
    assert result == expected
