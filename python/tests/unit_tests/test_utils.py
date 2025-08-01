# mypy: disable-error-code="annotation-unchecked"
import copy
import dataclasses
import functools
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
from langsmith.run_helpers import get_current_run_tree, tracing_context


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
        ls_utils.get_env_var.cache_clear()
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
            ls_utils.get_env_var.cache_clear()
            ls_utils.get_tracer_project.cache_clear()
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
    ls_utils.get_env_var.cache_clear()
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
    def grandchild_function():
        assert ls_utils.tracing_is_enabled()
        rt = get_current_run_tree()
        assert rt
        assert rt.parent_run_id is None
        assert "." not in rt.dotted_order
        assert rt.parent_dotted_order is None
        return 1

    @traceable
    def child_function():
        assert ls_utils.tracing_is_enabled()
        with tracing_context(parent=False):
            return grandchild_function()

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

    ls_utils.get_env_var.cache_clear()
    with patch.dict(
        "os.environ", {"LANGCHAIN_TRACING_V2": "true", "LANGSMITH_TRACING": "true"}
    ):
        mock_client = MagicMock(spec=Client)
        parent_function(langsmith_extra={"client": mock_client})


def test_tracing_disabled():
    ls_utils.get_env_var.cache_clear()
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


def test_get_api_key() -> None:
    ls_utils.get_env_var.cache_clear()
    assert ls_utils.get_api_key("provided_api_key") == "provided_api_key"
    assert ls_utils.get_api_key("'provided_api_key'") == "provided_api_key"
    assert ls_utils.get_api_key('"_provided_api_key"') == "_provided_api_key"

    with patch.dict("os.environ", {"LANGCHAIN_API_KEY": "env_api_key"}, clear=True):
        api_key_ = ls_utils.get_api_key(None)
        assert api_key_ == "env_api_key"

    ls_utils.get_env_var.cache_clear()

    with patch.dict("os.environ", {}, clear=True):
        assert ls_utils.get_api_key(None) is None
    ls_utils.get_env_var.cache_clear()
    assert ls_utils.get_api_key("") is None
    assert ls_utils.get_api_key(" ") is None


def test_get_api_url() -> None:
    ls_utils.get_env_var.cache_clear()
    assert ls_utils.get_api_url("http://provided.url") == "http://provided.url"

    with patch.dict("os.environ", {"LANGCHAIN_ENDPOINT": "http://env.url"}):
        assert ls_utils.get_api_url(None) == "http://env.url"

    ls_utils.get_env_var.cache_clear()
    with patch.dict("os.environ", {}, clear=True):
        assert ls_utils.get_api_url(None) == "https://api.smith.langchain.com"
    ls_utils.get_env_var.cache_clear()
    with patch.dict("os.environ", {}, clear=True):
        assert ls_utils.get_api_url(None) == "https://api.smith.langchain.com"
    ls_utils.get_env_var.cache_clear()
    with patch.dict("os.environ", {"LANGCHAIN_ENDPOINT": "http://env.url"}):
        assert ls_utils.get_api_url(None) == "http://env.url"
    ls_utils.get_env_var.cache_clear()
    with pytest.raises(ls_utils.LangSmithUserError):
        ls_utils.get_api_url(" ")


def test_get_func_name():
    class Foo:
        def __call__(self, foo: int):
            return "bar"

    assert ls_utils._get_function_name(Foo()) == "Foo"
    assert ls_utils._get_function_name(functools.partial(Foo(), foo=3)) == "Foo"

    class AFoo:
        async def __call__(self, foo: int):
            return "bar"

    assert ls_utils._get_function_name(AFoo()) == "AFoo"
    assert ls_utils._get_function_name(functools.partial(AFoo(), foo=3)) == "AFoo"

    def foo(bar: int) -> None:
        return bar

    assert ls_utils._get_function_name(foo) == "foo"
    assert ls_utils._get_function_name(functools.partial(foo, bar=3)) == "foo"

    async def afoo(bar: int) -> None:
        return bar

    assert ls_utils._get_function_name(afoo) == "afoo"
    assert ls_utils._get_function_name(functools.partial(afoo, bar=3)) == "afoo"

    lambda_func = lambda x: x + 1  # noqa
    assert ls_utils._get_function_name(lambda_func) == "<lambda>"

    class BarClass:
        pass

    assert ls_utils._get_function_name(BarClass) == "BarClass"

    assert ls_utils._get_function_name(print) == "print"

    assert ls_utils._get_function_name("not_a_function") == "not_a_function"


