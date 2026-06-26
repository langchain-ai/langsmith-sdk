# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Union, Optional
from datetime import datetime
from typing_extensions import Literal, TypeAlias

from .._models import BaseModel

__all__ = [
    "CustomChartsSection",
    "Chart",
    "ChartData",
    "ChartSeries",
    "ChartSeriesFilterDefinition",
    "ChartSeriesFilterDefinitionCustomChartFilterByTracingProject",
    "ChartSeriesFilterDefinitionCustomChartFilterByDataset",
    "ChartSeriesFilters",
    "ChartSeriesGroupBy",
    "ChartSeriesGroupByDefinition",
    "ChartSeriesGroupByDefinitionCustomChartGroupByPlain",
    "ChartSeriesGroupByDefinitionCustomChartGroupByComplex",
    "ChartSeriesMetricDefinition",
    "ChartSeriesMetricDefinitionCustomChartMetricCount",
    "ChartSeriesMetricDefinitionCustomChartMetricScalar",
    "ChartSeriesMetricDefinitionCustomChartMetricPercentile",
    "ChartSeriesMetricDefinitionCustomChartMetricPercentileParams",
    "ChartSeriesMetricDefinitionCustomChartMetricRatioOutput",
    "ChartSeriesMetricDefinitionCustomChartMetricRatioOutputDenominator",
    "ChartSeriesMetricDefinitionCustomChartMetricRatioOutputDenominatorCustomChartMetricCount",
    "ChartSeriesMetricDefinitionCustomChartMetricRatioOutputDenominatorCustomChartMetricScalar",
    "ChartSeriesMetricDefinitionCustomChartMetricRatioOutputDenominatorCustomChartMetricPercentile",
    "ChartSeriesMetricDefinitionCustomChartMetricRatioOutputDenominatorCustomChartMetricPercentileParams",
    "ChartSeriesMetricDefinitionCustomChartMetricRatioOutputNumerator",
    "ChartSeriesMetricDefinitionCustomChartMetricRatioOutputNumeratorCustomChartMetricCount",
    "ChartSeriesMetricDefinitionCustomChartMetricRatioOutputNumeratorCustomChartMetricScalar",
    "ChartSeriesMetricDefinitionCustomChartMetricRatioOutputNumeratorCustomChartMetricPercentile",
    "ChartSeriesMetricDefinitionCustomChartMetricRatioOutputNumeratorCustomChartMetricPercentileParams",
    "ChartCommonFilters",
    "SubSection",
    "SubSectionChart",
    "SubSectionChartData",
    "SubSectionChartSeries",
    "SubSectionChartSeriesFilterDefinition",
    "SubSectionChartSeriesFilterDefinitionCustomChartFilterByTracingProject",
    "SubSectionChartSeriesFilterDefinitionCustomChartFilterByDataset",
    "SubSectionChartSeriesFilters",
    "SubSectionChartSeriesGroupBy",
    "SubSectionChartSeriesGroupByDefinition",
    "SubSectionChartSeriesGroupByDefinitionCustomChartGroupByPlain",
    "SubSectionChartSeriesGroupByDefinitionCustomChartGroupByComplex",
    "SubSectionChartSeriesMetricDefinition",
    "SubSectionChartSeriesMetricDefinitionCustomChartMetricCount",
    "SubSectionChartSeriesMetricDefinitionCustomChartMetricScalar",
    "SubSectionChartSeriesMetricDefinitionCustomChartMetricPercentile",
    "SubSectionChartSeriesMetricDefinitionCustomChartMetricPercentileParams",
    "SubSectionChartSeriesMetricDefinitionCustomChartMetricRatioOutput",
    "SubSectionChartSeriesMetricDefinitionCustomChartMetricRatioOutputDenominator",
    "SubSectionChartSeriesMetricDefinitionCustomChartMetricRatioOutputDenominatorCustomChartMetricCount",
    "SubSectionChartSeriesMetricDefinitionCustomChartMetricRatioOutputDenominatorCustomChartMetricScalar",
    "SubSectionChartSeriesMetricDefinitionCustomChartMetricRatioOutputDenominatorCustomChartMetricPercentile",
    "SubSectionChartSeriesMetricDefinitionCustomChartMetricRatioOutputDenominatorCustomChartMetricPercentileParams",
    "SubSectionChartSeriesMetricDefinitionCustomChartMetricRatioOutputNumerator",
    "SubSectionChartSeriesMetricDefinitionCustomChartMetricRatioOutputNumeratorCustomChartMetricCount",
    "SubSectionChartSeriesMetricDefinitionCustomChartMetricRatioOutputNumeratorCustomChartMetricScalar",
    "SubSectionChartSeriesMetricDefinitionCustomChartMetricRatioOutputNumeratorCustomChartMetricPercentile",
    "SubSectionChartSeriesMetricDefinitionCustomChartMetricRatioOutputNumeratorCustomChartMetricPercentileParams",
    "SubSectionChartCommonFilters",
]


