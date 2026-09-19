# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Union, Iterable
from typing_extensions import Literal, Required, Annotated, TypeAlias, TypedDict

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
    "ProxyConfigRuleAwsSandboxesProxyAwsRoleConfig",
    "ProxyConfigRuleAwsSandboxesProxyAwsStaticConfig",
    "ProxyConfigRuleAwsSandboxesProxyAwsStaticConfigAccessKeyID",
    "ProxyConfigRuleAwsSandboxesProxyAwsStaticConfigSecretAccessKey",
    "ProxyConfigRuleGcp",
    "ProxyConfigRuleGcpServiceAccountJson",
    "ProxyConfigRuleHeader",
    "RunConfig",
]


class BoxUpdateParams(TypedDict, total=False):
    cpu_millicores: int

    delete_after_stop_seconds: int

    fs_capacity_bytes: int

    idle_ttl_seconds: int

    mem_bytes: int
    """New memory for the sandbox, in bytes.

    The 4 GiB per vCPU ratio applies when the sandbox is created; a resize enforces
    only the maximum of 64 GiB.
    """

    body_name: Annotated[str, PropertyInfo(alias="name")]

    proxy_config: ProxyConfig

    run_config: RunConfig
    """
    RunConfig changes what subsequent commands run with: user and work_dir replace
    the current values, env_vars merge over them. Commands already running are
    unaffected.
    """

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


class ProxyConfigRuleAwsSandboxesProxyAwsRoleConfig(TypedDict, total=False):
    role_arn: Required[str]
    """
    RoleARN selects automatically renewed IAM-role credentials instead of static
    keys. Access follows the role's effective AWS permissions, not the sandbox's
    mount scope. Configure at creation; the role cannot be changed afterward.
    """


class ProxyConfigRuleAwsSandboxesProxyAwsStaticConfigAccessKeyID(TypedDict, total=False):
    type: Required[Literal["plaintext", "opaque", "workspace_secret"]]

    is_set: bool

    value: str


class ProxyConfigRuleAwsSandboxesProxyAwsStaticConfigSecretAccessKey(TypedDict, total=False):
    type: Required[Literal["plaintext", "opaque", "workspace_secret"]]

    is_set: bool

    value: str


class ProxyConfigRuleAwsSandboxesProxyAwsStaticConfig(TypedDict, total=False):
    access_key_id: Required[ProxyConfigRuleAwsSandboxesProxyAwsStaticConfigAccessKeyID]

    secret_access_key: Required[ProxyConfigRuleAwsSandboxesProxyAwsStaticConfigSecretAccessKey]

    role_arn: Literal[""]
    """
    RoleARN selects automatically renewed IAM-role credentials instead of static
    keys. Access follows the role's effective AWS permissions, not the sandbox's
    mount scope. Configure at creation; the role cannot be changed afterward.
    """


ProxyConfigRuleAws: TypeAlias = Union[
    ProxyConfigRuleAwsSandboxesProxyAwsRoleConfig, ProxyConfigRuleAwsSandboxesProxyAwsStaticConfig
]


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

    description: str
    """
    Description says what this rule lets the sandbox reach, so an agent driving the
    sandbox can be told its capabilities. At most 1024 characters.
    """

    enabled: bool

    env_vars: Dict[str, str]
    """
    EnvVars are plaintext env vars set for every command in the sandbox while this
    rule is enabled. Use them for tools that refuse to run unless a credential env
    var is present (e.g. gh needs GH_TOKEN) even though this rule injects the real
    credential on the wire — set a dummy value here so the command starts. Explicit
    per-sandbox env_vars win over these, and provider-managed (AWS/GCP) vars win
    over both.
    """

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

    description: str
    """
    Description says what this configuration as a whole lets the sandbox reach,
    complementing the per-rule descriptions. At most 1024 characters.
    """

    no_proxy: SequenceNotStr[str]

    rules: Iterable[ProxyConfigRule]


class RunConfig(TypedDict, total=False):
    """
    RunConfig changes what subsequent commands run with: user and work_dir
    replace the current values, env_vars merge over them. Commands already
    running are unaffected.
    """

    env_vars: Dict[str, str]

    user: str

    work_dir: str
