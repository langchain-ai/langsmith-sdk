"""Test various permutations of langsmith-tracing and langchain runnables."""

import inspect
import pytest
from itertools import combinations_with_replacement
from typing import Union, Callable

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


@pytest.mark.parametrize("depth", range(0, 4))
def test_permutations(depth: int, block_type: str) -> None:
    """Test permutations.

    This function creates a bunch of testing permutations to test
    the interaction between langsmith and langchain tracing.

    """
    # Here we have two basic transformations one that
    # wraps logic in @traceable and another that wraps logic in a RunnableLambda.
    # We will generate all possible combinations of these transformations
    # to a certain depth and test that the resulting "program" gets traced correctly.
    # For example, if depth is 2, we will generate the following combinations:
    # 1. traceable(traceable(foo))
    # 2. traceable(RunnableLambda(foo))
    # 3. RunnableLambda(traceable(foo))
    # 4. RunnableLambda(RunnableLambda(foo))
    combinations_of_transforms = combinations_with_replacement(
        [_wrap_in_traceable, _wrap_in_lambda], r=depth
    )

    # Here we define a simple function that we will use as the base of our program.
    @traceable(client=mock_client, name=f"traceable_{depth + 1}")
    def foo(x):
        """Basic passthrough traced with @traceable decorator."""
        return x

    @RunnableLambda
    def bar(x):
        """Basic passthrough traced with RunnableLambda."""
        return x

    bar = bar.with_config({"run_name": f"traceable_{depth + 1}"})

    blocks = [foo, bar]

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
                if transform is _wrap_in_lambda:
                    traced_program = transform(traced_program, current_depth)
                elif transform is _wrap_in_traceable:
                    traced_program = transform(
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
        span_tree = extract_span_tree(mock_client)
        nodes = span_tree.get_breadth_first_traversal(
            include_level=False, attributes=["name"]
        )
        names = [node["name"] for node in nodes]

        assert len(names) == depth + 1