class ChartData(BaseModel):
    series_id: str

    timestamp: datetime

    value: Union[float, Dict[str, object], None] = None

    group: Optional[str] = None


class ChartSeriesFilterDefinitionCustomChartFilterByTracingProject(BaseModel):
    project_ids: List[str]

    source_type: Literal["tracing_project"]

    run_filter: Optional[str] = None

    trace_filter: Optional[str] = None

    tree_filter: Optional[str] = None


class ChartSeriesFilterDefinitionCustomChartFilterByDataset(BaseModel):
    dataset_ids: List[str]

    source_type: Literal["dataset"]


ChartSeriesFilterDefinition: TypeAlias = Union[
    ChartSeriesFilterDefinitionCustomChartFilterByTracingProject,
    ChartSeriesFilterDefinitionCustomChartFilterByDataset,
    None,
]


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


class ChartSeriesGroupByDefinitionCustomChartGroupByPlain(BaseModel):
    attribute: Literal["name", "run_type", "tag", "project", "status"]


class ChartSeriesGroupByDefinitionCustomChartGroupByComplex(BaseModel):
    attribute: Literal["metadata", "feedback_label"]

    path: str


ChartSeriesGroupByDefinition: TypeAlias = Union[
    ChartSeriesGroupByDefinitionCustomChartGroupByPlain, ChartSeriesGroupByDefinitionCustomChartGroupByComplex
]


class ChartSeriesMetricDefinitionCustomChartMetricCount(BaseModel):
    filter: Optional[str] = None

    type: Optional[Literal["count"]] = None


class ChartSeriesMetricDefinitionCustomChartMetricScalar(BaseModel):
    field: Literal[
        "latency_seconds",
        "first_token_seconds",
        "total_tokens",
        "prompt_tokens",
        "completion_tokens",
        "total_cost",
        "prompt_cost",
        "completion_cost",
    ]

    type: Literal["sum", "max", "min", "avg"]

    filter: Optional[str] = None


class ChartSeriesMetricDefinitionCustomChartMetricPercentileParams(BaseModel):
    p: float


class ChartSeriesMetricDefinitionCustomChartMetricPercentile(BaseModel):
    field: Literal[
        "latency_seconds",
        "first_token_seconds",
        "total_tokens",
        "prompt_tokens",
        "completion_tokens",
        "total_cost",
        "prompt_cost",
        "completion_cost",
    ]

    params: ChartSeriesMetricDefinitionCustomChartMetricPercentileParams

    type: Literal["percentile"]

    filter: Optional[str] = None


class ChartSeriesMetricDefinitionCustomChartMetricRatioOutputDenominatorCustomChartMetricCount(BaseModel):
    filter: Optional[str] = None

    type: Optional[Literal["count"]] = None


class ChartSeriesMetricDefinitionCustomChartMetricRatioOutputDenominatorCustomChartMetricScalar(BaseModel):
    field: Literal[
        "latency_seconds",
        "first_token_seconds",
        "total_tokens",
        "prompt_tokens",
        "completion_tokens",
        "total_cost",
        "prompt_cost",
        "completion_cost",
    ]

    type: Literal["sum", "max", "min", "avg"]

    filter: Optional[str] = None


class ChartSeriesMetricDefinitionCustomChartMetricRatioOutputDenominatorCustomChartMetricPercentileParams(BaseModel):
    p: float


