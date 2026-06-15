# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Iterable
from typing_extensions import Literal, TypedDict

from .._types import SequenceNotStr

__all__ = ["RunParam"]


class RunParam(TypedDict, total=False):
    id: str

    dotted_order: str

    end_time: str

    error: str

    events: Iterable[Dict[str, object]]

    extra: Dict[str, object]

    input_attachments: Dict[str, object]

    inputs: Dict[str, object]

    name: str

    output_attachments: Dict[str, object]

    outputs: Dict[str, object]

    parent_run_id: str

    reference_example_id: str

    run_type: Literal["tool", "chain", "llm", "retriever", "embedding", "prompt", "parser"]

    serialized: Dict[str, object]

    session_id: str

    session_name: str

    start_time: str

    status: str

    tags: SequenceNotStr[str]

    trace_id: str
