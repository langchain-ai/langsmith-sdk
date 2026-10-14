"""Helpers and type definitions for sandbox mount configurations."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal, TypedDict, Union, cast
from urllib.parse import urlsplit

from langsmith.sandbox._proxy_config import (
    SandboxProxyConfig,
    SandboxProxyRule,
    SandboxProxySecret,
    _aws_role_config,
)


class MountCacheConfig(TypedDict, total=False):
    """Optional per-mount cache configuration supported by bucket mounts."""

    max_size_bytes: int
    writeback_seconds: int


class MountEncryptionConfig(TypedDict):
    """Customer-managed key that uploads through a mount are encrypted with.

    For S3 mounts, ``kms_key`` is a KMS key ARN in the mount's region and uploads
    use SSE-KMS with it.
    """

    kms_key: str


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


class S3MountSpecBase(BucketMountSpecBase, total=False):
    """Optional fields applied per S3 sandbox mount."""

    encryption: MountEncryptionConfig


class S3MountSpec(S3MountSpecBase):
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


class AzureBlobMountConfigRequired(TypedDict):
    """Required Azure Blob configuration for a sandbox mount."""

    storage_account: str
    container: str


class AzureBlobMountConfig(AzureBlobMountConfigRequired, total=False):
    """Azure Blob container configuration for a sandbox mount."""

    prefix: str


class AzureBlobMountSpec(BucketMountSpecBase):
    """Azure Blob container-backed sandbox mount specification."""

    id: str
    type: Literal["azure_blob"]
    mount_path: str
    azure_blob: AzureBlobMountConfig


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


class ContextHubMountConfigRequired(TypedDict):
    """Required Context Hub configuration for a sandbox mount."""

    repo: str


class ContextHubMountConfig(ContextHubMountConfigRequired, total=False):
    """Context Hub configuration for a sandbox mount."""

    initial_pull_only: bool


class ContextHubMountSpec(TypedDict):
    """Read-only Context Hub-backed sandbox mount specification."""

    id: str
    type: Literal["contexthub"]
    mount_path: str
    contexthub: ContextHubMountConfig


SandboxMount = Union[
    S3MountSpec, GCSMountSpec, AzureBlobMountSpec, GitMountSpec, ContextHubMountSpec
]


class AWSMountAuthConfig(TypedDict):
    """AWS credentials used by the backend to authenticate S3 mounts."""

    access_key_id: SandboxProxySecret
    secret_access_key: SandboxProxySecret


class AWSMountRoleAuthConfigRequired(TypedDict):
    """IAM role restricted by the backend to this sandbox's S3 mount scopes."""

    role_arn: str


class AWSMountRoleAuthConfig(AWSMountRoleAuthConfigRequired, total=False):
    """IAM role restricted by the backend to this sandbox's S3 mount scopes."""

    subject_scope: str


class GCPMountAuthConfig(TypedDict):
    """GCP credentials used by the backend to authenticate GCS mounts."""

    service_account_json: SandboxProxySecret


class GCPMountWorkloadIdentityAuthConfigRequired(TypedDict):
    """GCP workload identity federation used to authenticate GCS mounts."""

    workload_identity_provider: str


class GCPMountWorkloadIdentityAuthConfig(
    GCPMountWorkloadIdentityAuthConfigRequired, total=False
):
    """GCP workload identity federation used to authenticate GCS mounts."""

    service_account_email: str
    subject_scope: str


class AzureMountWorkloadIdentityAuthConfigRequired(TypedDict):
    """Entra workload identity federation used to authenticate Azure Blob mounts."""

    tenant_id: str
    client_id: str


class AzureMountWorkloadIdentityAuthConfig(
    AzureMountWorkloadIdentityAuthConfigRequired, total=False
):
    """Entra workload identity federation used to authenticate Azure Blob mounts."""

    subject_scope: str


class AzureMountAccountKeyAuthConfig(TypedDict):
    """Storage account key used to authenticate Azure Blob mounts."""

    account_key: SandboxProxySecret


class AzureMountSASAuthConfig(TypedDict):
    """SAS token used to authenticate Azure Blob mounts."""

    sas_token: SandboxProxySecret


class SandboxMountAuthConfig(TypedDict, total=False):
    """Provider auth blocks for sandbox mounts."""

    aws: Union[AWSMountAuthConfig, AWSMountRoleAuthConfig]
    gcp: Union[GCPMountAuthConfig, GCPMountWorkloadIdentityAuthConfig]
    azure: Union[
        AzureMountWorkloadIdentityAuthConfig,
        AzureMountAccountKeyAuthConfig,
        AzureMountSASAuthConfig,
    ]


SandboxMountAuth = SandboxProxyRule


class SandboxMountConfig(TypedDict):
    """Public mount config sent to the sandbox API."""

    auth: SandboxMountAuthConfig
    mounts: list[SandboxMount]


def _require_non_empty_string(value: object, field: str) -> str:
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
    encryption: MountEncryptionConfig | None = None,
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
    if encryption is not None:
        mount["encryption"] = {
            "kms_key": _require_non_empty_string(
                encryption.get("kms_key", ""), "encryption.kms_key"
            )
        }
    return mount


