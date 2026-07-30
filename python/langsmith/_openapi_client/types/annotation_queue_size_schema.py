# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from .._models import BaseModel

__all__ = ["AnnotationQueueSizeSchema"]


class AnnotationQueueSizeSchema(BaseModel):
    """Size of an Annotation Queue"""

    size: int
