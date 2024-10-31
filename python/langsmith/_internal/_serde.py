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
from typing import (
    Any,
)

import orjson

try:
    from zoneinfo import ZoneInfo  # type: ignore[import-not-found]
except ImportError:

    class ZoneInfo:  # type: ignore[no-redef]
        """Introduced in python 3.9."""


logger = logging.getLogger(__name__)


def _simple_default(obj):
    try:
        # Only need to handle types that orjson doesn't serialize by default
        # https://github.com/ijl/orjson#serialize
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        if isinstance(obj, uuid.UUID):
            return str(obj)
        if hasattr(obj, "model_dump") and callable(obj.model_dump):
            return obj.model_dump()
        elif hasattr(obj, "dict") and callable(obj.dict):
            return obj.dict()
        elif hasattr(obj, "_asdict") and callable(obj._asdict):
            return obj._asdict()
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


def _serialize_json(obj: Any) -> Any:
    try:
        if isinstance(obj, (set, tuple)):
            if hasattr(obj, "_asdict") and callable(obj._asdict):
                # NamedTuple
                return obj._asdict()
            return list(obj)

        serialization_methods = [
            ("model_dump", True),  # Pydantic V2 with non-serializable fields
            ("dict", False),  # Pydantic V1 with non-serializable field
            ("to_dict", False),  # dataclasses-json
        ]
        for attr, exclude_none in serialization_methods:
            if (
                hasattr(obj, attr)
                and callable(getattr(obj, attr))
                and not isinstance(obj, type)
            ):
                try:
                    method = getattr(obj, attr)
                    response = (
                        method(exclude_none=exclude_none) if exclude_none else method()
                    )
                    if not isinstance(response, dict):
                        return str(response)
                    return response
                except Exception as e:
                    logger.error(
                        f"Failed to use {attr} to serialize {type(obj)} to"
                        f" JSON: {repr(e)}"
                    )
                    pass
        return _simple_default(obj)
    except BaseException as e:
        logger.debug(f"Failed to serialize {type(obj)} to JSON: {e}")
        return str(obj)


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
        return orjson.dumps(
            obj,
            default=_serialize_json,
            option=orjson.OPT_SERIALIZE_NUMPY
            | orjson.OPT_SERIALIZE_DATACLASS
            | orjson.OPT_SERIALIZE_UUID
            | orjson.OPT_NON_STR_KEYS,
        )
    except TypeError as e:
        # Usually caused by UTF surrogate characters
        logger.debug(f"Orjson serialization failed: {repr(e)}. Falling back to json.")
        result = json.dumps(
            obj,
            default=_simple_default,
            ensure_ascii=True,
        ).encode("utf-8")
        try:
            result = orjson.dumps(
                orjson.loads(result.decode("utf-8", errors="surrogateescape"))
            )
        except orjson.JSONDecodeError:
            result = _elide_surrogates(result)
        return result
