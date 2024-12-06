"""Fetch and prune the Langsmith spec."""

import argparse
from pathlib import Path

import requests
import yaml
from openapi_spec_validator import validate_spec


def get_dependencies(schema, obj_name, new_components):
    if obj_name in new_components["schemas"]:
        return

    obj_schema = schema["components"]["schemas"][obj_name]
    new_components["schemas"][obj_name] = obj_schema

    def process_schema(sub_schema):
        if "$ref" in sub_schema:
            get_dependencies(schema, sub_schema["$ref"].split("/")[-1], new_components)
        else:
            if "items" in sub_schema and "$ref" in sub_schema["items"]:
                get_dependencies(
                    schema, sub_schema["items"]["$ref"].split("/")[-1], new_components
                )
            for keyword in ["anyOf", "oneOf", "allOf"]:
                if keyword in sub_schema:
                    for item in sub_schema[keyword]:
                        process_schema(item)

    if "properties" in obj_schema:
        for prop_schema in obj_schema["properties"].values():
            process_schema(prop_schema)

    if "items" in obj_schema:
        process_schema(obj_schema["items"])

    for keyword in ["allOf", "anyOf", "oneOf"]:
        if keyword in obj_schema:
            for item in obj_schema[keyword]:
                process_schema(item)


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


def get_langsmith_runs_schema(
    url: str = "https://web.smith.langchain.com/openapi.json",
) -> dict:
    operation_ids = ["create_run_runs_post", "update_run_runs__run_id__patch"]
    response = requests.get(url)
    openapi_schema = response.json()
    return _extract_langsmith_routes_and_properties(openapi_schema, operation_ids)


def test_openapi_specification(spec: dict):
    # Validate the specification
    errors = validate_spec(spec)
    # Assert that there are no errors
    assert errors is None, f"OpenAPI validation failed: {errors}"


def main(
    out_file: str = "openapi.yaml",
    url: str = "https://web.smith.langchain.com/openapi.json",
):
    langsmith_schema = get_langsmith_runs_schema(url=url)
    parent_dir = Path(__file__).parent.parent
    test_openapi_specification(langsmith_schema)
    with (parent_dir / "openapi" / out_file).open("w") as f:
        # Sort the schema keys so the openapi version and info come at the top
        for key in ["openapi", "info", "paths", "components"]:
            langsmith_schema[key] = langsmith_schema.pop(key)
        f.write(yaml.dump(langsmith_schema, sort_keys=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--url", type=str, default="https://web.smith.langchain.com/openapi.json"
    )
    parser.add_argument("--output", type=str, default="openapi.yaml")
    args = parser.parse_args()
    main(args.output, url=args.url)
