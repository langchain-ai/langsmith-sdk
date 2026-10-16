"""Helpers for building sandbox proxy configurations."""

from __future__ import annotations

import warnings
from collections.abc import Mapping, Sequence
from typing import Any, Literal, TypedDict, overload


class SandboxProxySecret(TypedDict):
    """A secret value that can be used by sandbox proxy rules."""

    type: Literal["workspace_secret", "opaque"]
    value: str


SandboxProxyRule = dict[str, Any]
SandboxProxyConfig = dict[str, Any]


def _require_non_empty_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _require_non_empty_string_list(values: Sequence[str], field: str) -> list[str]:
    if isinstance(values, str) or not values:
        raise ValueError(f"{field} must be a non-empty list of strings")
    normalized = [_require_non_empty_string(value, field) for value in values]
    return normalized


def _require_env_vars(env_vars: Mapping[str, str]) -> dict[str, str]:
    if not isinstance(env_vars, Mapping) or not env_vars:
        raise ValueError("env_vars must be a non-empty mapping of names to values")
    resolved: dict[str, str] = {}
    for name, value in env_vars.items():
        # Validated on the trimmed form, stored verbatim: whitespace can be significant.
        _require_non_empty_string(value, f"env_vars[{name}]")
        resolved[_require_non_empty_string(name, "env_vars name")] = value
    return resolved


def workspace_secret(name: str) -> SandboxProxySecret:
    """Create a LangSmith workspace secret reference for a proxy configuration.

    Args:
        name: Workspace secret name, with or without surrounding braces.

    Returns:
        A proxy secret reference such as
        ``{"type": "workspace_secret", "value": "{AWS_ACCESS_KEY_ID}"}``.
    """
    normalized = _require_non_empty_string(name, "name")
    starts = normalized.startswith("{")
    ends = normalized.endswith("}")
    if starts != ends:
        raise ValueError("workspace secret must be a name or a {NAME} reference")
    if starts and not normalized[1:-1].strip():
        raise ValueError("workspace secret reference must contain a name")
    value = normalized if starts else f"{{{normalized}}}"
    return {"type": "workspace_secret", "value": value}


def opaque_secret(value: str) -> SandboxProxySecret:
    """Provide a write-only secret value for a proxy configuration.

    The value is sent when creating or updating the sandbox proxy config, but
    LangSmith stores it as an opaque secret and does not return it from the API.
    """
    return {"type": "opaque", "value": _require_non_empty_string(value, "value")}


def _normalize_proxy_rules(
    rules: Sequence[SandboxProxyRule] | None,
) -> list[SandboxProxyRule]:
    if rules is None:
        return []
    if isinstance(rules, dict) or isinstance(rules, str):
        raise ValueError("rules must be a list of proxy rule dictionaries")
    normalized: list[SandboxProxyRule] = []
    for rule in rules:
        if not isinstance(rule, dict) or not rule:
            raise ValueError("rules must be a list of proxy rule dictionaries")
        _validate_proxy_provider_rule(rule)
        normalized.append(rule)
    return normalized


def _validate_proxy_provider_rule(rule: SandboxProxyRule) -> None:
    if rule.get("type") == "aws":
        aws = rule.get("aws")
        if isinstance(aws, dict):
            _get_aws_role_arn(aws)
        return
    if rule.get("type") != "gcp":
        return
    gcp = rule.get("gcp")
    if isinstance(gcp, dict) and "scopes" in gcp:
        _require_non_empty_string_list(gcp["scopes"], "scopes")


_AWS_ROLE_FIELDS = {"role_arn", "subject_scope"}


def _get_aws_role_arn(aws: dict[str, Any]) -> str | None:
    """Validate role-only descriptors without tightening legacy static inputs."""
    if "role_arn" not in aws or aws["role_arn"] == "":
        return None
    role_arn = _require_non_empty_string(aws["role_arn"], "role_arn")
    if not set(aws) <= _AWS_ROLE_FIELDS:
        raise ValueError("AWS role auth must contain only role_arn and subject_scope")
    return role_arn


