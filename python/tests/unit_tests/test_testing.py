from langsmith._testing import _serde_example_values, _get_id
import uuid


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
        bar: str = "baz"

        def __init__(self, a: int, b: int):
            self.a = a
            self.b = b

    def foo(x: Foo):
        return x

    suite_id = uuid.UUID("4e32bff6-5762-4906-8d74-ee2bd0f1d234")

    _get_id(foo, {"x": Foo(1, 2)}, suite_id)
