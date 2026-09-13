"""LangSmith's serializer masks secrets, and is otherwise byte-for-byte unchanged."""

import collections
import dataclasses
import datetime
import decimal
import enum
import ipaddress
import json
import pathlib
import re
from typing import Any, NamedTuple

import pytest
from pydantic import BaseModel

from langsmith._internal._serde import dumps_json
from langsmith.secret import LANGSMITH_SECRET_MASK, LangSmithSecret

PLAINTEXT = "sk-proj-AbCdEfGhIjKlMnOpQrStUvWxYz"
MASK_BYTES = LANGSMITH_SECRET_MASK.encode()
PLAINTEXT_BYTES = PLAINTEXT.encode()


def secret() -> LangSmithSecret:
    return LangSmithSecret(PLAINTEXT)


# --------------------------------------------------------------------------
# Masking
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(secret(), id="top-level"),
        pytest.param({"api_key": secret()}, id="dict-value"),
        pytest.param([secret()], id="list-element"),
        pytest.param((secret(),), id="tuple-element"),
        pytest.param({secret()}, id="set-element"),
        pytest.param(collections.deque([secret()]), id="deque-element"),
        pytest.param({"a": [{"b": (secret(),)}]}, id="mixed-nesting"),
        pytest.param(collections.Counter(x=1, y=secret()), id="counter-value"),
        pytest.param(collections.OrderedDict(k=secret()), id="ordereddict-value"),
        pytest.param(
            {"cfg": {"headers": {"Authorization": secret()}}, "model": "gpt-4o"},
            id="headers",
        ),
    ],
)
def test_masks_secrets(payload):
    result = dumps_json(payload)
    assert PLAINTEXT_BYTES not in result
    assert MASK_BYTES in result


def test_masks_only_the_secret():
    assert dumps_json({"h": {"Authorization": secret()}, "model": "gpt-4o"}) == (
        b'{"h":{"Authorization":"[LANGSMITH SECRET]"},"model":"gpt-4o"}'
    )


def test_masks_below_the_anonymizer_depth_limit():
    """`create_anonymizer` stops at max_depth=10; this does not."""
    payload: Any = secret()
    for _ in range(25):
        payload = {"nested": payload}
    result = dumps_json(payload)
    assert PLAINTEXT_BYTES not in result
    assert MASK_BYTES in result


def test_masks_a_derived_secret():
    """A value derived from a secret keeps the marker, so it is masked too."""
    assert PLAINTEXT_BYTES not in dumps_json({"k": secret().upper()})
    assert PLAINTEXT_BYTES not in dumps_json({"k": secret()[:10]})
    assert PLAINTEXT_BYTES not in dumps_json({"k": secret().split("-")})


def test_masks_inside_objects_serialized_via_their_own_methods():
    class ViaDict:
        def dict(self):
            return {"api_key": secret()}

    class ViaToDict:
        def to_dict(self):
            return {"api_key": secret()}

    @dataclasses.dataclass
    class ViaDataclass:
        api_key: Any = dataclasses.field(default_factory=secret)

    class ViaNamedTuple(NamedTuple):
        api_key: Any

    for payload in (
        ViaDict(),
        ViaToDict(),
        ViaDataclass(),
        ViaNamedTuple(secret()),
        collections.OrderedDict(api_key=secret()),
        collections.defaultdict(str, {"api_key": secret()}),
    ):
        result = dumps_json({"v": payload})
        assert PLAINTEXT_BYTES not in result, payload
        assert MASK_BYTES in result, payload


def test_masks_when_an_objects_repr_interpolates_a_secret():
    class Holder:
        def __init__(self):
            self.api_key = secret()

        def __repr__(self):
            return f"Holder(api_key={self.api_key!r})"

    assert PLAINTEXT_BYTES not in dumps_json({"v": Holder()})


