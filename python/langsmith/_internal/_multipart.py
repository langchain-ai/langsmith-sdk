from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Tuple

MultipartPart = Tuple[str, Tuple[None, bytes, str, Dict[str, str]]]


@dataclass
class MultipartPartsAndContext:
    parts: list[MultipartPart]
    context: str


def join_multipart_parts_and_context(
    parts_and_contexts: Iterable[MultipartPartsAndContext],
) -> MultipartPartsAndContext:
    acc_parts: list[MultipartPart] = []
    acc_context: list[str] = []
    for parts_and_context in parts_and_contexts:
        acc_parts.extend(parts_and_context.parts)
        acc_context.append(parts_and_context.context)
    return MultipartPartsAndContext(acc_parts, "; ".join(acc_context))
