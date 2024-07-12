# mypy: disable-error-code="annotation-unchecked"
import copy
import dataclasses
import itertools
import threading
import unittest
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, NamedTuple, Optional
from unittest.mock import MagicMock, patch

import attr
import dataclasses_json
import pytest
from pydantic import BaseModel

import langsmith.utils as ls_utils
from langsmith import Client, traceable
from langsmith.run_helpers import tracing_context


class LangSmithProjectNameTest(unittest.TestCase):
    class GetTracerProjectTestCase:
        def __init__(
            self, test_name, envvars, expected_project_name, return_default_value=None
        ):
            self.test_name = test_name
            self.envvars = envvars
            self.expected_project_name = expected_project_name
            self.return_default_value = return_default_value

    def test_correct_get_tracer_project(self):
        cases = [
            self.GetTracerProjectTestCase(
                test_name="default to 'default' when no project provided",
                envvars={},
                expected_project_name="default",
            ),
            self.GetTracerProjectTestCase(
                test_name="default to 'default' when "
                + "return_default_value=True and no project provided",
                envvars={},
                expected_project_name="default",
            ),
            self.GetTracerProjectTestCase(
                test_name="do not default if return_default_value=False "
                + "when no project provided",
                envvars={},
                expected_project_name=None,
                return_default_value=False,
            ),
            self.GetTracerProjectTestCase(
                test_name="use session_name for legacy tracers",
                envvars={"LANGCHAIN_SESSION": "old_timey_session"},
                expected_project_name="old_timey_session",
            ),
            self.GetTracerProjectTestCase(
                test_name="use LANGCHAIN_PROJECT over SESSION_NAME",
                envvars={
                    "LANGCHAIN_SESSION": "old_timey_session",
                    "LANGCHAIN_PROJECT": "modern_session",
                },
                expected_project_name="modern_session",
            ),
            self.GetTracerProjectTestCase(
                test_name="hosted projects get precedence over all other defaults",
                envvars={
                    "HOSTED_LANGSERVE_PROJECT_NAME": "hosted_project",
                    "LANGCHAIN_SESSION": "old_timey_session",
                    "LANGCHAIN_PROJECT": "modern_session",
                },
                expected_project_name="hosted_project",
            ),
        ]

        for case in cases:
            with self.subTest(msg=case.test_name):
                with pytest.MonkeyPatch.context() as mp:
                    for k, v in case.envvars.items():
                        mp.setenv(k, v)

                    project = (
                        ls_utils.get_tracer_project()
                        if case.return_default_value is None
                        else ls_utils.get_tracer_project(case.return_default_value)
                    )
                    self.assertEqual(project, case.expected_project_name)


def test_tracing_enabled():
    with patch.dict(
        "os.environ", {"LANGCHAIN_TRACING_V2": "false", "LANGSMITH_TRACING": "false"}
    ):
        assert not ls_utils.tracing_is_enabled()
        with tracing_context(enabled=True):
            assert ls_utils.tracing_is_enabled()
            with tracing_context(enabled=False):
                assert not ls_utils.tracing_is_enabled()
        with tracing_context(enabled=False):
            assert not ls_utils.tracing_is_enabled()
        assert not ls_utils.tracing_is_enabled()

    @traceable
    def child_function():
        assert ls_utils.tracing_is_enabled()
        return 1

    @traceable
    def untraced_child_function():
        assert not ls_utils.tracing_is_enabled()
        return 1

    @traceable
    def parent_function():
        with patch.dict(
            "os.environ",
            {"LANGCHAIN_TRACING_V2": "false", "LANGSMITH_TRACING": "false"},
        ):
            assert ls_utils.tracing_is_enabled()
            child_function()
        with tracing_context(enabled=False):
            assert not ls_utils.tracing_is_enabled()
            return untraced_child_function()

    with patch.dict(
        "os.environ", {"LANGCHAIN_TRACING_V2": "true", "LANGSMITH_TRACING": "true"}
    ):
        mock_client = MagicMock(spec=Client)
        parent_function(langsmith_extra={"client": mock_client})


def test_tracing_disabled():
    with patch.dict(
        "os.environ", {"LANGCHAIN_TRACING_V2": "true", "LANGSMITH_TRACING": "true"}
    ):
        assert ls_utils.tracing_is_enabled()
        with tracing_context(enabled=False):
            assert not ls_utils.tracing_is_enabled()
        with tracing_context(enabled=True):
            assert ls_utils.tracing_is_enabled()
            with tracing_context(enabled=False):
                assert not ls_utils.tracing_is_enabled()
        assert ls_utils.tracing_is_enabled()


