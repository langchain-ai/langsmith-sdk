from __future__ import annotations

import base64
import collections
import datetime
import decimal
import ipaddress
import json
import logging
import pathlib
import re
import uuid
from typing import Any

from pydantic import BaseModel

from langsmith._internal import _orjson

try:
    from zoneinfo import ZoneInfo  # type: ignore[import-not-found]
except ImportError:

    class ZoneInfo:  # type: ignore[no-redef]
        """Introduced in python 3.9."""


logger = logging.getLogger(__name__)
_ORJSON_OPTIONS = (
    _orjson.OPT_SERIALIZE_NUMPY
    | _orjson.OPT_SERIALIZE_DATACLASS
    | _orjson.OPT_SERIALIZE_UUID
    | _orjson.OPT_NON_STR_KEYS
)
# Turn off OPT_NON_STR_KEYS, trading better speed in the general case where
# all dict keys are strings for worse speed in the exceptional case
_ORJSON_OPTIONS_FAST = _ORJSON_OPTIONS & ~_orjson.OPT_NON_STR_KEYS
_JSON_KEY_TYPES = (str, int, float, bool, type(None))
# Matches escaped lone UTF-16 surrogates (e.g. b"\\ud800") in ensure_ascii
# json.dumps output; used to strip them on the stdlib-json fallback path.
_SURROGATE_RE = re.compile(rb"\\ud[89a-f][0-9a-f]{2}", re.IGNORECASE)


def _simple_default(obj):
    try:
        # Only need to handle types that orjson doesn't serialize by default
        # https://github.com/ijl/orjson#serialize
        #
        # datetime/UUID look redundant with orjson's native encoders, but this
        # function is reached via two paths that bypass them, so keep them:
        #   (a) non-str dict keys normalized through _normalize_json_keys, and
        #   (b) the stdlib json.dumps fallback in dumps_json (surrogate path),
        #       which routes these *values* through this hook.
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        elif isinstance(obj, uuid.UUID):
            return str(obj)
        elif isinstance(obj, BaseException):
            return {"error": type(obj).__name__, "message": str(obj)}
        elif isinstance(obj, (set, frozenset, collections.deque)):
            return list(obj)
        elif isinstance(obj, (datetime.timezone, ZoneInfo)):
            return obj.tzname(None)
        elif isinstance(obj, datetime.timedelta):
            return obj.total_seconds()
        elif isinstance(obj, decimal.Decimal):
            if obj.as_tuple().exponent >= 0:
                return int(obj)
            else:
                return float(obj)
        elif isinstance(
            obj,
            (
                ipaddress.IPv4Address,
                ipaddress.IPv4Interface,
                ipaddress.IPv4Network,
                ipaddress.IPv6Address,
                ipaddress.IPv6Interface,
                ipaddress.IPv6Network,
                pathlib.Path,
            ),
        ):
            return str(obj)
        elif isinstance(obj, re.Pattern):
            return obj.pattern
        elif isinstance(obj, (bytes, bytearray)):
            return base64.b64encode(obj).decode()
        return str(obj)
    except Exception as e:
        logger.debug(f"Failed to serialize {type(obj)} to JSON: {e}")
    return str(obj)


_MISSING = object()
# Maps a Class to its Pydantic core serializer, or to None when the fast path
# below does not apply to it. Bounded rather than weakly keyed.
_PYDANTIC_SERIALIZER_CACHE_MAX = 1024
_pydantic_core_serializers: dict[type, Any] = {}


def _remember_pydantic_serializer(cls: type, serializer: Any) -> None:
    if len(_pydantic_core_serializers) >= _PYDANTIC_SERIALIZER_CACHE_MAX:
        _pydantic_core_serializers.clear()
    _pydantic_core_serializers[cls] = serializer


def _pydantic_json_dump(obj: Any) -> Any:
    """Serialize a Pydantic v2 model with its low level core serializer.

    `model_dump()` is a Python wrapper around this serializer. Calling the
    low-level serializer is measurably cheaper, if it hasn't been overridden.

    Returns `_MISSING` when the shortcut doesn't apply, so callers fall back to
    other methods. A raise is remembered per class, because
    `_serialization_methods` starts with the same json-mode dump: retrying it
    per object would only raise twice instead of once.
    """
    cls = type(obj)
    serializer = _pydantic_core_serializers.get(cls, _MISSING)
    if serializer is _MISSING:
        serializer = None
        if isinstance(obj, BaseModel) and cls.model_dump is BaseModel.model_dump:
            # getattr: a model whose schema build is still deferred has a
            # placeholder here, which the try below handles.
            serializer = getattr(cls, "__pydantic_serializer__", None)
        _remember_pydantic_serializer(cls, serializer)
    if serializer is None:
        return _MISSING

    try:
        return serializer.to_python(obj, mode="json", exclude_none=True, warnings=False)
    except Exception:
        _remember_pydantic_serializer(cls, None)
        return _MISSING


_serialization_methods: list[tuple[str, dict[str, Any]]] = [
    # Pydantic v2 primary: coerce fields to JSON-native types.
    # Raises on truly non-serializable fields -> the next entry handles those.
    ("model_dump", {"exclude_none": True, "mode": "json"}),
    # Pydantic v2 fallback: python-mode dump; leaves non-JSON values as objects
    # for orjson / _simple_default to serialize.
    ("model_dump", {"exclude_none": True}),
    ("dict", {}),  # Pydantic v1 .dict()
    ("to_dict", {}),  # dataclasses-json to_dict()
]


