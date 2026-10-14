"""Workload identity (AWS/GCP/Azure) and Azure Blob mount helpers."""

import json
from typing import Any

import pytest
from pytest_httpx import HTTPXMock

from langsmith.sandbox import (
    SandboxClient,
    aws_auth,
    azure_auth,
    azure_blob_mount,
    gcp_auth,
    gcs_mount,
    mount_config,
    opaque_secret,
    proxy_config,
    s3_mount,
    workspace_secret,
)

ROLE_ARN = "arn:aws:iam::123456789012:role/SandboxTest"
TAG_SCOPE = "tag:7d3c0c1e-1b7a-4e0a-9b8f-2f4a1d2c3b4a"
WIP = (
    "//iam.googleapis.com/projects/123456789/locations/global/"
    "workloadIdentityPools/langsmith/providers/langsmith"
)
SA_EMAIL = "vertex-ro@my-project.iam.gserviceaccount.com"
TENANT_ID = "2c6a46a8-f9b3-4f58-8e5d-4bab8c1f9270"
CLIENT_ID = "0b5a3f4e-8f1d-4c3a-9a63-1f6c2d8e7a10"
ENDPOINT = "http://test-server:8080"


def _s3():
    return [s3_mount(id="data", mount_path="/mnt/mounts/data", bucket="b")]


def _gcs():
    return [
        gcs_mount(id="gcs", mount_path="/mnt/mounts/gcs", bucket="b", read_only=True)
    ]


def _blob(account: str = "lsdata01", id: str = "blob"):
    return azure_blob_mount(
        id=id,
        mount_path=f"/mnt/mounts/{id}",
        storage_account=account,
        container="agent-data",
    )


def test_aws_subject_scope_in_proxy_and_mount_auth() -> None:
    rule = aws_auth(role_arn=ROLE_ARN, subject_scope=TAG_SCOPE)
    assert rule["aws"] == {"role_arn": ROLE_ARN, "subject_scope": TAG_SCOPE}
    assert proxy_config(rules=[rule]) == {"rules": [rule]}
    assert mount_config(auth=[rule], mounts=_s3())["auth"] == {
        "aws": {"role_arn": ROLE_ARN, "subject_scope": TAG_SCOPE}
    }


def test_aws_subject_scope_requires_role_arn() -> None:
    static = {
        "access_key_id": workspace_secret("AWS_KEY_ID_REF"),
        "secret_access_key": workspace_secret("AWS_KEY_VALUE_REF"),
    }
    with pytest.raises(ValueError, match="subject_scope requires role_arn"):
        aws_auth(**static, subject_scope="workspace")
    raw = {"type": "aws", "aws": {**static, "subject_scope": "workspace"}}
    with pytest.raises(ValueError, match="subject_scope requires role_arn"):
        mount_config(auth=[raw], mounts=_s3())


def test_gcp_workload_identity_rule() -> None:
    rule = gcp_auth(
        workload_identity_provider=WIP,
        service_account_email=SA_EMAIL,
        subject_scope=TAG_SCOPE,
    )
    assert rule == {
        "name": "gcp",
        "type": "gcp",
        "enabled": True,
        "gcp": {
            "workload_identity_provider": WIP,
            "service_account_email": SA_EMAIL,
            "subject_scope": TAG_SCOPE,
        },
    }
    assert proxy_config(rules=[rule]) == {"rules": [rule]}