def test_deepish_copy():
    class MyClass:
        def __init__(self, x: int) -> None:
            self.x = x
            self.y = "y"
            self.a_list = [1, 2, 3]
            self.a_tuple = (1, 2, 3)
            self.a_set = {1, 2, 3}
            self.a_dict = {"foo": "bar"}
            self.my_bytes = b"foo"

    class ClassWithTee:
        def __init__(self) -> None:
            tee_a, tee_b = itertools.tee(range(10))
            self.tee_a = tee_a
            self.tee_b = tee_b

    class MyClassWithSlots:
        __slots__ = ["x", "y"]

        def __init__(self, x: int) -> None:
            self.x = x
            self.y = "y"

    class MyPydantic(BaseModel):
        foo: str
        bar: int
        baz: dict

    @dataclasses.dataclass
    class MyDataclass:
        foo: str
        bar: int

        def something(self) -> None:
            pass

    class MyEnum(str, Enum):
        FOO = "foo"
        BAR = "bar"

    class ClassWithFakeJson:
        def json(self):
            raise ValueError("This should not be called")

        def to_json(self) -> dict:
            return {"foo": "bar"}

    @dataclasses_json.dataclass_json
    @dataclasses.dataclass
    class Person:
        name: str

    @attr.dataclass
    class AttrDict:
        foo: str = attr.ib()
        bar: int

    uid = uuid.uuid4()
    current_time = datetime.now()

    class NestedClass:
        __slots__ = ["person", "lock"]

        def __init__(self) -> None:
            self.person = Person(name="foo")
            self.lock = [threading.Lock()]

        def __deepcopy__(self, memo: Optional[dict] = None) -> Any:
            cls = type(self)
            m = cls.__new__(cls)
            setattr(m, "__dict__", copy.deepcopy(self.__dict__, memo=memo))

    class CyclicClass:
        def __init__(self) -> None:
            self.cyclic = self

        def __repr__(self) -> str:
            return "SoCyclic"

    class CyclicClass2:
        def __init__(self) -> None:
            self.cyclic: Any = None
            self.other: Any = None

        def __repr__(self) -> str:
            return "SoCyclic2"

    cycle_2 = CyclicClass2()
    cycle_2.cyclic = CyclicClass2()
    cycle_2.cyclic.other = cycle_2

    class MyNamedTuple(NamedTuple):
        foo: str
        bar: int

    my_dict = {
        "uid": uid,
        "time": current_time,
        "adict": {"foo": "bar"},
        "my_class": MyClass(1),
        "class_with_tee": ClassWithTee(),
        "my_slotted_class": MyClassWithSlots(1),
        "my_dataclass": MyDataclass("foo", 1),
        "my_enum": MyEnum.FOO,
        "my_pydantic": MyPydantic(foo="foo", bar=1, baz={"foo": "bar"}),
        "person": Person(name="foo"),
        "a_bool": True,
        "a_none": None,
        "a_str": "foo",
        "an_int": 1,
        "a_float": 1.1,
        "nested_class": NestedClass(),
        "attr_dict": AttrDict(foo="foo", bar=1),
        "named_tuple": MyNamedTuple(foo="foo", bar=1),
        "cyclic": CyclicClass(),
        "cyclic2": cycle_2,
        "fake_json": ClassWithFakeJson(),
    }
    assert ls_utils.deepish_copy(my_dict) == my_dict


def test_is_version_greater_or_equal():
    # Test versions equal to 0.5.23
    assert ls_utils.is_version_greater_or_equal("0.5.23", "0.5.23")

    # Test versions greater than 0.5.23
    assert ls_utils.is_version_greater_or_equal("0.5.24", "0.5.23")
    assert ls_utils.is_version_greater_or_equal("0.6.0", "0.5.23")
    assert ls_utils.is_version_greater_or_equal("1.0.0", "0.5.23")

    # Test versions less than 0.5.23
    assert not ls_utils.is_version_greater_or_equal("0.5.22", "0.5.23")
    assert not ls_utils.is_version_greater_or_equal("0.5.0", "0.5.23")
    assert not ls_utils.is_version_greater_or_equal("0.4.99", "0.5.23")


def test_parse_prompt_identifier():
    # Valid cases
    assert ls_utils.parse_prompt_identifier("name") == ("-", "name", "latest")
    assert ls_utils.parse_prompt_identifier("owner/name") == ("owner", "name", "latest")
    assert ls_utils.parse_prompt_identifier("owner/name:commit") == (
        "owner",
        "name",
        "commit",
    )
    assert ls_utils.parse_prompt_identifier("name:commit") == ("-", "name", "commit")

    # Invalid cases
    invalid_identifiers = [
        "",
        "/",
        ":",
        "owner/",
        "/name",
        "owner//name",
        "owner/name/",
        "owner/name/extra",
        ":commit",
    ]

    for invalid_id in invalid_identifiers:
        try:
            ls_utils.parse_prompt_identifier(invalid_id)
            assert False, f"Expected ValueError for identifier: {invalid_id}"
        except ValueError:
            pass  # This is the expected behavior