class ChartSeriesMetricDefinitionCustomChartMetricRatioOutputDenominatorCustomChartMetricPercentile(BaseModel):
    field: Literal[
        "latency_seconds",
        "first_token_seconds",
        "total_tokens",
        "prompt_tokens",
        "completion_tokens",
        "total_cost",
        "prompt_cost",
        "completion_cost",
    ]

    params: ChartSeriesMetricDefinitionCustomChartMetricRatioOutputDenominatorCustomChartMetricPercentileParams

    type: Literal["percentile"]

    filter: Optional[str] = None


ChartSeriesMetricDefinitionCustomChartMetricRatioOutputDenominator: TypeAlias = Union[
    ChartSeriesMetricDefinitionCustomChartMetricRatioOutputDenominatorCustomChartMetricCount,
    ChartSeriesMetricDefinitionCustomChartMetricRatioOutputDenominatorCustomChartMetricScalar,
    ChartSeriesMetricDefinitionCustomChartMetricRatioOutputDenominatorCustomChartMetricPercentile,
]


class ChartSeriesMetricDefinitionCustomChartMetricRatioOutputNumeratorCustomChartMetricCount(BaseModel):
    filter: Optional[str] = None

    type: Optional[Literal["count"]] = None


class ChartSeriesMetricDefinitionCustomChartMetricRatioOutputNumeratorCustomChartMetricScalar(BaseModel):
    field: Literal[
        "latency_seconds",
        "first_token_seconds",
        "total_tokens",
        "prompt_tokens",
        "completion_tokens",
        "total_cost",
        "prompt_cost",
        "completion_cost",
    ]

    type: Literal["sum", "max", "min", "avg"]

    filter: Optional[str] = None


class ChartSeriesMetricDefinitionCustomChartMetricRatioOutputNumeratorCustomChartMetricPercentileParams(BaseModel):
    p: float


class ChartSeriesMetricDefinitionCustomChartMetricRatioOutputNumeratorCustomChartMetricPercentile(BaseModel):
    field: Literal[
        "latency_seconds",
        "first_token_seconds",
        "total_tokens",
        "prompt_tokens",
        "completion_tokens",
        "total_cost",
        "prompt_cost",
        "completion_cost",
    ]

    params: ChartSeriesMetricDefinitionCustomChartMetricRatioOutputNumeratorCustomChartMetricPercentileParams

    type: Literal["percentile"]

    filter: Optional[str] = None


ChartSeriesMetricDefinitionCustomChartMetricRatioOutputNumerator: TypeAlias = Union[
    ChartSeriesMetricDefinitionCustomChartMetricRatioOutputNumeratorCustomChartMetricCount,
    ChartSeriesMetricDefinitionCustomChartMetricRatioOutputNumeratorCustomChartMetricScalar,
    ChartSeriesMetricDefinitionCustomChartMetricRatioOutputNumeratorCustomChartMetricPercentile,
]


class ChartSeriesMetricDefinitionCustomChartMetricRatioOutput(BaseModel):
    denominator: ChartSeriesMetricDefinitionCustomChartMetricRatioOutputDenominator

    numerator: ChartSeriesMetricDefinitionCustomChartMetricRatioOutputNumerator

    type: Literal["ratio"]


ChartSeriesMetricDefinition: TypeAlias = Union[
    ChartSeriesMetricDefinitionCustomChartMetricCount,
    ChartSeriesMetricDefinitionCustomChartMetricScalar,
    ChartSeriesMetricDefinitionCustomChartMetricPercentile,
    ChartSeriesMetricDefinitionCustomChartMetricRatioOutput,
    None,
]