# --------------------------------------------------------------------------
# Fallback paths. A lone surrogate or an exotic dict key anywhere in the
# payload diverts the whole thing away from orjson's fast path.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"bad": "x \ud800 y", "h": secret()}, id="lone-surrogate"),
        pytest.param({1: secret(), (1, 2): [secret()]}, id="non-str-keys"),
        pytest.param(
            {(1, 2): secret(), "bad": "\ud800", "n": {"deep": secret()}},
            id="surrogate-and-non-str-keys",
        ),
        pytest.param(
            {"bad": "\ud800", "m": collections.Counter({"n": 1}), "h": secret()},
            id="surrogate-and-builtin-subclass",
        ),
    ],
)
def test_masks_on_the_stdlib_json_fallback_paths(payload):
    result = dumps_json(payload)
    assert PLAINTEXT_BYTES not in result
    assert MASK_BYTES in result


@pytest.mark.parametrize(
    "payload",
    [
        {secret(): "v"},
        {"m": {secret(): "v"}},
        [{secret(): "v"}],
        ({secret(): "v"},),
        collections.deque([{secret(): "v"}]),
        {"a": [{"b": ({secret(): "v"},)}]},
    ],
    ids=["top", "nested", "list", "tuple", "deque", "deep"],
)
def test_dict_keys_are_masked(payload: Any):
    """A `str` subclass key always trips the fast path, so masking can run."""
    result = dumps_json(payload)
    assert PLAINTEXT_BYTES not in result
    assert MASK_BYTES in result


def test_two_secret_keys_collapse_into_one_entry():
    assert dumps_json({secret(): "a", LangSmithSecret("other"): "b"}) == (
        b'{"%s":"b"}' % MASK_BYTES
    )


def test_documented_limitation_dataclass_keys_and_pydantic_models():
    """orjson and pydantic serialize these themselves, so we never see them."""

    @dataclasses.dataclass
    class Holder:
        body: dict

    class Model(BaseModel):
        body: Any

    for payload in (
        Holder(body={secret(): "v"}),  # a dataclass hides only its dict *keys*
        Model(body={secret(): "v"}),  # a model hides its keys ...
        Model(body={"api_key": secret()}),  # ... and its values
    ):
        assert PLAINTEXT_BYTES in dumps_json(payload)


# --------------------------------------------------------------------------
# No regressions: enabling OPT_PASSTHROUGH_SUBCLASS must not change the output
# of any payload that holds no secrets.
# --------------------------------------------------------------------------


class _StrSubclass(str):
    pass


class _StrWithDict(str):
    def dict(self):
        return {"OVERRIDDEN": True}


class _StrWithCustomStr(str):
    def __str__(self):
        return "OVERRIDDEN"


class _IntSubclass(int):
    pass


class _FloatSubclass(float):
    pass


class _ListSubclass(list):
    pass


class _DictSubclass(dict):
    pass


class _DictWithDict(dict):
    def dict(self):
        return {"OVERRIDDEN": True}


class _TupleSubclass(tuple):
    pass


class _NT(NamedTuple):
    a: int


class _StrEnum(str, enum.Enum):
    A = "a"


class _IntEnum(int, enum.Enum):
    B = 1


class _DatetimeSubclass(datetime.datetime):
    pass


@dataclasses.dataclass
class _Dataclass:
    x: int = 1


class _PydanticV2(BaseModel):
    a: Any = None
    d: datetime.datetime = datetime.datetime(2020, 1, 1)


