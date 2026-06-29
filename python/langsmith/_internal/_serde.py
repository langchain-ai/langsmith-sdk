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
_JSON_KEY_TYPES = (str, int, float, bool, type(None))


def _simple_default(obj):
    try:
        # Only need to handle types that orjson doesn't serialize by default
        # https://github.com/ijl/orjson#serialize
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
    except BaseException as e:
        logger.debug(f"Failed to serialize {type(obj)} to JSON: {e}")
    return str(obj)


_serialization_methods: list[tuple[str, dict[str, Any]]] = [
    (
        "model_dump",
        {"exclude_none": True, "mode": "json"},
    ),  # Pydantic V2 with non-serializable fields
    ("model_dump", {"exclude_none": True}),  # Pydantic V2 without json mode
    ("dict", {}),  # Pydantic V1 with non-serializable field
    ("to_dict", {}),  # dataclasses-json
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

        for attr, kwargs in _serialization_methods:
            if (
                hasattr(obj, attr)
                and callable(getattr(obj, attr))
                and not isinstance(obj, type)
            ):
                try:
                    method = getattr(obj, attr)
                    response = method(**kwargs)
                    if not isinstance(response, dict):
                        return str(response)
                    return response
                except Exception as e:
                    logger.debug(
                        f"Failed to use {attr} to serialize {type(obj)} to"
                        f" JSON: {repr(e)}"
                    )
                    pass
        return _simple_default(obj)
    except BaseException as e:
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
            if norm_key in new and norm_key != key:
                logger.debug(
                    "Dict key collision during JSON key normalization: "
                    f"{key!r} maps to {norm_key!r}, which already exists; "
                    f"the previous value will be overwritten."
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
    pattern = re.compile(rb"\\ud[89a-f][0-9a-f]{2}", re.IGNORECASE)
    result = pattern.sub(b"", s)
    return result


def dumps_json(obj: Any) -> bytes:
    """Serialize an object to a JSON formatted string.

    Parameters
    ----------
    obj : Any
        The object to serialize.
    default : Callable[[Any], Any] or None, default=None
        The default function to use for serialization.

    Returns:
    -------
    str
        The JSON formatted string.
    """
    try:
        return _orjson.dumps(
            obj,
            default=_serialize_json,
            option=_ORJSON_OPTIONS,
        )
    except TypeError as e:
        # Usually caused by UTF surrogate characters
        logger.debug(f"Orjson serialization failed: {repr(e)}. Falling back to json.")
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
