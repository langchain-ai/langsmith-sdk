# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Optional
from datetime import datetime

from ..._models import BaseModel
from ..data_type import DataType
from ..dataset_transformation import DatasetTransformation

__all__ = ["DatasetListResponse"]


class DatasetListResponse(BaseModel):
    """Public schema for datasets.

    Doesn't currently include session counts/stats
    since public test project sharing is not yet shipped
    """

    id: str

    example_count: int

    name: str

    created_at: Optional[datetime] = None

    data_type: Optional[DataType] = None
    """Enum for dataset data types."""

    description: Optional[str] = None

    externally_managed: Optional[bool] = None

    inputs_schema_definition: Optional[Dict[str, object]] = None

    outputs_schema_definition: Optional[Dict[str, object]] = None

    transformations: Optional[List[DatasetTransformation]] = None
