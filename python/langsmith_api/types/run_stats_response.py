# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Union, Optional
from datetime import datetime
from typing_extensions import TypeAlias

from .._models import BaseModel

__all__ = ["RunStatsResponse", "RunStats", "UnionMember1UnionMember1Item"]


class RunStats(BaseModel):
    completion_cost: Optional[str] = None

    completion_cost_details: Optional[Dict[str, object]] = None

    completion_token_details: Optional[Dict[str, object]] = None

    completion_tokens: Optional[int] = None

    completion_tokens_p50: Optional[int] = None

    completion_tokens_p99: Optional[int] = None

    cost_p50: Optional[str] = None

    cost_p99: Optional[str] = None

    error_rate: Optional[float] = None

    feedback_stats: Optional[Dict[str, object]] = None

    first_token_p50: Optional[float] = None

    first_token_p99: Optional[float] = None

    last_run_start_time: Optional[datetime] = None

    latency_p50: Optional[float] = None

    latency_p99: Optional[float] = None

    median_tokens: Optional[int] = None

    prompt_cost: Optional[str] = None

    prompt_cost_details: Optional[Dict[str, object]] = None

    prompt_token_details: Optional[Dict[str, object]] = None

    prompt_tokens: Optional[int] = None

    prompt_tokens_p50: Optional[int] = None

    prompt_tokens_p99: Optional[int] = None

    run_count: Optional[int] = None

    run_facets: Optional[List[Dict[str, object]]] = None

    streaming_rate: Optional[float] = None

    tokens_p99: Optional[int] = None

    total_cost: Optional[str] = None

    total_tokens: Optional[int] = None


class UnionMember1UnionMember1Item(BaseModel):
    completion_cost: Optional[str] = None

    completion_cost_details: Optional[Dict[str, object]] = None

    completion_token_details: Optional[Dict[str, object]] = None

    completion_tokens: Optional[int] = None

    completion_tokens_p50: Optional[int] = None

    completion_tokens_p99: Optional[int] = None

    cost_p50: Optional[str] = None

    cost_p99: Optional[str] = None

    error_rate: Optional[float] = None

    feedback_stats: Optional[Dict[str, object]] = None

    first_token_p50: Optional[float] = None

    first_token_p99: Optional[float] = None

    last_run_start_time: Optional[datetime] = None

    latency_p50: Optional[float] = None

    latency_p99: Optional[float] = None

    median_tokens: Optional[int] = None

    prompt_cost: Optional[str] = None

    prompt_cost_details: Optional[Dict[str, object]] = None

    prompt_token_details: Optional[Dict[str, object]] = None

    prompt_tokens: Optional[int] = None

    prompt_tokens_p50: Optional[int] = None

    prompt_tokens_p99: Optional[int] = None

    run_count: Optional[int] = None

    run_facets: Optional[List[Dict[str, object]]] = None

    streaming_rate: Optional[float] = None

    tokens_p99: Optional[int] = None

    total_cost: Optional[str] = None

    total_tokens: Optional[int] = None


RunStatsResponse: TypeAlias = Union[RunStats, Dict[str, UnionMember1UnionMember1Item]]
