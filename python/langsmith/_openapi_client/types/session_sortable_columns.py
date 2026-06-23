# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing_extensions import Literal, TypeAlias

__all__ = ["SessionSortableColumns"]

SessionSortableColumns: TypeAlias = Literal[
    "name", "start_time", "last_run_start_time", "latency_p50", "latency_p99", "error_rate", "feedback", "runs_count"
]
