"""Tests for sandbox proxy configuration helpers."""

import json

import pytest
from pytest_httpx import HTTPXMock

import langsmith.sandbox as sandbox_module
from langsmith.sandbox import (
    SandboxClient,
    aws_auth,
    gcp_auth,
    gcs_mount,
    mount_config,
    opaque_secret,
    proxy_config,
    s3_mount,
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


def test_legacy_single_provider_config_helpers_are_not_exported() -> None:
    assert not hasattr(sandbox_module, "aws_auth_proxy_config")
    assert not hasattr(sandbox_module, "aws_auth_proxy_rule")
    assert not hasattr(sandbox_module, "gcp_auth_proxy_config")
    assert not hasattr(sandbox_module, "gcp_auth_proxy_rule")


def test_aws_auth_builds_aws_rule() -> None:
    rule = aws_auth(
        access_key_id=workspace_secret("AWS_ACCESS_KEY_ID"),
        secret_access_key=workspace_secret("AWS_SECRET_ACCESS_KEY"),
    )

    assert rule == {
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


def test_gcp_auth_builds_gcp_rule_with_default_gcs_hosts() -> None:
    rule = gcp_auth(
        service_account_json=workspace_secret("GCP_SERVICE_ACCOUNT_JSON"),
        scopes=["https://www.googleapis.com/auth/devstorage.read_write"],
    )

    assert rule == {
        "name": "gcp",
        "type": "gcp",
        "enabled": True,
        "match_hosts": ["storage.googleapis.com", "www.googleapis.com"],
        "gcp": {
            "service_account_json": {
                "type": "workspace_secret",
                "value": "{GCP_SERVICE_ACCOUNT_JSON}",
            },
            "scopes": ["https://www.googleapis.com/auth/devstorage.read_write"],
        },
    }


def test_proxy_config_composes_multiple_provider_rules() -> None:
    aws_rule = aws_auth(
        access_key_id=workspace_secret("AWS_ACCESS_KEY_ID"),
        secret_access_key=workspace_secret("AWS_SECRET_ACCESS_KEY"),
    )
    gcp_rule = gcp_auth(
        service_account_json=workspace_secret("GCP_SERVICE_ACCOUNT_JSON"),
        scopes=["https://www.googleapis.com/auth/devstorage.read_write"],
        match_hosts=["storage.googleapis.com"],
    )

    assert proxy_config(
        rules=[aws_rule, gcp_rule],
        no_proxy=["metadata.google.internal"],
        access_control={"allow_list": ["*.googleapis.com", "*.amazonaws.com"]},
    ) == {
        "rules": [aws_rule, gcp_rule],
        "no_proxy": ["metadata.google.internal"],
        "access_control": {"allow_list": ["*.googleapis.com", "*.amazonaws.com"]},
    }


def test_mount_config_expands_mounts_and_provider_auth() -> None:
    aws_rule = aws_auth(
        access_key_id=workspace_secret("AWS_ACCESS_KEY_ID"),
        secret_access_key=workspace_secret("AWS_SECRET_ACCESS_KEY"),
    )
    gcp_rule = gcp_auth(
        service_account_json=workspace_secret("GCP_SERVICE_ACCOUNT_JSON"),
        scopes=["https://www.googleapis.com/auth/devstorage.read_write"],
    )
    config = mount_config(
        auth=[aws_rule, gcp_rule],
        mounts=[
            s3_mount(
                id="s3_data",
                mount_path="/mnt/s3-data",
                bucket="s3-bucket",
                prefix="datasets",
                region="us-east-1",
                read_only=True,
            ),
            gcs_mount(
                id="gcs_data",
                mount_path="/mnt/gcs-data",
                bucket="gcs-bucket",
                prefix="datasets",
            ),
        ],
    )

    assert config == {
        "mounts": [
            {
                "id": "s3_data",
                "type": "s3",
                "mount_path": "/mnt/s3-data",
                "read_only": True,
                "s3": {
                    "endpoint_url": "https://s3.amazonaws.com",
                    "region": "us-east-1",
                    "bucket": "s3-bucket",
                    "prefix": "datasets",
                    "path_style": False,
                },
            },
            {
                "id": "gcs_data",
                "type": "gcs",
                "mount_path": "/mnt/gcs-data",
                "gcs": {
                    "bucket": "gcs-bucket",
                    "prefix": "datasets",
                },
            },
        ],
        "proxy_config": {"rules": [aws_rule, gcp_rule]},
    }


@pytest.mark.parametrize(
    ("auth", "mounts", "message"),
    [
        ([], [s3_mount(id="s3_data", mount_path="/mnt/s3-data", bucket="b")], "aws"),
        (
            [],
            [gcs_mount(id="gcs_data", mount_path="/mnt/gcs-data", bucket="b")],
            "gcp",
        ),
        (
            [
                aws_auth(
                    access_key_id=workspace_secret("AWS_ACCESS_KEY_ID"),
                    secret_access_key=workspace_secret("AWS_SECRET_ACCESS_KEY"),
                ),
                aws_auth(
                    access_key_id=workspace_secret("AWS_ACCESS_KEY_ID_2"),
                    secret_access_key=workspace_secret("AWS_SECRET_ACCESS_KEY_2"),
                ),
            ],
            [s3_mount(id="s3_data", mount_path="/mnt/s3-data", bucket="b")],
            "duplicate",
        ),
    ],
)
def test_mount_config_validates_provider_auth(auth, mounts, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        mount_config(auth=auth, mounts=mounts)


@pytest.mark.parametrize(
    ("scopes", "match_hosts"),
    [
        ([], ["storage.googleapis.com"]),
        (["https://www.googleapis.com/auth/devstorage.read_write"], []),
        ([""], ["storage.googleapis.com"]),
        (["https://www.googleapis.com/auth/devstorage.read_write"], [""]),
    ],
)
def test_gcp_auth_rejects_empty_scopes_and_hosts(
    scopes: list[str], match_hosts: list[str]
) -> None:
    with pytest.raises(ValueError):
        gcp_auth(
            service_account_json=workspace_secret("GCP_SERVICE_ACCOUNT_JSON"),
            scopes=scopes,
            match_hosts=match_hosts,
        )


def test_create_sandbox_forwards_composed_proxy_config(
    httpx_mock: HTTPXMock,
) -> None:
    client = SandboxClient(api_endpoint="http://test-server:8080", max_retries=0)
    httpx_mock.add_response(
        method="POST",
        url="http://test-server:8080/boxes",
        json={"name": "test-sandbox"},
        status_code=201,
    )
    config = proxy_config(
        rules=[
            aws_auth(
                access_key_id=workspace_secret("AWS_ACCESS_KEY_ID"),
                secret_access_key=workspace_secret("AWS_SECRET_ACCESS_KEY"),
            )
        ]
    )

    client.create_sandbox(snapshot_id="snap-1", proxy_config=config)

    body = json.loads(httpx_mock.get_request().content)
    assert body["proxy_config"] == config
    client.close()


def test_create_sandbox_expands_mount_config(
    httpx_mock: HTTPXMock,
) -> None:
    client = SandboxClient(api_endpoint="http://test-server:8080", max_retries=0)
    httpx_mock.add_response(
        method="POST",
        url="http://test-server:8080/boxes",
        json={"name": "test-sandbox"},
        status_code=201,
    )
    config = mount_config(
        auth=[
            aws_auth(
                access_key_id=workspace_secret("AWS_ACCESS_KEY_ID"),
                secret_access_key=workspace_secret("AWS_SECRET_ACCESS_KEY"),
            )
        ],
        mounts=[s3_mount(id="s3_data", mount_path="/mnt/s3-data", bucket="s3-bucket")],
    )

    client.create_sandbox(snapshot_id="snap-1", mount_config=config)

    body = json.loads(httpx_mock.get_request().content)
    assert body["mounts"] == config["mounts"]
    assert body["proxy_config"] == config["proxy_config"]
    client.close()
