# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List
from typing_extensions import TypeAlias

from .example_validation_result import ExampleValidationResult

__all__ = ["ValidateBulkResponse"]

ValidateBulkResponse: TypeAlias = List[ExampleValidationResult]
