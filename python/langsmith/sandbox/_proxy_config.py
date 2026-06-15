"""Helpers for building sandbox proxy configurations."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal, TypedDict


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
        normalized.append(rule)
    return normalized


def proxy_config(
    *,
    rules: Sequence[SandboxProxyRule] | None = None,
    no_proxy: Sequence[str] | None = None,
    access_control: dict[str, Any] | None = None,
) -> SandboxProxyConfig:
    """Build a sandbox proxy config from one or more proxy rules.

    Use provider-specific rule helpers such as ``aws_auth_proxy_rule`` and
    ``gcp_auth_proxy_rule`` when a sandbox needs multiple auth flows.
    """
    config: SandboxProxyConfig = {"rules": _normalize_proxy_rules(rules)}
    if no_proxy is not None:
        config["no_proxy"] = _require_non_empty_string_list(no_proxy, "no_proxy")
    if access_control is not None:
        if not isinstance(access_control, dict):
            raise ValueError("access_control must be a dictionary")
        config["access_control"] = dict(access_control)
    return config


def aws_auth_proxy_rule(
    *,
    access_key_id: SandboxProxySecret,
    secret_access_key: SandboxProxySecret,
    name: str = "aws",
    enabled: bool = True,
) -> SandboxProxyRule:
    """Build a sandbox proxy rule that signs AWS HTTPS requests.

    The sandbox proxy keeps the real AWS credentials outside the sandbox and
    signs supported AWS requests with SigV4 on the sandbox's behalf. AWS
    credentials must be supplied as ``workspace_secret`` or ``opaque`` values;
    plaintext AWS credentials are intentionally not supported.
    """
    rule_name = _require_non_empty_string(name, "name")
    return {
        "name": rule_name,
        "type": "aws",
        "enabled": enabled,
        "aws": {
            "access_key_id": access_key_id,
            "secret_access_key": secret_access_key,
        },
    }


def gcp_auth_proxy_rule(
    *,
    service_account_json: SandboxProxySecret,
    scopes: Sequence[str],
    match_hosts: Sequence[str],
    name: str = "gcp",
    enabled: bool = True,
) -> SandboxProxyRule:
    """Build a sandbox proxy rule that injects GCP OAuth bearer auth.

    The sandbox proxy keeps the service account JSON outside the sandbox and
    injects OAuth bearer tokens for the configured Google API hosts.
    ``service_account_json`` must be supplied as a ``workspace_secret`` or
    ``opaque`` value; plaintext service account JSON is intentionally not
    supported.
    """
    rule_name = _require_non_empty_string(name, "name")
    return {
        "name": rule_name,
        "type": "gcp",
        "enabled": enabled,
        "match_hosts": _require_non_empty_string_list(match_hosts, "match_hosts"),
        "gcp": {
            "service_account_json": service_account_json,
            "scopes": _require_non_empty_string_list(scopes, "scopes"),
        },
    }
