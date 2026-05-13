# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List
from typing_extensions import TypeAlias

from ..run_schema_with_annotation_queue_info import RunSchemaWithAnnotationQueueInfo

__all__ = ["RunListResponse"]

RunListResponse: TypeAlias = List[RunSchemaWithAnnotationQueueInfo]
