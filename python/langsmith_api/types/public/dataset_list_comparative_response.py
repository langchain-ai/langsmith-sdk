# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Optional
from datetime import datetime

from ..._models import BaseModel
from ..datasets.simple_experiment_info import SimpleExperimentInfo

__all__ = ["DatasetListComparativeResponse"]


class DatasetListComparativeResponse(BaseModel):
    """Publicly-shared ComparativeExperiment schema."""

    id: str

    created_at: datetime

    experiments_info: List[SimpleExperimentInfo]

    modified_at: datetime

    description: Optional[str] = None

    extra: Optional[Dict[str, object]] = None

    feedback_stats: Optional[Dict[str, object]] = None

    name: Optional[str] = None
