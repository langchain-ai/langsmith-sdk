"""Static extraction of feedback keys from evaluator functions.

An evaluator's feedback key is the ``key`` value it returns (e.g.
``{"key": "correctness", "score": 1}``). The runner uses these keys to render
per-evaluator progress and to synthesize error feedback when an evaluator
raises. They are inferred by parsing the function's source into an AST and
reading the literal ``key`` values it produces -- never by executing the
function.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from typing import Callable

# Python 3.14+ removes ast.Str in favor of ast.Constant
_AST_STR_TYPES: tuple = (
    (ast.Str, ast.Constant) if hasattr(ast, "Str") else (ast.Constant,)
)


def _get_str_value(node: ast.expr) -> str:
    """Get string value from ast.Str or ast.Constant."""
    return node.value if isinstance(node, ast.Constant) else node.s  # type: ignore[return-value,union-attr,attr-defined]


def _extract_code_evaluator_feedback_keys(func: Callable) -> list[str]:
    python_code = inspect.getsource(func)

    def extract_dict_keys(node):
        if isinstance(node, ast.Dict):
            keys = []
            key_value = None
            for key, value in zip(node.keys, node.values):
                if isinstance(key, _AST_STR_TYPES):
                    key_str = _get_str_value(key)
                    if key_str == "key" and isinstance(value, _AST_STR_TYPES):
                        key_value = _get_str_value(value)
            return [key_value] if key_value else keys
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "dict"
        ):
            for keyword in node.keywords:
                if keyword.arg == "key" and isinstance(keyword.value, _AST_STR_TYPES):
                    return [_get_str_value(keyword.value)]
        return []

    def extract_evaluation_result_key(node):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "EvaluationResult"
        ):
            for keyword in node.keywords:
                if keyword.arg == "key" and isinstance(keyword.value, _AST_STR_TYPES):
                    return [_get_str_value(keyword.value)]
        return []

    def extract_evaluation_results_keys(node, variables):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "EvaluationResults"
        ):
            for keyword in node.keywords:
                if keyword.arg == "results":
                    if isinstance(keyword.value, ast.Name):
                        return variables.get(keyword.value.id, [])
                    elif isinstance(keyword.value, ast.List):
                        keys = []
                        for elt in keyword.value.elts:
                            keys.extend(extract_evaluation_result_key(elt))
                        return keys
        elif isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, _AST_STR_TYPES) and _get_str_value(key) == "results":
                    if isinstance(value, ast.List):
                        keys = []
                        for elt in value.elts:
                            if isinstance(elt, ast.Dict):
                                for elt_key, elt_value in zip(elt.keys, elt.values):
                                    if (
                                        isinstance(elt_key, _AST_STR_TYPES)
                                        and _get_str_value(elt_key) == "key"
                                    ):
                                        if isinstance(elt_value, _AST_STR_TYPES):
                                            keys.append(_get_str_value(elt_value))
                            elif (
                                isinstance(elt, ast.Call)
                                and isinstance(elt.func, ast.Name)
                                and elt.func.id in ("EvaluationResult", "dict")
                            ):
                                for keyword in elt.keywords:
                                    if keyword.arg == "key" and isinstance(
                                        keyword.value, _AST_STR_TYPES
                                    ):
                                        keys.append(_get_str_value(keyword.value))

                        return keys
        return []

    python_code = textwrap.dedent(python_code)

    try:
        tree = ast.parse(python_code)
        function_def = tree.body[0]
        if not isinstance(function_def, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return []

        variables = {}
        keys = []

        for node in ast.walk(function_def):
            if isinstance(node, ast.Assign):
                if isinstance(node.value, ast.List):
                    list_keys = []
                    for elt in node.value.elts:
                        list_keys.extend(extract_evaluation_result_key(elt))
                    if isinstance(node.targets[0], ast.Name):
                        variables[node.targets[0].id] = list_keys
            elif isinstance(node, ast.Return) and node.value is not None:
                dict_keys = extract_dict_keys(node.value)
                eval_result_key = extract_evaluation_result_key(node.value)
                eval_results_keys = extract_evaluation_results_keys(
                    node.value, variables
                )

                keys.extend(dict_keys)
                keys.extend(eval_result_key)
                keys.extend(eval_results_keys)

        # If no keys found, return the function name
        return keys if keys else [function_def.name]

    except SyntaxError:
        return []


def _safe_extract_feedback_keys(func: Callable) -> list[str]:
    """Best-effort static extraction of an evaluator's feedback keys.

    Reads the function's source and returns the literal ``key`` values it emits.
    Degrades to ``[]`` when keys can't be statically inferred (dynamic keys,
    source unavailable, etc.) so evaluator construction never fails.
    """
    try:
        return _extract_code_evaluator_feedback_keys(func)
    except Exception:
        return []
