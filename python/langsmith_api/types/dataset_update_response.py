# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Optional
from datetime import datetime

from .._models import BaseModel
from .data_type import DataType
from .dataset_transformation import DatasetTransformation

__all__ = ["DatasetUpdateResponse"]


class DatasetUpdateResponse(BaseModel):
    id: str

    name: str

    tenant_id: str

    created_at: Optional[datetime] = None

    data_type: Optional[DataType] = None
    """Enum for dataset data types."""

    description: Optional[str] = None

    externally_managed: Optional[bool] = None

    inputs_schema_definition: Optional[Dict[str, object]] = None

    outputs_schema_definition: Optional[Dict[str, object]] = None

    transformations: Optional[List[DatasetTransformation]] = None