def azure_blob_mount(
    *,
    id: str,
    mount_path: str,
    storage_account: str,
    container: str,
    prefix: str | None = None,
    read_only: bool | None = None,
    cache: MountCacheConfig | None = None,
) -> AzureBlobMountSpec:
    """Build an Azure Blob container-backed sandbox mount specification."""
    azure_blob: AzureBlobMountConfig = {
        "storage_account": _require_non_empty_string(
            storage_account, "storage_account"
        ),
        "container": _require_non_empty_string(container, "container"),
    }
    if prefix is not None:
        azure_blob["prefix"] = _require_non_empty_string(prefix, "prefix")

    mount: AzureBlobMountSpec = {
        "id": _require_non_empty_string(id, "id"),
        "type": "azure_blob",
        "mount_path": _require_non_empty_string(mount_path, "mount_path"),
        "azure_blob": azure_blob,
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


def context_hub_mount(
    *,
    id: str,
    mount_path: str,
    repo: str,
    initial_pull_only: bool | None = None,
) -> ContextHubMountSpec:
    """Build a read-only Context Hub-backed sandbox mount specification.

    The repo's latest commit tree is mirrored into ``mount_path`` and kept in
    sync for the sandbox's lifetime unless ``initial_pull_only`` is set. The
    sync is one-way: files written under ``mount_path`` inside the sandbox are
    never pushed back to the repo, and the next sync overwrites them.
    """
    contexthub: ContextHubMountConfig = {
        "repo": _require_non_empty_string(repo, "repo"),
    }
    if initial_pull_only is not None:
        contexthub["initial_pull_only"] = initial_pull_only

    mount: ContextHubMountSpec = {
        "id": _require_non_empty_string(id, "id"),
        "type": "contexthub",
        "mount_path": _require_non_empty_string(mount_path, "mount_path"),
        "contexthub": contexthub,
    }
    return mount


def _normalize_mounts(mounts: Sequence[SandboxMount]) -> list[SandboxMount]:
    if isinstance(mounts, dict) or isinstance(mounts, str) or not mounts:
        raise ValueError("mounts must be a non-empty list of mount dictionaries")
    normalized: list[SandboxMount] = []
    for mount in mounts:
        if not isinstance(mount, dict) or not mount:
            raise ValueError("mounts must be a non-empty list of mount dictionaries")
        mount_type = mount.get("type")
        if mount_type not in {"s3", "gcs", "azure_blob", "git", "contexthub"}:
            raise ValueError(
                "mount_config only supports s3, gcs, azure_blob, git, and "
                "contexthub mounts"
            )
        _reject_provider_credentials_in_mount(mount)
        normalized.append(mount)
    return normalized


_FORBIDDEN_MOUNT_CREDENTIAL_FIELDS = {
    "access_key_id",
    "secret_access_key",
    "session_token",
    "service_account_json",
    "account_key",
    "sas_token",
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


def _gcp_mount_auth(gcp: dict[str, Any]) -> SandboxMountAuthConfig:
    if not gcp.get("workload_identity_provider"):
        return {
            "gcp": {
                "service_account_json": _copy_mount_secret(
                    gcp.get("service_account_json"), "service_account_json"
                )
            }
        }
    if gcp.get("service_account_json") is not None:
        raise ValueError(
            "workload_identity_provider and service_account_json are mutually exclusive"
        )
    config: GCPMountWorkloadIdentityAuthConfig = {
        "workload_identity_provider": _require_non_empty_string(
            gcp["workload_identity_provider"], "workload_identity_provider"
        )
    }
    if gcp.get("service_account_email") is not None:
        config["service_account_email"] = _require_non_empty_string(
            gcp["service_account_email"], "service_account_email"
        )
    if gcp.get("subject_scope") is not None:
        config["subject_scope"] = _require_non_empty_string(
            gcp["subject_scope"], "subject_scope"
        )
    return {"gcp": config}


def _azure_mount_auth(azure: dict[str, Any]) -> SandboxMountAuthConfig:
    """Keep only the fields mount_config.auth.azure accepts.

    A static block's ``storage_account`` is checked against the mounts by
    ``mount_config``; ``resources`` does not apply to mounts.
    """
    if azure.get("tenant_id") or azure.get("client_id"):
        if azure.get("account_key") is not None or azure.get("sas_token") is not None:
            raise ValueError(
                "tenant_id/client_id and account_key or sas_token are mutually "
                "exclusive"
            )
        config: AzureMountWorkloadIdentityAuthConfig = {
            "tenant_id": _require_non_empty_string(azure.get("tenant_id"), "tenant_id"),
            "client_id": _require_non_empty_string(azure.get("client_id"), "client_id"),
        }
        if azure.get("subject_scope") is not None:
            config["subject_scope"] = _require_non_empty_string(
                azure["subject_scope"], "subject_scope"
            )
        return {"azure": config}
    has_key = azure.get("account_key") is not None
    if has_key == (azure.get("sas_token") is not None):
        raise ValueError(
            "azure mount auth requires tenant_id and client_id, or exactly one "
            "of account_key or sas_token"
        )
    if has_key:
        return {
            "azure": {
                "account_key": _copy_mount_secret(azure["account_key"], "account_key")
            }
        }
    return {"azure": {"sas_token": _copy_mount_secret(azure["sas_token"], "sas_token")}}


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
        if provider not in {"aws", "gcp", "azure"}:
            raise ValueError(
                "mount_config auth only supports aws, gcp, and azure blocks"
            )
        if provider in by_provider:
            raise ValueError(f"duplicate {provider} auth rule in mount_config")
        config = block.get(provider)
        if not isinstance(config, dict):
            article = "a" if provider == "gcp" else "an"
            raise ValueError(
                f"{provider} mount auth must include {article} {provider} block"
            )
        if provider == "aws":
            role = _aws_role_config(config)
            if role is not None:
                by_provider["aws"] = cast(AWSMountRoleAuthConfig, role)
                continue
            if config.get("subject_scope") is not None:
                raise ValueError("subject_scope requires role_arn")
            by_provider["aws"] = {
                "access_key_id": _copy_mount_secret(
                    config.get("access_key_id"), "access_key_id"
                ),
                "secret_access_key": _copy_mount_secret(
                    config.get("secret_access_key"), "secret_access_key"
                ),
            }
        elif provider == "gcp":
            by_provider.update(_gcp_mount_auth(config))
        else:
            by_provider.update(_azure_mount_auth(config))
    return by_provider


def _static_azure_auth_storage_account(
    auth: Sequence[SandboxMountAuth],
) -> str | None:
    for block in auth:
        azure = block.get("azure") if block.get("type") == "azure" else None
        if isinstance(azure, dict) and not (
            azure.get("tenant_id") or azure.get("client_id")
        ):
            account = azure.get("storage_account")
            return account if isinstance(account, str) else None
    return None


def mount_config(
    *,
    mounts: Sequence[SandboxMount],
    auth: Sequence[SandboxMountAuth] = (),
    proxy_config: SandboxProxyConfig | None = None,
) -> SandboxMountConfig:
    """Build a high-level mount config from provider auth and mount specs.

    The returned value is sent as the public ``mount_config`` field. The
    backend expands provider auth into runtime proxy rules.

    Instead of mount-scoped ``auth``, mounts can use an enabled rule in the
    same ``proxy_config`` passed here and to sandbox creation: an AWS rule for
    S3, a GCP workload identity rule for GCS, or an Azure rule for Azure Blob.
    That rule remains general proxy auth; it is not copied into mount-scoped
    auth or restricted to mount paths.
    """
    normalized_mounts = _normalize_mounts(mounts)
    auth_by_provider = _normalize_mount_auth(auth)
    mount_providers = {mount["type"] for mount in normalized_mounts}
    enabled_rules = [
        rule
        for rule in (proxy_config or {}).get("rules", [])
        if isinstance(rule, dict) and rule.get("enabled") is True
    ]
    proxy_providers = {rule.get("type") for rule in enabled_rules}
    has_gcp_workload_identity_rule = any(
        rule.get("type") == "gcp"
        and isinstance(rule.get("gcp"), dict)
        and rule["gcp"].get("workload_identity_provider")
        for rule in enabled_rules
    )

    if (
        "s3" in mount_providers
        and "aws" not in auth_by_provider
        and "aws" not in proxy_providers
    ):
        raise ValueError("s3 mounts require aws auth in mount_config")
    if (
        "gcs" in mount_providers
        and "gcp" not in auth_by_provider
        and not has_gcp_workload_identity_rule
    ):
        raise ValueError(
            "gcs mounts require gcp auth in mount_config or a GCP workload "
            "identity rule in proxy_config"
        )
    if (
        "azure_blob" in mount_providers
        and "azure" not in auth_by_provider
        and "azure" not in proxy_providers
    ):
        raise ValueError("azure_blob mounts require azure auth in mount_config")
    if "aws" in auth_by_provider and "s3" not in mount_providers:
        raise ValueError("aws auth requires at least one s3 mount in mount_config")
    if "gcp" in auth_by_provider and "gcs" not in mount_providers:
        raise ValueError("gcp auth requires at least one gcs mount in mount_config")
    if "azure" in auth_by_provider and "azure_blob" not in mount_providers:
        raise ValueError(
            "azure auth requires at least one azure_blob mount in mount_config"
        )
    static_account = _static_azure_auth_storage_account(auth)
    if static_account is not None:
        accounts = {
            mount["azure_blob"]["storage_account"]
            for mount in normalized_mounts
            if mount["type"] == "azure_blob"
        }
        if accounts != {static_account}:
            raise ValueError(
                "azure_blob mounts using an azure account key or SAS token must "
                "all use the auth's storage_account"
            )

    config: SandboxMountConfig = {
        "auth": auth_by_provider,
        "mounts": normalized_mounts,
    }
    validate_mount_config_proxy_config(config, proxy_config)
    return config


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
        if rule_type in {"aws", "gcp", "azure"} and rule_type in auth:
            raise ValueError(
                f"{rule_type} auth cannot be provided in both "
                "mount_config and proxy_config"
            )
