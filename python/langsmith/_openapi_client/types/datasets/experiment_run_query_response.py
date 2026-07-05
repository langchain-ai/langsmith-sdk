# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional
from datetime import datetime

from ..run import Run
from ..._models import BaseModel

__all__ = ["ExperimentRunQueryResponse"]


class ExperimentRunQueryResponse(BaseModel):
    id: Optional[str] = None
    """`id` is the dataset example UUID."""

    attachment_urls: Optional[object] = None
    """`attachment_urls` maps each attachment name to a pre-signed download URL."""

    created_at: Optional[datetime] = None
    """`created_at` is when the example was created (RFC3339 date-time)."""

    dataset_id: Optional[str] = None
    """`dataset_id` is the parent dataset UUID."""

    inputs: Optional[object] = None
    """`inputs` is the example input payload (arbitrary JSON object)."""

    metadata: Optional[object] = None
    """`metadata` is arbitrary user-defined JSON metadata on the example."""

    modified_at: Optional[datetime] = None
    """`modified_at` is when the example was last modified (RFC3339 date-time)."""

    name: Optional[str] = None
    """`name` is the example's optional name."""

    outputs: Optional[object] = None
    """`outputs` is the example reference-output payload (arbitrary JSON object)."""

    runs: Optional[List[Run]] = None
    """`runs` is the list of experiment runs produced for this example."""

    source_run_id: Optional[str] = None
    """`source_run_id` is the run UUID the example was created from, if any."""
