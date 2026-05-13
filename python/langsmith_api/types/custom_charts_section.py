# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Union, Optional
from datetime import datetime
from typing_extensions import Literal

from .._models import BaseModel

__all__ = [
    "CustomChartsSection",
    "Chart",
    "ChartData",
    "ChartSeries",
    "ChartSeriesFilters",
    "ChartSeriesGroupBy",
    "ChartCommonFilters",
    "SubSection",
    "SubSectionChart",
    "SubSectionChartData",
    "SubSectionChartSeries",
    "SubSectionChartSeriesFilters",
    "SubSectionChartSeriesGroupBy",
    "SubSectionChartCommonFilters",
]


class ChartData(BaseModel):
    series_id: str

    timestamp: datetime

    value: Union[float, Dict[str, object], None] = None

    group: Optional[str] = None


class ChartSeriesFilters(BaseModel):
    filter: Optional[str] = None

    session: Optional[List[str]] = None

    trace_filter: Optional[str] = None

    tree_filter: Optional[str] = None


class ChartSeriesGroupBy(BaseModel):
    """Include additional information about where the group_by param was set."""

    attribute: Literal["name", "run_type", "tag", "metadata"]

    max_groups: Optional[int] = None

    path: Optional[str] = None

    set_by: Optional[Literal["section", "series"]] = None


class ChartSeries(BaseModel):
    id: str

    metric: Literal[
        "run_count",
        "latency_p50",
        "latency_p99",
        "latency_avg",
        "first_token_p50",
        "first_token_p99",
        "total_tokens",
        "prompt_tokens",
        "completion_tokens",
        "median_tokens",
        "completion_tokens_p50",
        "prompt_tokens_p50",
        "tokens_p99",
        "completion_tokens_p99",
        "prompt_tokens_p99",
        "feedback",
        "feedback_score_avg",
        "feedback_values",
        "total_cost",
        "prompt_cost",
        "completion_cost",
        "error_rate",
        "streaming_rate",
        "cost_p50",
        "cost_p99",
    ]
    """Metrics you can chart.

    Feedback metrics are not available for organization-scoped charts.
    """

    name: str

    feedback_key: Optional[str] = None

    filters: Optional[ChartSeriesFilters] = None

    group_by: Optional[ChartSeriesGroupBy] = None
    """Include additional information about where the group_by param was set."""

    project_metric: Optional[
        Literal[
            "memory_usage",
            "cpu_usage",
            "disk_usage",
            "restart_count",
            "replica_count",
            "worker_count",
            "lg_run_count",
            "responses_per_second",
            "error_responses_per_second",
            "p95_latency",
        ]
    ] = None
    """LGP Metrics you can chart."""

    workspace_id: Optional[str] = None


class ChartCommonFilters(BaseModel):
    filter: Optional[str] = None

    session: Optional[List[str]] = None

    trace_filter: Optional[str] = None

    tree_filter: Optional[str] = None


class Chart(BaseModel):
    id: str

    chart_type: Literal["line", "bar"]
    """Enum for custom chart types."""

    data: List[ChartData]

    index: int

    series: List[ChartSeries]

    title: str

    common_filters: Optional[ChartCommonFilters] = None

    description: Optional[str] = None

    metadata: Optional[Dict[str, object]] = None


class SubSectionChartData(BaseModel):
    series_id: str

    timestamp: datetime

    value: Union[float, Dict[str, object], None] = None

    group: Optional[str] = None


class SubSectionChartSeriesFilters(BaseModel):
    filter: Optional[str] = None

    session: Optional[List[str]] = None

    trace_filter: Optional[str] = None

    tree_filter: Optional[str] = None


class SubSectionChartSeriesGroupBy(BaseModel):
    """Include additional information about where the group_by param was set."""

    attribute: Literal["name", "run_type", "tag", "metadata"]

    max_groups: Optional[int] = None

    path: Optional[str] = None

    set_by: Optional[Literal["section", "series"]] = None


class SubSectionChartSeries(BaseModel):
    id: str

    metric: Literal[
        "run_count",
        "latency_p50",
        "latency_p99",
        "latency_avg",
        "first_token_p50",
        "first_token_p99",
        "total_tokens",
        "prompt_tokens",
        "completion_tokens",
        "median_tokens",
        "completion_tokens_p50",
        "prompt_tokens_p50",
        "tokens_p99",
        "completion_tokens_p99",
        "prompt_tokens_p99",
        "feedback",
        "feedback_score_avg",
        "feedback_values",
        "total_cost",
        "prompt_cost",
        "completion_cost",
        "error_rate",
        "streaming_rate",
        "cost_p50",
        "cost_p99",
    ]
    """Metrics you can chart.

    Feedback metrics are not available for organization-scoped charts.
    """

    name: str

    feedback_key: Optional[str] = None

    filters: Optional[SubSectionChartSeriesFilters] = None

    group_by: Optional[SubSectionChartSeriesGroupBy] = None
    """Include additional information about where the group_by param was set."""

    project_metric: Optional[
        Literal[
            "memory_usage",
            "cpu_usage",
            "disk_usage",
            "restart_count",
            "replica_count",
            "worker_count",
            "lg_run_count",
            "responses_per_second",
            "error_responses_per_second",
            "p95_latency",
        ]
    ] = None
    """LGP Metrics you can chart."""

    workspace_id: Optional[str] = None


class SubSectionChartCommonFilters(BaseModel):
    filter: Optional[str] = None

    session: Optional[List[str]] = None

    trace_filter: Optional[str] = None

    tree_filter: Optional[str] = None


class SubSectionChart(BaseModel):
    id: str

    chart_type: Literal["line", "bar"]
    """Enum for custom chart types."""

    data: List[SubSectionChartData]

    index: int

    series: List[SubSectionChartSeries]

    title: str

    common_filters: Optional[SubSectionChartCommonFilters] = None

    description: Optional[str] = None

    metadata: Optional[Dict[str, object]] = None


class SubSection(BaseModel):
    id: str

    charts: List[SubSectionChart]

    index: int

    title: str

    description: Optional[str] = None


class CustomChartsSection(BaseModel):
    id: str

    charts: List[Chart]

    title: str

    description: Optional[str] = None

    index: Optional[int] = None

    session_id: Optional[str] = None

    sub_sections: Optional[List[SubSection]] = None