def test_get_host_url():
    # If web_url is explicitly provided, it takes precedence over api_url.
    assert (
        ls_utils.get_host_url(
            "https://my-custom-web.com", "https://api.smith.langchain.com"
        )
        == "https://my-custom-web.com"
    )

    # When web_url is None and api_url is localhost.
    assert ls_utils.get_host_url(None, "http://localhost:5000") == "http://localhost"
    # A port variation on localhost.
    assert ls_utils.get_host_url(None, "http://127.0.0.1:8080") == "http://localhost", (
        "Should recognize 127.x.x.x as localhost."
    )

    # If api_url path ends with /api, trimmed back to netloc.
    assert (
        ls_utils.get_host_url(None, "https://my-awesome-domain.com/api")
        == "https://my-awesome-domain.com"
    )

    # If api_url path ends with /api/v1, trimmed back to netloc.
    assert (
        ls_utils.get_host_url(None, "https://my-other-domain.com/api/v1")
        == "https://my-other-domain.com"
    )

    # If netloc begins with dev.
    assert (
        ls_utils.get_host_url(None, "https://dev.smith.langchain.com/api/v1")
        == "https://dev.smith.langchain.com"
    )

    # If netloc begins with eu.
    assert (
        ls_utils.get_host_url(None, "https://eu.smith.langchain.com/api")
        == "https://eu.smith.langchain.com"
    )

    # If netloc begins with beta.
    assert (
        ls_utils.get_host_url(None, "https://beta.smith.langchain.com")
        == "https://beta.smith.langchain.com"
    )

    # If netloc begins with api.
    assert (
        ls_utils.get_host_url(None, "https://api.smith.langchain.com")
        == "https://smith.langchain.com"
    )

    # Otherwise, returns https://smith.langchain.com for unknown host.
    assert (
        ls_utils.get_host_url(None, "https://unknownhost.com")
        == "https://smith.langchain.com"
    )


class MockRequest:
    """Mock request object for testing filter_request_headers"""

    def __init__(self, url: str, headers: Optional[dict] = None):
        self.url = url
        self.headers = headers or {
            "Authorization": "Bearer token",
            "Content-Type": "application/json",
        }


def test_filter_request_headers():
    # Test with no filtering - both ignore_hosts and allow_hosts are None
    request = MockRequest("https://api.example.com/test")
    result = ls_utils.filter_request_headers(request)

    assert result is request


def test_filter_request_headers_allow_hosts():
    # Test allow_hosts functionality

    # Test matching hostname (exact match)
    request = MockRequest("https://api.example.com/test")
    result = ls_utils.filter_request_headers(request, allow_hosts=["api.example.com"])
    assert result is request

    # Test matching full URL
    request = MockRequest("https://api.example.com/test")
    result = ls_utils.filter_request_headers(
        request, allow_hosts=["https://api.example.com"]
    )
    assert result is request

    # Test subdomain matching
    request = MockRequest("https://sub.example.com/test")
    result = ls_utils.filter_request_headers(request, allow_hosts=["example.com"])
    assert result is request

    # Test non-matching host - should return None
    request = MockRequest("https://api.different.com/test")
    result = ls_utils.filter_request_headers(request, allow_hosts=["api.example.com"])
    assert result is None

    # Test multiple allow hosts - matching first
    request = MockRequest("https://api.first.com/test")
    result = ls_utils.filter_request_headers(
        request, allow_hosts=["api.first.com", "api.second.com"]
    )
    assert result is request

    # Test multiple allow hosts - matching second
    request = MockRequest("https://api.second.com/test")
    result = ls_utils.filter_request_headers(
        request, allow_hosts=["api.first.com", "api.second.com"]
    )
    assert result is request

    # Test multiple allow hosts - not matching any
    request = MockRequest("https://api.third.com/test")
    result = ls_utils.filter_request_headers(
        request, allow_hosts=["api.first.com", "api.second.com"]
    )
    assert result is None


