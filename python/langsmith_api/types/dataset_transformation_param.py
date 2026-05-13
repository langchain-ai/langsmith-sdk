# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Literal, Required, TypedDict

from .._types import SequenceNotStr

__all__ = ["DatasetTransformationParam"]


class DatasetTransformationParam(TypedDict, total=False):
    path: Required[SequenceNotStr[str]]

    transformation_type: Required[
        Literal[
            "convert_to_openai_message",
            "convert_to_openai_tool",
            "remove_system_messages",
            "remove_extra_fields",
            "extract_tools_from_run",
        ]
    ]
    """
    Enum for dataset transformation types. Ordering determines the order in which
    transformations are applied if there are multiple transformations on the same
    path.
    """
