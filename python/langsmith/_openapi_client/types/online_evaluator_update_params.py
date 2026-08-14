# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import TypedDict

from .update_online_llm_evaluator_request_param import UpdateOnlineLlmEvaluatorRequestParam
from .update_online_code_evaluator_request_param import UpdateOnlineCodeEvaluatorRequestParam

__all__ = ["OnlineEvaluatorUpdateParams"]


class OnlineEvaluatorUpdateParams(TypedDict, total=False):
    code_evaluator: UpdateOnlineCodeEvaluatorRequestParam

    llm_evaluator: UpdateOnlineLlmEvaluatorRequestParam

    name: str
