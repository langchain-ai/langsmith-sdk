import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable, Dict, Optional

import numpy as np
from pydantic import BaseModel, Field
from pydantic.v1 import BaseModel as BaseModelV1
from pydantic.v1 import Field as FieldV1


def _default():
    return {
        "some_val": "😈",
        "uuid_val": uuid.uuid4(),
        "datetime_val": datetime.now(),
        "list_val": [238928376271863487] * 5,
        "decimal_val": Decimal("3.14"),
        "set_val": {1, 2, 3},
        "tuple_val": (4, 5, 6),
        "bytes_val": b"hello world",
        "arr": np.random.random(10),
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


if __name__ == "__main__":
    import time

    from langsmith.client import _dumps_json

    class MyClass:
        def __init__(self):
            self.vals = {}

    def run():
        res = create_nested_instance(200, 150, leaf_constructor=MyClass)
        start_time = time.time()
        res = _dumps_json({"input": res})
        end_time = time.time()
        print(f"Size: {len(res) / 1024:.2f} KB")
        print(f"Time taken: {end_time - start_time:.2f} seconds")

    run()
