"""Mark a value as a secret, so LangSmith masks it instead of tracing it.

::

    from langsmith import LangSmithSecret

    API_KEY = LangSmithSecret(os.environ["VENDOR_API_KEY"])

See :class:`LangSmithSecret` for the guarantees and the known limits.
"""

from __future__ import annotations

import collections
from typing import Any

__all__ = ["LANGSMITH_SECRET_MASK", "LangSmithSecret"]

LANGSMITH_SECRET_MASK = "[LANGSMITH SECRET]"
"""Written in place of a secret. Distinct from the regex anonymizer's
``[SECRET_DETECTED]`` so the two mechanisms are distinguishable in a trace."""

_NOT_HANDLED: Any = object()
"""Returned by :func:`_coerce_builtin_subclass` when it does not apply."""

# `str` methods returning a new `str`; re-wrapped so a derived value stays
# secret. `partition`/`split` return sequences of `str` and are handled below.
_STR_RETURNING = (
    "__add__",
    "__format__",
    "__getitem__",
    "__mod__",
    "__mul__",
    "__rmul__",
    "capitalize",
    "casefold",
    "center",
    "expandtabs",
    "format",
    "format_map",
    "join",
    "ljust",
    "lower",
    "lstrip",
    "removeprefix",
    "removesuffix",
    "replace",
    "rjust",
    "rstrip",
    "strip",
    "swapcase",
    "title",
    "translate",
    "upper",
    "zfill",
)
_SEQUENCE_RETURNING = ("partition", "rpartition", "rsplit", "split", "splitlines")


class LangSmithSecret(str):
    """A string that LangSmith serializes as ``[LANGSMITH SECRET]``.

    Wrap a credential once, where it is read, and LangSmith masks it wherever
    it appears in a trace, at any nesting depth::

        @traceable
        def call_vendor(api_key: str, prompt: str) -> str: ...


        call_vendor(api_key=LangSmithSecret(key), prompt="hi")
        # traced inputs: {"api_key": "[LANGSMITH SECRET]", "prompt": "hi"}

    It is a real ``str`` everywhere else: ``json.dumps``, logging and
    third-party clients all see the true value. Operations that derive a new
    string return a ``LangSmithSecret`` again, so the marker is not lost by
    ``.strip()`` or slicing.

    Known limits:

    - ``"Bearer " + secret`` and ``"".join([secret])`` yield a plain ``str``:
      ``str`` handles those itself and never consults this class. Wrap the
      final value instead -- ``LangSmithSecret(f"Bearer {key}")``.
    - ``secret.encode()`` returns the real bytes, by design.
    - A secret used as a **dict key** is masked, but two of them in one dict
      collapse to a single entry. A key held inside a dataclass is not masked:
      orjson serializes those itself.
    - An object whose own ``__str__`` interpolates a secret leaks it wherever
      LangSmith stringifies that object. ``__repr__`` is masked; ``__str__``
      belongs to the object.
    - Nothing inside a **pydantic model** is masked. Pydantic serializes its
      own fields and LangSmith deliberately does not override that: a hook
      there would also replace the credential with the mask when a vendor
      client dumps the model to build a request.
    """

    __slots__ = ()

    def __str__(self) -> LangSmithSecret:
        """Return the plaintext, still marked as a secret."""
        return self

    def __repr__(self) -> str:
        """Mask the plaintext.

        So an object whose own ``__repr__`` interpolates a secret does not leak
        it when LangSmith stringifies that object.
        """
        return f"{type(self).__name__}({LANGSMITH_SECRET_MASK!r})"


def _make_str_wrapper(name: str) -> Any:
    base = getattr(str, name)

    def wrapper(self: LangSmithSecret, *args: Any, **kwargs: Any) -> Any:
        result = base(self, *args, **kwargs)
        return LangSmithSecret(result) if type(result) is str else result

    wrapper.__name__ = name
    wrapper.__qualname__ = f"LangSmithSecret.{name}"
    return wrapper


def _make_sequence_wrapper(name: str) -> Any:
    base = getattr(str, name)

    def wrapper(self: LangSmithSecret, *args: Any, **kwargs: Any) -> Any:
        result = base(self, *args, **kwargs)
        return type(result)(
            LangSmithSecret(item) if type(item) is str else item for item in result
        )

    wrapper.__name__ = name
    wrapper.__qualname__ = f"LangSmithSecret.{name}"
    return wrapper


# Patch builting methods to return LangSmithSecret instances when appropriate
for _name in _STR_RETURNING:
    setattr(LangSmithSecret, _name, _make_str_wrapper(_name))
for _name in _SEQUENCE_RETURNING:
    setattr(LangSmithSecret, _name, _make_sequence_wrapper(_name))


def _coerce_builtin_subclass(obj: Any) -> Any:
    """Mask a secret, or coerce a builtin subclass back to its exact type.

    orjson's ``OPT_PASSTHROUGH_SUBCLASS`` is what routes a
    :class:`~langsmith.LangSmithSecret` to LangSmith's ``default`` hook, but it
    diverts *every* ``str``/``int``/``dict``/``list`` subclass there as a side
    effect. Coercing those back reproduces the output orjson wrote natively, so
    enabling the option changes nothing for payloads without secrets.
    """
    if isinstance(obj, LangSmithSecret):
        return LANGSMITH_SECRET_MASK
    if isinstance(obj, str):
        # `str.__str__` bypasses a subclass `__str__` override and returns an
        # exact `str` holding the underlying data, which is what orjson writes.
        return str.__str__(obj)
    if isinstance(obj, int):
        return int(obj)
    if isinstance(obj, dict):
        return dict(obj)
    if isinstance(obj, list):
        return list(obj)
    # `float` is absent deliberately: the option does not divert float
    # subclasses, so coercing them would change output unrelated to secrets.
    return _NOT_HANDLED


def _redact_secrets(obj: Any) -> Any:
    """Return a copy of ``obj`` with every :class:`LangSmithSecret` masked.

    For the places no ``default`` hook can intercept a secret: the stdlib
    ``json`` fallback, which writes ``str`` subclasses natively, OpenTelemetry
    span attributes, and dict keys, which orjson never routes through it.
    """
    if isinstance(obj, LangSmithSecret):
        return LANGSMITH_SECRET_MASK
    if isinstance(obj, dict):
        return {
            _redact_secrets(key): _redact_secrets(value) for key, value in obj.items()
        }
    if isinstance(obj, list):
        return [_redact_secrets(value) for value in obj]
    if isinstance(obj, tuple):
        return tuple(_redact_secrets(value) for value in obj)
    if isinstance(obj, collections.deque):
        return collections.deque(_redact_secrets(value) for value in obj)
    return obj