class ChartSeries(BaseModel):
    id: str

    name: str

    feedback_key: Optional[str] = None

    filter_definition: Optional[ChartSeriesFilterDefinition] = None

    filters: Optional[ChartSeriesFilters] = None

    group_by: Optional[ChartSeriesGroupBy] = None
    """Include additional information about where the group_by param was set."""

    group_by_definitions: Optional[List[ChartSeriesGroupByDefinition]] = None

    metric: Optional[
        Literal[
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
    ] = None
    """Metrics you can chart.

    Feedback metrics are not available for organization-scoped charts.
    """

    metric_definition: Optional[ChartSeriesMetricDefinition] = None

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

    chart_type: Literal["line", "bar", "table", "kpi", "top-k", "pie"]
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


class SubSectionChartSeriesFilterDefinitionCustomChartFilterByTracingProject(BaseModel):
    project_ids: List[str]

    source_type: Literal["tracing_project"]

    run_filter: Optional[str] = None

    trace_filter: Optional[str] = None

    tree_filter: Optional[str] = None


class SubSectionChartSeriesFilterDefinitionCustomChartFilterByDataset(BaseModel):
    dataset_ids: List[str]

    source_type: Literal["dataset"]


SubSectionChartSeriesFilterDefinition: TypeAlias = Union[
    SubSectionChartSeriesFilterDefinitionCustomChartFilterByTracingProject,
    SubSectionChartSeriesFilterDefinitionCustomChartFilterByDataset,
    None,
]


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


class SubSectionChartSeriesGroupByDefinitionCustomChartGroupByPlain(BaseModel):
    attribute: Literal["name", "run_type", "tag", "project", "status"]


class SubSectionChartSeriesGroupByDefinitionCustomChartGroupByComplex(BaseModel):
    attribute: Literal["metadata", "feedback_label"]

    path: str


SubSectionChartSeriesGroupByDefinition: TypeAlias = Union[
    SubSectionChartSeriesGroupByDefinitionCustomChartGroupByPlain,
    SubSectionChartSeriesGroupByDefinitionCustomChartGroupByComplex,
]


class SubSectionChartSeriesMetricDefinitionCustomChartMetricCount(BaseModel):
    filter: Optional[str] = None

    type: Optional[Literal["count"]] = None


class SubSectionChartSeriesMetricDefinitionCustomChartMetricScalar(BaseModel):
    field: Literal[
        "latency_seconds",
        "first_token_seconds",
        "total_tokens",
        "prompt_tokens",
        "completion_tokens",
        "total_cost",
        "prompt_cost",
        "completion_cost",
    ]

    type: Literal["sum", "max", "min", "avg"]

    filter: Optional[str] = None


class SubSectionChartSeriesMetricDefinitionCustomChartMetricPercentileParams(BaseModel):
    p: float


class SubSectionChartSeriesMetricDefinitionCustomChartMetricPercentile(BaseModel):
    field: Literal[
        "latency_seconds",
        "first_token_seconds",
        "total_tokens",
        "prompt_tokens",
        "completion_tokens",
        "total_cost",
        "prompt_cost",
        "completion_cost",
    ]

    params: SubSectionChartSeriesMetricDefinitionCustomChartMetricPercentileParams

    type: Literal["percentile"]

    filter: Optional[str] = None


class SubSectionChartSeriesMetricDefinitionCustomChartMetricRatioOutputDenominatorCustomChartMetricCount(BaseModel):
    filter: Optional[str] = None

    type: Optional[Literal["count"]] = None


class SubSectionChartSeriesMetricDefinitionCustomChartMetricRatioOutputDenominatorCustomChartMetricScalar(BaseModel):
    field: Literal[
        "latency_seconds",
        "first_token_seconds",
        "total_tokens",
        "prompt_tokens",
        "completion_tokens",
        "total_cost",
        "prompt_cost",
        "completion_cost",
    ]

    type: Literal["sum", "max", "min", "avg"]

    filter: Optional[str] = None


class SubSectionChartSeriesMetricDefinitionCustomChartMetricRatioOutputDenominatorCustomChartMetricPercentileParams(
    BaseModel
):
    p: float


class SubSectionChartSeriesMetricDefinitionCustomChartMetricRatioOutputDenominatorCustomChartMetricPercentile(
    BaseModel
):
    field: Literal[
        "latency_seconds",
        "first_token_seconds",
        "total_tokens",
        "prompt_tokens",
        "completion_tokens",
        "total_cost",
        "prompt_cost",
        "completion_cost",
    ]

    params: (
        SubSectionChartSeriesMetricDefinitionCustomChartMetricRatioOutputDenominatorCustomChartMetricPercentileParams
    )

    type: Literal["percentile"]

    filter: Optional[str] = None


SubSectionChartSeriesMetricDefinitionCustomChartMetricRatioOutputDenominator: TypeAlias = Union[
    SubSectionChartSeriesMetricDefinitionCustomChartMetricRatioOutputDenominatorCustomChartMetricCount,
    SubSectionChartSeriesMetricDefinitionCustomChartMetricRatioOutputDenominatorCustomChartMetricScalar,
    SubSectionChartSeriesMetricDefinitionCustomChartMetricRatioOutputDenominatorCustomChartMetricPercentile,
]


class SubSectionChartSeriesMetricDefinitionCustomChartMetricRatioOutputNumeratorCustomChartMetricCount(BaseModel):
    filter: Optional[str] = None

    type: Optional[Literal["count"]] = None


class SubSectionChartSeriesMetricDefinitionCustomChartMetricRatioOutputNumeratorCustomChartMetricScalar(BaseModel):
    field: Literal[
        "latency_seconds",
        "first_token_seconds",
        "total_tokens",
        "prompt_tokens",
        "completion_tokens",
        "total_cost",
        "prompt_cost",
        "completion_cost",
    ]

    type: Literal["sum", "max", "min", "avg"]

    filter: Optional[str] = None


class SubSectionChartSeriesMetricDefinitionCustomChartMetricRatioOutputNumeratorCustomChartMetricPercentileParams(
    BaseModel
):
    p: float


class SubSectionChartSeriesMetricDefinitionCustomChartMetricRatioOutputNumeratorCustomChartMetricPercentile(BaseModel):
    field: Literal[
        "latency_seconds",
        "first_token_seconds",
        "total_tokens",
        "prompt_tokens",
        "completion_tokens",
        "total_cost",
        "prompt_cost",
        "completion_cost",
    ]

    params: SubSectionChartSeriesMetricDefinitionCustomChartMetricRatioOutputNumeratorCustomChartMetricPercentileParams

    type: Literal["percentile"]

    filter: Optional[str] = None


SubSectionChartSeriesMetricDefinitionCustomChartMetricRatioOutputNumerator: TypeAlias = Union[
    SubSectionChartSeriesMetricDefinitionCustomChartMetricRatioOutputNumeratorCustomChartMetricCount,
    SubSectionChartSeriesMetricDefinitionCustomChartMetricRatioOutputNumeratorCustomChartMetricScalar,
    SubSectionChartSeriesMetricDefinitionCustomChartMetricRatioOutputNumeratorCustomChartMetricPercentile,
]


class SubSectionChartSeriesMetricDefinitionCustomChartMetricRatioOutput(BaseModel):
    denominator: SubSectionChartSeriesMetricDefinitionCustomChartMetricRatioOutputDenominator

    numerator: SubSectionChartSeriesMetricDefinitionCustomChartMetricRatioOutputNumerator

    type: Literal["ratio"]


SubSectionChartSeriesMetricDefinition: TypeAlias = Union[
    SubSectionChartSeriesMetricDefinitionCustomChartMetricCount,
    SubSectionChartSeriesMetricDefinitionCustomChartMetricScalar,
    SubSectionChartSeriesMetricDefinitionCustomChartMetricPercentile,
    SubSectionChartSeriesMetricDefinitionCustomChartMetricRatioOutput,
    None,
]


class SubSectionChartSeries(BaseModel):
    id: str

    name: str

    feedback_key: Optional[str] = None

    filter_definition: Optional[SubSectionChartSeriesFilterDefinition] = None

    filters: Optional[SubSectionChartSeriesFilters] = None

    group_by: Optional[SubSectionChartSeriesGroupBy] = None
    """Include additional information about where the group_by param was set."""

    group_by_definitions: Optional[List[SubSectionChartSeriesGroupByDefinition]] = None

    metric: Optional[
        Literal[
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
    ] = None
    """Metrics you can chart.

    Feedback metrics are not available for organization-scoped charts.
    """

    metric_definition: Optional[SubSectionChartSeriesMetricDefinition] = None

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

    chart_type: Literal["line", "bar", "table", "kpi", "top-k", "pie"]
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
