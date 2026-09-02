from __future__ import annotations

from collections.abc import Iterable
from io import BufferedReader
from typing import Union

from requests_toolbelt import (  # type: ignore[import-untyped]
    multipart as rqtb_multipart,
)

MultipartPart = tuple[
    str, tuple[None, Union[bytes, BufferedReader], str, dict[str, str]]
]


class MultipartPartsAndContext:
    parts: list[MultipartPart]
    context: str

    __slots__ = ("parts", "context")

    def __init__(self, parts: list[MultipartPart], context: str) -> None:
        self.parts = parts
        self.context = context


class SeekableMultipartEncoder:
    """A ``MultipartEncoder`` that supports ``tell``/``seek(0)`` for retries.

    ``requests_toolbelt``'s ``MultipartEncoder`` exposes neither, so when it's
    passed straight to ``requests`` as a streaming body, urllib3 can't rewind
    it before resending on a retryable failure (a dropped connection, or a
    502/503/504 response). The retry then resends a stale ``Content-Length``
    against an already-exhausted stream -- zero body bytes -- so the server
    hangs waiting for a body that will never arrive.

    Below the size threshold where the body is buffered to ``bytes`` outright
    this doesn't matter: urllib3 just resends the same immutable bytes, no
    seek required. This wrapper gives the same resend guarantee to bodies
    kept as a stream (to avoid loading huge attachments fully into memory),
    by rebuilding the encoder and rewinding every underlying file-like part
    back to its start on ``seek(0)``.
    """

    __slots__ = ("_parts", "_boundary", "_encoder", "_len", "_pos")

    def __init__(self, parts: list[MultipartPart], boundary: str) -> None:
        self._parts = parts
        self._boundary = boundary
        self._encoder = rqtb_multipart.MultipartEncoder(parts, boundary=boundary)
        self._len = self._encoder.len
        self._pos = 0

    @property
    def content_type(self) -> str:
        return self._encoder.content_type

    @property
    def len(self) -> int:
        return self._len

    def __len__(self) -> int:
        return self._len

    def read(self, size: int = -1) -> bytes:
        chunk = self._encoder.read(size)
        self._pos += len(chunk)
        return chunk

    def tell(self) -> int:
        return self._pos

    def seek(self, pos: int, whence: int = 0) -> int:
        if whence != 0 or pos != 0:
            raise OSError(
                "SeekableMultipartEncoder only supports seeking back to the start"
            )
        for _, (_, part_data, _, _) in self._parts:
            rewind = getattr(part_data, "seek", None)
            if rewind is not None:
                rewind(0)
        self._encoder = rqtb_multipart.MultipartEncoder(
            self._parts, boundary=self._boundary
        )
        self._pos = 0
        return self._pos

    def to_bytes(self) -> bytes:
        """Rewind and read the entire body, e.g. to dump it for debugging."""
        self.seek(0)
        return self.read()


def join_multipart_parts_and_context(
    parts_and_contexts: Iterable[MultipartPartsAndContext],
) -> MultipartPartsAndContext:
    acc_parts: list[MultipartPart] = []
    acc_context: list[str] = []
    for parts_and_context in parts_and_contexts:
        acc_parts.extend(parts_and_context.parts)
        acc_context.append(parts_and_context.context)
    return MultipartPartsAndContext(acc_parts, "; ".join(acc_context))
