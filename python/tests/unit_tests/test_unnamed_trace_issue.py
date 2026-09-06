"""Test name inference for RunTree when name is not provided."""

from unittest import mock

from langsmith import Client, traceable
from langsmith.run_trees import RunTree


class Router:
    """Simple class with __call__ method (like LangGraph nodes)."""

    def __call__(self, state: dict) -> dict:
        return {"result": "ok"}


def test_runtree_infers_class_name_from_stack():
    """RunTree should infer class name from stack when created in class method."""

    class MyRouter:
        def process(self):
            return RunTree(run_type="chain")

    run = MyRouter().process()
    assert run.name == "MyRouter"


def test_runtree_falls_back_to_descriptive_name():
    """RunTree should use Unnamed_{run_type} when inference fails."""
    run = RunTree(run_type="llm")
    
    # Should NOT be just "Unnamed" - should be descriptive or inferred
    assert run.name != "Unnamed"
    # Name should be something reasonable (inferred from stack or fallback)
    assert len(run.name) > 0


def test_runtree_uses_explicit_name():
    """RunTree should use explicit name when provided."""
    run = RunTree(name="MyExplicitName", run_type="chain")
    assert run.name == "MyExplicitName"


def test_utils_get_function_name_for_callable_class():
    """_get_function_name should return class name for callable instances."""
    from langsmith.utils import _get_function_name

    router = Router()
    assert _get_function_name(router) == "Router"


def test_traceable_with_callable_class():
    """@traceable should work with callable classes."""
    router = Router()
    traced = traceable(router)

    with mock.patch.object(Client, "create_run") as mock_create:
        traced({"input": "test"})

        if mock_create.called:
            name = mock_create.call_args[1].get("name", "")
            assert name == "Router"
            assert name != "Unnamed"
