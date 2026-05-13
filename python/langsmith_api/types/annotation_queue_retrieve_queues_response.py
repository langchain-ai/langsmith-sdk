# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List
from typing_extensions import TypeAlias

from .annotation_queue_schema import AnnotationQueueSchema

__all__ = ["AnnotationQueueRetrieveQueuesResponse"]

AnnotationQueueRetrieveQueuesResponse: TypeAlias = List[AnnotationQueueSchema]