@pytest.mark.parametrize(
    ("options", "message"),
    [
        (
            {
                "workload_identity_provider": WIP,
                "service_account_json": workspace_secret("GCP_SA"),
            },
            "mutually exclusive",
        ),
        (
            {
                "service_account_json": workspace_secret("GCP_SA"),
                "service_account_email": SA_EMAIL,
            },
            "require workload_identity_provider",
        ),
        (
            {
                "service_account_json": workspace_secret("GCP_SA"),
                "subject_scope": "workspace",
            },
            "require workload_identity_provider",
        ),
        ({}, "service_account_json or workload_identity_provider"),
    ],
)
def test_gcp_auth_rejects_mixed_or_missing_credentials(
    options: dict[str, Any], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        gcp_auth(**options)


def test_gcs_mount_auth_with_workload_identity_drops_scopes() -> None:
    rule = gcp_auth(
        workload_identity_provider=WIP,
        subject_scope="workspace",
        scopes=["https://www.googleapis.com/auth/devstorage.read_only"],
    )
    assert mount_config(auth=[rule], mounts=_gcs())["auth"] == {
        "gcp": {"workload_identity_provider": WIP, "subject_scope": "workspace"}
    }


@pytest.mark.parametrize("enabled", [True, False])
def test_gcs_mounts_can_use_enabled_gcp_workload_identity_rule(enabled: bool) -> None:
    proxy = proxy_config(
        rules=[gcp_auth(workload_identity_provider=WIP, enabled=enabled)]
    )
    if enabled:
        config = mount_config(proxy_config=proxy, mounts=_gcs())
        assert config == {"auth": {}, "mounts": _gcs()}
    else:
        with pytest.raises(ValueError, match="gcs mounts require gcp auth"):
            mount_config(proxy_config=proxy, mounts=_gcs())


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        (
            {
                "tenant_id": TENANT_ID,
                "client_id": CLIENT_ID,
                "subject_scope": TAG_SCOPE,
                "resources": ["https://storage.azure.com"],
            },
            {
                "tenant_id": TENANT_ID,
                "client_id": CLIENT_ID,
                "subject_scope": TAG_SCOPE,
                "resources": ["https://storage.azure.com"],
            },
        ),
        (
            {"storage_account": "lsdata01", "account_key": opaque_secret("k")},
            {"storage_account": "lsdata01", "account_key": opaque_secret("k")},
        ),
        (
            {"storage_account": "lsdata01", "sas_token": workspace_secret("SAS")},
            {"storage_account": "lsdata01", "sas_token": workspace_secret("SAS")},
        ),
    ],
)
def test_azure_auth_forms(options: dict[str, Any], expected: dict[str, Any]) -> None:
    rule = azure_auth(**options)
    assert rule == {
        "name": "azure",
        "type": "azure",
        "enabled": True,
        "azure": expected,
    }
    assert proxy_config(rules=[rule]) == {"rules": [rule]}


