# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Literal, Required, TypedDict

__all__ = ["RegistryCreateParams"]


class RegistryCreateParams(TypedDict, total=False):
    name: Required[str]

    url: Required[str]

    auth_type: Literal["DOCKER_CONFIG", "AWS_ROLE"]

    aws_role_arn: str

    password: str

    username: str
