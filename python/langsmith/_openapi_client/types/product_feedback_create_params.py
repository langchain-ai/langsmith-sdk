# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Literal, Required, Annotated, TypedDict

from .._utils import PropertyInfo

__all__ = ["ProductFeedbackCreateParams", "Client"]


class ProductFeedbackCreateParams(TypedDict, total=False):
    category: Required[Literal["BUG", "FEATURE_REQUEST", "USABILITY", "DOCUMENTATION", "OTHER"]]

    message: Required[str]

    source: Required[Literal["LANGSMITH_CLI"]]

    client: Client

    idempotency_key: Annotated[str, PropertyInfo(alias="Idempotency-Key")]


class Client(TypedDict, total=False):
    architecture: str

    os: str

    version: str
