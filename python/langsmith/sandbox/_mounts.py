"""Helpers and type definitions for sandbox mount configurations."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal, TypedDict, Union
from urllib.parse import urlsplit

from langsmith.sandbox._proxy_config import (
    SandboxProxyConfig,
    SandboxProxySecret,
)


class MountCacheConfig(TypedDict, total=False):
    """Optional per-mount cache configuration supported by bucket mounts."""

    max_size_bytes: int
    writeback_seconds: int


class BucketMountSpecBase(TypedDict, total=False):
    """Optional fields applied per bucket-backed sandbox mount."""

    read_only: bool
    cache: MountCacheConfig


class S3MountConfigRequired(TypedDict):
    """Required S3 configuration for a sandbox mount."""

    endpoint_url: str
    region: str
    bucket: str


class S3MountConfig(S3MountConfigRequired, total=False):
    """S3 configuration for a sandbox mount."""

    prefix: str
    path_style: bool


class S3MountSpec(BucketMountSpecBase):
    """S3-backed sandbox mount specification."""

    id: str
    type: Literal["s3"]
    mount_path: str
    s3: S3MountConfig


class GCSMountConfigRequired(TypedDict):
    """Required GCS configuration for a sandbox mount."""

    bucket: str


class GCSMountConfig(GCSMountConfigRequired, total=False):
    """GCS configuration for a sandbox mount."""

    prefix: str


class GCSMountSpec(BucketMountSpecBase):
    """GCS-backed sandbox mount specification."""

    id: str
    type: Literal["gcs"]
    mount_path: str
    gcs: GCSMountConfig


class GitMountRefSpec(TypedDict):
    """Git ref selected for a sandbox mount."""

    type: Literal["branch", "tag"]
    name: str


class GitMountConfigRequired(TypedDict):
    """Required Git configuration for a sandbox mount."""

    remote_url: str


class GitMountConfig(GitMountConfigRequired, total=False):
    """Git configuration for a sandbox mount."""

    ref: GitMountRefSpec
    refresh_interval_seconds: int


class GitMountSpec(TypedDict):
    """Git-backed sandbox mount specification."""

    id: str
    type: Literal["git"]
    mount_path: str
    git: GitMountConfig


SandboxMount = Union[S3MountSpec, GCSMountSpec, GitMountSpec]


class AWSMountAuthConfig(TypedDict):
    """AWS credentials used by the backend to authenticate S3 mounts."""

    access_key_id: SandboxProxySecret
    secret_access_key: SandboxProxySecret


class GCPMountAuthConfig(TypedDict):
    """GCP credentials used by the backend to authenticate GCS mounts."""

    service_account_json: SandboxProxySecret


class SandboxMountAuthConfig(TypedDict, total=False):
    """Provider auth blocks for sandbox mounts."""

    aws: AWSMountAuthConfig
    gcp: GCPMountAuthConfig


class AWSMountAuth(TypedDict):
    """SDK helper output for AWS mount auth."""

    type: Literal["aws"]
    aws: AWSMountAuthConfig


class GCPMountAuth(TypedDict):
    """SDK helper output for GCP mount auth."""

    type: Literal["gcp"]
    gcp: GCPMountAuthConfig


SandboxMountAuth = Union[AWSMountAuth, GCPMountAuth]


class SandboxMountConfig(TypedDict):
    """Public mount config sent to the sandbox API."""

    auth: SandboxMountAuthConfig
    mounts: list[SandboxMount]


def _require_non_empty_string(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _copy_cache_config(cache: MountCacheConfig) -> MountCacheConfig:
    copied: MountCacheConfig = {}
    if "max_size_bytes" in cache:
        copied["max_size_bytes"] = cache["max_size_bytes"]
    if "writeback_seconds" in cache:
        copied["writeback_seconds"] = cache["writeback_seconds"]
    return copied


def _copy_mount_secret(secret: Any, field: str) -> SandboxProxySecret:
    if not isinstance(secret, dict):
        raise ValueError(f"{field} must be a sandbox secret")
    secret_type = secret.get("type")
    if secret_type not in {"workspace_secret", "opaque"}:
        raise ValueError(f"{field} must use workspace_secret or opaque")
    value = secret.get("value")
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field}.value must be a non-empty string")
    return {"type": secret_type, "value": value}


def aws_mount_auth(
    *,
    access_key_id: SandboxProxySecret,
    secret_access_key: SandboxProxySecret,
) -> AWSMountAuth:
    """Build AWS auth for S3 mounts inside ``mount_config.auth.aws``."""
    return {
        "type": "aws",
        "aws": {
            "access_key_id": _copy_mount_secret(access_key_id, "access_key_id"),
            "secret_access_key": _copy_mount_secret(
                secret_access_key, "secret_access_key"
            ),
        },
    }


def gcp_mount_auth(
    *,
    service_account_json: SandboxProxySecret,
) -> GCPMountAuth:
    """Build GCP auth for GCS mounts inside ``mount_config.auth.gcp``."""
    return {
        "type": "gcp",
        "gcp": {
            "service_account_json": _copy_mount_secret(
                service_account_json, "service_account_json"
            ),
        },
    }


def _require_git_remote_url(remote_url: str) -> str:
    if not isinstance(remote_url, str) or remote_url == "":
        raise ValueError("remote_url must be a non-empty string")
    if remote_url != remote_url.strip() or any(
        char.isspace() or char == "\x00" for char in remote_url
    ):
        raise ValueError("remote_url must not contain whitespace or NUL bytes")

    parsed = urlsplit(remote_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("remote_url must be an absolute HTTPS URL")
    if parsed.username or parsed.password:
        raise ValueError("remote_url must not include embedded credentials")
    if not parsed.path or parsed.path == "/":
        raise ValueError("remote_url must include a repository path")
    if parsed.query or parsed.fragment:
        raise ValueError("remote_url must not include query or fragment")
    return remote_url


def _copy_git_ref(ref: GitMountRefSpec) -> GitMountRefSpec:
    if not isinstance(ref, dict):
        raise ValueError("ref must be a dictionary")
    ref_type = ref.get("type")
    if ref_type not in {"branch", "tag"}:
        raise ValueError("ref.type must be branch or tag")
    return {
        "type": ref_type,
        "name": _require_non_empty_string(ref.get("name", ""), "ref.name"),
    }


def s3_mount(
    *,
    id: str,
    mount_path: str,
    bucket: str,
    region: str = "us-east-1",
    prefix: str | None = None,
    endpoint_url: str = "https://s3.amazonaws.com",
    path_style: bool = False,
    read_only: bool | None = None,
    cache: MountCacheConfig | None = None,
) -> S3MountSpec:
    """Build an S3-backed sandbox mount specification."""
    s3: S3MountConfig = {
        "endpoint_url": _require_non_empty_string(endpoint_url, "endpoint_url"),
        "region": _require_non_empty_string(region, "region"),
        "bucket": _require_non_empty_string(bucket, "bucket"),
        "path_style": path_style,
    }
    if prefix is not None:
        s3["prefix"] = _require_non_empty_string(prefix, "prefix")

    mount: S3MountSpec = {
        "id": _require_non_empty_string(id, "id"),
        "type": "s3",
        "mount_path": _require_non_empty_string(mount_path, "mount_path"),
        "s3": s3,
    }
    if read_only is not None:
        mount["read_only"] = read_only
    if cache is not None:
        mount["cache"] = _copy_cache_config(cache)
    return mount


def git_mount(
    *,
    id: str,
    mount_path: str,
    remote_url: str,
    ref: GitMountRefSpec | None = None,
    refresh_interval_seconds: int | None = None,
) -> GitMountSpec:
    """Build a public Git-backed sandbox mount specification."""
    git: GitMountConfig = {
        "remote_url": _require_git_remote_url(remote_url),
    }
    if ref is not None:
        git["ref"] = _copy_git_ref(ref)
    if refresh_interval_seconds is not None:
        if refresh_interval_seconds < 1:
            raise ValueError("refresh_interval_seconds must be at least 1")
        git["refresh_interval_seconds"] = refresh_interval_seconds

    return {
        "id": _require_non_empty_string(id, "id"),
        "type": "git",
        "mount_path": _require_non_empty_string(mount_path, "mount_path"),
        "git": git,
    }


def gcs_mount(
    *,
    id: str,
    mount_path: str,
    bucket: str,
    prefix: str | None = None,
    read_only: bool | None = None,
    cache: MountCacheConfig | None = None,
) -> GCSMountSpec:
    """Build a GCS-backed sandbox mount specification."""
    gcs: GCSMountConfig = {
        "bucket": _require_non_empty_string(bucket, "bucket"),
    }
    if prefix is not None:
        gcs["prefix"] = _require_non_empty_string(prefix, "prefix")

    mount: GCSMountSpec = {
        "id": _require_non_empty_string(id, "id"),
        "type": "gcs",
        "mount_path": _require_non_empty_string(mount_path, "mount_path"),
        "gcs": gcs,
    }
    if read_only is not None:
        mount["read_only"] = read_only
    if cache is not None:
        mount["cache"] = _copy_cache_config(cache)
    return mount


def _normalize_mounts(mounts: Sequence[SandboxMount]) -> list[SandboxMount]:
    if isinstance(mounts, dict) or isinstance(mounts, str) or not mounts:
        raise ValueError("mounts must be a non-empty list of mount dictionaries")
    normalized: list[SandboxMount] = []
    for mount in mounts:
        if not isinstance(mount, dict) or not mount:
            raise ValueError("mounts must be a non-empty list of mount dictionaries")
        mount_type = mount.get("type")
        if mount_type not in {"s3", "gcs", "git"}:
            raise ValueError("mount_config only supports s3, gcs, and git mounts")
        _reject_provider_credentials_in_mount(mount)
        normalized.append(mount)
    return normalized


_FORBIDDEN_MOUNT_CREDENTIAL_FIELDS = {
    "access_key_id",
    "secret_access_key",
    "session_token",
    "service_account_json",
    "access_token",
    "refresh_token",
    "credentials",
    "credential",
}


def _reject_provider_credentials_in_mount(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in _FORBIDDEN_MOUNT_CREDENTIAL_FIELDS:
                raise ValueError(
                    "provider credentials must be supplied in mount_config.auth, "
                    "not individual mount specs"
                )
            _reject_provider_credentials_in_mount(child)
    elif isinstance(value, list):
        for child in value:
            _reject_provider_credentials_in_mount(child)


def _normalize_mount_auth(
    auth: Sequence[SandboxMountAuth],
) -> SandboxMountAuthConfig:
    if isinstance(auth, dict) or isinstance(auth, str):
        raise ValueError("auth must be a list of provider auth blocks")
    by_provider: SandboxMountAuthConfig = {}
    for block in auth:
        if not isinstance(block, dict) or not block:
            raise ValueError("auth must be a list of provider auth blocks")
        provider = block.get("type")
        if provider not in {"aws", "gcp"}:
            raise ValueError("mount_config auth only supports aws and gcp blocks")
        if provider in by_provider:
            raise ValueError(f"duplicate {provider} auth rule in mount_config")
        if provider == "aws":
            aws = block.get("aws")
            if not isinstance(aws, dict):
                raise ValueError("aws mount auth must include an aws block")
            by_provider["aws"] = {
                "access_key_id": _copy_mount_secret(
                    aws.get("access_key_id"), "access_key_id"
                ),
                "secret_access_key": _copy_mount_secret(
                    aws.get("secret_access_key"), "secret_access_key"
                ),
            }
        else:
            gcp = block.get("gcp")
            if not isinstance(gcp, dict):
                raise ValueError("gcp mount auth must include a gcp block")
            by_provider["gcp"] = {
                "service_account_json": _copy_mount_secret(
                    gcp.get("service_account_json"), "service_account_json"
                )
            }
    return by_provider


def mount_config(
    *,
    mounts: Sequence[SandboxMount],
    auth: Sequence[SandboxMountAuth] = (),
) -> SandboxMountConfig:
    """Build a high-level mount config from provider auth and mount specs.

    The returned value is sent as the public ``mount_config`` field. The
    backend expands provider auth into runtime proxy rules.
    """
    normalized_mounts = _normalize_mounts(mounts)
    auth_by_provider = _normalize_mount_auth(auth)
    mount_providers = {mount["type"] for mount in normalized_mounts}

    if "s3" in mount_providers and "aws" not in auth_by_provider:
        raise ValueError("s3 mounts require aws auth in mount_config")
    if "gcs" in mount_providers and "gcp" not in auth_by_provider:
        raise ValueError("gcs mounts require gcp auth in mount_config")
    if "aws" in auth_by_provider and "s3" not in mount_providers:
        raise ValueError("aws auth requires at least one s3 mount in mount_config")
    if "gcp" in auth_by_provider and "gcs" not in mount_providers:
        raise ValueError("gcp auth requires at least one gcs mount in mount_config")

    return {
        "auth": auth_by_provider,
        "mounts": normalized_mounts,
    }


def validate_mount_config_proxy_config(
    mount_config: SandboxMountConfig,
    proxy_config: SandboxProxyConfig | None,
) -> None:
    """Reject explicit provider proxy rules owned by mount_config auth."""
    if proxy_config is None:
        return
    auth = mount_config.get("auth", {})
    rules = proxy_config.get("rules", [])
    if not isinstance(rules, list):
        raise ValueError("proxy_config rules must be a list")
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        rule_type = rule.get("type")
        if rule_type in {"aws", "gcp"} and rule_type in auth:
            raise ValueError(
                f"{rule_type} auth cannot be provided in both "
                "mount_config and proxy_config"
            )
