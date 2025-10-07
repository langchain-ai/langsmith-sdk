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