@pytest.mark.parametrize(
    ("options", "message"),
    [
        (
            {
                "tenant_id": TENANT_ID,
                "client_id": CLIENT_ID,
                "storage_account": "lsdata01",
            },
            "mutually exclusive",
        ),
        (
            {
                "tenant_id": TENANT_ID,
                "client_id": CLIENT_ID,
                "sas_token": workspace_secret("SAS"),
            },
            "mutually exclusive",
        ),
        ({"tenant_id": TENANT_ID}, "client_id"),
        (
            {
                "storage_account": "lsdata01",
                "account_key": opaque_secret("k"),
                "sas_token": workspace_secret("SAS"),
            },
            "exactly one",
        ),
        ({"storage_account": "lsdata01"}, "exactly one"),
        ({"account_key": opaque_secret("k")}, "storage_account"),
        (
            {
                "storage_account": "lsdata01",
                "account_key": opaque_secret("k"),
                "subject_scope": "workspace",
            },
            "require tenant_id and client_id",
        ),
        (
            {
                "storage_account": "lsdata01",
                "account_key": opaque_secret("k"),
                "resources": ["https://storage.azure.com"],
            },
            "require tenant_id and client_id",
        ),
    ],
)
def test_azure_auth_rejects_mixed_or_incomplete_forms(
    options: dict[str, Any], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        azure_auth(**options)


def test_azure_blob_mount_serializes_backend_shape() -> None:
    mount = azure_blob_mount(
        id="data",
        mount_path="/mnt/mounts/data",
        storage_account="lsdata01",
        container="agent-data",
        prefix="runs/",
        read_only=True,
        cache={"max_size_bytes": 1024},
    )
    assert mount == {
        "id": "data",
        "type": "azure_blob",
        "mount_path": "/mnt/mounts/data",
        "azure_blob": {
            "storage_account": "lsdata01",
            "container": "agent-data",
            "prefix": "runs/",
        },
        "read_only": True,
        "cache": {"max_size_bytes": 1024},
    }


@pytest.mark.parametrize(
    ("rule", "expected"),
    [
        (
            azure_auth(
                tenant_id=TENANT_ID,
                client_id=CLIENT_ID,
                subject_scope="workspace",
                resources=["https://storage.azure.com"],
            ),
            {
                "tenant_id": TENANT_ID,
                "client_id": CLIENT_ID,
                "subject_scope": "workspace",
            },
        ),
        (
            azure_auth(storage_account="lsdata01", account_key=opaque_secret("k")),
            {"account_key": opaque_secret("k")},
        ),
        (
            azure_auth(storage_account="lsdata01", sas_token=workspace_secret("SAS")),
            {"sas_token": workspace_secret("SAS")},
        ),
    ],
)
def test_azure_mount_auth_keeps_mount_fields(rule, expected) -> None:
    config = mount_config(auth=[rule], mounts=[_blob()])
    assert config == {"auth": {"azure": expected}, "mounts": [_blob()]}


def test_azure_blob_mounts_can_use_enabled_azure_proxy_rule() -> None:
    proxy = proxy_config(rules=[azure_auth(tenant_id=TENANT_ID, client_id=CLIENT_ID)])
    assert mount_config(proxy_config=proxy, mounts=[_blob()]) == {
        "auth": {},
        "mounts": [_blob()],
    }


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"mounts": [_blob()]}, "azure_blob mounts require azure auth"),
        (
            {
                "mounts": [_blob()],
                "proxy_config": proxy_config(
                    rules=[
                        azure_auth(
                            tenant_id=TENANT_ID, client_id=CLIENT_ID, enabled=False
                        )
                    ]
                ),
            },
            "azure_blob mounts require azure auth",
        ),
        (
            {
                "mounts": _s3(),
                "auth": [
                    aws_auth(role_arn=ROLE_ARN),
                    azure_auth(tenant_id=TENANT_ID, client_id=CLIENT_ID),
                ],
            },
            "at least one azure_blob mount",
        ),
        (
            {
                "mounts": [_blob(), _blob("other02", id="other")],
                "auth": [
                    azure_auth(storage_account="lsdata01", sas_token=opaque_secret("s"))
                ],
            },
            "storage_account",
        ),
        (
            {
                "mounts": [_blob()],
                "auth": [azure_auth(tenant_id=TENANT_ID, client_id=CLIENT_ID)],
                "proxy_config": proxy_config(
                    rules=[azure_auth(tenant_id=TENANT_ID, client_id=CLIENT_ID)]
                ),
            },
            "both mount_config and proxy_config",
        ),
    ],
)
def test_azure_mount_config_errors(kwargs: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        mount_config(**kwargs)


def test_create_sandbox_forwards_azure_and_gcp_workload_identity(
    httpx_mock: HTTPXMock,
) -> None:
    proxy = proxy_config(
        rules=[
            gcp_auth(workload_identity_provider=WIP),
            azure_auth(tenant_id=TENANT_ID, client_id=CLIENT_ID),
        ]
    )
    mounts = mount_config(proxy_config=proxy, mounts=[*_gcs(), _blob()])
    httpx_mock.add_response(
        method="POST", url=f"{ENDPOINT}/boxes", json={"name": "wi-box"}, status_code=201
    )
    with SandboxClient(api_endpoint=ENDPOINT, max_retries=0) as client:
        client.create_sandbox(
            snapshot_id="snap-1", proxy_config=proxy, mount_config=mounts
        )
    body = json.loads(httpx_mock.get_request().content)
    assert body["proxy_config"] == proxy
    assert body["mount_config"] == mounts


@pytest.mark.parametrize("tag_value_ids", [None, [TAG_SCOPE.removeprefix("tag:")]])
def test_create_sandbox_serializes_tag_value_ids(
    httpx_mock: HTTPXMock, tag_value_ids: Any
) -> None:
    proxy = proxy_config(rules=[aws_auth(role_arn=ROLE_ARN, subject_scope=TAG_SCOPE)])
    httpx_mock.add_response(
        method="POST",
        url=f"{ENDPOINT}/boxes",
        json={"name": "tag-box"},
        status_code=201,
    )
    with SandboxClient(api_endpoint=ENDPOINT, max_retries=0) as client:
        client.create_sandbox(
            snapshot_id="snap-1", proxy_config=proxy, tag_value_ids=tag_value_ids
        )
    body = json.loads(httpx_mock.get_request().content)
    if tag_value_ids is None:
        assert "tag_value_ids" not in body
    else:
        assert body["tag_value_ids"] == tag_value_ids
