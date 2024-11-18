"""Stubs for orjson operations, compatible with PyPy via a json fallback."""

try:
    from orjson import (
        OPT_NON_STR_KEYS,
        OPT_SERIALIZE_DATACLASS,
        OPT_SERIALIZE_NUMPY,
        OPT_SERIALIZE_UUID,
        Fragment,
        JSONDecodeError,
        dumps,
        loads,
    )

except ImportError:
    import json
    from typing import Any, Callable, Optional

    OPT_NON_STR_KEYS = 1
    OPT_SERIALIZE_DATACLASS = 2
    OPT_SERIALIZE_NUMPY = 4
    OPT_SERIALIZE_UUID = 8

    class Fragment:
        def __init__(self, payloadb: bytes):
            self.payloadb = payloadb

    from json import JSONDecodeError

    def dumps(
        obj: Any,
        *,
        default: Optional[Callable[[Any], Any]] = None,
        option: int = 0,
    ) -> bytes:
        class CustomEncoder(json.JSONEncoder):
            def encode(o: Any) -> str:
                if isinstance(o, Fragment):
                    return o.payloadb.decode("utf-8")
                return super().encode(o)

            def default(o: Any) -> Any:
                if default is not None:
                    return default(o)
                # TODO: handle OPT_ keys
                return super().default(o)

        return json.dumps(obj, cls=CustomEncoder).encode("utf-8")

    def loads(payload: bytes) -> Any:
        return json.loads(payload)


__all__ = [
    "loads",
    "dumps",
    "Fragment",
    "JSONDecodeError",
    "OPT_SERIALIZE_NUMPY",
    "OPT_SERIALIZE_DATACLASS",
    "OPT_SERIALIZE_UUID",
    "OPT_NON_STR_KEYS",
]
