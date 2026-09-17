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


def _require_non_empty_string(value: str, field: str) -> str:
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
    if not isinstance(gcp, dict) or "scopes" not in gcp:
        raise ValueError("gcp proxy auth rules require scopes")
    _require_non_empty_string_list(gcp["scopes"], "scopes")


def _get_aws_role_arn(aws: dict[str, Any]) -> str | None:
    """Validate role-only descriptors without tightening legacy static inputs."""
    if "role_arn" not in aws or aws["role_arn"] == "":
        return None
    role_arn = _require_non_empty_string(aws["role_arn"], "role_arn")
    if set(aws) != {"role_arn"}:
        raise ValueError("AWS role auth must contain only role_arn")
    return role_arn


def proxy_config(
    *,
    rules: Sequence[SandboxProxyRule] | None = None,
    no_proxy: Sequence[str] | None = None,
    access_control: dict[str, Any] | None = None,
) -> SandboxProxyConfig:
    """Build a sandbox proxy config from one or more proxy rules.

    Use provider-specific rule helpers such as ``aws_auth`` and ``gcp_auth``
    when a sandbox needs multiple auth flows.

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
    name: str = "aws",
    enabled: bool = True,
    env_vars: Mapping[str, str] | None = None,
) -> SandboxProxyRule: ...


@overload
def aws_auth(
    *,
    role_arn: str,
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
    name: str = "aws",
    enabled: bool = True,
    env_vars: Mapping[str, str] | None = None,
) -> SandboxProxyRule:
    """Build a sandbox proxy rule that signs AWS HTTPS requests.

    The sandbox proxy keeps the real AWS credentials outside the sandbox and
    signs supported AWS requests with SigV4 on the sandbox's behalf.
    Provide either ``role_arn`` or both static credentials, supplied as
    ``workspace_secret`` or ``opaque`` values. IAM-role support must be enabled
    on the backend. LangSmith supplies the workspace External ID and renews
    credentials; clients must not provide temporary credentials or External IDs.

    In ``proxy_config``, a role uses its effective IAM permissions. In
    ``mount_config(auth=[...])``, it is restricted to the configured S3 mounts.
    Role authentication is configured at sandbox creation, not through updates.

    Args:
        env_vars: Plaintext environment variables set for every command in the
            sandbox while this rule is enabled, for tools that refuse to run
            unless a credential variable is present even though the proxy
            injects the real credential on the wire.
    """
    rule_name = _require_non_empty_string(name, "name")
    aws: dict[str, Any] = {}
    if role_arn is not None:
        aws["role_arn"] = role_arn
    if access_key_id is not None:
        aws["access_key_id"] = access_key_id
    if secret_access_key is not None:
        aws["secret_access_key"] = secret_access_key
    normalized_role = _get_aws_role_arn(aws)
    if normalized_role is not None:
        aws = {"role_arn": normalized_role}
    else:
        if access_key_id is None or secret_access_key is None:
            raise ValueError("AWS auth requires role_arn or both static credentials")
        aws = {
            "access_key_id": access_key_id,
            "secret_access_key": secret_access_key,
        }
    rule: SandboxProxyRule = {
        "name": rule_name,
        "type": "aws",
        "enabled": enabled,
        "aws": aws,
    }
    if env_vars is not None:
        rule["env_vars"] = _require_env_vars(env_vars)
    return rule


def gcp_auth(
    *,
    service_account_json: SandboxProxySecret,
    scopes: Sequence[str] | None = None,
    name: str = "gcp",
    enabled: bool = True,
    env_vars: Mapping[str, str] | None = None,
) -> SandboxProxyRule:
    """Build a sandbox proxy rule that injects GCP OAuth bearer auth.

    The sandbox proxy keeps the service account JSON outside the sandbox and
    injects OAuth bearer tokens for built-in Google API host matching.
    ``service_account_json`` must be supplied as a ``workspace_secret`` or
    ``opaque`` value; plaintext service account JSON is intentionally not
    supported.

    Args:
        env_vars: Plaintext environment variables set for every command in the
            sandbox while this rule is enabled, for tools that refuse to run
            unless a credential variable is present even though the proxy
            injects the real credential on the wire.
    """
    rule_name = _require_non_empty_string(name, "name")
    gcp_config: dict[str, Any] = {
        "service_account_json": service_account_json,
    }
    if scopes is not None:
        gcp_config["scopes"] = _require_non_empty_string_list(scopes, "scopes")
    rule: SandboxProxyRule = {
        "name": rule_name,
        "type": "gcp",
        "enabled": enabled,
        "gcp": gcp_config,
    }
    if env_vars is not None:
        rule["env_vars"] = _require_env_vars(env_vars)
    return rule
