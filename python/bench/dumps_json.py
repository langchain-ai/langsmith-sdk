import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable, Dict, Optional

from pydantic import BaseModel, Field
from pydantic.v1 import BaseModel as BaseModelV1
from pydantic.v1 import Field as FieldV1


def _default():

    return {
        "some_val": "😈",
        "uuid_val": uuid.uuid4(),
        "datetime_val": datetime.now(),
        "list_val": [1, 2, 3],
        "decimal_val": Decimal("3.14"),
        "set_val": {1, 2, 3},
        "tuple_val": (4, 5, 6),
        "bytes_val": b"hello world",
    }


@dataclass
class DeeplyNested:
    """An object."""

    vals: Dict[str, Any] = field(default_factory=_default)


class DeeplyNestedModel(BaseModel):
    vals: Dict[str, Any] = Field(default_factory=_default)


class DeeplyNestedModelV1(BaseModelV1):
    vals: Dict[str, Any] = FieldV1(default_factory=_default)


def create_nested_instance(
    depth: int = 5,
    width: int = 5,
    branch_constructor: Optional[Callable] = DeeplyNested,
    leaf_constructor: Optional[Callable] = None,
) -> DeeplyNested:
    top_level = DeeplyNested()
    current_level = top_level
    root_constructor = leaf_constructor or DeeplyNested
    for i in range(depth):
        for j in range(width):
            key = f"key_{i}_{j}"
            if i < depth - 1:
                value = branch_constructor()
                current_level.vals[key] = value
                if j == 0:
                    next_level = value
            else:
                current_level.vals[key] = root_constructor()

        if i < depth - 1:
            current_level = next_level
    return top_level
