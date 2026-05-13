# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Union, Optional
from datetime import datetime

from ..._models import BaseModel

__all__ = ["ExampleValidationResult"]


class ExampleValidationResult(BaseModel):
    """
    Validation result for Example, combining fields from Create/Base/Update schemas.
    """

    id: Optional[str] = None

    created_at: Optional[datetime] = None

    dataset_id: Optional[str] = None

    inputs: Optional[Dict[str, object]] = None

    metadata: Optional[Dict[str, object]] = None

    outputs: Optional[Dict[str, object]] = None

    overwrite: Optional[bool] = None

    source_run_id: Optional[str] = None

    split: Union[List[str], str, None] = None

    use_source_run_io: Optional[bool] = None
