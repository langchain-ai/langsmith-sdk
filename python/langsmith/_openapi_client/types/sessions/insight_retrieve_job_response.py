# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Optional
from datetime import datetime

from ..._models import BaseModel

__all__ = ["InsightRetrieveJobResponse", "Cluster", "Report", "ReportHighlightedTrace"]


class Cluster(BaseModel):
    """A single cluster of runs."""

    id: str

    description: str

    level: int

    name: str

    num_runs: int

    stats: Optional[Dict[str, object]] = None

    parent_id: Optional[str] = None

    parent_name: Optional[str] = None


class ReportHighlightedTrace(BaseModel):
    """A trace highlighted in an insights report summary. Up to 10 per insights job."""

    highlight_reason: str

    rank: int

    run_id: str

    cluster_id: Optional[str] = None

    cluster_name: Optional[str] = None

    summary: Optional[str] = None


class Report(BaseModel):
    """
    High level summary of an insights job that pulls out patterns and specific traces.
    """

    created_at: Optional[datetime] = None

    highlighted_traces: Optional[List[ReportHighlightedTrace]] = None

    key_points: Optional[List[str]] = None

    title: Optional[str] = None


class InsightRetrieveJobResponse(BaseModel):
    """Response to get a specific cluster job for a session."""

    id: str

    clusters: List[Cluster]

    created_at: datetime

    name: str

    status: str

    config_id: Optional[str] = None

    end_time: Optional[datetime] = None

    error: Optional[str] = None

    metadata: Optional[Dict[str, object]] = None

    report: Optional[Report] = None
    """
    High level summary of an insights job that pulls out patterns and specific
    traces.
    """

    shape: Optional[Dict[str, int]] = None

    start_time: Optional[datetime] = None
