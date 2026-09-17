"""AWS role helpers preserve static auth and mount/proxy permission boundaries."""

import json
from typing import Any

import pytest
from pytest_httpx import HTTPXMock

from langsmith.sandbox import (
    AsyncSandboxClient,
    AWSMountAuthConfig,
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

ROLE_ARN = "arn:aws:iam::123456789012:role/SandboxTest"
ENDPOINT = "http://test-server:8080"


def _mounts():
    return [s3_mount(id="data", mount_path="/mnt/data", bucket="test-bucket")]


def test_aws_role_helper() -> None:
    assert aws_auth(
        role_arn=ROLE_ARN, name="role", env_vars={"AWS_REGION": "us-east-1"}
    ) == {
        "name": "role",
        "type": "aws",
        "enabled": True,
        "env_vars": {"AWS_REGION": "us-east-1"},
        "aws": {"role_arn": ROLE_ARN},
    }


@pytest.mark.parametrize("secret", [workspace_secret, opaque_secret])
def test_static_helpers_and_type_constructor_remain_compatible(secret) -> None:
    static = AWSMountAuthConfig(
        access_key_id=secret("AWS_KEY_ID_REF"),
        secret_access_key=secret("AWS_KEY_VALUE_REF"),
    )
    rule = aws_auth(**static)
    assert rule["aws"] == static
    assert aws_auth(**static, role_arn="")["aws"] == static
    assert mount_config(auth=[rule], mounts=_mounts())["auth"]["aws"] == static


@pytest.mark.parametrize(
    "options",
    [
        {},
        {"role_arn": ""},
        {"role_arn": "   "},
        {"role_arn": 42},
        {"access_key_id": workspace_secret("AWS_KEY_ID_REF")},
        {"secret_access_key": workspace_secret("AWS_KEY_VALUE_REF")},
        {"role_arn": ROLE_ARN, "access_key_id": workspace_secret("AWS_KEY_ID_REF")},
        {
            "role_arn": ROLE_ARN,
            "secret_access_key": workspace_secret("AWS_KEY_VALUE_REF"),
        },
    ],
)
def test_helper_rejects_empty_partial_and_mixed_modes(options: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        aws_auth(**options)


@pytest.mark.parametrize(
    "extra",
    [
        {"access_key_id": None},
        {"secret_access_key": None},
        {"external_id": "caller-controlled"},
        {"session_token": "not-accepted"},
    ],
)
def test_raw_role_descriptors_reject_extra_fields(extra: dict[str, Any]) -> None:
    rule = {"type": "aws", "enabled": True, "aws": {"role_arn": ROLE_ARN, **extra}}
    with pytest.raises(ValueError, match="only role_arn"):
        proxy_config(rules=[rule])
    with pytest.raises(ValueError, match="only role_arn"):
        mount_config(auth=[rule], mounts=_mounts())


def test_mount_scoped_role_stays_in_mount_auth() -> None:
    config = mount_config(auth=[aws_auth(role_arn=ROLE_ARN)], mounts=_mounts())
    assert config["auth"] == {"aws": {"role_arn": ROLE_ARN}}
    assert "aws_role" not in config["auth"]


def test_shared_proxy_role_is_not_copied_into_mount_auth() -> None:
    proxy = proxy_config(rules=[aws_auth(role_arn=ROLE_ARN)])
    config = mount_config(proxy_config=proxy, mounts=_mounts())
    assert config == {"auth": {}, "mounts": _mounts()}
    assert proxy["rules"][0]["aws"] == {"role_arn": ROLE_ARN}
    with pytest.raises(ValueError, match="both mount_config and proxy_config"):
        mount_config(
            auth=[aws_auth(role_arn=ROLE_ARN)], proxy_config=proxy, mounts=_mounts()
        )


@pytest.mark.parametrize(
    "proxy",
    [
        None,
        {"rules": []},
        proxy_config(rules=[aws_auth(role_arn=ROLE_ARN, enabled=False)]),
    ],
)
def test_mounts_still_require_enabled_auth(proxy) -> None:
    with pytest.raises(ValueError, match="s3 mounts require aws auth"):
        mount_config(proxy_config=proxy, mounts=_mounts())


@pytest.mark.parametrize("enabled", [True, False])
def test_gcp_proxy_rule_does_not_supply_gcs_mount_auth(enabled: bool) -> None:
    proxy = proxy_config(
        rules=[
            gcp_auth(
                service_account_json=workspace_secret("GCP_SERVICE_ACCOUNT"),
                scopes=["https://www.googleapis.com/auth/devstorage.read_only"],
                enabled=enabled,
            )
        ]
    )
    with pytest.raises(ValueError, match="gcs mounts require gcp auth"):
        mount_config(
            proxy_config=proxy,
            mounts=[gcs_mount(id="gcs", mount_path="/mnt/gcs", bucket="test-bucket")],
        )


@pytest.mark.parametrize("shared_aws", [False, True])
def test_explicit_gcs_mount_auth_with_optional_shared_aws(shared_aws: bool) -> None:
    secret = workspace_secret("GCP_SERVICE_ACCOUNT")
    mounts = [gcs_mount(id="gcs", mount_path="/mnt/gcs", bucket="test-bucket")]
    proxy = None
    if shared_aws:
        mounts += _mounts()
        proxy = proxy_config(rules=[aws_auth(role_arn=ROLE_ARN)])
    config = mount_config(
        auth=[gcp_auth(service_account_json=secret)],
        proxy_config=proxy,
        mounts=mounts,
    )
    assert config["auth"] == {"gcp": {"service_account_json": secret}}
    assert config["mounts"] == mounts


def test_shared_static_aws_auth_is_not_copied_into_mount_auth() -> None:
    proxy = proxy_config(
        rules=[
            aws_auth(
                access_key_id=workspace_secret("AWS_KEY_ID_REF"),
                secret_access_key=workspace_secret("AWS_KEY_VALUE_REF"),
            )
        ]
    )
    assert mount_config(proxy_config=proxy, mounts=_mounts()) == {
        "auth": {},
        "mounts": _mounts(),
    }


@pytest.mark.parametrize("mode", ["proxy", "mount", "shared"])
def test_create_role_auth_wire_shape(httpx_mock: HTTPXMock, mode: str) -> None:
    rule = aws_auth(role_arn=ROLE_ARN)
    options: dict[str, Any] = {}
    if mode in {"proxy", "shared"}:
        options["proxy_config"] = proxy_config(rules=[rule])
    if mode == "mount":
        options["mount_config"] = mount_config(auth=[rule], mounts=_mounts())
    elif mode == "shared":
        options["mount_config"] = mount_config(
            proxy_config=options["proxy_config"], mounts=_mounts()
        )
    httpx_mock.add_response(
        method="POST",
        url=f"{ENDPOINT}/boxes",
        json={"name": "role-box"},
        status_code=201,
    )
    with SandboxClient(api_endpoint=ENDPOINT, max_retries=0) as client:
        assert client.create_sandbox(snapshot_id="snap-1", **options).name == "role-box"
    body = json.loads(httpx_mock.get_request().content)
    for field in ("mount_config", "proxy_config"):
        if field in options:
            assert body[field] == options[field]
        else:
            assert field not in body


async def test_async_create_shared_proxy_role(httpx_mock: HTTPXMock) -> None:
    proxy = proxy_config(rules=[aws_auth(role_arn=ROLE_ARN)])
    mounts = mount_config(proxy_config=proxy, mounts=_mounts())
    httpx_mock.add_response(
        method="POST",
        url=f"{ENDPOINT}/boxes",
        json={"name": "role-box"},
        status_code=201,
    )
    async with AsyncSandboxClient(api_endpoint=ENDPOINT, max_retries=0) as client:
        box = await client.create_sandbox(
            snapshot_id="snap-1", mount_config=mounts, proxy_config=proxy
        )
        assert box.name == "role-box"
    body = json.loads(httpx_mock.get_request().content)
    assert body["proxy_config"] == proxy
    assert body["mount_config"] == mounts


def _mixed_boxes():
    static = {
        "access_key_id": {"type": "opaque"},
        "secret_access_key": {"type": "opaque"},
    }
    return [
        {
            "name": "static-box",
            "mount_config": {"auth": {"aws": static}, "mounts": _mounts()},
        },
        {
            "name": "role-box",
            "mount_config": {
                "auth": {"aws": {"role_arn": ROLE_ARN}},
                "mounts": _mounts(),
            },
        },
        {
            "name": "proxy-box",
            "proxy_config": proxy_config(rules=[aws_auth(role_arn=ROLE_ARN)]),
        },
    ]


def test_get_and_list_accept_mixed_auth_responses(httpx_mock: HTTPXMock) -> None:
    boxes = _mixed_boxes()
    httpx_mock.add_response(
        method="GET", url=f"{ENDPOINT}/boxes", json={"sandboxes": boxes}
    )
    for box in boxes:
        httpx_mock.add_response(
            method="GET", url=f"{ENDPOINT}/boxes/{box['name']}", json=box
        )
    with SandboxClient(api_endpoint=ENDPOINT, max_retries=0) as client:
        assert [box.name for box in client.list_sandboxes()] == [
            box["name"] for box in boxes
        ]
        for box in boxes:
            assert client.get_sandbox(box["name"]).name == box["name"]


async def test_async_get_and_list_accept_mixed_auth_responses(
    httpx_mock: HTTPXMock,
) -> None:
    boxes = _mixed_boxes()
    httpx_mock.add_response(
        method="GET", url=f"{ENDPOINT}/boxes", json={"sandboxes": boxes}
    )
    for box in boxes:
        httpx_mock.add_response(
            method="GET", url=f"{ENDPOINT}/boxes/{box['name']}", json=box
        )
    async with AsyncSandboxClient(api_endpoint=ENDPOINT, max_retries=0) as client:
        assert [box.name for box in await client.list_sandboxes()] == [
            box["name"] for box in boxes
        ]
        for box in boxes:
            assert (await client.get_sandbox(box["name"])).name == box["name"]