BYTE_IDENTICAL_CASES = {
    # Builtin subclasses now routed through the `default` hook. These are the
    # cases the coercion in `_serialize_json` exists to protect.
    "str-subclass": (_StrSubclass("x"), b'{"v":"x"}'),
    "str-subclass-with-dict-method": (_StrWithDict("x"), b'{"v":"x"}'),
    "str-subclass-with-custom-str": (_StrWithCustomStr("x"), b'{"v":"x"}'),
    "int-subclass": (_IntSubclass(7), b'{"v":7}'),
    "list-subclass": (_ListSubclass([1, 2]), b'{"v":[1,2]}'),
    "dict-subclass": (_DictSubclass(a=1), b'{"v":{"a":1}}'),
    "dict-subclass-with-dict-method": (_DictWithDict(a=1), b'{"v":{"a":1}}'),
    "counter": (collections.Counter(a=1), b'{"v":{"a":1}}'),
    "defaultdict": (collections.defaultdict(int, {"a": 1}), b'{"v":{"a":1}}'),
    "ordereddict": (collections.OrderedDict(a=1), b'{"v":{"a":1}}'),
    # Not diverted by the option; pinned so the coercion does not overreach.
    "float-subclass": (_FloatSubclass(1.5), b'{"v":"1.5"}'),
    "tuple-subclass": (_TupleSubclass([1, 2]), b'{"v":[1,2]}'),
    "namedtuple": (_NT(1), b'{"v":{"a":1}}'),
    "str-enum": (_StrEnum.A, b'{"v":"a"}'),
    "int-enum": (_IntEnum.B, b'{"v":1}'),
    "datetime-subclass": (
        _DatetimeSubclass(2020, 1, 1),
        b'{"v":"2020-01-01T00:00:00"}',
    ),
    "timedelta": (datetime.timedelta(seconds=5), b'{"v":5.0}'),
    "decimal": (decimal.Decimal("1.5"), b'{"v":1.5}'),
    "decimal-integral": (decimal.Decimal("3"), b'{"v":3}'),
    "bytes": (b"ab", b'{"v":"YWI="}'),
    "path": (pathlib.Path("/a/b"), b'{"v":"/a/b"}'),
    "regex": (re.compile("a+"), b'{"v":"a+"}'),
    "ip": (ipaddress.IPv4Address("1.2.3.4"), b'{"v":"1.2.3.4"}'),
    "set": ({1}, b'{"v":[1]}'),
    "frozenset": (frozenset([1]), b'{"v":[1]}'),
    "deque": (collections.deque([1, 2]), b'{"v":[1,2]}'),
    "pydantic-v2": (
        _PydanticV2(a={"k": [1, 2]}),
        b'{"v":{"a":{"k":[1,2]},"d":"2020-01-01T00:00:00"}}',
    ),
}


@pytest.mark.parametrize(
    "value,expected",
    list(BYTE_IDENTICAL_CASES.values()),
    ids=list(BYTE_IDENTICAL_CASES),
)
def test_output_is_unchanged_for_payloads_without_secrets(value, expected):
    assert dumps_json({"v": value}) == expected


def test_class_objects_are_unchanged():
    """A `dict` subclass *class* is not a `dict` instance; coercion must skip it."""
    assert dumps_json({"v": _DictSubclass}) == (
        b'{"v":"%s"}' % repr(_DictSubclass).encode()
    )


def test_exception_is_unchanged():
    assert dumps_json({"v": ValueError("boom")}) == (
        b'{"v":{"error":"ValueError","message":"boom"}}'
    )


def test_non_str_keys_are_unchanged():
    assert dumps_json({1: "a", (1, 2): "b"}) == b'{"1":"a","(1, 2)":"b"}'


def test_redact_secrets_masks_every_secret_in_place_of_the_stdlib_fallback():
    """The PyPy path: `json.dumps` serializes `str` subclasses natively.

    It never calls `default` for them, so secrets have to be replaced by a walk
    before the dump. Not reachable on CPython, hence tested directly.
    """
    from langsmith.secret import _redact_secrets

    payload = {
        "api_key": secret(),
        "list": [secret(), "keep"],
        "tuple": (secret(),),
        "nested": {"deep": secret()},
        "number": 7,
    }

    result = _redact_secrets(payload)

    assert result == {
        "api_key": LANGSMITH_SECRET_MASK,
        "list": [LANGSMITH_SECRET_MASK, "keep"],
        "tuple": (LANGSMITH_SECRET_MASK,),
        "nested": {"deep": LANGSMITH_SECRET_MASK},
        "number": 7,
    }
    assert PLAINTEXT not in json.dumps(result), "stdlib json must not see it"
    # The caller's payload is untouched.
    assert payload["api_key"] == PLAINTEXT
