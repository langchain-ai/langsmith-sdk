"""Tests for config.py - auth, client factory, headers."""

from __future__ import annotations

import os
from unittest.mock import patch

import click
import pytest

from langsmith.cli.config import get_api_headers, get_api_url, get_client


def _make_ctx(api_key="test-key", api_url="https://api.smith.langchain.com"):
    """Create a minimal Click context with obj dict."""
    ctx = click.Context(click.Command("test"))
    ctx.obj = {"api_key": api_key, "api_url": api_url}
    return ctx


class TestGetClient:
    @patch("langsmith.cli.config.Client")
    def test_returns_client(self, mock_client_cls):
        ctx = _make_ctx(api_key="lsv2_pt_abc123")
        client = get_client(ctx)
        mock_client_cls.assert_called_once_with(
            api_key="lsv2_pt_abc123",
            api_url="https://api.smith.langchain.com",
        )
        assert client == mock_client_cls.return_value

    @patch("langsmith.cli.config.Client")
    def test_custom_api_url(self, mock_client_cls):
        ctx = _make_ctx(api_key="key", api_url="https://custom.langsmith.com")
        get_client(ctx)
        mock_client_cls.assert_called_once_with(
            api_key="key",
            api_url="https://custom.langsmith.com",
        )

    def test_missing_api_key_exits(self):
        ctx = _make_ctx(api_key=None)
        with pytest.raises(SystemExit):
            get_client(ctx)


class TestGetApiHeaders:
    def test_basic_headers(self):
        ctx = _make_ctx(api_key="my-key")
        headers = get_api_headers(ctx)
        assert headers["x-api-key"] == "my-key"
        assert headers["Content-Type"] == "application/json"
        assert "x-tenant-id" not in headers

    @patch.dict(os.environ, {"LANGSMITH_WORKSPACE_ID": "ws-123"})
    def test_workspace_id_header(self):
        ctx = _make_ctx(api_key="my-key")
        headers = get_api_headers(ctx)
        assert headers["x-tenant-id"] == "ws-123"

    def test_missing_api_key_exits(self):
        ctx = _make_ctx(api_key=None)
        with pytest.raises(SystemExit):
            get_api_headers(ctx)


class TestGetApiUrl:
    def test_returns_url_from_context(self):
        ctx = _make_ctx(api_url="https://custom.example.com")
        assert get_api_url(ctx) == "https://custom.example.com"

    def test_default_url(self):
        ctx = click.Context(click.Command("test"))
        ctx.obj = {}
        assert get_api_url(ctx) == "https://api.smith.langchain.com"
