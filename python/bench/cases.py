"""Benchmark cases shared by the pyperf runner and the pytest-benchmark suite.

Each entry is ``(name, fn, input)``; ``fn(input)`` is the timed call.
"""

from bench.create_compressed_run_tree import create_compressed_run_trees
from bench.create_run_tree import create_run_trees
from bench.dumps_json import (
    DeeplyNestedModel,
    DeeplyNestedModelV1,
    create_nested_instance,
)
from bench.hybrid_tracing import handle_hybrid_batches, make_batches
from bench.wrapped_llm_calls import (
    make_anthropic_case,
    make_openai_case,
    run_wrapped_calls,
)
from langsmith.client import _dumps_json


class MyClass:
    def __init__(self):
        self.vals = {}


BENCHMARKS = (
    (
        "create_5_000_run_trees",
        create_run_trees,
        5_000,
    ),
    (
        "create_10_000_run_trees",
        create_run_trees,
        10_000,
    ),
    (
        "create_20_000_run_trees",
        create_run_trees,
        20_000,
    ),
    (
        "create_5_000_compressed_run_trees",
        create_compressed_run_trees,
        5_000,
    ),
    (
        "create_10_000_compressed_run_trees",
        create_compressed_run_trees,
        10_000,
    ),
    (
        "create_20_000_compressed_run_trees",
        create_compressed_run_trees,
        20_000,
    ),
    (
        "hybrid_handle_200_batches_of_100",
        handle_hybrid_batches,
        make_batches(200, ops_per_batch=100),
    ),
    (
        "dumps_class_nested_py_branch_and_leaf_200x400",
        lambda x: _dumps_json({"input": x}),
        create_nested_instance(
            200, 400, branch_constructor=MyClass, leaf_constructor=MyClass
        ),
    ),
    (
        "dumps_class_nested_py_leaf_50x100",
        lambda x: _dumps_json({"input": x}),
        create_nested_instance(50, 100, leaf_constructor=MyClass),
    ),
    (
        "dumps_class_nested_py_leaf_100x200",
        lambda x: _dumps_json({"input": x}),
        create_nested_instance(100, 200, leaf_constructor=MyClass),
    ),
    (
        "dumps_dataclass_nested_50x100",
        lambda x: _dumps_json({"input": x}),
        create_nested_instance(50, 100),
    ),
    (
        "dumps_pydantic_nested_50x100",
        lambda x: _dumps_json({"input": x}),
        create_nested_instance(50, 100, branch_constructor=DeeplyNestedModel),
    ),
    (
        "dumps_pydanticv1_nested_50x100",
        lambda x: _dumps_json({"input": x}),
        create_nested_instance(50, 100, branch_constructor=DeeplyNestedModelV1),
    ),
    (
        "openai_wrapped_200_calls_baseline",
        run_wrapped_calls,
        make_openai_case("baseline", 200),
    ),
    (
        "openai_wrapped_200_calls_secret_anonymizer",
        run_wrapped_calls,
        make_openai_case("secret_anonymizer", 200),
    ),
    (
        "openai_wrapped_200_calls_langsmith_secret",
        run_wrapped_calls,
        make_openai_case("langsmith_secret", 200),
    ),
    (
        "anthropic_wrapped_200_calls_baseline",
        run_wrapped_calls,
        make_anthropic_case("baseline", 200),
    ),
    (
        "anthropic_wrapped_200_calls_secret_anonymizer",
        run_wrapped_calls,
        make_anthropic_case("secret_anonymizer", 200),
    ),
    (
        "anthropic_wrapped_200_calls_langsmith_secret",
        run_wrapped_calls,
        make_anthropic_case("langsmith_secret", 200),
    ),
)
