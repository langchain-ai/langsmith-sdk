# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing_extensions import Literal, TypeAlias

__all__ = ["ExampleSelect"]

ExampleSelect: TypeAlias = Literal[
    "id",
    "created_at",
    "modified_at",
    "name",
    "dataset_id",
    "source_run_id",
    "metadata",
    "inputs",
    "outputs",
    "attachment_urls",
]
