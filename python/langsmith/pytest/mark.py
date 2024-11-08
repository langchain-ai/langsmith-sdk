from __future__ import annotations

import inspect
from typing import Any, Callable, Optional

import pytest

from langsmith import evaluate
from langsmith.evaluation._runner import TARGET_T


def parametrize(
    dataset_name: str,
    target_fn: TARGET_T,
    *,
    client: Optional[Any] = None,
    max_concurrency: Optional[int] = None,
) -> Callable:
    """Decorator to parametrize a test function with LangSmith dataset examples.

    Args:
        dataset_name: Name of the LangSmith dataset to use
        target_fn: Function to test that takes inputs dict and returns outputs dict
        client: Optional LangSmith client to use
        max_concurrency: Optional max number of concurrent evaluations

    Returns:
        Decorated test function that will be parametrized with dataset examples.
    """

    def decorator(test_fn: Callable) -> Callable:
        # Verify test function signature
        sig = inspect.signature(test_fn)
        required_params = {"inputs", "outputs", "reference_outputs"}
        if not all(param in sig.parameters for param in required_params):
            raise ValueError(f"Test function must accept parameters: {required_params}")

        def evaluator(run, example):
            """Evaluator that runs the test function and returns pass/fail result."""
            try:
                results = test_fn(
                    inputs=example.inputs,
                    outputs=run.outputs,
                    reference_outputs=example.outputs,
                )
            except AssertionError as e:
                return {"score": 0.0, "key": "pass", "comment": str(e)}
            except Exception as e:
                return {
                    "score": 0.0,
                    "key": "pass",
                    "comment": f"Unexpected error: {str(e)}",
                }
            else:
                if not results:
                    return {"score": 1.0, "key": "pass"}
                elif "results" not in results:
                    results = {"results": results}
                else:
                    pass
                results["results"].append({"score": 1.0, "key": "pass"})
            return results

        @pytest.mark.parametrize(
            "example_result",
            evaluate(
                target_fn,
                data=dataset_name,
                evaluators=[evaluator],
                client=client,
                max_concurrency=max_concurrency,
                experiment_prefix=f"pytest_{test_fn.__name__}",
                blocking=False,
            ),
        )
        # @functools.wraps(test_fn)
        def wrapped(example_result):
            """Wrapped test function that gets parametrized with results."""
            # Fail the test if the evaluation failed
            eval_results = example_result["evaluation_results"]["results"]
            if not eval_results:
                pytest.fail("No evaluation results")

            pass_result = [r for r in eval_results if r.key == "pass"][0]
            if not pass_result.score:
                error = pass_result.comment
                pytest.fail(
                    f"Test failed for example {example_result['example'].id}: {error}"
                )

        return wrapped

    return decorator
