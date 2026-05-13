# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List
from typing_extensions import Literal

from .._models import BaseModel

__all__ = ["DatasetTransformation"]


class DatasetTransformation(BaseModel):
    path: List[str]

    transformation_type: Literal[
        "convert_to_openai_message",
        "convert_to_openai_tool",
        "remove_system_messages",
        "remove_extra_fields",
        "extract_tools_from_run",
    ]
    """
    Enum for dataset transformation types. Ordering determines the order in which
    transformations are applied if there are multiple transformations on the same
    path.
    """
