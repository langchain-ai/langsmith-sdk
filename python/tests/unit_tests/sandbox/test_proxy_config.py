"""Tests for sandbox proxy configuration helpers."""

import json

import pytest
from pytest_httpx import HTTPXMock

from langsmith.sandbox import (
    SandboxClient,
    aws_auth_proxy_config,
    opaque_secret,
    workspace_secret,
)


def test_workspace_secret_wraps_names() -> None:
    assert workspace_secret("AWS_ACCESS_KEY_ID") == {
        "type": "workspace_secret",
        "value": "{AWS_ACCESS_KEY_ID}",
    }
    assert workspace_secret("{AWS_SECRET_ACCESS_KEY}") == {
        "type": "workspace_secret",
        "value": "{AWS_SECRET_ACCESS_KEY}",
    }


@pytest.mark.parametrize("name", ["", "   ", "{}", "{AWS_ACCESS_KEY_ID"])
def test_workspace_secret_rejects_invalid_names(name: str) -> None:
    with pytest.raises(ValueError):
        workspace_secret(name)


def test_opaque_secret_builds_write_only_value() -> None:
    assert opaque_secret("AKIAFAKE") == {
        "type": "opaque",
        "value": "AKIAFAKE",
    }


def test_aws_auth_proxy_config_builds_aws_rule() -> None:
    config = aws_auth_proxy_config(
        access_key_id=workspace_secret("AWS_ACCESS_KEY_ID"),
        secret_access_key=workspace_secret("AWS_SECRET_ACCESS_KEY"),
    )

    assert config == {
        "rules": [
            {
                "name": "aws",
                "type": "aws",
                "enabled": True,
                "aws": {
                    "access_key_id": {
                        "type": "workspace_secret",
                        "value": "{AWS_ACCESS_KEY_ID}",
                    },
                    "secret_access_key": {
                        "type": "workspace_secret",
                        "value": "{AWS_SECRET_ACCESS_KEY}",
                    },
                },
            }
        ]
    }


def test_create_sandbox_forwards_aws_auth_proxy_config(
    httpx_mock: HTTPXMock,
) -> None:
    client = SandboxClient(api_endpoint="http://test-server:8080", max_retries=0)
    httpx_mock.add_response(
        method="POST",
        url="http://test-server:8080/boxes",
        json={"name": "test-sandbox"},
        status_code=201,
    )
    proxy_config = aws_auth_proxy_config(
        access_key_id=workspace_secret("AWS_ACCESS_KEY_ID"),
        secret_access_key=workspace_secret("AWS_SECRET_ACCESS_KEY"),
    )

    client.create_sandbox(snapshot_id="snap-1", proxy_config=proxy_config)

    body = json.loads(httpx_mock.get_request().content)
    assert body["proxy_config"] == proxy_config
    client.close()
