"""Fetch and merge the OpenAI and Langsmith schemas."""
from copy import deepcopy
from pathlib import Path

import requests
import yaml
from openapi_spec_validator import validate_spec
import argparse


def get_subschemas(schema, required_objects):
    subschemas = {}

    def extract_schema(obj_name):
        if obj_name in subschemas:
            return

        obj_schema = schema["components"]["schemas"][obj_name]
        subschemas[obj_name] = obj_schema

        if "properties" in obj_schema:
            for prop_schema in obj_schema["properties"].values():
                ref = prop_schema.get("$ref")
                if ref:
                    extract_schema(ref.split("/")[-1])

        if "items" in obj_schema:
            ref = obj_schema["items"].get("$ref")
            if ref:
                extract_schema(ref.split("/")[-1])

        if "allOf" in obj_schema:
            for all_of_item in obj_schema["allOf"]:
                ref = all_of_item.get("$ref")
                if ref:
                    extract_schema(ref.split("/")[-1])

    for obj_name in required_objects:
        extract_schema(obj_name)

    return subschemas


def modify_openai_schema(schema: dict) -> dict:
    """Remove the default and description fields from the given schema and make sure none of them are marked as required."""

    # Remove default and description fields
    for obj in schema.values():
        obj.pop("default", None)
        obj.pop("description", None)

        # Check and remove required fields if present
        if "properties" in obj:
            for prop in obj["properties"].values():
                prop.pop("default", None)
                prop.pop("description", None)

        # Remove 'required' list if present
        obj.pop("required", None)

    return schema


def get_openai_components() -> dict:
    required_objects = [
        "CreateChatCompletionRequest",
        "CreateChatCompletionResponse",
        "CreateCompletionRequest",
        "CreateCompletionResponse",
        "ChatCompletionRequestMessage",
        "ChatCompletionFunctions",
        "ChatCompletionFunctionCallOption",
        "ChatCompletionResponseMessage",
    ]

    response = requests.get(
        "https://raw.githubusercontent.com/openai/openai-openapi/master/openapi.yaml"
    )
    openapi_schema = yaml.safe_load(response.text)

    subschemas = get_subschemas(openapi_schema, required_objects)
    modified_subschemas = modify_openai_schema(subschemas)

    return modified_subschemas


def get_dependencies(schema, obj_name, new_components):
    if obj_name in new_components["schemas"]:
        return

    obj_schema = schema["components"]["schemas"][obj_name]
    new_components["schemas"][obj_name] = obj_schema

    if "properties" in obj_schema:
        for prop_schema in obj_schema["properties"].values():
            ref = prop_schema.get("$ref")
            if ref:
                get_dependencies(schema, ref.split("/")[-1], new_components)

    if "items" in obj_schema:
        ref = obj_schema["items"].get("$ref")
        if ref:
            get_dependencies(schema, ref.split("/")[-1], new_components)

    if "allOf" in obj_schema:
        for all_of_item in obj_schema["allOf"]:
            ref = all_of_item.get("$ref")
            if ref:
                get_dependencies(schema, ref.split("/")[-1], new_components)


def _extract_langsmith_routes_and_properties(schema, operation_ids):
    new_paths = {}
    new_components = {"schemas": {}}

    for path, methods in schema["paths"].items():
        for method, operation in methods.items():
            if operation.get("operationId") in operation_ids:
                new_paths[path] = {method: operation}

                request_body = operation.get("requestBody", {})
                request_body_content = request_body.get("content", {}).get(
                    "application/json", {}
                )
                request_body_ref = request_body_content.get("schema", {}).get("$ref")
                if request_body_ref:
                    schema_name = request_body_ref.split("/")[-1]
                    get_dependencies(schema, schema_name, new_components)

                responses = operation.get("responses", {})
                for response in responses.values():
                    response_ref = (
                        response.get("content", {})
                        .get("application/json", {})
                        .get("schema", {})
                        .get("$ref")
                    )
                    if response_ref:
                        schema_name = response_ref.split("/")[-1]
                        get_dependencies(schema, schema_name, new_components)

    get_dependencies(schema, "ValidationError", new_components)

    new_schema = {
        "openapi": schema["openapi"],
        "info": schema["info"],
        "paths": new_paths,
        "components": new_components,
    }

    return new_schema


def get_langsmith_runs_schema() -> dict:
    operation_ids = ["create_run_runs_post", "update_run_runs__run_id__patch"]
    response = requests.get("https://web.smith.langchain.com/openapi.json")
    openapi_schema = response.json()
    return _extract_langsmith_routes_and_properties(openapi_schema, operation_ids)


def merge_schemas(langsmith_schema: dict, openai_components: dict) -> dict:
    merged_schema = deepcopy(langsmith_schema)

    for name, component in openai_components.items():
        merged_schema["components"]["schemas"][name] = component

    # Update the RunUpdateSchema and RunCreateSchema
    # to reflect the union type of the inputs and outputs
    # for LLM runs
    for schema_name in ["RunUpdateSchema", "RunCreateSchema"]:
        if schema_name in merged_schema["components"]["schemas"]:
            schema = merged_schema["components"]["schemas"][schema_name]

            schema["properties"]["inputs"]["anyOf"] = [
                {"type": "object"},
                {"$ref": "#/components/schemas/CreateChatCompletionRequest"},
                {"$ref": "#/components/schemas/CreateCompletionRequest"},
            ]

            schema["properties"]["outputs"]["anyOf"] = [
                {"type": "object"},
                {"$ref": "#/components/schemas/CreateChatCompletionResponse"},
                {"$ref": "#/components/schemas/CreateCompletionResponse"},
            ]

            del schema["properties"]["inputs"]["type"]
            del schema["properties"]["outputs"]["type"]

    return merged_schema


def test_openapi_specification(spec: dict):
    # Validate the specification
    errors = validate_spec(spec)
    # Assert that there are no errors
    assert errors is None, f"OpenAPI validation failed: {errors}"


def main(out_file: str = "openapi.yaml"):
    langsmith_schema = get_langsmith_runs_schema()
    openai_components = get_openai_components()
    merged_schema = merge_schemas(langsmith_schema, openai_components)
    parent_dir = Path(__file__).parent.parent
    test_openapi_specification(merged_schema)
    with (parent_dir / "openapi" / out_file).open("w") as f:
        # Make sure it's ordered well for an openapi schema:
        f.write(yaml.dump(merged_schema))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=str, default="openapi.yaml")
    args = parser.parse_args()
    main(args.output)
