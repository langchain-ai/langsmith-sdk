"""Test various permutations of langsmith-tracing and langchain runnables."""

import inspect
from itertools import combinations_with_replacement
from typing import Callable, Union

import pytest
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_core.tracers import LangChainTracer

from langsmith import Client, traceable, tracing_context
from tests.interop_tracing.test_lineage import _get_mock_client
from tests.interop_tracing.utils import extract_span_tree


def _wrap_in_lambda(
    underlying: Union[Runnable, Callable], depth: int
) -> RunnableLambda:
    """Wrap the underlying logic inside a Runnable Lambda.

    This function should create another layer of nesting for tracing purposes.

    Args:
        underlying (Union[Runnable, Callable]): The underlying logic to wrap.
        depth (int): The depth of the current transformation -- used for naming purposes
    """
    if inspect.isfunction(underlying):
        return RunnableLambda(underlying).with_config({"run_name": f"lambda_{depth}"})
    elif isinstance(underlying, Runnable):

        def _wrapped(inputs):
            return underlying.invoke(inputs)

        return RunnableLambda(_wrapped).with_config({"run_name": f"lambda_{depth}"})
    else:
        raise NotImplementedError(f"Unsupported type {type(underlying)}")


def _wrap_in_traceable(
    client: Client, underlying: Union[Runnable, Callable], depth: int
) -> Callable:
    """Wrap the underlying logic inside a traceable decorator.
    This function should create another layer of nesting for tracing purposes.

    Args:
        client (Client): The client to use for tracing
        underlying (Union[Runnable, Callable]): The underlying logic to wrap
        depth (int): The depth of the current transformation -- used for naming purposes
    """
    if inspect.isfunction(underlying):
        return traceable(client=client, name=f"traceable_{depth}")(underlying)
    elif isinstance(underlying, Runnable):
        return traceable(client=client, name=f"traceable_{depth}")(underlying.invoke)
    else:
        raise TypeError(f"Unsupported type {type(underlying)}")


@pytest.mark.parametrize("depth", range(1, 4))
def test_permutations(depth: int) -> None:
    """Generate a bunch of "programs" and verify that they get traced correctly.

    The programs are built by transforming a simple passthrough function
    with a bunch of different transformations. The transformations are
    applied in all possible combinations to a certain depth.

    We're trying to verify that primarily that tracing works smoothly across
    langsmith-sdk and langchain primitives.

    For example, if we use the two transformations of:

    1. wrap in @traceable decorator
    2. wrap in RunnableLambda

    Then we will generate the following combinations for depth=2:

    1. traceable(traceable(foo))
    2. traceable(RunnableLambda(foo))
    3. RunnableLambda(traceable(foo))
    4. RunnableLambda(RunnableLambda(foo))
    """

    failed_test_cases = []

    combinations_of_transforms = combinations_with_replacement(
        ["@traceable", "lambda"], r=depth
    )

    # Here we define a simple function that we will use as the base of our program.
    def foo(x):
        """Basic passthrough traced with @traceable decorator."""
        return x

    # Now, we will iterate over all combinations of transformations and
    # apply them to the base program.
    # And after we generate the transformed program, we will run it
    # and verify that it gets traced properly.
    for transforms in combinations_of_transforms:
        mock_client = _get_mock_client()
        with tracing_context(enabled=True):
            traced_program = foo
            for idx, transform in enumerate(transforms):
                current_depth = depth - idx
                if transform == "lambda":
                    traced_program = _wrap_in_lambda(traced_program, current_depth)
                elif transform == "@traceable":
                    traced_program = _wrap_in_traceable(
                        mock_client, traced_program, current_depth
                    )
                else:
                    raise NotImplementedError(f"Unsupported transform {transform}")
                if traced_program is None:
                    raise ValueError(f"Traced program is None after {transform}")

            if isinstance(traced_program, Runnable):
                tracer = LangChainTracer(client=mock_client)
                traced_program.invoke({"x": 1}, {"callbacks": [tracer]})
            else:
                traced_program({"x": 1})

        # The span tree creation runs a number of assertion tests to verify
        # that mock client creates valid spans.
        try:
            span_tree = extract_span_tree(mock_client)
            nodes = span_tree.get_breadth_first_traversal(
                include_level=False, attributes=["name"]
            )
            names = [node["name"] for node in nodes]
            assert len(names) == depth
        except Exception as e:
            failed_test_cases.append({"error": str(e), "transforms": transforms})
            continue

    if failed_test_cases:
        full_error_message = "\n".join(
            [
                f"Error: {test_case['error']}, Transforms: {test_case['transforms']}"
                for test_case in failed_test_cases
            ]
        )
        raise AssertionError(f"Failed test cases:\n{full_error_message}")
