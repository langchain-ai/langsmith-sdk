"""Tool extraction and conversion utilities for Google ADK integration."""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _convert_type_enum(type_enum: Any) -> str:
    """Convert Google Type enum to JSON Schema type string."""
    if type_enum is None:
        return "object"

    type_str = str(type_enum).upper()

    # Map Google types to JSON Schema types
    type_mapping = {
        "STRING": "string",
        "NUMBER": "number",
        "INTEGER": "integer",
        "BOOLEAN": "boolean",
        "ARRAY": "array",
        "OBJECT": "object",
        "NULL": "null",
        "TYPE_UNSPECIFIED": "object",
    }

    # Extract enum value (e.g., "Type.STRING" -> "STRING")
    if "." in type_str:
        type_str = type_str.split(".")[-1]

    return type_mapping.get(type_str, "object")


def _convert_schema_to_json(schema: Any) -> dict[str, Any]:
    """Convert Google Schema to JSON Schema format."""
    if schema is None:
        return {}

    if isinstance(schema, dict):
        return schema

    result: dict[str, Any] = {}

    # Convert type
    if hasattr(schema, "type") and schema.type is not None:
        result["type"] = _convert_type_enum(schema.type)

    # Copy scalar fields
    scalar_fields = [
        "description",
        "default",
        "format",
        "pattern",
        "minimum",
        "maximum",
        "min_length",
        "max_length",
        "min_items",
        "max_items",
        "nullable",
        "title",
    ]
    for field in scalar_fields:
        if hasattr(schema, field):
            value = getattr(schema, field)
            if value is not None:
                result[field] = value

    # Convert enum
    if hasattr(schema, "enum") and schema.enum:
        result["enum"] = list(schema.enum)

    # Convert required
    if hasattr(schema, "required") and schema.required:
        result["required"] = list(schema.required)

    # Recursively convert properties
    if hasattr(schema, "properties") and schema.properties:
        result["properties"] = {
            key: _convert_schema_to_json(value)
            for key, value in schema.properties.items()
        }

    # Recursively convert items (for arrays)
    if hasattr(schema, "items") and schema.items:
        result["items"] = _convert_schema_to_json(schema.items)

    # Convert anyOf
    if hasattr(schema, "any_of") and schema.any_of:
        result["anyOf"] = [_convert_schema_to_json(s) for s in schema.any_of]

    return result


def _convert_function_declaration(func_decl: Any) -> Optional[dict[str, Any]]:
    """Convert a single FunctionDeclaration to OpenAI tool format."""
    if func_decl is None:
        return None

    name = getattr(func_decl, "name", None)
    if not name:
        return None

    tool_def = {
        "type": "function",
        "function": {
            "name": str(name),
        },
    }

    # Add description
    description = getattr(func_decl, "description", None)
    if description:
        tool_def["function"]["description"] = str(description)

    # Convert parameters
    parameters = getattr(func_decl, "parameters", None)
    if parameters:
        try:
            tool_def["function"]["parameters"] = _convert_schema_to_json(parameters)
        except Exception as e:
            logger.debug(f"Failed to convert parameters for {name}: {e}")

    # Check parameters_json_schema (alternative format)
    if not parameters:
        parameters_json = getattr(func_decl, "parameters_json_schema", None)
        if parameters_json:
            tool_def["function"]["parameters"] = parameters_json

    return tool_def


def extract_tools_from_llm_request(llm_request: Any) -> list[dict[str, Any]]:
    """Extract tool definitions from LlmRequest and convert to OpenAI format."""
    if llm_request is None:
        return []

    config = getattr(llm_request, "config", None)
    if config is None:
        return []

    tools_list = getattr(config, "tools", None)
    if not tools_list:
        return []

    result = []

    for tool in tools_list:
        try:
            function_declarations = getattr(tool, "function_declarations", None)
            if not function_declarations:
                continue

            for func_decl in function_declarations:
                tool_def = _convert_function_declaration(func_decl)
                if tool_def:
                    result.append(tool_def)

        except Exception as e:
            logger.debug(f"Failed to extract tool: {e}")
            continue

    return result