def _aws_role_config(aws: dict[str, Any]) -> dict[str, Any] | None:
    """Return the normalized role descriptor, or None for static credentials."""
    role_arn = _get_aws_role_arn(aws)
    if role_arn is None:
        if aws.get("subject_scope") is not None:
            raise ValueError("subject_scope requires role_arn")
        return None
    return {"role_arn": role_arn, **_optional_strings(aws, "subject_scope")}


def _optional_strings(source: Mapping[str, Any], *fields: str) -> dict[str, str]:
    return {
        field: _require_non_empty_string(source[field], field)
        for field in fields
        if source.get(field) is not None
    }


def _gcp_config(gcp: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a gcp rule config: service account key or workload identity."""
    wif_only = _optional_strings(gcp, "service_account_email", "subject_scope")
    if gcp.get("workload_identity_provider") is not None:
        if gcp.get("service_account_json") is not None:
            raise ValueError(
                "workload_identity_provider and service_account_json are "
                "mutually exclusive"
            )
        config: dict[str, Any] = {
            "workload_identity_provider": _require_non_empty_string(
                gcp["workload_identity_provider"], "workload_identity_provider"
            ),
            **wif_only,
        }
    elif wif_only:
        raise ValueError(
            "service_account_email and subject_scope require workload_identity_provider"
        )
    elif gcp.get("service_account_json") is None:
        raise ValueError(
            "GCP auth requires service_account_json or workload_identity_provider"
        )
    else:
        config = {"service_account_json": gcp["service_account_json"]}
    if gcp.get("scopes") is not None:
        config["scopes"] = _require_non_empty_string_list(gcp["scopes"], "scopes")
    return config


def _azure_config(azure: Mapping[str, Any]) -> dict[str, Any]:
    """Validate an azure rule config: workload identity, account key, or SAS."""
    if azure.get("tenant_id") is not None or azure.get("client_id") is not None:
        if any(
            azure.get(field) is not None
            for field in ("storage_account", "account_key", "sas_token")
        ):
            raise ValueError(
                "tenant_id/client_id and storage_account, account_key or "
                "sas_token are mutually exclusive"
            )
        config: dict[str, Any] = {
            "tenant_id": _require_non_empty_string(azure.get("tenant_id"), "tenant_id"),
            "client_id": _require_non_empty_string(azure.get("client_id"), "client_id"),
            **_optional_strings(azure, "subject_scope"),
        }
        if azure.get("resources") is not None:
            config["resources"] = _require_non_empty_string_list(
                azure["resources"], "resources"
            )
        return config
    if azure.get("subject_scope") is not None or azure.get("resources") is not None:
        raise ValueError("subject_scope and resources require tenant_id and client_id")
    if (azure.get("account_key") is None) == (azure.get("sas_token") is None):
        raise ValueError(
            "Azure auth requires tenant_id and client_id, or storage_account "
            "with exactly one of account_key or sas_token"
        )
    secret = "account_key" if azure.get("account_key") is not None else "sas_token"
    return {
        "storage_account": _require_non_empty_string(
            azure.get("storage_account"), "storage_account"
        ),
        secret: azure[secret],
    }


def _provider_rule(
    provider: str,
    config: dict[str, Any],
    name: str,
    enabled: bool,
    env_vars: Mapping[str, str] | None,
) -> SandboxProxyRule:
    rule: SandboxProxyRule = {
        "name": _require_non_empty_string(name, "name"),
        "type": provider,
        "enabled": enabled,
        provider: config,
    }
    if env_vars is not None:
        rule["env_vars"] = _require_env_vars(env_vars)
    return rule


def proxy_config(
    *,
    rules: Sequence[SandboxProxyRule] | None = None,
    no_proxy: Sequence[str] | None = None,
    access_control: dict[str, Any] | None = None,
) -> SandboxProxyConfig:
    """Build a sandbox proxy config from one or more proxy rules.

    Use provider-specific rule helpers such as ``aws_auth``, ``gcp_auth``
    and ``azure_auth`` when a sandbox needs multiple auth flows.

    Args:
        no_proxy: Deprecated and ignored. The sandbox runtime intercepts
            egress transparently and has no proxy bypass list.
    """
    if no_proxy is not None:
        warnings.warn(
            "no_proxy is deprecated and ignored; the sandbox runtime has no "
            "proxy bypass list",
            DeprecationWarning,
            stacklevel=2,
        )
    config: SandboxProxyConfig = {"rules": _normalize_proxy_rules(rules)}
    if access_control is not None:
        if not isinstance(access_control, dict):
            raise ValueError("access_control must be a dictionary")
        config["access_control"] = dict(access_control)
    return config


@overload
def aws_auth(
    *,
    access_key_id: SandboxProxySecret,
    secret_access_key: SandboxProxySecret,
    role_arn: Literal[""] | None = None,
    subject_scope: None = None,
    name: str = "aws",
    enabled: bool = True,
    env_vars: Mapping[str, str] | None = None,
) -> SandboxProxyRule: ...


@overload
def aws_auth(
    *,
    role_arn: str,
    subject_scope: str | None = None,
    access_key_id: None = None,
    secret_access_key: None = None,
    name: str = "aws",
    enabled: bool = True,
    env_vars: Mapping[str, str] | None = None,
) -> SandboxProxyRule: ...


def aws_auth(
    *,
    access_key_id: SandboxProxySecret | None = None,
    secret_access_key: SandboxProxySecret | None = None,
    role_arn: str | None = None,
    subject_scope: str | None = None,
    name: str = "aws",
    enabled: bool = True,
    env_vars: Mapping[str, str] | None = None,
) -> SandboxProxyRule:
    """Build a sandbox proxy rule that signs AWS HTTPS requests.

    The sandbox proxy keeps the real AWS credentials outside the sandbox and
    signs supported AWS requests with SigV4 on the sandbox's behalf.
    Provide either ``role_arn`` or both static credentials, supplied as
    ``workspace_secret`` or ``opaque`` values. ``role_arn`` is assumed with
    ``AssumeRoleWithWebIdentity`` using a LangSmith-signed workload identity
    token; the role's trust policy must trust LangSmith's OIDC issuer.
    LangSmith renews credentials; clients must not provide temporary
    credentials.

    In ``proxy_config``, a role uses its effective IAM permissions. In
    ``mount_config(auth=[...])``, it is restricted to the configured S3 mounts.
    Role authentication is configured at sandbox creation, not through updates.

    Args:
        subject_scope: Workload identity token subject, ``"workspace"``
            (the default) or ``"tag:<tag value id>"``. A tag scope must name one
            of the sandbox's ``tag_value_ids``. Only valid with ``role_arn``.
        env_vars: Plaintext environment variables set for every command in the
            sandbox while this rule is enabled, for tools that refuse to run
            unless a credential variable is present even though the proxy
            injects the real credential on the wire.
    """
    aws: dict[str, Any] = {}
    if role_arn is not None:
        aws["role_arn"] = role_arn
    if subject_scope is not None:
        aws["subject_scope"] = subject_scope
    if access_key_id is not None:
        aws["access_key_id"] = access_key_id
    if secret_access_key is not None:
        aws["secret_access_key"] = secret_access_key
    role_config = _aws_role_config(aws)
    if role_config is not None:
        aws = role_config
    else:
        if access_key_id is None or secret_access_key is None:
            raise ValueError("AWS auth requires role_arn or both static credentials")
        aws = {
            "access_key_id": access_key_id,
            "secret_access_key": secret_access_key,
        }
    return _provider_rule("aws", aws, name, enabled, env_vars)


@overload
def gcp_auth(
    *,
    service_account_json: SandboxProxySecret,
    scopes: Sequence[str] | None = None,
    name: str = "gcp",
    enabled: bool = True,
    env_vars: Mapping[str, str] | None = None,
) -> SandboxProxyRule: ...


@overload
def gcp_auth(
    *,
    workload_identity_provider: str,
    service_account_email: str | None = None,
    subject_scope: str | None = None,
    scopes: Sequence[str] | None = None,
    name: str = "gcp",
    enabled: bool = True,
    env_vars: Mapping[str, str] | None = None,
) -> SandboxProxyRule: ...


def gcp_auth(
    *,
    service_account_json: SandboxProxySecret | None = None,
    workload_identity_provider: str | None = None,
    service_account_email: str | None = None,
    subject_scope: str | None = None,
    scopes: Sequence[str] | None = None,
    name: str = "gcp",
    enabled: bool = True,
    env_vars: Mapping[str, str] | None = None,
) -> SandboxProxyRule:
    """Build a sandbox proxy rule that injects GCP OAuth bearer auth.

    Provide ``service_account_json`` (a ``workspace_secret`` or ``opaque``
    value) or ``workload_identity_provider``, the full name of a workload
    identity provider that trusts LangSmith's OIDC issuer, optionally with
    ``service_account_email`` to impersonate. Workload identity is fixed at
    sandbox creation.

    Args:
        scopes: OAuth scopes; the server defaults to cloud-platform.
        subject_scope: ``"workspace"`` (default) or ``"tag:<tag value id>"``.
        env_vars: Plaintext environment variables set for every command in the
            sandbox while this rule is enabled, for tools that refuse to run
            unless a credential variable is present even though the proxy
            injects the real credential on the wire.
    """
    config = _gcp_config(
        {
            "service_account_json": service_account_json,
            "workload_identity_provider": workload_identity_provider,
            "service_account_email": service_account_email,
            "subject_scope": subject_scope,
            "scopes": scopes,
        }
    )
    return _provider_rule("gcp", config, name, enabled, env_vars)


AzureResource = Literal[
    "https://storage.azure.com",
    "https://vault.azure.net",
    "https://management.azure.com",
    "https://cognitiveservices.azure.com",
]


@overload
def azure_auth(
    *,
    tenant_id: str,
    client_id: str,
    subject_scope: str | None = None,
    resources: Sequence[AzureResource] | None = None,
    name: str = "azure",
    enabled: bool = True,
    env_vars: Mapping[str, str] | None = None,
) -> SandboxProxyRule: ...


@overload
def azure_auth(
    *,
    storage_account: str,
    account_key: SandboxProxySecret,
    name: str = "azure",
    enabled: bool = True,
    env_vars: Mapping[str, str] | None = None,
) -> SandboxProxyRule: ...


@overload
def azure_auth(
    *,
    storage_account: str,
    sas_token: SandboxProxySecret,
    name: str = "azure",
    enabled: bool = True,
    env_vars: Mapping[str, str] | None = None,
) -> SandboxProxyRule: ...


def azure_auth(
    *,
    tenant_id: str | None = None,
    client_id: str | None = None,
    subject_scope: str | None = None,
    resources: Sequence[AzureResource] | None = None,
    storage_account: str | None = None,
    account_key: SandboxProxySecret | None = None,
    sas_token: SandboxProxySecret | None = None,
    name: str = "azure",
    enabled: bool = True,
    env_vars: Mapping[str, str] | None = None,
) -> SandboxProxyRule:
    """Build a sandbox proxy rule that authenticates Azure requests.

    Use one form: workload identity (``tenant_id`` and ``client_id`` of an Entra
    app or managed identity that trusts LangSmith's OIDC issuer; fixed at
    sandbox creation), or ``storage_account`` with ``account_key`` or
    ``sas_token`` (``workspace_secret`` or ``opaque`` values).

    Args:
        subject_scope: ``"workspace"`` (default) or ``"tag:<tag value id>"``.
        resources: Azure resources to request tokens for; all when omitted.
        env_vars: See ``aws_auth``.
    """
    config = _azure_config(
        {
            "tenant_id": tenant_id,
            "client_id": client_id,
            "subject_scope": subject_scope,
            "resources": resources,
            "storage_account": storage_account,
            "account_key": account_key,
            "sas_token": sas_token,
        }
    )
    return _provider_rule("azure", config, name, enabled, env_vars)
