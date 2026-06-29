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


def _stringify_json_key(key: Any) -> Any:
    if isinstance(key, _JSON_KEY_TYPES):
        return key
    return str(_simple_default(key))


def _normalize_json_keys(obj: Any, seen: set[int] | None = None) -> Any:
    if seen is None:
        seen = set()

    if isinstance(obj, dict):
        obj_id = id(obj)
        if obj_id in seen:
            return obj
        seen.add(obj_id)
        try:
            return {
                _stringify_json_key(key): _normalize_json_keys(value, seen)
                for key, value in obj.items()
            }
        finally:
            seen.remove(obj_id)

    if isinstance(obj, list):
        obj_id = id(obj)
        if obj_id in seen:
            return obj
        seen.add(obj_id)
        try:
            return [_normalize_json_keys(value, seen) for value in obj]
        finally:
            seen.remove(obj_id)

    if isinstance(obj, tuple):
        if hasattr(obj, "_asdict") and callable(obj._asdict):
            return obj
        obj_id = id(obj)
        if obj_id in seen:
            return obj
        seen.add(obj_id)
        try:
            return tuple(_normalize_json_keys(value, seen) for value in obj)
        finally:
            seen.remove(obj_id)

    if isinstance(obj, collections.deque):
        obj_id = id(obj)
        if obj_id in seen:
            return obj
        seen.add(obj_id)
        try:
            return collections.deque(_normalize_json_keys(value, seen) for value in obj)
        finally:
            seen.remove(obj_id)

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
