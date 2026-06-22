# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from ..._models import BaseModel

__all__ = ["DatasetShareSchema"]


class DatasetShareSchema(BaseModel):
    dataset_id: str

    share_token: str
