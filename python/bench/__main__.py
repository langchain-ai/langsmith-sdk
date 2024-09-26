import random
from uuid import uuid4

from pyperf._runner import Runner
from bench.dumps_json import (
    create_nested_instance,
    DeeplyNestedModel,
    DeeplyNestedModelV1,
)
from langsmith.client import _dumps_json


class MyClass:
    def __init__(self):
        self.vals = {}


benchmarks = (
    (
        "dumps_dataclass_nested_200x10",
        lambda x: _dumps_json({"input": x}),
        create_nested_instance(200, 100),
    ),
    (
        "dumps_pydantic_nested_200x10",
        lambda x: _dumps_json({"input": x}),
        create_nested_instance(200, 100, branch_constructor=DeeplyNestedModel),
    ),
    (
        "dumps_pydanticv1_nested_200x10",
        lambda x: _dumps_json({"input": x}),
        create_nested_instance(200, 100, branch_constructor=DeeplyNestedModelV1),
    ),
    # Add random python class at the leaf
    (
        "dumps_dataclass_nested_py_leaf_200x10",
        lambda x: _dumps_json({"input": x}),
        create_nested_instance(200, 100, leaf_constructor=MyClass),
    ),
    (
        "dumps_pydantic_nested_py_leaf_200x10",
        lambda x: _dumps_json({"input": x}),
        create_nested_instance(
            200, 100, branch_constructor=DeeplyNestedModel, leaf_constructor=MyClass
        ),
    ),
    (
        "dumps_pydanticv1_nested_py_leaf_200x10",
        lambda x: _dumps_json({"input": x}),
        create_nested_instance(
            200, 100, branch_constructor=DeeplyNestedModelV1, leaf_constructor=MyClass
        ),
    ),
    (
        "dumps_class_nested_py_leaf_200x10",
        lambda x: _dumps_json({"input": x}),
        create_nested_instance(
            200, 100, branch_constructor=MyClass, leaf_constructor=MyClass
        ),
    ),
)


r = Runner()

for name, fn, input_ in benchmarks:
    r.bench_func(name, fn, input)
