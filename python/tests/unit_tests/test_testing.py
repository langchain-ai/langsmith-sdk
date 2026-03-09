import uuid

from langsmith.testing._internal import _get_example_id, _serde_example_values


def test__serde_example_values():
    class Foo:
        def __init__(self, a, b):
            self.a = a
            self.b = b

    results = _serde_example_values({"foo": Foo(1, 2)})
    assert "foo" in results
    assert isinstance(results["foo"], str)


def test__get_id():
    class Foo:
        bar: str = "baz"  # type: ignore

        def __init__(self, a: int, b: int):
            self.a = a
            self.b = b

    def foo(x: Foo):
        return x

    dataset_id = "4e32bff6-5762-4906-8d74-ee2bd0f1d234"
    inputs = {"x": Foo(1, 2)}
    outputs = {"y": Foo(3, 4)}

    result = _get_example_id(dataset_id, inputs, outputs)
    assert isinstance(result, uuid.UUID)


def test_example_id_differs_by_test_name():
    """Tests with the same inputs/outputs but different names get different IDs."""
    dataset_id = "4e32bff6-5762-4906-8d74-ee2bd0f1d234"
    inputs = {"model": "gpt-4"}

    id_a = _get_example_id(dataset_id, inputs, test_name="test_a")
    id_b = _get_example_id(dataset_id, inputs, test_name="test_b")
    assert id_a != id_b

    # Same test name produces the same ID (stable across runs)
    id_a2 = _get_example_id(dataset_id, inputs, test_name="test_a")
    assert id_a == id_a2


def test_example_id_same_name_different_inputs():
    """Same test name but different inputs get different IDs (parametrize)."""
    dataset_id = "4e32bff6-5762-4906-8d74-ee2bd0f1d234"

    id_1 = _get_example_id(
        dataset_id, {"a": 1, "b": 2}, test_name="test_addition[1-2]"
    )
    id_2 = _get_example_id(
        dataset_id, {"a": 3, "b": 4}, test_name="test_addition[3-4]"
    )
    assert id_1 != id_2
