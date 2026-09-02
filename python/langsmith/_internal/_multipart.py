from __future__ import annotations

from collections.abc import Iterable, Sequence
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


def join_multipart_parts_and_context(
    parts_and_contexts: Iterable[MultipartPartsAndContext],
) -> MultipartPartsAndContext:
    acc_parts: list[MultipartPart] = []
    acc_context: list[str] = []
    for parts_and_context in parts_and_contexts:
        acc_parts.extend(parts_and_context.parts)
        acc_context.append(parts_and_context.context)
    return MultipartPartsAndContext(acc_parts, "; ".join(acc_context))


def _rewind_parts(parts: Iterable[MultipartPart]) -> None:
    """Return every file-backed part to byte 0 so the parts can be re-encoded."""
    for _name, (_filename, data, _content_type, _headers) in parts:
        if hasattr(data, "seek"):
            data.seek(0)


class RewindableMultipartBody:
    """A replayable request body for ``MultipartEncoder``-encoded parts.

    ``MultipartEncoder`` is single-use: it reads every file-backed part to EOF
    and exposes neither ``seek`` nor ``tell``, so no retry layer can replay it.
    urllib3 retries the statuses in ``_default_retry_config``'s
    ``status_forcelist`` beneath our own retry loop, and it resends the *same*
    body object -- an exhausted encoder, i.e. an empty body under the
    already-declared ``Content-Length``. The server accepts that as a complete
    run, so the attachment is dropped with an HTTP 200.

    ``tell``/``seek`` are what urllib3's ``rewind_body`` looks for: a
    ``seek(0)`` rewinds the parts and builds a fresh encoder, so every resend
    carries the full payload. ``__len__`` keeps ``requests``' ``super_len``
    reporting the total size, so ``Content-Length`` stays correct.
    """

    __slots__ = ("_boundary", "_encoder", "_parts", "_pos", "_total")

    def __init__(self, parts: Sequence[MultipartPart], boundary: str) -> None:
        self._parts = parts
        self._boundary = boundary
        self._encoder = self._encode()
        self._total = self._encoder.len
        self._pos = 0

    def _encode(self) -> rqtb_multipart.MultipartEncoder:
        _rewind_parts(self._parts)
        return rqtb_multipart.MultipartEncoder(self._parts, boundary=self._boundary)

    @property
    def content_type(self) -> str:
        return self._encoder.content_type

    @property
    def parts(self) -> Sequence[MultipartPart]:
        """The parts this body encodes, in order."""
        return self._parts

    def to_bytes(self) -> bytes:
        """Materialize the whole body; the result is inherently replayable.

        Rewinds first, so this is correct even after the body has been read.
        """
        self.seek(0)
        body = self._encoder.to_string()
        self._pos = self._total
        return body

    def __len__(self) -> int:
        return self._total

    def read(self, amt: int = -1) -> bytes:
        chunk = self._encoder.read(amt)
        self._pos += len(chunk)
        return chunk

    def tell(self) -> int:
        return self._pos

    def seek(self, pos: int, whence: int = 0) -> int:
        if (pos, whence) != (0, 0):
            raise OSError(
                f"{type(self).__name__} only rewinds to the start, "
                f"got seek({pos}, {whence})"
            )
        self._encoder = self._encode()
        self._pos = 0
        return 0