# IMPORTANT: This function is used from Rust code in `langsmith-pyo3` serialization,
#            in order to handle serializing these tricky Python types *from Rust*.
#            Do not cause this function to become inaccessible (e.g. by deleting
#            or renaming it) without also fixing the corresponding Rust code found in:
#               rust/crates/langsmith-pyo3/src/serialization/mod.rs
def _serialize_json(obj: Any) -> Any:
    try:
        if isinstance(obj, (set, tuple)):
            if hasattr(obj, "_asdict") and callable(obj._asdict):
                # NamedTuple
                return obj._asdict()
            return list(obj)

        # A class object has no useful instance serialization method
        if isinstance(obj, type):
            return _simple_default(obj)

        # Try using the speedier Pydantic serialization first
        fast_serialized = _pydantic_json_dump(obj)
        if fast_serialized is not _MISSING:
            return fast_serialized

        for attr, kwargs in _serialization_methods:
            method = getattr(obj, attr, None)
            if callable(method):
                try:
                    response = method(**kwargs)
                    if not isinstance(response, dict):
                        return str(response)
                    return response
                except Exception as e:
                    logger.debug(
                        f"Failed to use {attr} to serialize {type(obj)} to"
                        f" JSON: {repr(e)}"
                    )
        return _simple_default(obj)
    except Exception as e:
        logger.debug(f"Failed to serialize {type(obj)} to JSON: {e}")
        return str(obj)


def _normalize_json_keys(obj: Any) -> Any:
    """Recursively stringify dict keys that orjson will reject.

    Walks ``dict``, ``list``, ``tuple`` and ``deque`` so that unsupported keys
    hidden at any depth are coerced before serialization. Tuples and deques
    are covered here even though they're only ever *values*: orjson serializes
    them natively (as arrays) and therefore never routes them through the
    ``default`` hook, so a bad-keyed dict nested inside one would otherwise
    slip past normalization. Cycles are handled downstream by
    ``_serialize_json`` (which collapses them to ``str``), not here.

    JSON object keys must ultimately be ``str``/``int``/``float``/``bool``/
    ``None``; other key types are stringified via ``_simple_default`` so they
    match the formats the fast path would produce (e.g. ``datetime`` -> ISO
    8601, ``bytes`` -> base64) rather than Python's ``str()`` or ``repr()``.

    Note: stringifying a non-str key can collide with another key (e.g. a
    literal ``"(1, 2)"`` and a coerced ``(1, 2)``). When that happens one entry
    overwrites the other (last-in-iteration-order wins); the collision is
    logged at debug level so the data loss is traceable.
    """
    if isinstance(obj, dict):
        new: dict[Any, Any] = {}
        for key, value in obj.items():
            norm_key: Any = (
                key if isinstance(key, _JSON_KEY_TYPES) else str(_simple_default(key))
            )
            if norm_key in new:
                logger.debug(
                    "Dict key collision during JSON key normalization; "
                    "an existing value will be overwritten."
                )
            new[norm_key] = _normalize_json_keys(value)
        return new
    if isinstance(obj, list):
        return [_normalize_json_keys(value) for value in obj]
    if isinstance(obj, tuple) and not (
        hasattr(obj, "_asdict") and callable(obj._asdict)
    ):
        # Plain tuples recurse; NamedTuples are left for _serialize_json, which
        # converts them to dicts (preserving field names) before normalization.
        return tuple(_normalize_json_keys(value) for value in obj)
    if isinstance(obj, collections.deque):
        return collections.deque(_normalize_json_keys(value) for value in obj)
    return obj


def _serialize_json_with_normalized_keys(obj: Any) -> Any:
    return _normalize_json_keys(_serialize_json(obj))


def _elide_surrogates(s: bytes) -> bytes:
    return _SURROGATE_RE.sub(b"", s)


def dumps_json(obj: Any) -> bytes:
    """Serialize an object to a JSON formatted string.

    Parameters
    ----------
    obj : Any
        The object to serialize.

    Returns:
    -------
    bytes
        The JSON formatted string, encoded as UTF-8 bytes.
    """
    try:
        return _orjson.dumps(
            obj,
            default=_serialize_json,
            option=_ORJSON_OPTIONS_FAST,
        )
    except TypeError as e:
        # Usually caused by UTF surrogate characters or non-str dict keys
        logger.debug(f"Orjson serialization failed: {repr(e)}. Falling back to json.")
        try:
            # Let orjson coerce non-str keys. Only stringify the ones it can't handle.
            return _orjson.dumps(
                obj,
                default=_serialize_json,
                option=_ORJSON_OPTIONS,
            )
        except TypeError:
            pass
        normalized_obj = _normalize_json_keys(obj)
        try:
            return _orjson.dumps(
                normalized_obj,
                default=_serialize_json_with_normalized_keys,
                option=_ORJSON_OPTIONS,
            )
        except TypeError as retry_e:
            logger.debug(
                "Orjson serialization with normalized keys failed: "
                f"{repr(retry_e)}. Falling back to json."
            )
        result = json.dumps(
            normalized_obj,
            default=_serialize_json_with_normalized_keys,
            ensure_ascii=True,
        ).encode("utf-8")
        try:
            result = _orjson.dumps(
                _orjson.loads(result.decode("utf-8", errors="surrogateescape"))
            )
        except _orjson.JSONDecodeError:
            result = _elide_surrogates(result)
        return result