def test_filter_request_headers_url_parsing_error():
    # Test URL parsing error handling
    class BadRequest:
        def __init__(self, bad_url: str):
            self.url = bad_url
            self.headers = {"Authorization": "Bearer token"}

    # Mock urllib_parse.urlparse to raise an exception
    with patch(
        "langsmith.utils.urllib_parse.urlparse", side_effect=Exception("Parse error")
    ):
        request = BadRequest("not-a-valid-url")
        result = ls_utils.filter_request_headers(request, allow_hosts=["example.com"])
        assert result is None


def test_filter_request_headers_hostname_none():
    # Test when parsed_url.hostname is None
    request = MockRequest("file:///local/path")  # This URL has no hostname
    result = ls_utils.filter_request_headers(request, allow_hosts=["example.com"])
    assert result is None


def test_filter_request_headers_combined_ignore_and_allow():
    # Test when both ignore_hosts and allow_hosts are provided
    # ignore_hosts takes precedence (legacy behavior)

    request = MockRequest("https://api.example.com/test")
    result = ls_utils.filter_request_headers(
        request,
        ignore_hosts=["https://api.example.com"],
        allow_hosts=["api.example.com"],
    )
    assert result is None  # Should be ignored despite being in allow_hosts


def test_filter_request_headers_edge_cases():
    # Test various edge cases

    # Empty ignore_hosts list
    request = MockRequest("https://api.example.com/test")
    result = ls_utils.filter_request_headers(request, ignore_hosts=[])
    assert result is request

    # Empty allow_hosts list - empty list evaluates to False, so no filtering occurs
    request = MockRequest("https://api.example.com/test")
    result = ls_utils.filter_request_headers(request, allow_hosts=[])
    assert result is request  # Empty list means no allow_hosts filtering

    # HTTP vs HTTPS in allow_hosts
    request = MockRequest("http://api.example.com/test")
    result = ls_utils.filter_request_headers(
        request, allow_hosts=["https://api.example.com"]
    )
    assert result is None  # Should not match different protocol

    # Port numbers in URLs
    request = MockRequest("https://api.example.com:8080/test")
    result = ls_utils.filter_request_headers(request, allow_hosts=["api.example.com"])
    assert result is request

    # Subdomain with allow_hosts containing full URL
    request = MockRequest("https://sub.example.com/test")
    result = ls_utils.filter_request_headers(
        request, allow_hosts=["https://example.com"]
    )
    assert result is None  # Full URL should not match subdomain


def test_filter_request_headers_localhost():
    # Test localhost with different ports

    # Test localhost with port 8080
    request = MockRequest("http://localhost:8080/test")
    result = ls_utils.filter_request_headers(request, allow_hosts=["localhost"])
    assert result is request

    # Test 127.0.0.1 with port 3000
    request = MockRequest("http://127.0.0.1:3000/api")
    result = ls_utils.filter_request_headers(request, allow_hosts=["127.0.0.1"])
    assert result is request

    # Test localhost without port matching localhost with port
    request = MockRequest("http://localhost/test")
    result = ls_utils.filter_request_headers(request, allow_hosts=["localhost"])
    assert result is request

    # Test different localhost formats
    request = MockRequest("https://127.0.0.1:5000/test")
    result = ls_utils.filter_request_headers(request, allow_hosts=["localhost"])
    assert result is None  # 127.0.0.1 doesn't match "localhost" string

    # Test full URL matching for localhost with port
    request = MockRequest("http://localhost:9000/test")
    result = ls_utils.filter_request_headers(
        request, allow_hosts=["http://localhost:9000"]
    )
    assert result is request

    # Test port mismatch
    request = MockRequest("http://localhost:8080/test")
    result = ls_utils.filter_request_headers(
        request, allow_hosts=["http://localhost:3000"]
    )
    assert result is None
