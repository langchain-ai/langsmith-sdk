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
    git_mount,
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
    assert not hasattr(sandbox_module, "aws_mount_auth")
    assert not hasattr(sandbox_module, "gcp_mount_auth")


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


def test_gcp_auth_builds_gcp_rule_with_builtin_google_api_host_matching() -> None:
    rule = gcp_auth(
        service_account_json=workspace_secret("GCP_SERVICE_ACCOUNT_JSON"),
        scopes=["https://www.googleapis.com/auth/devstorage.read_write"],
    )

    assert rule == {
        "name": "gcp",
        "type": "gcp",
        "enabled": True,
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


def test_mount_config_nests_mounts_and_provider_auth() -> None:
    aws_auth_rule = aws_auth(
        access_key_id=workspace_secret("AWS_ACCESS_KEY_ID"),
        secret_access_key=workspace_secret("AWS_SECRET_ACCESS_KEY"),
    )
    gcp_auth_rule = gcp_auth(
        service_account_json=workspace_secret("GCP_SERVICE_ACCOUNT_JSON"),
    )
    config = mount_config(
        auth=[aws_auth_rule, gcp_auth_rule],
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
        "auth": {
            "aws": aws_auth_rule["aws"],
            "gcp": {
                "service_account_json": {
                    "type": "workspace_secret",
                    "value": "{GCP_SERVICE_ACCOUNT_JSON}",
                },
            },
        },
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
    }


def test_git_mount_serializes_backend_shape() -> None:
    assert git_mount(
        id="repo",
        mount_path="/mnt/repo",
        remote_url="https://github.com/langchain-ai/langsmith-sdk.git",
        ref={"type": "branch", "name": "main"},
        refresh_interval_seconds=60,
    ) == {
        "id": "repo",
        "type": "git",
        "mount_path": "/mnt/repo",
        "git": {
            "remote_url": "https://github.com/langchain-ai/langsmith-sdk.git",
            "ref": {"type": "branch", "name": "main"},
            "refresh_interval_seconds": 60,
        },
    }


def test_git_mount_allows_tag_ref_and_omitted_optional_fields() -> None:
    assert git_mount(
        id="repo",
        mount_path="/mnt/repo",
        remote_url="https://github.com/langchain-ai/langsmith-sdk.git",
        ref={"type": "tag", "name": "v1.0.0"},
    )["git"] == {
        "remote_url": "https://github.com/langchain-ai/langsmith-sdk.git",
        "ref": {"type": "tag", "name": "v1.0.0"},
    }
    assert git_mount(
        id="repo",
        mount_path="/mnt/repo",
        remote_url="https://github.com/langchain-ai/langsmith-sdk.git",
    )["git"] == {
        "remote_url": "https://github.com/langchain-ai/langsmith-sdk.git",
    }


@pytest.mark.parametrize(
    "remote_url",
    [
        "",
        "http://github.com/langchain-ai/langsmith-sdk.git",
        "https://github.com",
        "https://user:pass@github.com/langchain-ai/langsmith-sdk.git",
        "https://github.com/langchain-ai/langsmith-sdk.git?token=secret",
        "https://github.com/langchain-ai/langsmith-sdk.git#main",
        "https://github.com/langchain-ai/langsmith-sdk.git\n",
        "https://github.com/langchain-ai/langsmith-sdk.git\x00",
    ],
)
def test_git_mount_rejects_invalid_remote_urls(remote_url: str) -> None:
    with pytest.raises(ValueError):
        git_mount(id="repo", mount_path="/mnt/repo", remote_url=remote_url)


@pytest.mark.parametrize(
    ("ref", "refresh_interval_seconds"),
    [
        ({"type": "commit", "name": "abc123"}, None),
        ({"type": "branch"}, None),
        ({"type": "branch", "name": ""}, None),
        (None, 0),
    ],
)
def test_git_mount_rejects_invalid_ref_and_refresh_interval(
    ref, refresh_interval_seconds
) -> None:
    with pytest.raises(ValueError):
        git_mount(
            id="repo",
            mount_path="/mnt/repo",
            remote_url="https://github.com/langchain-ai/langsmith-sdk.git",
            ref=ref,
            refresh_interval_seconds=refresh_interval_seconds,
        )


def test_mount_config_accepts_git_mount_without_provider_auth() -> None:
    mount = git_mount(
        id="repo",
        mount_path="/mnt/repo",
        remote_url="https://github.com/langchain-ai/langsmith-sdk.git",
    )

    assert mount_config(mounts=[mount]) == {
        "auth": {},
        "mounts": [mount],
    }


def test_mount_config_nests_mixed_bucket_and_git_mounts() -> None:
    aws_auth_rule = aws_auth(
        access_key_id=workspace_secret("AWS_ACCESS_KEY_ID"),
        secret_access_key=workspace_secret("AWS_SECRET_ACCESS_KEY"),
    )
    gcp_auth_rule = gcp_auth(
        service_account_json=workspace_secret("GCP_SERVICE_ACCOUNT_JSON"),
    )
    mounts = [
        s3_mount(id="s3_data", mount_path="/mnt/s3-data", bucket="s3-bucket"),
        gcs_mount(id="gcs_data", mount_path="/mnt/gcs-data", bucket="gcs-bucket"),
        git_mount(
            id="repo",
            mount_path="/mnt/repo",
            remote_url="https://github.com/langchain-ai/langsmith-sdk.git",
        ),
    ]

    assert mount_config(auth=[aws_auth_rule, gcp_auth_rule], mounts=mounts) == {
        "auth": {
            "aws": aws_auth_rule["aws"],
            "gcp": {
                "service_account_json": {
                    "type": "workspace_secret",
                    "value": "{GCP_SERVICE_ACCOUNT_JSON}",
                },
            },
        },
        "mounts": mounts,
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


@pytest.mark.parametrize("scopes", [[], [""]])
def test_gcp_auth_rejects_empty_scopes(scopes: list[str]) -> None:
    with pytest.raises(ValueError):
        gcp_auth(
            service_account_json=workspace_secret("GCP_SERVICE_ACCOUNT_JSON"),
            scopes=scopes,
        )


def test_proxy_config_rejects_gcp_auth_without_scopes() -> None:
    with pytest.raises(ValueError, match="scopes"):
        proxy_config(
            rules=[
                gcp_auth(
                    service_account_json=workspace_secret("GCP_SERVICE_ACCOUNT_JSON")
                )
            ]
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
    assert body["mount_config"] == config
    assert "mounts" not in body
    assert "proxy_config" not in body
    client.close()


def test_create_sandbox_preserves_mount_config_and_proxy_config_separately(
    httpx_mock: HTTPXMock,
) -> None:
    client = SandboxClient(api_endpoint="http://test-server:8080", max_retries=0)
    httpx_mock.add_response(
        method="POST",
        url="http://test-server:8080/boxes",
        json={"name": "test-sandbox"},
        status_code=201,
    )
    aws_auth_rule = aws_auth(
        access_key_id=workspace_secret("AWS_ACCESS_KEY_ID"),
        secret_access_key=workspace_secret("AWS_SECRET_ACCESS_KEY"),
    )
    extra_rule = {
        "name": "github",
        "type": "headers",
        "enabled": True,
        "match_hosts": ["github.com"],
        "headers": {"authorization": "Bearer {GITHUB_TOKEN}"},
    }
    config = mount_config(
        auth=[aws_auth_rule],
        mounts=[s3_mount(id="s3_data", mount_path="/mnt/s3-data", bucket="s3-bucket")],
    )
    extra_proxy_config = proxy_config(
        rules=[extra_rule],
        no_proxy=["metadata.google.internal"],
        access_control={"allow_list": ["github.com", "*.amazonaws.com"]},
    )

    client.create_sandbox(
        snapshot_id="snap-1",
        mount_config=config,
        proxy_config=extra_proxy_config,
    )

    body = json.loads(httpx_mock.get_request().content)
    assert body["mount_config"] == config
    assert "mounts" not in body
    assert body["proxy_config"] == {
        "rules": [extra_rule],
        "no_proxy": ["metadata.google.internal"],
        "access_control": {"allow_list": ["github.com", "*.amazonaws.com"]},
    }
    client.close()


@pytest.mark.parametrize(
    ("provider", "mount_auth", "mounts", "explicit_auth", "message"),
    [
        (
            "aws",
            lambda: aws_auth(
                access_key_id=workspace_secret("AWS_ACCESS_KEY_ID"),
                secret_access_key=workspace_secret("AWS_SECRET_ACCESS_KEY"),
            ),
            lambda: [
                s3_mount(
                    id="s3_data",
                    mount_path="/mnt/s3-data",
                    bucket="s3-bucket",
                )
            ],
            lambda: aws_auth(
                access_key_id=workspace_secret("AWS_ACCESS_KEY_ID_2"),
                secret_access_key=workspace_secret("AWS_SECRET_ACCESS_KEY_2"),
                name="aws-extra",
            ),
            "aws auth cannot be provided in both mount_config and proxy_config",
        ),
        (
            "gcp",
            lambda: gcp_auth(
                service_account_json=workspace_secret("GCP_SERVICE_ACCOUNT_JSON"),
            ),
            lambda: [
                gcs_mount(
                    id="gcs_data",
                    mount_path="/mnt/gcs-data",
                    bucket="gcs-bucket",
                )
            ],
            lambda: gcp_auth(
                service_account_json=workspace_secret("GCP_SERVICE_ACCOUNT_JSON_2"),
                scopes=["https://www.googleapis.com/auth/devstorage.read_write"],
                name="gcp-extra",
            ),
            "gcp auth cannot be provided in both mount_config and proxy_config",
        ),
    ],
)
def test_create_sandbox_rejects_duplicate_provider_auth_in_proxy_config(
    provider: str,
    mount_auth,
    mounts,
    explicit_auth,
    message: str,
) -> None:
    client = SandboxClient(api_endpoint="http://test-server:8080", max_retries=0)
    config = mount_config(auth=[mount_auth()], mounts=mounts())
    extra_proxy_config = proxy_config(rules=[explicit_auth()])

    with pytest.raises(ValueError, match=message):
        client.create_sandbox(
            snapshot_id=f"{provider}-snap",
            mount_config=config,
            proxy_config=extra_proxy_config,
        )
    client.close()


def test_create_sandbox_does_not_accept_raw_mounts() -> None:
    client = SandboxClient(api_endpoint="http://test-server:8080", max_retries=0)

    with pytest.raises(TypeError):
        getattr(client, "create_sandbox")(
            snapshot_id="snap-1",
            mounts=[
                {
                    "id": "customer_data",
                    "type": "s3",
                    "mount_path": "/mnt/mounts/customer-data",
                    "s3": {
                        "endpoint_url": "https://s3.amazonaws.com",
                        "region": "us-east-1",
                        "bucket": "example-bucket",
                    },
                }
            ],
        )

    client.close()


def test_mount_config_rejects_provider_credentials_in_mount_specs() -> None:
    mount = s3_mount(id="s3_data", mount_path="/mnt/s3-data", bucket="s3-bucket")
    mount["s3"]["access_key_id"] = workspace_secret("AWS_ACCESS_KEY_ID")  # type: ignore[typeddict-unknown-key]

    with pytest.raises(ValueError, match="credentials"):
        mount_config(
            auth=[
                aws_auth(
                    access_key_id=workspace_secret("AWS_ACCESS_KEY_ID"),
                    secret_access_key=workspace_secret("AWS_SECRET_ACCESS_KEY"),
                )
            ],
            mounts=[mount],
        )
