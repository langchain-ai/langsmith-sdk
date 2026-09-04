# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Literal, Annotated, TypedDict

from ..._utils import PropertyInfo

__all__ = ["RegistryUpdateParams"]


class RegistryUpdateParams(TypedDict, total=False):
    auth_type: Literal["DOCKER_CONFIG", "AWS_ROLE"]

    aws_role_arn: str

    body_name: Annotated[str, PropertyInfo(alias="name")]

    password: str

    url: str

    username: str
