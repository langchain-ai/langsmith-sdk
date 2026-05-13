# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing_extensions import Literal, TypeAlias

__all__ = ["SortByDatasetColumn"]

SortByDatasetColumn: TypeAlias = Literal[
    "name", "created_at", "last_session_start_time", "example_count", "session_count", "modified_at"
]
