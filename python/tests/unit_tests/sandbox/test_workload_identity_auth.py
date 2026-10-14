"""Workload identity (AWS/GCP/Azure) auth, Azure Blob mounts, tag_value_ids."""

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
)

ROLE = "arn:aws:iam::123456789012:role/SandboxTest"
TAG_ID = "7d3c0c1e-1b7a-4e0a-9b8f-2f4a1d2c3b4a"
WIP = (
    "//iam.googleapis.com/projects/1/locations/global/"
    "workloadIdentityPools/p/providers/p"
)
EMAIL = "sa@my-project.iam.gserviceaccount.com"
WI = {"tenant_id": "2c6a46a8-f9b3-4f58-8e5d-4bab8c1f9270", "client_id": "0b5a3f4e"}
KEY = opaque_secret("key")
S3 = s3_mount(id="s3", mount_path="/mnt/mounts/s3", bucket="b")
GCS = gcs_mount(id="gcs", mount_path="/mnt/mounts/gcs", bucket="b", read_only=True)


def blob(account: str = "acct", id: str = "blob") -> Any:
    return azure_blob_mount(
        id=id, mount_path=f"/mnt/mounts/{id}", storage_account=account, container="c"
    )


@pytest.mark.parametrize(
    ("helper", "kwargs"),
    [
        (aws_auth, {"role_arn": ROLE, "subject_scope": "workspace"}),
        (
            gcp_auth,
            {
                "workload_identity_provider": WIP,
                "service_account_email": EMAIL,
                "subject_scope": f"tag:{TAG_ID}",
            },
        ),
        (azure_auth, {**WI, "resources": ["https://storage.azure.com"]}),
        (azure_auth, {"storage_account": "acct", "account_key": KEY}),
        (azure_auth, {"storage_account": "acct", "sas_token": KEY}),
    ],
)
def test_helper_forms_serialize(helper, kwargs: dict) -> None:
    rule = helper(**kwargs)
    assert rule[rule["type"]] == kwargs
    assert proxy_config(rules=[rule]) == {"rules": [rule]}


@pytest.mark.parametrize(
    ("helper", "kwargs", "message"),
    [
        (
            aws_auth,
            {"access_key_id": KEY, "secret_access_key": KEY, "subject_scope": "x"},
            "requires role_arn",
        ),
        (
            gcp_auth,
            {"workload_identity_provider": WIP, "service_account_json": KEY},
            "mutually exclusive",
        ),
        (
            gcp_auth,
            {"service_account_json": KEY, "service_account_email": EMAIL},
            "require workload_identity_provider",
        ),
        (gcp_auth, {}, "service_account_json or workload_identity_provider"),
        (azure_auth, {**WI, "sas_token": KEY}, "mutually exclusive"),
        (azure_auth, {"tenant_id": WI["tenant_id"]}, "client_id"),
        (
            azure_auth,
            {"storage_account": "acct", "account_key": KEY, "sas_token": KEY},
            "exactly one",
        ),
        (azure_auth, {"account_key": KEY}, "storage_account"),
        (
            azure_auth,
            {"storage_account": "acct", "account_key": KEY, "subject_scope": "x"},
            "require tenant_id and client_id",
        ),
    ],
)
def test_helper_rejects_invalid_forms(helper, kwargs: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        helper(**kwargs)


def test_azure_blob_mount_serializes_backend_shape() -> None:
    mount = azure_blob_mount(
        id="d",
        mount_path="/mnt/mounts/d",
        storage_account="acct",
        container="c",
        prefix="runs/",
        read_only=True,
    )
    assert mount == {
        "id": "d",
        "type": "azure_blob",
        "mount_path": "/mnt/mounts/d",
        "azure_blob": {"storage_account": "acct", "container": "c", "prefix": "runs/"},
        "read_only": True,
    }


@pytest.mark.parametrize(
    ("rule", "mount", "expected"),
    [
        (
            aws_auth(role_arn=ROLE, subject_scope="workspace"),
            S3,
            {"aws": {"role_arn": ROLE, "subject_scope": "workspace"}},
        ),
        (
            gcp_auth(workload_identity_provider=WIP, scopes=["s"]),
            GCS,
            {"gcp": {"workload_identity_provider": WIP}},
        ),
        (
            azure_auth(**WI, resources=["https://storage.azure.com"]),
            blob(),
            {"azure": WI},
        ),
        (
            azure_auth(storage_account="acct", account_key=KEY),
            blob(),
            {"azure": {"account_key": KEY}},
        ),
    ],
)
def test_mount_auth_keeps_only_mount_fields(rule, mount, expected) -> None:
    assert mount_config(auth=[rule], mounts=[mount])["auth"] == expected


@pytest.mark.parametrize(
    ("rule", "mount"),
    [(gcp_auth(workload_identity_provider=WIP), GCS), (azure_auth(**WI), blob())],
)
def test_mounts_can_use_enabled_proxy_rule(rule, mount) -> None:
    proxy = proxy_config(rules=[rule])
    assert mount_config(proxy_config=proxy, mounts=[mount]) == {
        "auth": {},
        "mounts": [mount],
    }
    rule["enabled"] = False
    with pytest.raises(ValueError, match="require"):
        mount_config(proxy_config=proxy, mounts=[mount])


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"mounts": [blob()]}, "azure_blob mounts require azure auth"),
        (
            {"mounts": [S3], "auth": [aws_auth(role_arn=ROLE), azure_auth(**WI)]},
            "at least one azure_blob mount",
        ),
        (
            {
                "mounts": [blob(), blob("other", id="other")],
                "auth": [azure_auth(storage_account="acct", sas_token=KEY)],
            },
            "storage_account",
        ),
        (
            {
                "mounts": [blob()],
                "auth": [azure_auth(**WI)],
                "proxy_config": proxy_config(rules=[azure_auth(**WI)]),
            },
            "both mount_config and proxy_config",
        ),
    ],
)
def test_mount_config_rejects_invalid_azure_auth(kwargs: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        mount_config(**kwargs)


@pytest.mark.parametrize("tag_value_ids", [None, [TAG_ID]])
def test_create_sandbox_sends_tag_value_ids_and_configs(
    httpx_mock: HTTPXMock, tag_value_ids
) -> None:
    proxy = proxy_config(rules=[aws_auth(role_arn=ROLE, subject_scope=f"tag:{TAG_ID}")])
    mounts = mount_config(auth=[azure_auth(**WI)], mounts=[blob()])
    httpx_mock.add_response(
        method="POST", url="http://test:8080/boxes", json={"name": "b"}, status_code=201
    )
    with SandboxClient(api_endpoint="http://test:8080", max_retries=0) as client:
        client.create_sandbox(
            proxy_config=proxy, mount_config=mounts, tag_value_ids=tag_value_ids
        )
    body = json.loads(httpx_mock.get_request().content)
    assert (body["proxy_config"], body["mount_config"]) == (proxy, mounts)
    assert body.get("tag_value_ids") == tag_value_ids
