"""`LangSmithSecret` reads as its plaintext everywhere but LangSmith's serializer."""

import copy
import json
import pickle
from typing import Any

import pytest
from pydantic import BaseModel

from langsmith.anonymizer import SECRET_PLACEHOLDER
from langsmith.secret import LANGSMITH_SECRET_MASK, LangSmithSecret

PLAINTEXT = "sk-proj-AbCdEfGhIjKlMnOpQrStUvWxYz"


@pytest.fixture
def secret() -> LangSmithSecret:
    return LangSmithSecret(PLAINTEXT)


def test_mask_is_distinguishable_from_other_redactions():
    assert LANGSMITH_SECRET_MASK == "[LANGSMITH SECRET]"
    # Must not be confusable with the regex anonymizer's token, or with
    # pydantic's SecretStr rendering.
    assert LANGSMITH_SECRET_MASK != SECRET_PLACEHOLDER
    assert LANGSMITH_SECRET_MASK != "**********"


# --------------------------------------------------------------------------
# Value semantics: indistinguishable from the plaintext str.
# --------------------------------------------------------------------------


def test_is_a_real_str(secret):
    assert isinstance(secret, str) and secret == PLAINTEXT


def test_no_instance_dict(secret):
    assert not hasattr(secret, "__dict__")
    with pytest.raises(AttributeError):
        secret.extra = 1  # type: ignore[attr-defined]


def test_encode_returns_the_real_bytes(secret):
    assert secret.encode() == PLAINTEXT.encode()


def test_repr_is_masked_but_str_is_not(secret):
    # repr is masked so an unrelated object whose own __repr__ interpolates a
    # secret does not leak it when LangSmith stringifies that object.
    assert repr(secret) == f"LangSmithSecret('{LANGSMITH_SECRET_MASK}')"
    assert PLAINTEXT not in repr(secret)
    assert str(secret) == PLAINTEXT


def test_copy_deepcopy_and_pickle_preserve_the_marker(secret):
    for clone in (
        copy.copy(secret),
        copy.deepcopy(secret),
        pickle.loads(pickle.dumps(secret)),
    ):
        assert isinstance(clone, LangSmithSecret)
        assert clone == PLAINTEXT


# --------------------------------------------------------------------------
# Only LangSmith masks. Everything else sees the plaintext.
# --------------------------------------------------------------------------


def test_plain_json_dumps_always_emits_the_plaintext(secret):
    assert json.dumps(secret) == json.dumps(PLAINTEXT)
    assert json.dumps({secret: secret}) == json.dumps({PLAINTEXT: PLAINTEXT})


def test_pydantic_dump_always_emits_the_plaintext(secret):
    """A vendor client dumping a model must get the credential, not the mask."""

    class Body(BaseModel):
        metadata: Any

    body = Body(metadata={"Authorization": secret})
    assert body.model_dump() == {"metadata": {"Authorization": PLAINTEXT}}
    assert PLAINTEXT in body.model_dump_json()


# --------------------------------------------------------------------------
# Stickiness: the *value* matches plain str exactly, the *type* propagates.
# --------------------------------------------------------------------------

# (method name, args) -> compared against the same call on a plain str.
_STR_RETURNING_CALLS = [
    ("upper", ()),
    ("lower", ()),
    ("title", ()),
    ("capitalize", ()),
    ("casefold", ()),
    ("swapcase", ()),
    ("strip", ()),
    ("lstrip", ()),
    ("rstrip", ()),
    ("replace", ("sk-", "xx-")),
    ("removeprefix", ("sk-",)),
    ("removesuffix", ("Yz",)),
    ("center", (60,)),
    ("ljust", (60,)),
    ("rjust", (60,)),
    ("zfill", (60,)),
    ("expandtabs", ()),
    ("join", (["a", "b"],)),
    ("format", ()),
]


@pytest.mark.parametrize("method,args", _STR_RETURNING_CALLS)
def test_str_methods_return_plaintext_value_and_keep_the_marker(secret, method, args):
    result = getattr(secret, method)(*args)
    assert result == getattr(PLAINTEXT, method)(*args), "value must match plain str"
    assert isinstance(result, LangSmithSecret), "marker must survive"


@pytest.mark.parametrize(
    "op,expected_type",
    [
        (lambda s: str(s), LangSmithSecret),
        (lambda s: f"{s}", LangSmithSecret),
        # A bare `"%s"` is a CPython fast path that hands the object back.
        (lambda s: "%s" % s, LangSmithSecret),
        (lambda s: s[:6], LangSmithSecret),
        (lambda s: s[0], LangSmithSecret),
        (lambda s: s + "!", LangSmithSecret),
        (lambda s: s * 2, LangSmithSecret),
        (lambda s: 2 * s, LangSmithSecret),
        (lambda s: s.format_map({}), LangSmithSecret),
    ],
)
def test_operators_return_plaintext_value_and_keep_the_marker(
    secret, op, expected_type
):
    assert op(secret) == op(PLAINTEXT), "value must match plain str"
    assert type(op(secret)) is expected_type


@pytest.mark.parametrize(
    "method,args",
    [("split", ("-",)), ("rsplit", ("-",)), ("splitlines", ()), ("partition", ("-",))],
)
def test_sequence_returning_methods_mark_each_element(secret, method, args):
    result = getattr(secret, method)(*args)
    assert result == getattr(PLAINTEXT, method)(*args), "value must match plain str"
    assert all(isinstance(part, LangSmithSecret) for part in result)


def test_rpartition_marks_each_element(secret):
    result = secret.rpartition("-")
    assert result == PLAINTEXT.rpartition("-")
    assert all(isinstance(part, LangSmithSecret) for part in result)


@pytest.mark.parametrize(
    "op",
    [
        pytest.param(lambda s: "Bearer " + s, id="prepend-concat"),
        pytest.param(lambda s: "".join([s]), id="str.join"),
        pytest.param(lambda s: "Bearer {}".format(s), id="format-into-plain-str"),
        pytest.param(lambda s: "Bearer %s" % s, id="percent-format-into-plain-str"),
        pytest.param(lambda s: f"Bearer {s}", id="f-string-interpolation"),
    ],
)
def test_documented_marker_loss_when_str_owns_the_operation(secret, op):
    """`str` handles these itself and never consults the subclass.

    Documented in `LangSmithSecret`: wrap the final value, not a part of it.
    """
    result = op(secret)
    assert type(result) is str
    assert not isinstance(result, LangSmithSecret)
