# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Iterable
from typing_extensions import Literal, Required, Annotated, TypedDict

from ..._types import SequenceNotStr
from ..._utils import PropertyInfo

__all__ = [
    "BoxUpdateParams",
    "ProxyConfig",
    "ProxyConfigAccessControl",
    "ProxyConfigCallback",
    "ProxyConfigCallbackRequestHeader",
    "ProxyConfigRule",
    "ProxyConfigRuleAws",
    "ProxyConfigRuleAwsAccessKeyID",
    "ProxyConfigRuleAwsSecretAccessKey",
    "ProxyConfigRuleGcp",
    "ProxyConfigRuleGcpServiceAccountJson",
    "ProxyConfigRuleHeader",
]


class BoxUpdateParams(TypedDict, total=False):
    cpu_millicores: int

    delete_after_stop_seconds: int

    fs_capacity_bytes: int

    idle_ttl_seconds: int

    mem_bytes: int

    body_name: Annotated[str, PropertyInfo(alias="name")]

    proxy_config: ProxyConfig

    tag_value_ids: SequenceNotStr[str]

    vcpus: int


class ProxyConfigAccessControl(TypedDict, total=False):
    allow_list: SequenceNotStr[str]

    deny_list: SequenceNotStr[str]


class ProxyConfigCallbackRequestHeader(TypedDict, total=False):
    name: Required[str]

    type: Required[Literal["plaintext", "opaque", "workspace_secret"]]

    is_set: bool

    value: str


class ProxyConfigCallback(TypedDict, total=False):
    match_hosts: Required[SequenceNotStr[str]]

    ttl_seconds: Required[int]

    url: Required[str]

    full_request: bool

    request_headers: Iterable[ProxyConfigCallbackRequestHeader]


class ProxyConfigRuleAwsAccessKeyID(TypedDict, total=False):
    type: Required[Literal["plaintext", "opaque", "workspace_secret"]]

    is_set: bool

    value: str


class ProxyConfigRuleAwsSecretAccessKey(TypedDict, total=False):
    type: Required[Literal["plaintext", "opaque", "workspace_secret"]]

    is_set: bool

    value: str


class ProxyConfigRuleAws(TypedDict, total=False):
    access_key_id: Required[ProxyConfigRuleAwsAccessKeyID]

    secret_access_key: Required[ProxyConfigRuleAwsSecretAccessKey]


class ProxyConfigRuleGcpServiceAccountJson(TypedDict, total=False):
    type: Required[Literal["plaintext", "opaque", "workspace_secret"]]

    is_set: bool

    value: str


class ProxyConfigRuleGcp(TypedDict, total=False):
    scopes: Required[SequenceNotStr[str]]

    service_account_json: Required[ProxyConfigRuleGcpServiceAccountJson]


class ProxyConfigRuleHeader(TypedDict, total=False):
    name: Required[str]

    type: Required[Literal["plaintext", "opaque", "workspace_secret"]]

    is_set: bool

    value: str


class ProxyConfigRule(TypedDict, total=False):
    name: Required[str]

    aws: ProxyConfigRuleAws

    enabled: bool

    gcp: ProxyConfigRuleGcp

    headers: Iterable[ProxyConfigRuleHeader]

    match_hosts: SequenceNotStr[str]
    """MatchHosts is only accepted for header injection rules.

    Provider auth rules use built-in host matching.
    """

    match_paths: SequenceNotStr[str]

    type: str


class ProxyConfig(TypedDict, total=False):
    access_control: ProxyConfigAccessControl

    callbacks: Iterable[ProxyConfigCallback]

    no_proxy: SequenceNotStr[str]

    rules: Iterable[ProxyConfigRule]
