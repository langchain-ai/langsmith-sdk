"""LangSmith langchain_client Integration Tests."""

import asyncio
import datetime
import importlib
import io
import logging
import os
import queue
import random
import string
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Callable, Dict, cast
from unittest import mock

import pytest
from freezegun import freeze_time
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.trace import set_tracer_provider
from pydantic import BaseModel
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor

import langsmith
from langsmith import env as ls_env
from langsmith import uuid7
from langsmith._internal._background_thread import (
    TracingQueueItem,
    _otel_tracing_thread_handle_batch,
)
from langsmith._internal._operations import serialize_run_dict
from langsmith._internal._serde import dumps_json
from langsmith._internal.otel import _otel_exporter
from langsmith._internal.otel._otel_client import get_otlp_tracer_provider
from langsmith.client import ID_TYPE, Client, _close_files
from langsmith.evaluation import aevaluate, evaluate
from langsmith.run_helpers import traceable
from langsmith.schemas import (
    AttachmentsOperations,
    Dataset,
    DataType,
    Example,
    ExampleCreate,
    ExampleUpdate,
    ExampleUpdateWithAttachments,
    Run,
)
from langsmith.utils import (
    LangSmithConflictError,
    LangSmithConnectionError,
    LangSmithError,
    LangSmithNotFoundError,
    get_env_var,
)

logger = logging.getLogger(__name__)

# Global lock to prevent parallel dataset deletions that can cause deadlocks
_dataset_deletion_lock = threading.Lock()


def safe_delete_dataset(
    client: Client, dataset_id: str = None, dataset_name: str = None
):
    """Delete a dataset with thread safety to prevent deadlocks in parallel tests."""
    with _dataset_deletion_lock:
        try:
            if dataset_id:
                client.delete_dataset(dataset_id=dataset_id)
            elif dataset_name:
                client.delete_dataset(dataset_name=dataset_name)
        except Exception as e:
            # Log the error but don't fail the test - dataset might already be deleted
            logger.warning(f"Failed to delete dataset: {e}")


def wait_for(
    condition: Callable[[], bool], max_sleep_time: int = 120, sleep_time: int = 3
):
    """Wait for a condition to be true."""
    start_time = time.time()
    while time.time() - start_time < max_sleep_time:
        try:
            if condition():
                return
        except Exception:
            time.sleep(sleep_time)
    total_time = time.time() - start_time
    raise ValueError(f"Callable did not return within {total_time}")


@pytest.fixture
def langchain_client() -> Client:
    get_env_var.cache_clear()
    return Client(
        info={
            "instance_flags": {
                "dataset_examples_multipart_enabled": True,
                "examples_multipart_enabled": True,
                "zstd_compression_enabled": True,
            }
        }
    )


@pytest.fixture(params=[True, False])
def parameterized_multipart_client(request) -> Client:
    """Client fixture with parameterized dataset_examples_multipart_enabled setting."""
    get_env_var.cache_clear()
    return Client(
        info={
            "instance_flags": {
                "dataset_examples_multipart_enabled": request.param,
            }
        }
    )


def test_datasets(parameterized_multipart_client: Client) -> None:
    """Test datasets."""
    csv_content = "col1,col2\nval1,val2"
    blob_data = io.BytesIO(csv_content.encode("utf-8"))

    description = "Test Dataset"
    input_keys = ["col1"]
    output_keys = ["col2"]
    filename = "".join(random.sample(string.ascii_lowercase, 10)) + ".csv"
    new_dataset = parameterized_multipart_client.upload_csv(
        csv_file=(filename, blob_data),
        description=description,
        input_keys=input_keys,
        output_keys=output_keys,
    )
    assert new_dataset.id is not None
    assert new_dataset.description == description

    dataset = parameterized_multipart_client.read_dataset(dataset_id=new_dataset.id)
    dataset_id = dataset.id
    dataset2 = parameterized_multipart_client.read_dataset(dataset_id=dataset_id)
    assert dataset.id == dataset2.id

    datasets = list(
        parameterized_multipart_client.list_datasets(dataset_ids=[dataset_id])
    )
    assert len(datasets) > 0
    assert dataset_id in [dataset.id for dataset in datasets]

    # Test Example CRD
    example = parameterized_multipart_client.create_example(
        inputs={"col1": "addedExampleCol1"},
        outputs={"col2": "addedExampleCol2"},
        dataset_id=new_dataset.id,
    )
    example_to_delete = parameterized_multipart_client.create_example(
        inputs={"col1": "addedExampleCol1"},
        outputs={"col2": "addedExampleCol2"},
        dataset_id=new_dataset.id,
    )
    example_value = parameterized_multipart_client.read_example(example.id)
    assert example_value.inputs is not None
    assert example_value.inputs["col1"] == "addedExampleCol1"
    assert example_value.outputs is not None
    assert example_value.outputs["col2"] == "addedExampleCol2"

    examples = list(
        parameterized_multipart_client.list_examples(dataset_id=new_dataset.id)  # type: ignore
    )
    assert len(examples) == 3
    assert example.id in [example.id for example in examples]

    parameterized_multipart_client.update_example(
        example_id=example.id,
        inputs={"col1": "updatedExampleCol1"},
        outputs={"col2": "updatedExampleCol2"},
        metadata={"foo": "bar"},
    )
    updated_example = parameterized_multipart_client.read_example(example.id)
    assert updated_example.id == example.id
    updated_example_value = parameterized_multipart_client.read_example(
        updated_example.id
    )
    assert updated_example_value.inputs["col1"] == "updatedExampleCol1"
    assert updated_example_value.outputs is not None
    assert updated_example_value.outputs["col2"] == "updatedExampleCol2"
    assert (updated_example_value.metadata or {}).get("foo") == "bar"

    new_example = parameterized_multipart_client.create_example(
        inputs={"col1": "newAddedExampleCol1"},
        outputs={"col2": "newAddedExampleCol2"},
        dataset_id=new_dataset.id,
    )
    example_value = parameterized_multipart_client.read_example(new_example.id)
    assert example_value.inputs is not None
    assert example_value.inputs["col1"] == "newAddedExampleCol1"
    assert example_value.outputs is not None
    assert example_value.outputs["col2"] == "newAddedExampleCol2"

    parameterized_multipart_client.update_examples(
        example_ids=[new_example.id, example.id],
        inputs=[{"col1": "newUpdatedExampleCol1"}, {"col1": "newNewUpdatedExampleCol"}],
        outputs=[
            {"col2": "newUpdatedExampleCol2"},
            {"col2": "newNewUpdatedExampleCol2"},
        ],
        metadata=[{"foo": "baz"}, {"foo": "qux"}],
    )
    updated_example = parameterized_multipart_client.read_example(new_example.id)
    assert updated_example.id == new_example.id
    assert updated_example.inputs["col1"] == "newUpdatedExampleCol1"
    assert updated_example.outputs is not None
    assert updated_example.outputs["col2"] == "newUpdatedExampleCol2"
    assert (updated_example.metadata or {}).get("foo") == "baz"

    updated_example = parameterized_multipart_client.read_example(example.id)
    assert updated_example.id == example.id
    assert updated_example.inputs["col1"] == "newNewUpdatedExampleCol"
    assert updated_example.outputs is not None
    assert updated_example.outputs["col2"] == "newNewUpdatedExampleCol2"
    assert (updated_example.metadata or {}).get("foo") == "qux"

    parameterized_multipart_client.delete_example(example.id)
    parameterized_multipart_client.delete_examples(example_ids=[example_to_delete.id])
    examples2 = list(
        parameterized_multipart_client.list_examples(dataset_id=new_dataset.id)  # type: ignore
    )
    assert len(examples2) == 2

    hard_delete_example = examples2[0]
    parameterized_multipart_client.delete_examples(
        example_ids=[hard_delete_example.id], hard_delete=True
    )
    examples_after_hard_delete = list(
        parameterized_multipart_client.list_examples(dataset_id=new_dataset.id)  # type: ignore
    )
    assert len(examples_after_hard_delete) == len(examples2) - 1
    parameterized_multipart_client.create_example(
        inputs={},
        outputs=None,
        dataset_id=new_dataset.id,
    )
    examples3 = list(
        parameterized_multipart_client.list_examples(dataset_id=new_dataset.id)  # type: ignore
    )
    assert len(examples3) == 2

    # Find the example with empty inputs that we just created
    empty_input_examples = [ex for ex in examples3 if ex.inputs == {}]
    assert len(empty_input_examples) == 1, (
        f"Expected exactly 1 example with empty inputs, "
        f"found {len(empty_input_examples)}"
    )

    empty_example = empty_input_examples[0]
    # The backend currently returns None for outputs when None is provided,
    # regardless of flags
    assert empty_example.outputs is None, (
        f"Expected None outputs for example created with outputs=None, "
        f"got {empty_example.outputs}"
    )
    safe_delete_dataset(parameterized_multipart_client, dataset_id=dataset_id)


def _create_dataset(client: Client, dataset_name: str) -> Dataset:
    if client.has_dataset(dataset_name=dataset_name):
        safe_delete_dataset(client, dataset_name=dataset_name)
    return client.create_dataset(dataset_name=dataset_name)


@dataclass(frozen=True)
class ListReq:
    key: str
    kwargs: dict[str, Any]


def _fetch_list(client: "Client", dataset_id: str, req: ListReq):
    return req.key, list(client.list_examples(dataset_id=dataset_id, **req.kwargs))


def test_list_examples(langchain_client: "Client") -> None:
    examples = [
        ("Shut up, idiot", "Toxic", ["train", "validation"]),
        ("You're a wonderful person", "Not toxic", "test"),
        ("This is the worst thing ever", "Toxic", ["train"]),
        ("I had a great day today", "Not toxic", "test"),
        ("Nobody likes you", "Toxic", "train"),
        ("This is unacceptable. I want to speak to the manager.", "Not toxic", None),
    ]

    dataset_name = "__test_list_examples" + uuid7().hex
    dataset = _create_dataset(langchain_client, dataset_name)

    try:
        inputs, outputs, splits = zip(
            *[
                ({"text": text}, {"label": label}, split)
                for text, label, split in examples
            ]
        )
        langchain_client.create_examples(
            inputs=inputs, outputs=outputs, splits=splits, dataset_id=dataset.id
        )

        batch1 = [
            ListReq("all", {}),
            ListReq("offset_limit", {"offset": 1, "limit": 2}),
            ListReq("offset_only", {"offset": 1}),
            ListReq("train", {"splits": ["train"]}),
            ListReq("validation", {"splits": ["validation"]}),
            ListReq("test", {"splits": ["test"]}),
            ListReq("train_test", {"splits": ["train", "test"]}),
        ]

        with ThreadPoolExecutor(max_workers=min(8, len(batch1))) as tp:
            results1 = dict(
                tp.map(lambda r: _fetch_list(langchain_client, dataset.id, r), batch1)
            )

        assert len(results1["all"]) == len(examples)
        assert len(results1["offset_limit"]) == 2
        assert len(results1["offset_only"]) == len(examples) - 1
        assert len(results1["train"]) == 3
        assert len(results1["validation"]) == 1
        assert len(results1["test"]) == 2
        assert len(results1["train_test"]) == 5

        example_list_train_test = results1["train_test"]
        to_move = [
            ex.id
            for ex in example_list_train_test
            if ex.metadata is not None
            and "test" in ex.metadata.get("dataset_split", [])
        ][0]

        langchain_client.update_example(example_id=to_move, split="train")

        batch2 = [
            ListReq("test_after_move", {"splits": ["test"]}),
            ListReq("train_after_move", {"splits": ["train"]}),
        ]
        with ThreadPoolExecutor(max_workers=len(batch2)) as tp:
            results2 = dict(
                tp.map(lambda r: _fetch_list(langchain_client, dataset.id, r), batch2)
            )

        assert len(results2["test_after_move"]) == 1
        assert len(results2["train_after_move"]) == 4

        langchain_client.create_example(
            inputs={"text": "What's up!"},
            outputs={"label": "Not toxic"},
            metadata={"foo": "bar", "baz": "qux"},
            dataset_name=dataset_name,
        )

        batch3 = [
            ListReq("all_after_create", {}),
            ListReq("meta_foo", {"metadata": {"foo": "bar"}}),
            ListReq("meta_baz", {"metadata": {"baz": "qux"}}),
            ListReq("meta_both", {"metadata": {"foo": "bar", "baz": "qux"}}),
            ListReq("meta_miss", {"metadata": {"foo": "bar", "baz": "quux"}}),
            ListReq("filter_exists_baz", {"filter": 'exists(metadata, "baz")'}),
            ListReq(
                "filter_has_foo", {"filter": 'has("metadata", \'{"foo": "bar"}\')'}
            ),
            ListReq("filter_exists_bazzz", {"filter": 'exists(metadata, "bazzz")'}),
        ]
        with ThreadPoolExecutor(max_workers=min(8, len(batch3))) as tp:
            results3 = dict(
                tp.map(lambda r: _fetch_list(langchain_client, dataset.id, r), batch3)
            )

        assert len(results3["all_after_create"]) == len(examples) + 1
        assert len(results3["meta_foo"]) == 1
        assert len(results3["meta_baz"]) == 1
        assert len(results3["meta_both"]) == 1
        assert len(results3["meta_miss"]) == 0
        assert len(results3["filter_exists_baz"]) == 1
        assert len(results3["filter_has_foo"]) == 1
        assert len(results3["filter_exists_bazzz"]) == 0

    finally:
        safe_delete_dataset(langchain_client, dataset_id=dataset.id)


@pytest.mark.slow
def test_similar_examples(langchain_client: Client) -> None:
    inputs = [{"text": "how are you"}, {"text": "good bye"}, {"text": "see ya later"}]
    outputs = [
        {"response": "good how are you"},
        {"response": "ta ta"},
        {"response": "tootles"},
    ]
    dataset_name = "__test_similar_examples" + uuid7().hex
    if langchain_client.has_dataset(dataset_name=dataset_name):
        safe_delete_dataset(langchain_client, dataset_name=dataset_name)
    dataset = langchain_client.create_dataset(
        dataset_name=dataset_name,
        inputs_schema={
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "text": {"type": "string"},
            },
            "required": ["text"],
            "additionalProperties": False,
        },
        outputs_schema={
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "response": {"type": "string"},
            },
            "required": ["response"],
            "additionalProperties": False,
        },
    )
    langchain_client.create_examples(
        inputs=inputs, outputs=outputs, dataset_id=dataset.id
    )
    langchain_client.index_dataset(dataset_id=dataset.id)
    # Need to wait for indexing to finish.
    time.sleep(5)
    similar_list = langchain_client.similar_examples(
        {"text": "howdy"}, limit=2, dataset_id=dataset.id
    )
    assert len(similar_list) == 2

    langchain_client.create_example(
        inputs={"text": "howdy"},
        outputs={"response": "howdy"},
        dataset_id=dataset.id,
    )

    langchain_client.sync_indexed_dataset(dataset_id=dataset.id)
    time.sleep(5)

    similar_list = langchain_client.similar_examples(
        {"text": "howdy"}, limit=5, dataset_id=dataset.id
    )
    assert len(similar_list) == 4

    safe_delete_dataset(langchain_client, dataset_id=dataset.id)


@pytest.mark.skip(reason="This test is flaky")
def test_persist_update_run(langchain_client: Client) -> None:
    """Test the persist and update methods work as expected."""
    project_name = "__test_persist_update_run" + uuid7().hex
    if langchain_client.has_project(project_name):
        langchain_client.delete_project(project_name=project_name)
    try:
        start_time = datetime.datetime.now()
        revision_id = uuid7()
        run: dict = dict(
            id=uuid7(),
            name="test_run",
            run_type="llm",
            inputs={"text": "hello world"},
            project_name=project_name,
            api_url=os.getenv("LANGCHAIN_ENDPOINT"),
            start_time=start_time,
            extra={"extra": "extra"},
            revision_id=revision_id,
        )
        langchain_client.create_run(**run)
        run["outputs"] = {"output": ["Hi"]}
        run["extra"]["foo"] = "bar"
        run["name"] = "test_run_updated"
        langchain_client.update_run(run["id"], **run)
        wait_for(lambda: langchain_client.read_run(run["id"]).end_time is not None)
        stored_run = langchain_client.read_run(run["id"])
        assert stored_run.name == run["name"]
        assert stored_run.id == run["id"]
        assert stored_run.outputs == run["outputs"]
        assert stored_run.start_time == run["start_time"]
        assert stored_run.revision_id == str(revision_id)
    finally:
        langchain_client.delete_project(project_name=project_name)


@pytest.mark.slow
def test_update_run_attachments(langchain_client: Client) -> None:
    """Test the persist and update methods work as expected."""
    project_name = "__test_update_run_attachments" + uuid7().hex
    try:
        trace_id = uuid7()
        start_time = datetime.datetime.now(datetime.timezone.utc)
        run: dict = dict(
            id=str(trace_id),
            name="test_run",
            run_type="llm",
            inputs={"text": "hello world"},
            project_name=project_name,
            api_url=os.getenv("LANGCHAIN_ENDPOINT"),
            start_time=start_time,
            extra={"extra": "extra"},
            trace_id=str(trace_id),
            dotted_order=f"{start_time.strftime('%Y%m%dT%H%M%S%fZ')}{str(trace_id)}",
        )
        langchain_client.create_run(**run)
        run["outputs"] = {"output": ["Hi"]}
        run["extra"]["foo"] = "bar"
        run["name"] = "test_run_updated"
        langchain_client.update_run(run["id"], **run)
        wait_for(lambda: langchain_client.read_run(run["id"]).end_time is not None)
        stored_run = langchain_client.read_run(run["id"])
        assert stored_run.name == run["name"]
        assert str(stored_run.id) == run["id"]
        assert stored_run.outputs == run["outputs"]
        assert stored_run.start_time == run["start_time"].replace(tzinfo=None)
    finally:
        langchain_client.delete_project(project_name=project_name)


@pytest.mark.parametrize("uri", ["http://localhost:1981", "http://api.langchain.minus"])
def test_error_surfaced_invalid_uri(uri: str) -> None:
    get_env_var.cache_clear()
    client = Client(api_url=uri, api_key="test")
    # expect connect error
    with pytest.raises(LangSmithConnectionError):
        client.create_run("My Run", inputs={"text": "hello world"}, run_type="llm")


def test_upload_examples_multipart(langchain_client: Client):
    """Test uploading examples with attachments via multipart endpoint."""
    dataset_name = "__test_upload_examples_multipart" + uuid7().hex
    dataset = _create_dataset(langchain_client, dataset_name)

    # Test example with all fields
    example_id = uuid7()
    example_1 = ExampleCreate(
        id=example_id,
        inputs={"text": "hello world"},
        attachments={
            "test_file": ("text/plain", b"test content"),
        },
    )

    # Test example with minimum required fields
    example_2 = ExampleCreate(
        inputs={"text": "minimal example"},
    )

    # Test example with outputs and multiple attachments
    example_3 = ExampleCreate(
        inputs={"text": "example with outputs"},
        outputs={"response": "test response"},
        attachments={
            "file1": ("text/plain", b"content 1"),
            "file2": ("text/plain", b"content 2"),
        },
    )

    # Test uploading multiple examples at once
    created_examples = langchain_client.upload_examples_multipart(
        dataset_id=dataset.id, uploads=[example_1, example_2, example_3]
    )
    assert created_examples["count"] == 3

    created_example_1 = langchain_client.read_example(example_id)
    assert created_example_1.inputs["text"] == "hello world"

    # Verify the examples were created correctly
    examples = [
        ex
        for ex in langchain_client.list_examples(
            dataset_id=dataset.id,
            include_attachments=True,
        )
    ]
    assert len(examples) == 3

    # Verify example with ID was created with correct ID
    example_with_id = [ex for ex in examples if ex.id == example_id][0]
    assert example_with_id.inputs["text"] == "hello world"
    assert "test_file" in example_with_id.attachments

    # Verify example with outputs and multiple attachments
    example_with_outputs = next(
        ex
        for ex in examples
        if ex.outputs and ex.outputs.get("response") == "test response"
    )
    assert len(example_with_outputs.attachments) == 2
    assert "file1" in example_with_outputs.attachments
    assert "file2" in example_with_outputs.attachments

    # Test uploading to non-existent dataset fails
    fake_id = uuid7()
    with pytest.raises(LangSmithNotFoundError):
        langchain_client.upload_examples_multipart(
            dataset_id=fake_id,
            uploads=[
                ExampleCreate(
                    inputs={"text": "should fail"},
                )
            ],
        )

    # Clean up
    safe_delete_dataset(langchain_client, dataset_name=dataset_name)


def test_update_example_preserves_existing_inputs_outputs(langchain_client: Client):
    """Test update example with omitted inputs/outputs preserves existing values."""
    dataset_name = "__test_update_preserve_values" + uuid7().hex
    dataset = _create_dataset(langchain_client, dataset_name)

    # Create an example with both inputs and outputs
    original_example = langchain_client.create_example(
        inputs={"original": "input", "number": 42},
        outputs={"original": "output", "score": 0.85},
        metadata={"version": "1.0"},
        dataset_id=dataset.id,
    )

    # Update with None inputs - should preserve original inputs
    langchain_client.update_example(
        example_id=original_example.id,
        outputs={"updated": "output", "score": 0.90},
        metadata={"version": "2.0"},
    )

    # Verify inputs were preserved, outputs were updated
    updated_example = langchain_client.read_example(original_example.id)
    assert updated_example.inputs == {"original": "input", "number": 42}  # Preserved
    assert updated_example.outputs == {"updated": "output", "score": 0.90}  # Updated
    assert updated_example.metadata["version"] == "2.0"  # Updated

    # Update with None outputs - should preserve current outputs
    langchain_client.update_example(
        example_id=original_example.id,
        inputs={"final": "input", "count": 100},
        metadata={"version": "3.0"},
    )

    # Verify outputs were preserved, inputs were updated
    final_example = langchain_client.read_example(original_example.id)
    assert final_example.inputs == {"final": "input", "count": 100}  # Updated
    assert final_example.outputs == {"updated": "output", "score": 0.90}  # Preserved
    assert final_example.metadata["version"] == "3.0"  # Updated

    # Update with both None - should preserve both
    langchain_client.update_example(
        example_id=original_example.id,
        metadata={"version": "4.0"},
    )

    # Verify both inputs and outputs were preserved
    preserved_example = langchain_client.read_example(original_example.id)
    assert preserved_example.inputs == {"final": "input", "count": 100}  # Preserved
    assert preserved_example.outputs == {
        "updated": "output",
        "score": 0.90,
    }  # Preserved
    assert preserved_example.metadata["version"] == "4.0"  # Updated

    # Clean up
    safe_delete_dataset(langchain_client, dataset_name=dataset_name)


def test_create_dataset(langchain_client: Client) -> None:
    dataset_name = "__test_create_dataset" + uuid7().hex
    if langchain_client.has_dataset(dataset_name=dataset_name):
        safe_delete_dataset(langchain_client, dataset_name=dataset_name)
    dataset = langchain_client.create_dataset(dataset_name, data_type=DataType.llm)
    ground_truth = "bcde"
    example = langchain_client.create_example(
        inputs={"input": "hello world"},
        outputs={"output": ground_truth},
        dataset_id=dataset.id,
    )
    initial_version = example.modified_at
    loaded_dataset = langchain_client.read_dataset(dataset_name=dataset_name)
    assert loaded_dataset.data_type == DataType.llm
    example_2 = langchain_client.create_example(
        inputs={"input": "hello world 2"},
        outputs={"output": "fghi"},
        dataset_id=dataset.id,
    )
    langchain_client.update_example(
        example_id=example.id,
        inputs={"input": "hello world"},
        outputs={"output": "bcde"},
    )
    initial_examples = list(
        langchain_client.list_examples(dataset_id=dataset.id, as_of=initial_version)
    )
    assert len(initial_examples) == 1
    latest_examples = list(langchain_client.list_examples(dataset_id=dataset.id))
    assert len(latest_examples) == 2
    latest_tagged_examples = list(
        langchain_client.list_examples(dataset_id=dataset.id, as_of="latest")
    )
    assert len(latest_tagged_examples) == 2
    assert latest_tagged_examples == latest_examples
    diffs = langchain_client.diff_dataset_versions(
        loaded_dataset.id, from_version=initial_version, to_version="latest"
    )
    assert diffs.examples_added == [example_2.id]
    assert diffs.examples_removed == []
    assert diffs.examples_modified == [example.id]
    safe_delete_dataset(langchain_client, dataset_id=dataset.id)


def test_dataset_schema_validation(langchain_client: Client) -> None:
    dataset_name = "__test_create_dataset" + uuid7().hex
    if langchain_client.has_dataset(dataset_name=dataset_name):
        safe_delete_dataset(langchain_client, dataset_name=dataset_name)

    class InputSchema(BaseModel):
        input: str

    class OutputSchema(BaseModel):
        output: str

    dataset = langchain_client.create_dataset(
        dataset_name,
        data_type=DataType.kv,
        inputs_schema=InputSchema.model_json_schema(),
        outputs_schema=OutputSchema.model_json_schema(),
        metadata={"dataset_metadata_k1": "v1", "dataset_metadata_k2": "v2"},
    )

    # confirm we store the schema from the create request
    assert dataset.inputs_schema == InputSchema.model_json_schema()
    assert dataset.outputs_schema == OutputSchema.model_json_schema()

    # create an example that matches the schema, which should succeed
    langchain_client.create_example(
        inputs={"input": "hello world"},
        outputs={"output": "hello"},
        dataset_id=dataset.id,
    )

    # create an example that does not match the input schema
    with pytest.raises(LangSmithError):
        langchain_client.create_example(
            inputs={"john": 1},
            outputs={"output": "hello"},
            dataset_id=dataset.id,
        )

    # create an example that does not match the output schema
    with pytest.raises(LangSmithError):
        langchain_client.create_example(
            inputs={"input": "hello world"},
            outputs={"john": 1},
            dataset_id=dataset.id,
        )

    # assert read API includes the schema definition
    read_dataset = langchain_client.read_dataset(dataset_id=dataset.id)
    assert read_dataset.inputs_schema == InputSchema.model_json_schema()
    assert read_dataset.outputs_schema == OutputSchema.model_json_schema()

    # assert read API includes the metadata
    assert read_dataset.metadata is not None
    assert read_dataset.metadata == {
        "dataset_metadata_k1": "v1",
        "dataset_metadata_k2": "v2",
        "runtime": ls_env.get_runtime_environment(),
    }

    safe_delete_dataset(langchain_client, dataset_id=dataset.id)


@freeze_time("2023-01-01")
def test_list_datasets(langchain_client: Client) -> None:
    ds1n = "__test_list_datasets1" + uuid7().hex
    ds2n = "__test_list_datasets2" + uuid7().hex
    try:
        dataset1 = langchain_client.create_dataset(
            ds1n, data_type=DataType.llm, metadata={"foo": "barqux"}
        )
        dataset2 = langchain_client.create_dataset(ds2n, data_type=DataType.kv)
        assert dataset1.url is not None
        assert dataset2.url is not None

        datasets = list(
            langchain_client.list_datasets(dataset_ids=[dataset1.id, dataset2.id])
        )
        assert len(datasets) == 2
        assert dataset1.id in [dataset.id for dataset in datasets]
        assert dataset2.id in [dataset.id for dataset in datasets]
        assert dataset1.data_type == DataType.llm
        assert dataset2.data_type == DataType.kv
        # Sub-filter on data type
        datasets = list(langchain_client.list_datasets(data_type=DataType.llm.value))
        assert len(datasets) > 0
        assert dataset1.id in {dataset.id for dataset in datasets}
        # Sub-filter on name
        datasets = list(
            langchain_client.list_datasets(
                dataset_ids=[dataset1.id, dataset2.id], dataset_name=ds1n
            )
        )
        assert len(datasets) == 1
        # Sub-filter on metadata
        datasets = list(
            langchain_client.list_datasets(
                dataset_ids=[dataset1.id, dataset2.id], metadata={"foo": "barqux"}
            )
        )
        assert len(datasets) == 1

        # Test metadata property
        dataset_with_metadata = next(d for d in datasets if d.id == dataset1.id)
        assert dataset_with_metadata.metadata == {
            "foo": "barqux",
            "runtime": ls_env.get_runtime_environment(),
        }

        # Test read_dataset also includes metadata
        read_dataset = langchain_client.read_dataset(dataset_id=dataset1.id)
        assert read_dataset.metadata == {
            "foo": "barqux",
            "runtime": ls_env.get_runtime_environment(),
        }

    finally:
        # Delete datasets
        for name in [ds1n, ds2n]:
            try:
                langchain_client.delete_dataset(dataset_name=name)
            except LangSmithError:
                pass


@pytest.mark.skip(reason="This test is flaky")
def test_create_run_with_masked_inputs_outputs(
    langchain_client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_name = "__test_create_run_with_masked_inputs_outputs" + uuid7().hex
    monkeypatch.setenv("LANGCHAIN_HIDE_INPUTS", "true")
    monkeypatch.setenv("LANGCHAIN_HIDE_OUTPUTS", "true")
    if langchain_client.has_project(project_name):
        langchain_client.delete_project(project_name=project_name)
    try:
        run_id = uuid7()
        langchain_client.create_run(
            id=run_id,
            project_name=project_name,
            name="test_run",
            run_type="llm",
            inputs={"prompt": "hello world"},
            outputs={"generation": "hi there"},
            start_time=datetime.datetime.now(datetime.timezone.utc),
            end_time=datetime.datetime.now(datetime.timezone.utc),
            hide_inputs=True,
            hide_outputs=True,
        )

        run_id2 = uuid7()
        langchain_client.create_run(
            id=run_id2,
            project_name=project_name,
            name="test_run_2",
            run_type="llm",
            inputs={"messages": "hello world 2"},
            start_time=datetime.datetime.now(datetime.timezone.utc),
            hide_inputs=True,
        )

        langchain_client.update_run(
            run_id2,
            outputs={"generation": "hi there 2"},
            end_time=datetime.datetime.now(datetime.timezone.utc),
            hide_outputs=True,
        )
        wait_for(lambda: langchain_client.read_run(run_id).end_time is not None)
        stored_run = langchain_client.read_run(run_id)
        assert "hello" not in str(stored_run.inputs)
        assert stored_run.outputs is not None
        assert "hi" not in str(stored_run.outputs)
        wait_for(lambda: langchain_client.read_run(run_id2).end_time is not None)
        stored_run2 = langchain_client.read_run(run_id2)
        assert "hello" not in str(stored_run2.inputs)
        assert stored_run2.outputs is not None
        assert "hi" not in str(stored_run2.outputs)
    finally:
        langchain_client.delete_project(project_name=project_name)


@freeze_time("2023-01-01")
def test_create_chat_example(
    monkeypatch: pytest.MonkeyPatch, langchain_client: Client
) -> None:
    from langchain_core.messages import FunctionMessage, HumanMessage

    dataset_name = "__createChatExample-test-dataset"
    try:
        existing_dataset = langchain_client.read_dataset(dataset_name=dataset_name)
        langchain_client.delete_dataset(dataset_id=existing_dataset.id)
    except LangSmithError:
        # If the dataset doesn't exist,
        pass

    dataset = langchain_client.create_dataset(dataset_name)

    input = [HumanMessage(content="Hello, world!")]
    generation = FunctionMessage(
        name="foo",
        content="",
        additional_kwargs={"function_call": {"arguments": "args", "name": "foo"}},
    )
    # Create the example from messages
    langchain_client.create_chat_example(input, generation, dataset_id=dataset.id)

    # Read the example
    examples = []
    for example in langchain_client.list_examples(dataset_id=dataset.id):
        examples.append(example)
    assert len(examples) == 1
    assert examples[0].inputs == {
        "input": [
            {
                "type": "human",
                "data": {"content": "Hello, world!"},
            },
        ],
    }
    assert examples[0].outputs == {
        "output": {
            "type": "function",
            "data": {
                "content": "",
                "additional_kwargs": {
                    "function_call": {"arguments": "args", "name": "foo"}
                },
            },
        },
    }
    safe_delete_dataset(langchain_client, dataset_id=dataset.id)


@pytest.mark.parametrize("use_multipart_endpoint", [True, False])
@pytest.mark.slow
def test_batch_ingest_runs(
    langchain_client: Client, use_multipart_endpoint: bool
) -> None:
    _session = "__test_batch_ingest_runs + " + str(uuid7)
    trace_id = uuid7()
    trace_id_2 = uuid7()
    run_id_2 = uuid7()
    current_time = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y%m%dT%H%M%S%fZ"
    )
    later_time = (
        datetime.datetime.now(datetime.timezone.utc) + timedelta(seconds=1)
    ).strftime("%Y%m%dT%H%M%S%fZ")

    """
    Here we create:
    - run 1: a top level trace with inputs and outputs
    - run 3: a top level trace with an error with inputs and outputs
    - run 2: a child of run 1 with inputs, no outputs
    and we update:
    - run 2 (the child): to add outputs
    """

    runs_to_create = [
        {
            "id": str(trace_id),
            "session_name": _session,
            "name": "run 1",
            "run_type": "chain",
            "dotted_order": f"{current_time}{str(trace_id)}",
            "trace_id": str(trace_id),
            "inputs": {"input1": 1, "input2": 2},
            "outputs": {"output1": 3, "output2": 4},
        },
        {
            "id": str(trace_id_2),
            "session_name": _session,
            "name": "run 3",
            "run_type": "chain",
            "dotted_order": f"{current_time}{str(trace_id_2)}",
            "trace_id": str(trace_id_2),
            "inputs": {"input1": 1, "input2": 2},
            "error": "error",
        },
        {
            "id": str(run_id_2),
            "session_name": _session,
            "name": "run 2",
            "run_type": "chain",
            "dotted_order": f"{current_time}{str(trace_id)}."
            f"{later_time}{str(run_id_2)}",
            "trace_id": str(trace_id),
            "parent_run_id": str(trace_id),
            "inputs": {"input1": 5, "input2": 6},
        },
    ]
    runs_to_update = [
        {
            "id": str(run_id_2),
            "dotted_order": f"{current_time}{str(trace_id)}."
            f"{later_time}{str(run_id_2)}",
            "trace_id": str(trace_id),
            "parent_run_id": str(trace_id),
            "outputs": {"output1": 4, "output2": 5},
        },
    ]
    if use_multipart_endpoint:
        langchain_client.multipart_ingest(create=runs_to_create, update=runs_to_update)
    else:
        langchain_client.batch_ingest_runs(create=runs_to_create, update=runs_to_update)
    runs = []
    wait = 4
    for _ in range(15):
        try:
            runs = list(
                langchain_client.list_runs(
                    project_name=_session,
                    run_ids=[str(trace_id), str(run_id_2), str(trace_id_2)],
                )
            )
            if len(runs) == 3:
                break
            raise LangSmithError("Runs not created yet")
        except LangSmithError:
            time.sleep(wait)
            wait += 1
    else:
        pytest.skip("Aya.")
    assert len(runs) == 3
    # Write all the assertions here
    assert len(runs) == 3

    # Assert inputs and outputs of run 1
    run1 = next(run for run in runs if run.id == trace_id)
    assert run1.inputs == {"input1": 1, "input2": 2}
    assert run1.outputs == {"output1": 3, "output2": 4}

    # Assert inputs and outputs of run 2
    run2 = next(run for run in runs if run.id == run_id_2)
    assert run2.inputs == {"input1": 5, "input2": 6}
    assert run2.outputs == {"output1": 4, "output2": 5}

    # Assert inputs and outputs of run 3
    run3 = next(run for run in runs if run.id == trace_id_2)
    assert run3.inputs == {"input1": 1, "input2": 2}
    assert run3.error == "error"


def test_multipart_ingest_empty(
    langchain_client: Client, caplog: pytest.LogCaptureFixture
) -> None:
    runs_to_create: list[dict] = []
    runs_to_update: list[dict] = []

    # make sure no warnings logged
    with caplog.at_level(logging.WARNING, logger="langsmith.client"):
        langchain_client.multipart_ingest(create=runs_to_create, update=runs_to_update)

        assert not caplog.records


def test_multipart_ingest_create_with_attachments_error(
    langchain_client: Client, caplog: pytest.LogCaptureFixture
) -> None:
    _session = "__test_multipart_ingest_create_with_attachments"
    trace_a_id = uuid7()
    current_time = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y%m%dT%H%M%S%fZ"
    )

    runs_to_create: list[dict] = [
        {
            "id": str(trace_a_id),
            "session_name": _session,
            "name": "trace a root",
            "run_type": "chain",
            "dotted_order": f"{current_time}{str(trace_a_id)}",
            "trace_id": str(trace_a_id),
            "inputs": {"input1": 1, "input2": 2},
            "attachments": {
                "foo": ("text/plain", b"bar"),
                "bar": (
                    "image/png",
                    Path(__file__).parent / "test_data/parrot-icon.png",
                ),
            },
        }
    ]

    # make sure no warnings logged
    with pytest.raises(ValueError, match="Must set dangerously_allow_filesystem"):
        langchain_client.multipart_ingest(create=runs_to_create, update=[])


@pytest.mark.slow
def test_multipart_ingest_create_with_attachments(
    langchain_client: Client, caplog: pytest.LogCaptureFixture
) -> None:
    _session = "__test_multipart_ingest_create_with_attachments"
    trace_a_id = uuid7()
    current_time = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y%m%dT%H%M%S%fZ"
    )

    runs_to_create: list[dict] = [
        {
            "id": str(trace_a_id),
            "session_name": _session,
            "name": "trace a root",
            "run_type": "chain",
            "dotted_order": f"{current_time}{str(trace_a_id)}",
            "trace_id": str(trace_a_id),
            "inputs": {"input1": 1, "input2": 2},
            "attachments": {
                "foo": ("text/plain", b"bar"),
                "bar": (
                    "image/png",
                    Path(__file__).parent / "test_data/parrot-icon.png",
                ),
            },
        }
    ]

    # make sure no warnings logged
    with caplog.at_level(logging.WARNING, logger="langsmith.client"):
        langchain_client.multipart_ingest(
            create=runs_to_create, update=[], dangerously_allow_filesystem=True
        )
        langchain_client.flush()
        assert not caplog.records
        wait_for(lambda: _get_run(str(trace_a_id), langchain_client))
        created_run = langchain_client.read_run(run_id=str(trace_a_id))
        assert sorted(created_run.attachments.keys()) == sorted(["foo", "bar"]), (
            f"See failed run at {created_run.url}"
        )
        assert created_run.attachments["foo"]["reader"].read() == b"bar"
        assert (
            created_run.attachments["bar"]["reader"].read()
            == (Path(__file__).parent / "test_data/parrot-icon.png").read_bytes()
        )


@pytest.mark.slow
def test_multipart_ingest_update_with_attachments_no_paths(
    langchain_client: Client, caplog: pytest.LogCaptureFixture
):
    _session = (
        "__test_multipart_ingest_update_with_attachments_no_paths" + uuid7().hex[:6]
    )
    trace_a_id = uuid7()
    current_time = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y%m%dT%H%M%S%fZ"
    )

    runs_to_create: list[dict] = [
        {
            "id": str(trace_a_id),
            "session_name": _session,
            "name": "trace a root",
            "run_type": "chain",
            "dotted_order": f"{current_time}{str(trace_a_id)}",
            "trace_id": str(trace_a_id),
            "outputs": {"output1": 3, "output2": 4},
            "attachments": {
                "foo": ("text/plain", b"bar"),
                "bar": ("image/png", b"bar"),
            },
        }
    ]
    with caplog.at_level(logging.WARNING, logger="langsmith.client"):
        langchain_client.multipart_ingest(create=runs_to_create, update=[])

        assert not caplog.records
        wait_for(lambda: _get_run(str(trace_a_id), langchain_client))
        created_run = langchain_client.read_run(run_id=str(trace_a_id))
        assert created_run.attachments
        assert sorted(created_run.attachments.keys()) == sorted(["foo", "bar"])
        assert created_run.attachments["foo"]["reader"].read() == b"bar"
        assert created_run.attachments["bar"]["reader"].read() == b"bar"

    runs_to_update: list[dict] = [
        {
            "id": str(trace_a_id),
            "dotted_order": f"{current_time}{str(trace_a_id)}",
            "trace_id": str(trace_a_id),
            "outputs": {"output1": 3, "output2": 4},
            "attachments": {
                "baz": ("text/plain", b"bar"),
                "qux": ("image/png", b"bar"),
            },
        }
    ]
    with caplog.at_level(logging.WARNING, logger="langsmith.client"):
        langchain_client.multipart_ingest(create=[], update=runs_to_update)

        assert not caplog.records


def _get_run(run_id: ID_TYPE, langchain_client: Client, has_end: bool = False) -> bool:
    try:
        r = langchain_client.read_run(run_id)  # type: ignore
        if has_end:
            return r.end_time is not None
        return True
    except LangSmithError:
        return False


@pytest.mark.skip(reason="Flakey")
def test_multipart_ingest_update_with_attachments_error(
    langchain_client: Client, caplog: pytest.LogCaptureFixture
) -> None:
    _session = "__test_multipart_ingest_update_with_attachments"

    trace_a_id = uuid7()
    current_time = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y%m%dT%H%M%S%fZ"
    )

    runs_to_create: list[dict] = [
        {
            "id": str(trace_a_id),
            "session_name": _session,
            "name": "trace a root",
            "run_type": "chain",
            "dotted_order": f"{current_time}{str(trace_a_id)}",
            "trace_id": str(trace_a_id),
            "inputs": {"input1": 1, "input2": 2},
        }
    ]

    # make sure no warnings logged
    with caplog.at_level(logging.WARNING, logger="langsmith.client"):
        langchain_client.multipart_ingest(create=runs_to_create, update=[])
        assert not caplog.records
        wait_for(lambda: _get_run(str(trace_a_id), langchain_client))

        runs_to_update: list[dict] = [
            {
                "id": str(trace_a_id),
                "dotted_order": f"{current_time}{str(trace_a_id)}",
                "trace_id": str(trace_a_id),
                "inputs": {"input1": 3, "input2": 4},
                "attachments": {
                    "foo": ("text/plain", b"bar"),
                    "bar": (
                        "image/png",
                        Path(__file__).parent / "test_data/parrot-icon.png",
                    ),
                },
            }
        ]
        with pytest.raises(ValueError, match="Must set dangerously_allow_filesystem"):
            langchain_client.multipart_ingest(create=[], update=runs_to_update)


# TODO: fix flakiness
@pytest.mark.skip(reason="Flakey")
def test_multipart_ingest_update_with_attachments(
    langchain_client: Client, caplog: pytest.LogCaptureFixture
) -> None:
    _session = "__test_multipart_ingest_update_with_attachments"
    trace_a_id = uuid7()
    current_time = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y%m%dT%H%M%S%fZ"
    )
    runs_to_create: list[dict] = [
        {
            "id": str(trace_a_id),
            "session_name": _session,
            "name": "trace a root",
            "run_type": "chain",
            "dotted_order": f"{current_time}{str(trace_a_id)}",
            "trace_id": str(trace_a_id),
            "inputs": {"input1": 1, "input2": 2},
        }
    ]

    # make sure no warnings logged
    with caplog.at_level(logging.WARNING, logger="langsmith.client"):
        langchain_client.multipart_ingest(create=runs_to_create, update=[])
        assert not caplog.records
        image_path = Path(__file__).parent / "test_data/parrot-icon.png"
        image_content = image_path.read_bytes()  # Read content before multipart request

        runs_to_update: list[dict] = [
            {
                "id": str(trace_a_id),
                "dotted_order": f"{current_time}{str(trace_a_id)}",
                "trace_id": str(trace_a_id),
                "inputs": {"input1": 3, "input2": 4},
                "attachments": {
                    "foo": ("text/plain", b"bar"),
                    "bar": (
                        "image/png",
                        image_path,
                    ),
                },
            }
        ]
        langchain_client.multipart_ingest(
            create=[], update=runs_to_update, dangerously_allow_filesystem=True
        )

        # this would fail if the internal file handle wasn't closed
        assert image_path.read_bytes() == image_content

        assert not caplog.records
        wait_for(lambda: _get_run(str(trace_a_id), langchain_client))
        created_run = langchain_client.read_run(run_id=str(trace_a_id))
        assert created_run.inputs == {"input1": 3, "input2": 4}
        assert sorted(created_run.attachments.keys()) == sorted(["foo", "bar"])
        assert created_run.attachments["foo"]["reader"].read() == b"bar"
        assert (
            created_run.attachments["bar"]["reader"].read()
            == (Path(__file__).parent / "test_data/parrot-icon.png").read_bytes()
        )


def test_multipart_ingest_create_then_update(
    langchain_client: Client, caplog: pytest.LogCaptureFixture
) -> None:
    _session = "__test_multipart_ingest_create_then_update"

    trace_a_id = uuid7()
    current_time = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y%m%dT%H%M%S%fZ"
    )

    runs_to_create: list[dict] = [
        {
            "id": str(trace_a_id),
            "session_name": _session,
            "name": "trace a root",
            "run_type": "chain",
            "dotted_order": f"{current_time}{str(trace_a_id)}",
            "trace_id": str(trace_a_id),
            "inputs": {"input1": 1, "input2": 2},
        }
    ]

    # make sure no warnings logged
    with caplog.at_level(logging.WARNING, logger="langsmith.client"):
        langchain_client.multipart_ingest(create=runs_to_create, update=[])

        assert not caplog.records

    runs_to_update: list[dict] = [
        {
            "id": str(trace_a_id),
            "dotted_order": f"{current_time}{str(trace_a_id)}",
            "trace_id": str(trace_a_id),
            "outputs": {"output1": 3, "output2": 4},
        }
    ]
    with caplog.at_level(logging.WARNING, logger="langsmith.client"):
        langchain_client.multipart_ingest(create=[], update=runs_to_update)

        assert not caplog.records


def test_multipart_ingest_update_then_create(
    langchain_client: Client, caplog: pytest.LogCaptureFixture
) -> None:
    _session = "__test_multipart_ingest_update_then_create"

    trace_a_id = uuid7()
    current_time = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y%m%dT%H%M%S%fZ"
    )

    runs_to_update: list[dict] = [
        {
            "id": str(trace_a_id),
            "dotted_order": f"{current_time}{str(trace_a_id)}",
            "trace_id": str(trace_a_id),
            "outputs": {"output1": 3, "output2": 4},
        }
    ]

    # make sure no warnings logged
    with caplog.at_level(logging.WARNING, logger="langsmith.client"):
        langchain_client.multipart_ingest(create=[], update=runs_to_update)

        assert not caplog.records

    runs_to_create: list[dict] = [
        {
            "id": str(trace_a_id),
            "session_name": _session,
            "name": "trace a root",
            "run_type": "chain",
            "dotted_order": f"{current_time}{str(trace_a_id)}",
            "trace_id": str(trace_a_id),
            "inputs": {"input1": 1, "input2": 2},
        }
    ]

    with caplog.at_level(logging.WARNING, logger="langsmith.client"):
        langchain_client.multipart_ingest(create=runs_to_create, update=[])

        assert not caplog.records


def test_multipart_ingest_create_wrong_type(
    langchain_client: Client, caplog: pytest.LogCaptureFixture
) -> None:
    _session = "__test_multipart_ingest_create_then_update"

    trace_a_id = uuid7()
    current_time = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y%m%dT%H%M%S%fZ"
    )

    runs_to_create: list[dict] = [
        {
            "id": str(trace_a_id),
            "session_name": _session,
            "name": "trace a root",
            "run_type": "agent",
            "dotted_order": f"{current_time}{str(trace_a_id)}",
            "trace_id": str(trace_a_id),
            "inputs": {"input1": 1, "input2": 2},
        }
    ]

    # make sure no warnings logged
    with caplog.at_level(logging.WARNING, logger="langsmith.client"):
        langchain_client.multipart_ingest(create=runs_to_create, update=[])

        # this should 422
        assert len(caplog.records) == 1, "Should get 1 warning for 422, not retried"
        assert all(
            "422" in record.message
            or "429" in record.message
            or "400" in record.message
            for record in caplog.records
        ), [record.message for record in caplog.records]


@freeze_time("2023-01-01")
def test_get_info() -> None:
    langchain_client = Client(api_key="not-a-real-key")
    info = langchain_client.info
    assert info
    assert info.version is not None  # type: ignore
    assert info.batch_ingest_config is not None  # type: ignore
    assert info.batch_ingest_config["size_limit"] > 0  # type: ignore


@pytest.mark.skip(reason="This test is flaky")
@pytest.mark.parametrize("add_metadata", [True, False])
@pytest.mark.parametrize("do_batching", [True, False])
def test_update_run_extra(add_metadata: bool, do_batching: bool) -> None:
    langchain_client = Client()
    run_id = uuid7()
    run: Dict[str, Any] = {
        "id": run_id,
        "name": "run 1",
        "start_time": datetime.datetime.now(datetime.timezone.utc),
        "run_type": "chain",
        "inputs": {"input1": 1, "input2": 2},
        "outputs": {"output1": 3, "output2": 4},
        "extra": {
            "metadata": {
                "foo": "bar",
            }
        },
        "tags": ["tag1", "tag2"],
    }
    if do_batching:
        run["trace_id"] = run_id
        dotted_order = run["start_time"].strftime("%Y%m%dT%H%M%S%fZ") + str(run_id)  # type: ignore
        run["dotted_order"] = dotted_order
    revision_id = uuid7()
    langchain_client.create_run(**run, revision_id=revision_id)  # type: ignore

    wait_for(lambda: _get_run(run_id, langchain_client))
    created_run = langchain_client.read_run(run_id)
    assert created_run.metadata["foo"] == "bar"
    assert created_run.metadata["revision_id"] == str(revision_id)
    # Update the run
    if add_metadata:
        run["extra"]["metadata"]["foo2"] = "baz"  # type: ignore
        run["tags"] = ["tag3"]
    langchain_client.update_run(run_id, **run)  # type: ignore
    wait_for(lambda: _get_run(run_id, langchain_client, has_end=True))
    updated_run = langchain_client.read_run(run_id)
    assert updated_run.metadata["foo"] == "bar"  # type: ignore
    assert updated_run.revision_id == str(revision_id)
    if add_metadata:
        updated_run.metadata["foo2"] == "baz"  # type: ignore
        assert updated_run.tags == ["tag3"]
    else:
        assert updated_run.tags == ["tag1", "tag2"]
    assert updated_run.extra["runtime"] == created_run.extra["runtime"]  # type: ignore


def test_surrogates():
    chars = "".join(chr(cp) for cp in range(0, sys.maxunicode + 1))
    trans_table = str.maketrans("", "", "")
    all_chars = chars.translate(trans_table)
    langchain_client = Client()
    langchain_client.create_run(
        name="test_run",
        inputs={
            "text": [
                "Hello\ud83d\ude00",
                "Python\ud83d\udc0d",
                "Surrogate\ud834\udd1e",
                "Example\ud83c\udf89",
                "String\ud83c\udfa7",
                "With\ud83c\udf08",
                "Surrogates\ud83d\ude0e",
                "Embedded\ud83d\udcbb",
                "In\ud83c\udf0e",
                "The\ud83d\udcd6",
                "Text\ud83d\udcac",
                "收花🙄·到",
            ]
        },
        run_type="llm",
        end_time=datetime.datetime.now(datetime.timezone.utc),
    )
    langchain_client.create_run(
        name="test_run",
        inputs={
            "text": all_chars,
        },
        run_type="llm",
        end_time=datetime.datetime.now(datetime.timezone.utc),
    )


def test_fallback_json_serialization():
    class Document(BaseModel):
        content: str

    raw_surrogates = [
        ("Hello\ud83d\ude00", "Hello😀"),
        ("Python\ud83d\udc0d", "Python🐍"),
        ("Surrogate\ud834\udd1e", "Surrogate𝄞"),
        ("Example\ud83c\udf89", "Example🎉"),
        ("String\ud83c\udfa7", "String🎧"),
        ("With\ud83c\udf08", "With🌈"),
        ("Surrogates\ud83d\ude0e", "Surrogates😎"),
        ("Embedded\ud83d\udcbb", "Embedded💻"),
        ("In\ud83c\udf0e", "In🌎"),
        ("The\ud83d\udcd6", "The📖"),
        ("Text\ud83d\udcac", "Text💬"),
        ("收花🙄·到", "收花🙄·到"),
    ]
    pydantic_surrogates = [
        (Document(content=item), expected) for item, expected in raw_surrogates
    ]

    for item, expected in raw_surrogates:
        output = dumps_json(item).decode("utf8")
        assert f'"{expected}"' == output

    for item, expected in pydantic_surrogates:
        output = dumps_json(item).decode("utf8")
        assert f'{{"content":"{expected}"}}' == output


def test_runs_stats():
    langchain_client = Client()
    # We always have stuff in the "default" project...
    stats = langchain_client.get_run_stats(project_names=["default"], run_type="llm")
    assert stats


def test_slow_run_read_multipart(
    langchain_client: Client, caplog: pytest.LogCaptureFixture
):
    myobj = {f"key_{i}": f"val_{i}" for i in range(500)}
    id_ = str(uuid7())
    current_time = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y%m%dT%H%M%S%fZ"
    )
    run_to_create = {
        "id": id_,
        "session_name": "default",
        "name": "trace a root",
        "run_type": "chain",
        "dotted_order": f"{current_time}{id_}",
        "trace_id": id_,
        "inputs": myobj,
    }

    class CB:
        def __init__(self):
            self.called = 0
            self.start_time = None

        def __call__(self, monitor: MultipartEncoderMonitor):
            self.called += 1
            if not self.start_time:
                self.start_time = time.time()
            logger.debug(
                f"[{self.called}]: {monitor.bytes_read} bytes,"
                f" {time.time() - self.start_time:.2f} seconds"
                " elapsed",
            )
            if self.called == 1:
                time.sleep(6)

    def create_encoder(*args, **kwargs):
        encoder = MultipartEncoder(*args, **kwargs)
        encoder = MultipartEncoderMonitor(encoder, CB())
        return encoder

    with caplog.at_level(logging.WARNING, logger="langsmith.client"):
        with mock.patch(
            "langsmith.client.rqtb_multipart.MultipartEncoder", create_encoder
        ):
            langchain_client.create_run(**run_to_create)
            time.sleep(1)
            start_time = time.time()
            while time.time() - start_time < 8:
                myobj["key_1"]

        assert not caplog.records


def test_list_examples_attachments_keys(langchain_client: Client) -> None:
    """Test list_examples returns same keys with and without attachments."""
    dataset_name = "__test_list_examples_attachments" + uuid7().hex
    dataset = _create_dataset(langchain_client, dataset_name)

    langchain_client.upload_examples_multipart(
        dataset_id=dataset.id,
        uploads=[
            ExampleCreate(
                inputs={"text": "hello world"},
                outputs={"response": "hi there"},
                attachments={
                    "test_file": ("text/plain", b"test content"),
                },
            )
        ],
    )

    # Get examples with attachments
    with_attachments = next(
        langchain_client.list_examples(dataset_id=dataset.id, include_attachments=True)
    )

    # Get examples without attachments
    without_attachments = next(
        langchain_client.list_examples(dataset_id=dataset.id, include_attachments=False)
    )

    with_keys = set(with_attachments.dict().keys())
    without_keys = set(without_attachments.dict().keys())
    assert with_keys == without_keys, (
        f"Keys differ when include_attachments=True vs False.\n"
        f"Only in with_attachments: {with_keys - without_keys}\n"
        f"Only in without_attachments: {without_keys - with_keys}"
    )

    safe_delete_dataset(langchain_client, dataset_id=dataset.id)


def test_mime_type_is_propogated(langchain_client: Client) -> None:
    """Test that the mime type is propogated correctly."""
    dataset_name = "__test_mime_type_is_propogated" + uuid7().hex
    dataset = _create_dataset(langchain_client, dataset_name)

    langchain_client.upload_examples_multipart(
        dataset_id=dataset.id,
        uploads=[
            ExampleCreate(
                inputs={"text": "hello world"},
                outputs={"response": "hi there"},
                attachments={
                    "test_file": ("text/plain", b"test content"),
                },
            )
        ],
    )

    example = next(
        langchain_client.list_examples(dataset_id=dataset.id, include_attachments=True)
    )
    assert example.attachments["test_file"]["mime_type"] == "text/plain"

    example = langchain_client.read_example(example_id=example.id)
    assert example.attachments["test_file"]["mime_type"] == "text/plain"

    safe_delete_dataset(langchain_client, dataset_id=dataset.id)


def test_evaluate_mime_type_is_propagated(langchain_client: Client) -> None:
    """Test that the mime type is propogated correctly when evaluating."""
    dataset_name = "__test_evaluate_mime_type_is_propagated" + uuid7().hex
    dataset = _create_dataset(langchain_client, dataset_name)

    langchain_client.upload_examples_multipart(
        dataset_id=dataset.id,
        uploads=[
            ExampleCreate(
                inputs={"text": "hello world"},
                outputs={"response": "hi there"},
                attachments={
                    "test_file": ("text/plain", b"test content"),
                },
            )
        ],
    )

    def target(inputs: Dict[str, Any], attachments: Dict[str, Any]) -> Dict[str, Any]:
        # Verify we receive the attachment data
        assert attachments["test_file"]["mime_type"] == "text/plain"
        return {"answer": "hi there"}

    def evaluator(
        outputs: dict, reference_outputs: dict, attachments: dict
    ) -> Dict[str, Any]:
        # Verify we receive the attachment data
        assert attachments["test_file"]["mime_type"] == "text/plain"
        return {
            "score": float(
                reference_outputs.get("answer") == outputs.get("answer")  # type: ignore
            )
        }

    langchain_client.evaluate(target, data=dataset_name, evaluators=[evaluator])

    safe_delete_dataset(langchain_client, dataset_name=dataset_name)


async def test_aevaluate_mime_type_is_propogated(langchain_client: Client) -> None:
    """Test that the mime type is propogated correctly when evaluating."""
    dataset_name = "__test_evaluate_mime_type_is_propogated" + uuid7().hex
    dataset = _create_dataset(langchain_client, dataset_name)

    langchain_client.upload_examples_multipart(
        dataset_id=dataset.id,
        uploads=[
            ExampleCreate(
                inputs={"text": "hello world"},
                outputs={"response": "hi there"},
                attachments={
                    "test_file": ("text/plain", b"test content"),
                },
            )
        ],
    )

    async def target(
        inputs: Dict[str, Any], attachments: Dict[str, Any]
    ) -> Dict[str, Any]:
        # Verify we receive the attachment data
        assert attachments["test_file"]["mime_type"] == "text/plain"
        return {"answer": "hi there"}

    async def evaluator(
        outputs: dict, reference_outputs: dict, attachments: dict
    ) -> Dict[str, Any]:
        # Verify we receive the attachment data
        assert attachments["test_file"]["mime_type"] == "text/plain"
        return {
            "score": float(
                reference_outputs.get("answer") == outputs.get("answer")  # type: ignore
            )
        }

    await langchain_client.aevaluate(target, data=dataset_name, evaluators=[evaluator])

    safe_delete_dataset(langchain_client, dataset_name=dataset_name)


def test_evaluate_with_attachments_multiple_evaluators(
    langchain_client: Client,
) -> None:
    """Test evaluating examples with attachments and multiple evaluators."""
    dataset_name = "__test_evaluate_attachments_multiple" + uuid7().hex
    dataset = _create_dataset(langchain_client, dataset_name)

    # 2. Create example with attachments
    example = ExampleCreate(
        inputs={"question": "What is shown in the image?"},
        outputs={"answer": "test image"},
        attachments={
            "image": ("image/png", b"fake image data for testing"),
        },
    )

    langchain_client.upload_examples_multipart(dataset_id=dataset.id, uploads=[example])

    def target(inputs: Dict[str, Any], attachments: Dict[str, Any]) -> Dict[str, Any]:
        # Verify we receive the attachment data
        assert "image" in attachments
        assert "presigned_url" in attachments["image"]
        image_data = attachments["image"]["reader"]
        assert image_data.read() == b"fake image data for testing"
        return {"answer": "test image"}

    def evaluator_1(
        outputs: dict, reference_outputs: dict, attachments: dict
    ) -> Dict[str, Any]:
        assert "image" in attachments
        assert "presigned_url" in attachments["image"]
        image_data = attachments["image"]["reader"]
        assert image_data.read() == b"fake image data for testing"
        return {
            "score": float(
                reference_outputs.get("answer") == outputs.get("answer")  # type: ignore
            )
        }

    def evaluator_2(
        outputs: dict, reference_outputs: dict, attachments: dict
    ) -> Dict[str, Any]:
        assert "image" in attachments
        assert "presigned_url" in attachments["image"]
        image_data = attachments["image"]["reader"]
        assert image_data.read() == b"fake image data for testing"
        return {
            "score": float(
                reference_outputs.get("answer") == outputs.get("answer")  # type: ignore
            )
        }

    results = langchain_client.evaluate(
        target,
        data=dataset_name,
        evaluators=[evaluator_1, evaluator_2],
        num_repetitions=2,
    )

    assert len(results) == 2
    for result in results:
        assert result["evaluation_results"]["results"][0].score == 1.0
        assert result["evaluation_results"]["results"][1].score == 1.0

    safe_delete_dataset(langchain_client, dataset_name=dataset_name)


def test_evaluate_with_attachments(langchain_client: Client) -> None:
    """Test evaluating examples with attachments."""
    dataset_name = "__test_evaluate_attachments" + uuid7().hex
    dataset = _create_dataset(langchain_client, dataset_name)

    # 2. Create example with attachments
    example = ExampleCreate(
        inputs={"question": "What is shown in the image?"},
        outputs={"answer": "test image"},
        attachments={
            "image": ("image/png", b"fake image data for testing"),
        },
    )

    langchain_client.upload_examples_multipart(dataset_id=dataset.id, uploads=[example])

    def target(inputs: Dict[str, Any], attachments: Dict[str, Any]) -> Dict[str, Any]:
        # Verify we receive the attachment data
        assert "image" in attachments
        assert "presigned_url" in attachments["image"]
        image_data = attachments["image"]["reader"]
        assert image_data.read() == b"fake image data for testing"
        return {"answer": "test image"}

    def evaluator(
        outputs: dict, reference_outputs: dict, attachments: dict
    ) -> Dict[str, Any]:
        assert "image" in attachments
        assert "presigned_url" in attachments["image"]
        image_data = attachments["image"]["reader"]
        assert image_data.read() == b"fake image data for testing"
        return {
            "score": float(
                reference_outputs.get("answer") == outputs.get("answer")  # type: ignore
            )
        }

    results = langchain_client.evaluate(
        target,
        data=dataset_name,
        evaluators=[evaluator],
        num_repetitions=2,
    )

    assert len(results) == 2
    for result in results:
        assert result["evaluation_results"]["results"][0].score == 1.0

    safe_delete_dataset(langchain_client, dataset_name=dataset_name)


def test_evaluate_with_attachments_not_in_target(langchain_client: Client) -> None:
    """Test evaluating examples with attachments."""
    dataset_name = "__test_evaluate_attachments" + uuid7().hex
    dataset = _create_dataset(langchain_client, dataset_name)

    example = ExampleCreate(
        inputs={"question": "What is shown in the image?"},
        outputs={"answer": "test image"},
        attachments={
            "image": ("image/png", b"fake image data for testing"),
        },
    )

    langchain_client.upload_examples_multipart(dataset_id=dataset.id, uploads=[example])

    def target(inputs: Dict[str, Any]) -> Dict[str, Any]:
        return {"answer": "test image"}

    def evaluator(
        outputs: dict, reference_outputs: dict, attachments: dict
    ) -> Dict[str, Any]:
        assert "image" in attachments
        assert "presigned_url" in attachments["image"]
        image_data = attachments["image"]["reader"]
        assert image_data.read() == b"fake image data for testing"
        return {
            "score": float(
                reference_outputs.get("answer") == outputs.get("answer")  # type: ignore
            )
        }

    results = langchain_client.evaluate(
        target,
        data=dataset_name,
        evaluators=[evaluator],
        num_repetitions=2,
    )

    assert len(results) == 2
    for result in results:
        assert result["evaluation_results"]["results"][0].score == 1.0

    results = langchain_client.evaluate(
        target,
        data=dataset_name,
        evaluators=[evaluator],
    )

    assert len(results) == 1
    for result in results:
        assert result["evaluation_results"]["results"][0].score == 1.0

    safe_delete_dataset(langchain_client, dataset_name=dataset_name)


def test_evaluate_with_no_attachments(langchain_client: Client) -> None:
    """Test evaluating examples without attachments using a target with attachments."""
    dataset_name = "__test_evaluate_no_attachments" + uuid7().hex
    dataset = _create_dataset(langchain_client, dataset_name)

    # Create example using old way, attachments should be set to {}
    langchain_client.create_example(
        dataset_id=dataset.id,
        inputs={"question": "What is 2+2?"},
        outputs={"answer": "4"},
    )

    # Verify we can create example the new way without attachments
    example = ExampleCreate(
        inputs={"question": "What is 3+1?"},
        outputs={"answer": "4"},
    )
    langchain_client.upload_examples_multipart(dataset_id=dataset.id, uploads=[example])

    def target(inputs: Dict[str, Any], attachments: Dict[str, Any]) -> Dict[str, Any]:
        # Verify we receive an empty attachments dict
        assert isinstance(attachments, dict)
        assert len(attachments) == 0
        return {"answer": "4"}

    def evaluator(run: Run, example: Example) -> Dict[str, Any]:
        return {
            "score": float(
                run.outputs.get("answer") == example.outputs.get("answer")  # type: ignore
            )
        }

    results = evaluate(
        target, data=dataset_name, evaluators=[evaluator], client=langchain_client
    )

    assert len(results) == 2
    for result in results:
        assert result["evaluation_results"]["results"][0].score == 1.0

    safe_delete_dataset(langchain_client, dataset_name=dataset_name)


async def test_aevaluate_with_attachments(langchain_client: Client) -> None:
    """Test evaluating examples with attachments."""
    dataset_name = "__test_aevaluate_attachments" + uuid7().hex
    dataset = _create_dataset(langchain_client, dataset_name)

    examples = [
        ExampleCreate(
            inputs={"question": "What is shown in the image?", "index": i},
            outputs={"answer": "test image"},
            attachments={
                "image": ("text/plain", bytes(f"data: {i}", "utf-8")),
            },
        )
        for i in range(10)
    ]

    langchain_client.create_examples(dataset_id=dataset.id, examples=examples)

    async def target(
        inputs: Dict[str, Any], attachments: Dict[str, Any]
    ) -> Dict[str, Any]:
        # Verify we receive the attachment data
        assert "image" in attachments
        assert "presigned_url" in attachments["image"]
        image_data = attachments["image"]["reader"]
        assert image_data.read() == bytes(f"data: {inputs['index']}", "utf-8")
        return {"answer": "test image"}

    async def evaluator_1(
        inputs: dict, outputs: dict, reference_outputs: dict, attachments: dict
    ) -> bool:
        assert "image" in attachments
        assert "presigned_url" in attachments["image"]
        image_data = attachments["image"]["reader"]
        return image_data.read() == bytes(f"data: {inputs['index']}", "utf-8")

    async def evaluator_2(
        inputs: dict, outputs: dict, reference_outputs: dict, attachments: dict
    ) -> bool:
        assert "image" in attachments
        assert "presigned_url" in attachments["image"]
        image_data = attachments["image"]["reader"]
        return image_data.read() == bytes(f"data: {inputs['index']}", "utf-8")

    results = await langchain_client.aevaluate(
        target,
        data=dataset_name,
        evaluators=[evaluator_1, evaluator_2],
        num_repetitions=2,
        max_concurrency=3,
    )

    assert len(results) == 20
    async for result in results:
        assert result["evaluation_results"]["results"][0].score == 1.0
        assert result["evaluation_results"]["results"][1].score == 1.0

    results = await langchain_client.aevaluate(
        target,
        data=dataset_name,
        evaluators=[],
        num_repetitions=1,
        max_concurrency=3,
    )

    assert len(results) == 10

    safe_delete_dataset(langchain_client, dataset_name=dataset_name)


async def test_aevaluate_with_attachments_not_in_target(
    langchain_client: Client,
) -> None:
    """Test evaluating examples with attachments."""
    dataset_name = "__test_aevaluate_attachments" + uuid7().hex
    dataset = _create_dataset(langchain_client, dataset_name)

    example = ExampleCreate(
        inputs={"question": "What is shown in the image?"},
        outputs={"answer": "test image"},
        attachments={
            "image": ("image/png", b"fake image data for testing"),
        },
    )

    langchain_client.upload_examples_multipart(dataset_id=dataset.id, uploads=[example])

    async def target(inputs: Dict[str, Any]) -> Dict[str, Any]:
        # Verify we receive the attachment data
        return {"answer": "test image"}

    async def evaluator(
        outputs: dict, reference_outputs: dict, attachments: dict
    ) -> Dict[str, Any]:
        assert "image" in attachments
        assert "presigned_url" in attachments["image"]
        image_data = attachments["image"]["reader"]
        assert image_data.read() == b"fake image data for testing"
        return {
            "score": float(
                reference_outputs.get("answer") == outputs.get("answer")  # type: ignore
            )
        }

    results = await langchain_client.aevaluate(
        target, data=dataset_name, evaluators=[evaluator], num_repetitions=2
    )

    assert len(results) == 2
    async for result in results:
        assert result["evaluation_results"]["results"][0].score == 1.0

    safe_delete_dataset(langchain_client, dataset_name=dataset_name)


async def test_aevaluate_with_no_attachments(langchain_client: Client) -> None:
    """Test evaluating examples without attachments using a target with attachments."""
    dataset_name = "__test_aevaluate_no_attachments" + uuid7().hex
    dataset = _create_dataset(langchain_client, dataset_name)

    # Create example using old way, attachments should be set to {}
    langchain_client.create_example(
        dataset_id=dataset.id,
        inputs={"question": "What is 2+2?"},
        outputs={"answer": "4"},
    )

    # Verify we can create example the new way without attachments
    example = ExampleCreate(
        inputs={"question": "What is 3+1?"},
        outputs={"answer": "4"},
    )
    langchain_client.upload_examples_multipart(dataset_id=dataset.id, uploads=[example])

    async def target(
        inputs: Dict[str, Any], attachments: Dict[str, Any]
    ) -> Dict[str, Any]:
        # Verify we receive an empty attachments dict
        assert isinstance(attachments, dict)
        assert len(attachments) == 0
        return {"answer": "4"}

    async def evaluator(run: Run, example: Example) -> Dict[str, Any]:
        return {
            "score": float(
                run.outputs.get("answer") == example.outputs.get("answer")  # type: ignore
            )
        }

    results = await aevaluate(
        target, data=dataset_name, evaluators=[evaluator], client=langchain_client
    )

    assert len(results) == 2
    async for result in results:
        assert result["evaluation_results"]["results"][0].score == 1.0

    safe_delete_dataset(langchain_client, dataset_name=dataset_name)


def test_examples_length_validation(langchain_client: Client) -> None:
    """Test that mismatched lengths raise ValueError for create and update examples."""
    dataset_name = "__test_examples_length_validation" + uuid7().hex
    dataset = _create_dataset(langchain_client, dataset_name)

    # Test create_examples validation
    inputs = [{"text": "hello"}, {"text": "world"}]
    outputs = [{"response": "hi"}]  # One less than inputs
    with pytest.raises(ValueError) as exc_info:
        langchain_client.create_examples(
            inputs=inputs, outputs=outputs, dataset_id=dataset.id
        )
    assert "Length of outputs (1) does not match length of inputs (2)" in str(
        exc_info.value
    )

    # Create some valid examples for testing update
    langchain_client.create_examples(
        inputs=[{"text": "hello"}, {"text": "world"}],
        outputs=[{"response": "hi"}, {"response": "earth"}],
        dataset_id=dataset.id,
    )
    example_ids = [
        example.id for example in langchain_client.list_examples(dataset_id=dataset.id)
    ]

    # Test update_examples validation
    with pytest.raises(ValueError) as exc_info:
        langchain_client.update_examples(
            example_ids=example_ids,
            inputs=[{"text": "new hello"}],  # One less than example_ids
            outputs=[{"response": "new hi"}, {"response": "new earth"}],
        )
    assert "Length of inputs (1) does not match length of examples (2)" in str(
        exc_info.value
    )

    # Clean up
    safe_delete_dataset(langchain_client, dataset_id=dataset.id)


def test_new_create_example(parameterized_multipart_client: Client) -> None:
    """Test create_examples works with multipart style input."""
    dataset_name = "__test_update_examples_output" + uuid7().hex
    dataset = _create_dataset(parameterized_multipart_client, dataset_name)

    supports_attachments = (
        parameterized_multipart_client.info.instance_flags or {}
    ).get("dataset_examples_multipart_enabled", False)

    example_id = uuid7()
    parameterized_multipart_client.create_example(
        dataset_name=dataset_name,
        example_id=example_id,
        inputs={"query": "What's in this image?"},
        outputs={"answer": "A test image"},
        attachments=(
            {
                "image1": ("image/png", b"fake image data 1"),
                "image2": ("image/png", b"fake image data 2"),
            }
            if supports_attachments
            else None
        ),
    )

    retrieved_example = parameterized_multipart_client.read_example(
        example_id=example_id
    )

    assert retrieved_example.id == example_id
    assert retrieved_example.dataset_id == dataset.id
    assert retrieved_example.inputs == {"query": "What's in this image?"}
    assert retrieved_example.outputs == {"answer": "A test image"}
    if supports_attachments:
        assert list(retrieved_example.attachments.keys()) == ["image1", "image2"]

    # Clean up
    parameterized_multipart_client.delete_dataset(dataset_id=dataset.id)


def test_new_create_examples(parameterized_multipart_client: Client) -> None:
    """Test create_examples works with multipart style input."""
    dataset_name = "__test_update_examples_output" + uuid7().hex
    dataset = _create_dataset(parameterized_multipart_client, dataset_name)

    supports_attachments = (
        parameterized_multipart_client.info.instance_flags or {}
    ).get("dataset_examples_multipart_enabled", False)

    example_id = uuid7()
    example = dict(
        id=example_id,
        inputs={"query": "What's in this image?"},
        outputs={"answer": "A test image"},
        attachments={
            "image1": ("image/png", b"fake image data 1"),
            "image2": ("image/png", b"fake image data 2"),
        },
    )

    if not supports_attachments:
        del example["attachments"]

    # Use new way of passing example
    parameterized_multipart_client.create_examples(
        dataset_name=dataset_name, examples=[example]
    )

    retrieved_example = parameterized_multipart_client.read_example(
        example_id=example_id
    )
    examples_in_dataset = parameterized_multipart_client.list_examples(
        dataset_id=dataset.id
    )
    assert len(list(examples_in_dataset)) == 1

    assert retrieved_example.id == example_id
    assert retrieved_example.dataset_id == dataset.id
    assert retrieved_example.inputs == example["inputs"]
    assert retrieved_example.outputs == example["outputs"]
    if supports_attachments:
        assert retrieved_example.attachments.keys() == example["attachments"].keys()

    # Use old way of passing example
    # Can't pass in attachments this way
    example_id2 = uuid7()
    parameterized_multipart_client.create_examples(
        dataset_name=dataset_name,
        ids=[example_id2],
        inputs=[{"query": "What's not in this image?"}],
        outputs=[{"answer": "A real image"}],
    )

    retrieved_example = parameterized_multipart_client.read_example(
        example_id=example_id2
    )
    examples_in_dataset = parameterized_multipart_client.list_examples(
        dataset_id=dataset.id
    )
    assert len(list(examples_in_dataset)) == 2

    assert retrieved_example.id == example_id2
    assert retrieved_example.dataset_id == dataset.id
    assert retrieved_example.inputs == {"query": "What's not in this image?"}
    assert retrieved_example.outputs == {"answer": "A real image"}

    # Clean up
    parameterized_multipart_client.delete_dataset(dataset_id=dataset.id)


def test_new_update_examples(parameterized_multipart_client: Client) -> None:
    """Test update_examples works with multipart style input."""
    dataset_name = "__test_update_examples_output" + uuid7().hex
    dataset = _create_dataset(parameterized_multipart_client, dataset_name)

    supports_attachments = (
        parameterized_multipart_client.info.instance_flags or {}
    ).get("dataset_examples_multipart_enabled", False)

    example_id = uuid7()
    example = dict(
        id=example_id,
        inputs={"query": "What's in this image?"},
        outputs={"answer": "A test image"},
        attachments={
            "image1": ("image/png", b"fake image data 1"),
            "image2": ("image/png", b"fake image data 2"),
        },
    )

    if not supports_attachments:
        del example["attachments"]

    # Create some valid examples for testing update
    parameterized_multipart_client.create_examples(
        dataset_name=dataset_name, examples=[example]
    )

    example_update = ExampleUpdate(
        id=example_id,
        inputs={"query": "What's not in this image?"},
        outputs={"answer": "A real image"},
        attachments=(
            {
                "image3": ("image/png", b"fake image data 3"),
            }
            if supports_attachments
            else None
        ),
    )

    parameterized_multipart_client.update_examples(
        dataset_id=dataset.id, updates=[example_update]
    )

    retrieved_example = parameterized_multipart_client.read_example(
        example_id=example_id
    )

    assert retrieved_example.id == example_id
    assert retrieved_example.dataset_id == dataset.id
    assert retrieved_example.inputs == example_update.inputs
    assert retrieved_example.outputs == example_update.outputs
    if supports_attachments:
        assert retrieved_example.attachments.keys() == example_update.attachments.keys()

    parameterized_multipart_client.update_examples(
        dataset_ids=[dataset.id],
        example_ids=[example_id],
        inputs=[{"query": "What's not in this image?"}],
        outputs=[{"answer": "A real image"}],
        **(
            {
                "attachments": [
                    {
                        "image4": ("image/png", b"fake image data 4"),
                    }
                ]
            }
            if supports_attachments
            else {}
        ),
    )

    retrieved_example = parameterized_multipart_client.read_example(
        example_id=example_id
    )

    assert retrieved_example.id == example_id
    assert retrieved_example.dataset_id == dataset.id
    assert retrieved_example.inputs == example_update.inputs
    assert retrieved_example.outputs == example_update.outputs
    if supports_attachments:
        assert list(retrieved_example.attachments.keys()) == ["image4"]

    # Clean up
    parameterized_multipart_client.delete_dataset(dataset_id=dataset.id)


def test_update_examples_multiple_datasets(langchain_client: Client) -> None:
    """Test update_examples does not work with multiple datasets."""
    dataset_name1 = "__test_update_examples_output" + uuid7().hex
    dataset_name2 = "__test_update_examples_output" + uuid7().hex
    dataset1 = _create_dataset(langchain_client, dataset_name1)
    dataset2 = _create_dataset(langchain_client, dataset_name2)

    example1_id = uuid7()
    example2_id = uuid7()
    example_1 = dict(
        id=example1_id,
        inputs={"query": "What's in this image?"},
        outputs={"answer": "A test image"},
        attachments={
            "image1": ("image/png", b"fake image data 1"),
            "image2": ("image/png", b"fake image data 2"),
        },
    )
    example_2 = dict(
        id=example2_id,
        inputs={"query": "What's in this image?"},
        outputs={"answer": "A test image"},
        attachments={
            "image1": ("image/png", b"fake image data 1"),
            "image2": ("image/png", b"fake image data 2"),
        },
    )

    # Create some valid examples for testing update
    langchain_client.create_examples(dataset_name=dataset_name1, examples=[example_1])

    langchain_client.create_examples(dataset_name=dataset_name2, examples=[example_2])

    example_update_1 = ExampleUpdate(
        id=example1_id,
        inputs={"query": "What's not in this image?"},
        outputs={"answer": "A real image"},
        attachments={
            "image3": ("image/png", b"fake image data 1"),
        },
    )

    example_update_2 = ExampleUpdate(
        id=example2_id,
        inputs={"query": "What's not in this image?"},
        outputs={"answer": "A real image"},
        attachments={
            "image3": ("image/png", b"fake image data 1"),
        },
    )

    with pytest.raises(LangSmithConflictError, match="Dataset ID mismatch"):
        langchain_client.update_examples(
            dataset_id=dataset1.id, updates=[example_update_1, example_update_2]
        )

    with pytest.raises(LangSmithConflictError, match="Dataset ID mismatch"):
        langchain_client.update_examples(
            example_ids=[example1_id, example2_id],
            inputs=[example_update_1.inputs, example_update_2.inputs],
            outputs=[example_update_1.outputs, example_update_2.outputs],
        )

    # Clean up
    langchain_client.delete_dataset(dataset_id=dataset1.id)
    langchain_client.delete_dataset(dataset_id=dataset2.id)


@pytest.mark.xfail(reason="Need to wait for backend changes to go endpoint")
def test_use_source_run_io(langchain_client: Client) -> None:
    dataset_name = "__test_use_source_run_io" + uuid7().hex
    dataset = _create_dataset(langchain_client, dataset_name)

    run_id = uuid7()
    langchain_client.create_run(
        name="foo",
        run_type="llm",
        inputs={"foo": "bar"},
        outputs={"foo": "bar"},
        attachments={
            "test_file": ("text/plain", b"test content"),
        },
        id=run_id,
    )

    retrieved_example = langchain_client.create_example(
        use_source_run_io=True, source_run_id=run_id, dataset_id=dataset.id
    )

    assert retrieved_example.dataset_id == dataset.id
    assert retrieved_example.inputs == {"foo": "bar"}
    assert retrieved_example.outputs == {"foo": "bar"}
    assert list(retrieved_example.attachments.keys()) == ["test_file"]

    # Clean up
    safe_delete_dataset(langchain_client, dataset_id=dataset.id)


@pytest.mark.xfail(reason="Need to wait for backend changes to go endpoint")
def test_use_source_run_attachments(langchain_client: Client) -> None:
    dataset_name = "__test_use_source_run_attachments" + uuid7().hex
    dataset = _create_dataset(langchain_client, dataset_name)

    run_id = uuid7()
    langchain_client.create_run(
        name="foo",
        run_type="llm",
        inputs={"foo": "bar"},
        outputs={"foo": "bar"},
        attachments={
            "test_file": ("text/plain", b"test content"),
        },
        id=run_id,
    )

    retrieved_example = langchain_client.create_example(
        use_source_run_io=True,
        use_source_run_attachments=[],
        source_run_id=run_id,
        dataset_id=dataset.id,
        inputs={"bar": "baz"},
        outputs={"bar": "baz"},
        attachments={
            "test_file2": ("text/plain", b"test content"),
        },
    )

    assert retrieved_example.dataset_id == dataset.id
    assert retrieved_example.inputs == {"bar": "baz"}
    assert retrieved_example.outputs == {"bar": "baz"}
    # source run attachments should override manually passed ones
    assert list(retrieved_example.attachments.keys()) == ["test_file"]

    example_id = uuid7()
    example = dict(
        id=example_id,
        use_source_run_io=True,
        source_run_id=run_id,
        attachments={
            "test_file2": ("text/plain", b"test content"),
        },
        inputs={"bar": "baz"},
        outputs={"bar": "baz"},
    )

    langchain_client.create_examples(dataset_id=dataset.id, examples=[example])

    retrieved_example = langchain_client.read_example(example_id=example_id)

    assert retrieved_example.dataset_id == dataset.id
    assert retrieved_example.inputs == {"foo": "bar"}
    assert retrieved_example.outputs == {"foo": "bar"}
    # source run attachments should override manually passed ones
    assert list(retrieved_example.attachments.keys()) == ["test_file"]

    # Clean up
    safe_delete_dataset(langchain_client, dataset_id=dataset.id)


def test_create_examples_xor_dataset_args(langchain_client: Client) -> None:
    """Test create_examples fails if both dataset_name and dataset_id are provided."""
    dataset_name = "__test_create_examples_xor_dataset_args" + uuid7().hex
    dataset = _create_dataset(langchain_client, dataset_name)

    with pytest.raises(
        ValueError,
        match="Exactly one argument in each of the following "
        "groups must be defined: dataset_id, dataset_name",
    ):
        langchain_client.create_examples(
            dataset_name=dataset_name, dataset_id=dataset.id
        )

    # Clean up
    safe_delete_dataset(langchain_client, dataset_id=dataset.id)


def test_must_pass_uploads_or_inputs(langchain_client: Client) -> None:
    """Test create_examples fails if no uploads or inputs are provided."""
    dataset_name = "__test_must_pass_uploads_or_inputs" + uuid7().hex
    dataset = _create_dataset(langchain_client, dataset_name)

    with pytest.raises(ValueError, match="Must specify either 'examples' or 'inputs.'"):
        langchain_client.create_examples(dataset_id=dataset.id, outputs={"foo": "bar"})

    # Clean up
    safe_delete_dataset(langchain_client, dataset_id=dataset.id)


def test_create_examples_errors(langchain_client: Client) -> None:
    """Test create_examples fails in a number of cases."""
    dataset_name = "__test_create_examples_errors" + uuid7().hex
    dataset = _create_dataset(langchain_client, dataset_name)
    with pytest.raises(
        ValueError, match="Cannot specify 'outputs' when 'examples' is specified."
    ):
        langchain_client.create_examples(
            dataset_id=dataset.id, outputs={"foo": "bar"}, examples=[ExampleCreate()]
        )

    # Clean up
    safe_delete_dataset(langchain_client, dataset_id=dataset.id)


def test_create_examples_batching(parameterized_multipart_client: Client) -> None:
    """Test create_examples batching with large numbers of examples."""
    dataset_name = "__test_batching_" + uuid7().hex
    dataset = _create_dataset(parameterized_multipart_client, dataset_name)

    # Test batching with 250 examples (> default batch_size=200)
    examples = [
        {"inputs": {"q": f"Q{i}"}, "outputs": {"a": f"A{i}"}} for i in range(250)
    ]

    result = parameterized_multipart_client.create_examples(
        dataset_id=dataset.id, examples=examples
    )

    assert result["count"] == 250
    assert len(result["example_ids"]) == 250

    # Verify examples exist
    listed = list(parameterized_multipart_client.list_examples(dataset_id=dataset.id))
    assert len(listed) == 250

    safe_delete_dataset(parameterized_multipart_client, dataset_id=dataset.id)


def test_create_examples_large_multipart_batching(
    parameterized_multipart_client: Client,
) -> None:
    """Test create_examples batching with large multipart payloads."""
    dataset_name = "__test_large_multipart_" + uuid7().hex
    dataset = _create_dataset(parameterized_multipart_client, dataset_name)

    # Create examples with large attachments to simulate >100MB payload
    large_data = b"x" * 5_000_000  # 5MB per attachment
    examples = [
        {
            "inputs": {"question": f"What's in image {i}?"},
            "outputs": {"answer": f"Image {i} content"},
            "attachments": {
                f"image_{i}": ("image/png", large_data),
                f"doc_{i}": ("text/plain", large_data),
            },
        }
        for i in range(20)  # ~100MB total payload
    ]

    result = parameterized_multipart_client.create_examples(
        dataset_id=dataset.id, examples=examples
    )

    assert result["count"] == 20
    assert len(result["example_ids"]) == 20

    # Verify attachments were uploaded
    first_example = parameterized_multipart_client.read_example(
        result["example_ids"][0]
    )
    if hasattr(first_example, "attachments") and first_example.attachments:
        assert len(first_example.attachments) == 2

    safe_delete_dataset(parameterized_multipart_client, dataset_id=dataset.id)


def test_create_examples_large_multipart_batching_parallel(
    parameterized_multipart_client: Client,
) -> None:
    """Test create_examples batching with large multipart payloads in parallel."""
    dataset_name = "__test_large_multipart_" + uuid7().hex
    dataset = _create_dataset(parameterized_multipart_client, dataset_name)

    # Create examples with large attachments to simulate >100MB payload
    large_data = b"x" * 5_000_000  # 5MB per attachment
    examples = [
        {
            "inputs": {"question": f"What's in image {i}?"},
            "outputs": {"answer": f"Image {i} content"},
            "attachments": {
                f"image_{i}": ("image/png", large_data),
                f"doc_{i}": ("text/plain", large_data),
            },
        }
        for i in range(20)  # ~100MB total payload
    ]

    result = parameterized_multipart_client.create_examples(
        dataset_id=dataset.id, examples=examples, max_concurrency=3
    )

    assert result["count"] == 20
    assert len(result["example_ids"]) == 20

    # Verify attachments were uploaded
    first_example = parameterized_multipart_client.read_example(
        result["example_ids"][0]
    )
    if hasattr(first_example, "attachments") and first_example.attachments:
        assert len(first_example.attachments) == 2

    safe_delete_dataset(parameterized_multipart_client, dataset_id=dataset.id)


def test_create_examples_invalid_max_concurrency(
    parameterized_multipart_client: Client,
) -> None:
    """Test that invalid max_concurrency values raise errors."""
    dataset_name = "__test_invalid_concurrency_" + uuid7().hex
    dataset = _create_dataset(parameterized_multipart_client, dataset_name)
    examples = [{"inputs": {"q": "Q1"}, "outputs": {"a": "A1"}}]

    # Test max_concurrency < 1
    with pytest.raises(ValueError, match="max_concurrency must be between 1 and 3"):
        parameterized_multipart_client.create_examples(
            dataset_id=dataset.id, examples=examples, max_concurrency=0
        )

    # Test max_concurrency > 3
    with pytest.raises(ValueError, match="max_concurrency must be between 1 and 3"):
        parameterized_multipart_client.create_examples(
            dataset_id=dataset.id, examples=examples, max_concurrency=4
        )

    safe_delete_dataset(parameterized_multipart_client, dataset_id=dataset.id)


def test_create_examples_boundary_concurrency(
    parameterized_multipart_client: Client,
) -> None:
    """Test max_concurrency boundary values (1 and 3)."""
    dataset_name = "__test_boundary_" + uuid7().hex
    dataset = _create_dataset(parameterized_multipart_client, dataset_name)
    examples = [
        {"inputs": {"q": f"Q{i}"}, "outputs": {"a": f"A{i}"}} for i in range(50)
    ]

    # Test min value (sequential)
    result1 = parameterized_multipart_client.create_examples(
        dataset_id=dataset.id, examples=examples, max_concurrency=1
    )
    assert result1["count"] == 50
    assert len(result1["example_ids"]) == 50

    # Test max value (max parallelism)
    examples2 = [
        {"inputs": {"q": f"Q{i}_2"}, "outputs": {"a": f"A{i}_2"}} for i in range(50)
    ]
    result2 = parameterized_multipart_client.create_examples(
        dataset_id=dataset.id, examples=examples2, max_concurrency=3
    )
    assert result2["count"] == 50
    assert len(result2["example_ids"]) == 50

    # Verify all examples exist
    listed = list(parameterized_multipart_client.list_examples(dataset_id=dataset.id))
    assert len(listed) == 100

    safe_delete_dataset(parameterized_multipart_client, dataset_id=dataset.id)


def test_create_examples_empty_list(parameterized_multipart_client: Client) -> None:
    """Test create_examples with empty list."""
    dataset_name = "__test_empty_" + uuid7().hex
    dataset = _create_dataset(parameterized_multipart_client, dataset_name)

    # Test max_concurrency > 3
    with pytest.raises(ValueError, match="Must specify either 'examples' or 'inputs.'"):
        parameterized_multipart_client.create_examples(
            dataset_id=dataset.id, examples=[]
        )


@pytest.mark.xfail(reason="Need to wait for backend changes to go endpoint")
def test_use_source_run_io_multiple_examples(langchain_client: Client) -> None:
    dataset_name = "__test_use_source_run_io" + uuid7().hex
    dataset = _create_dataset(langchain_client, dataset_name)

    run_id = uuid7()
    langchain_client.create_run(
        name="foo",
        run_type="llm",
        inputs={"foo": "bar"},
        outputs={"foo": "bar"},
        attachments={
            "test_file": ("text/plain", b"test content"),
            "real_file": ("text/plain", b"real content"),
        },
        id=run_id,
    )

    example_ids = [uuid7(), uuid7(), uuid7()]
    examples = [
        {
            "id": uuid7(),
            "inputs": {"bar": "baz"},
            "outputs": {"bar": "baz"},
            "attachments": {"test_file2": ("text/plain", b"test content")},
            "use_source_run_io": True,
            "use_source_run_attachments": [],
            "source_run_id": run_id,
        },
        {
            "id": uuid7(),
            "inputs": {"bar": "baz"},
            "outputs": {"bar": "baz"},
            "attachments": {"test_file2": ("text/plain", b"test content")},
            "use_source_run_io": False,
            "use_source_run_attachments": ["test_file"],
            "source_run_id": run_id,
        },
        {
            "id": uuid7(),
            "inputs": {"bar": "baz"},
            "outputs": {"bar": "baz"},
            "attachments": {"test_file2": ("text/plain", b"test content")},
            "use_source_run_io": True,
            "use_source_run_attachments": ["test_file"],
            "source_run_id": run_id,
        },
    ]
    langchain_client.create_examples(examples=examples, dataset_id=dataset.id)

    example_1 = langchain_client.read_example(example_id=example_ids[0])
    example_2 = langchain_client.read_example(example_id=example_ids[1])
    example_3 = langchain_client.read_example(example_id=example_ids[2])

    assert example_1.dataset_id == dataset.id
    assert example_1.inputs == {"foo": "bar"}
    assert example_1.outputs == {"foo": "bar"}
    assert sorted(example_1.attachments.keys()) == ["real_file", "test_file"]

    assert example_2.dataset_id == dataset.id
    assert example_2.inputs == {"bar": "baz"}
    assert example_2.outputs == {"bar": "baz"}
    assert sorted(example_2.attachments.keys()) == ["test_file"]

    assert example_3.dataset_id == dataset.id
    assert example_3.inputs == {"foo": "bar"}
    assert example_3.outputs == {"foo": "bar"}
    assert sorted(example_3.attachments.keys()) == ["real_file", "test_file"]

    # Clean up
    safe_delete_dataset(langchain_client, dataset_id=dataset.id)


def test_update_example_with_attachments_operations(langchain_client: Client) -> None:
    """Test updating an example with attachment operations."""
    dataset_name = "__test_update_example_attachments" + uuid7().hex
    if langchain_client.has_dataset(dataset_name=dataset_name):
        safe_delete_dataset(langchain_client, dataset_name=dataset_name)
    dataset = _create_dataset(langchain_client, dataset_name)
    example_id = uuid7()
    # Create example with attachments
    example = ExampleCreate(
        id=example_id,
        inputs={"query": "What's in this image?"},
        outputs={"answer": "A test image"},
        attachments={
            "image1": ("image/png", b"fake image data 1"),
            "image2": ("image/png", b"fake image data 2"),
        },
    )
    langchain_client.create_examples(dataset_id=dataset.id, examples=[example])

    # Update example with attachment operations to rename and retain attachments
    attachments_operations = AttachmentsOperations(
        rename={"image1": "renamed_image"},
        retain=["image2"],  # Only keep the renamed image1, drop image2
    )

    langchain_client.update_example(
        example_id=example_id,
        attachments_operations=attachments_operations,
    )

    # Verify the update
    retrieved_example = langchain_client.read_example(
        example_id=example_id,
    )

    # Check that only the renamed attachment exists
    assert len(retrieved_example.attachments) == 2
    assert "renamed_image" in retrieved_example.attachments
    assert "image2" in retrieved_example.attachments
    assert "image1" not in retrieved_example.attachments
    assert (
        retrieved_example.attachments["image2"]["reader"].read() == b"fake image data 2"
    )
    assert (
        retrieved_example.attachments["renamed_image"]["reader"].read()
        == b"fake image data 1"
    )

    langchain_client.update_example(
        dataset_id=dataset.id,
        example_id=example_id,
        attachments={"image3": ("image/png", b"fake image data 3")},
    )

    # Verify the update
    retrieved_example = langchain_client.read_example(
        example_id=example_id,
    )

    # Check that only the renamed attachment exists
    assert len(retrieved_example.attachments) == 1
    assert "image3" in retrieved_example.attachments
    assert (
        retrieved_example.attachments["image3"]["reader"].read() == b"fake image data 3"
    )

    # Clean up
    safe_delete_dataset(langchain_client, dataset_id=dataset.id)


def test_bulk_update_examples_with_attachments_operations(
    langchain_client: Client,
) -> None:
    """Test bulk updating examples with attachment operations."""
    dataset_name = "__test_bulk_update_attachments" + uuid7().hex
    if langchain_client.has_dataset(dataset_name=dataset_name):
        safe_delete_dataset(langchain_client, dataset_name=dataset_name)
    dataset = _create_dataset(langchain_client, dataset_name)

    example_id1, example_id2 = uuid7(), uuid7()
    # Create two examples with attachments
    example1 = ExampleCreate(
        id=example_id1,
        inputs={"query": "What's in this image?"},
        outputs={"answer": "A test image 1"},
        attachments={
            "image1": ("image/png", b"fake image data 1"),
            "extra": ("text/plain", b"extra data"),
        },
    )
    example2 = ExampleCreate(
        id=example_id2,
        inputs={"query": "What's in this image?"},
        outputs={"answer": "A test image 2"},
        attachments={
            "image2": ("image/png", b"fake image data 2"),
            "extra": ("text/plain", b"extra data"),
        },
    )

    created_examples = langchain_client.upload_examples_multipart(
        dataset_id=dataset.id,
        uploads=[example1, example2],
    )
    assert len(created_examples["example_ids"]) == 2
    assert str(example_id1) in created_examples["example_ids"]
    assert str(example_id2) in created_examples["example_ids"]

    # Update both examples with different attachment operations
    attachments_operations = [
        AttachmentsOperations(
            rename={"image1": "renamed_image1"},
        ),
        AttachmentsOperations(retain=["extra"]),
    ]

    langchain_client.update_examples(
        example_ids=[example_id1, example_id2],
        attachments_operations=attachments_operations,
    )

    # Verify the updates
    updated_examples = list(
        langchain_client.list_examples(
            dataset_id=dataset.id,
            example_ids=[example_id1, example_id2],
            include_attachments=True,
        )
    )

    updated_example_1 = next(ex for ex in updated_examples if ex.id == example_id1)
    updated_example_2 = next(ex for ex in updated_examples if ex.id == example_id2)
    # Check first example
    assert len(updated_example_1.attachments) == 1
    assert "renamed_image1" in updated_example_1.attachments
    assert "extra" not in updated_example_1.attachments

    # Check second example
    assert len(updated_example_2.attachments) == 1
    assert "extra" in updated_example_2.attachments
    assert "image2" not in updated_example_2.attachments

    # Check attachment data
    assert (
        updated_example_1.attachments["renamed_image1"]["reader"].read()
        == b"fake image data 1"
    )
    assert updated_example_2.attachments["extra"]["reader"].read() == b"extra data"

    # Clean up
    safe_delete_dataset(langchain_client, dataset_id=dataset.id)


def test_examples_multipart_attachment_path(
    langchain_client: Client, caplog: pytest.LogCaptureFixture
) -> None:
    """Test uploading examples with attachments via multipart endpoint."""
    dataset_name = "__test_upload_examples_multipart" + uuid7().hex
    dataset = _create_dataset(langchain_client, dataset_name)

    file_path = Path(__file__).parent / "test_data/parrot-icon.png"
    example_id = uuid7()
    example = ExampleCreate(
        id=example_id,
        inputs={"text": "hello world"},
        attachments={
            "file1": ("text/plain", b"original content 1"),
            "file2": ("image/png", file_path),
            "file3": ("image/png", file_path),
        },
    )

    # Get the multipart data first to check file handling
    _, _, opened_files_dict = langchain_client._prepare_multipart_data(
        [example],
        include_dataset_id=False,
        dangerously_allow_filesystem=True,
    )

    file_obj = list(opened_files_dict.values())[0]
    fd = file_obj.fileno()

    # Verify the file is open by trying to read from it
    try:
        os.fstat(fd)
        file_is_open = True
    except OSError:
        file_is_open = False
    assert file_is_open, "File should be open after _prepare_multipart_data"

    # Now close the files
    _close_files(list(opened_files_dict.values()))

    # Verify the file is closed by checking if the file descriptor is invalid
    try:
        os.fstat(fd)
        file_is_closed = False
    except OSError:
        file_is_closed = True
    assert file_is_closed, "File should be closed after _close_files"

    created_examples = langchain_client.upload_examples_multipart(
        dataset_id=dataset.id, uploads=[example], dangerously_allow_filesystem=True
    )
    assert created_examples["count"] == 1

    # Verify the upload
    retrieved = langchain_client.read_example(example_id)

    assert len(retrieved.attachments) == 3
    assert "file1" in retrieved.attachments
    assert "file2" in retrieved.attachments
    assert "file3" in retrieved.attachments
    assert retrieved.attachments["file1"]["reader"].read() == b"original content 1"
    assert (
        retrieved.attachments["file2"]["reader"].read()
        == (Path(__file__).parent / "test_data/parrot-icon.png").read_bytes()
    )
    assert (
        retrieved.attachments["file3"]["reader"].read()
        == (Path(__file__).parent / "test_data/parrot-icon.png").read_bytes()
    )

    example_update = ExampleUpdate(
        id=example_id,
        attachments={
            "new_file1": (
                "image/png",
                file_path,
            ),
            "new_file2": (
                "image/png",
                file_path,
            ),
        },
    )

    langchain_client.update_examples_multipart(
        dataset_id=dataset.id,
        updates=[example_update],
        dangerously_allow_filesystem=True,
    )

    retrieved = langchain_client.read_example(example_id)

    assert len(retrieved.attachments) == 2
    assert "new_file1" in retrieved.attachments
    assert "new_file2" in retrieved.attachments
    assert retrieved.attachments["new_file1"]["reader"].read() == file_path.read_bytes()
    assert retrieved.attachments["new_file2"]["reader"].read() == file_path.read_bytes()

    example_wrong_path = ExampleCreate(
        id=uuid7(),
        inputs={"text": "hello world"},
        attachments={
            "file1": (
                "text/plain",
                Path(__file__).parent / "test_data/not-a-real-file.txt",
            ),
        },
    )

    # Test that missing files are skipped with a warning (like unit tests expect)
    with caplog.at_level(logging.WARNING, logger="langsmith.client"):
        result = langchain_client.upload_examples_multipart(
            dataset_id=dataset.id,
            uploads=[example_wrong_path],
            dangerously_allow_filesystem=True,
        )
        # Should succeed but skip the missing file
        assert (
            result["count"] == 1
        )  # Example is created but without the missing attachment
        assert "Attachment file not found" in caplog.text

    # Clean up
    safe_delete_dataset(langchain_client, dataset_id=dataset.id)


def test_update_examples_multipart(langchain_client: Client) -> None:
    """Test updating examples with attachments via multipart endpoint."""
    dataset_name = "__test_update_examples_multipart" + uuid7().hex
    dataset = _create_dataset(langchain_client, dataset_name)
    example_ids = [uuid7() for _ in range(2)]

    # First create some examples with attachments
    example_1 = ExampleCreate(
        id=example_ids[0],
        inputs={"text": "hello world"},
        attachments={
            "file1": ("text/plain", b"original content 1"),
            "file2": ("text/plain", b"original content 2"),
        },
    )

    example_2 = ExampleCreate(
        id=example_ids[1],
        inputs={"text": "second example"},
        attachments={
            "file3": ("text/plain", b"original content 3"),
            "file4": ("text/plain", b"original content 4"),
        },
    )

    created_examples = langchain_client.upload_examples_multipart(
        dataset_id=dataset.id, uploads=[example_1, example_2]
    )
    assert created_examples["count"] == 2

    # Now create update operations
    update_1 = ExampleUpdate(
        id=example_ids[0],
        inputs={"text": "updated hello world"},
        attachments={
            "new_file1": ("text/plain", b"new content 1"),
        },
        attachments_operations=AttachmentsOperations(
            retain=["file1"],
        ),
    )

    update_2 = ExampleUpdate(
        id=example_ids[1],
        inputs={"text": "updated second example"},
        attachments={
            "new_file2": ("text/plain", b"new content 2"),
        },
        attachments_operations=AttachmentsOperations(retain=["file3"]),
    )

    # Test updating multiple examples at once
    updated_examples = langchain_client.update_examples_multipart(
        dataset_id=dataset.id, updates=[update_1, update_2]
    )
    assert updated_examples["count"] == 2

    # Verify the updates
    updated = list(
        langchain_client.list_examples(
            dataset_id=dataset.id,
            include_attachments=True,
        )
    )

    # Verify first example updates
    example_1_updated = next(ex for ex in updated if ex.id == example_ids[0])
    assert example_1_updated.inputs["text"] == "updated hello world"
    assert "file1" in example_1_updated.attachments
    assert "new_file1" in example_1_updated.attachments
    assert "file2" not in example_1_updated.attachments
    assert (
        example_1_updated.attachments["new_file1"]["reader"].read() == b"new content 1"
    )
    assert (
        example_1_updated.attachments["file1"]["reader"].read() == b"original content 1"
    )

    # Verify second example updates
    example_2_updated = next(ex for ex in updated if ex.id == example_ids[1])
    assert example_2_updated.inputs["text"] == "updated second example"
    assert "file3" in example_2_updated.attachments
    assert "new_file2" in example_2_updated.attachments
    assert "file4" not in example_2_updated.attachments
    assert "file3" in example_2_updated.attachments
    assert "new_file2" in example_2_updated.attachments
    assert "file4" not in example_2_updated.attachments
    assert (
        example_2_updated.attachments["file3"]["reader"].read() == b"original content 3"
    )
    assert (
        example_2_updated.attachments["new_file2"]["reader"].read() == b"new content 2"
    )

    # Test updating non-existent example doesn't do anything
    with pytest.raises(LangSmithNotFoundError):
        langchain_client.update_examples_multipart(
            dataset_id=dataset.id,
            updates=[
                ExampleUpdateWithAttachments(
                    id=uuid7(),
                    inputs={"text": "should fail"},
                )
            ],
        )

    # Test new attachments have priority
    response = langchain_client.update_examples_multipart(
        dataset_id=dataset.id,
        updates=[
            ExampleUpdate(
                id=example_ids[0],
                attachments={
                    "new_file1": ("text/plain", b"new content 1"),
                },
                attachments_operations=AttachmentsOperations(
                    retain=["new_file1"],
                ),
            )
        ],
    )
    assert response["count"] == 1
    example_1_updated = langchain_client.read_example(example_ids[0])
    assert list(example_1_updated.attachments.keys()) == ["new_file1"]
    assert (
        example_1_updated.attachments["new_file1"]["reader"].read() == b"new content 1"
    )

    # Test new attachments have priority
    response = langchain_client.update_examples_multipart(
        dataset_id=dataset.id,
        updates=[
            ExampleUpdate(
                id=example_ids[0],
                attachments={
                    "foo": ("text/plain", b"new content 2"),
                },
                attachments_operations=AttachmentsOperations(
                    rename={"new_file1": "foo"},
                ),
            )
        ],
    )
    assert response["count"] == 1
    example_1_updated = langchain_client.read_example(example_ids[0])
    assert list(example_1_updated.attachments.keys()) == ["foo"]
    assert example_1_updated.attachments["foo"]["reader"].read() == b"new content 2"

    # Clean up
    safe_delete_dataset(langchain_client, dataset_id=dataset.id)


async def test_aevaluate_max_concurrency(langchain_client: Client) -> None:
    """Test max concurrency works as expected."""
    dataset_name = "__test_a_ton_of_feedback" + uuid7().hex
    dataset = _create_dataset(langchain_client, dataset_name)

    examples = [
        ExampleCreate(
            inputs={"query": "What's in this image?"},
            outputs={"answer": "A test image 1"},
        )
        for _ in range(5)
    ]

    langchain_client.upload_examples_multipart(dataset_id=dataset.id, uploads=examples)

    # Takes 2 sec to run all evaluators on an example.
    async def eval_func(inputs, outputs):
        await asyncio.sleep(0.1)
        return {"score": random.random()}

    evaluators = [eval_func] * 20

    async def target(inputs):
        return {"foo": "bar"}

    start_time = time.time()
    await langchain_client.aevaluate(
        target,
        data=dataset_name,
        evaluators=evaluators,
        max_concurrency=4,
    )
    end_time = time.time()

    # should proceed in two rounds (4 examples then 1), taking around 4 seconds
    # total.
    # TODO: Investigate why this requires 10 sec
    assert end_time - start_time < 10
    langchain_client.delete_dataset(dataset_name=dataset.name)


def test_annotation_queue_crud(langchain_client: Client):
    """Test basic CRUD operations for annotation queues."""
    queue_name = f"test_queue_{uuid7().hex[:8]}"
    queue_id = uuid7()

    # Test creation
    queue = langchain_client.create_annotation_queue(
        name=queue_name, description="Test queue", queue_id=queue_id
    )
    assert queue.name == queue_name
    assert queue.id == queue_id

    # Test reading
    read_queue = langchain_client.read_annotation_queue(queue_id)
    assert read_queue.id == queue_id
    assert read_queue.name == queue_name

    # Test updating
    new_name = f"updated_{queue_name}"
    langchain_client.update_annotation_queue(
        queue_id=queue_id, name=new_name, description="Updated description"
    )

    updated_queue = langchain_client.read_annotation_queue(queue_id)
    assert updated_queue.name == new_name

    # Test deletion
    langchain_client.delete_annotation_queue(queue_id)

    # Verify deletion
    queues = list(langchain_client.list_annotation_queues(queue_ids=[queue_id]))
    assert len(queues) == 0


def test_list_annotation_queues(langchain_client: Client):
    """Test listing and filtering annotation queues."""
    queue_names = [f"test_queue_{i}_{uuid7().hex[:8]}" for i in range(3)]
    queue_ids = []

    try:
        # Create test queues
        for name in queue_names:
            queue = langchain_client.create_annotation_queue(
                name=name, description="Test queue"
            )
            queue_ids.append(queue.id)

        # Test listing with various filters
        queues = list(
            langchain_client.list_annotation_queues(queue_ids=queue_ids[:2], limit=2)
        )
        assert len(queues) == 2

        # Test name filter
        queues = list(langchain_client.list_annotation_queues(name=queue_names[0]))
        assert len(queues) == 1
        assert queues[0].name == queue_names[0]

        # Test name_contains filter
        queues = list(
            langchain_client.list_annotation_queues(name_contains="test_queue")
        )
        assert len(queues) >= 3  # Could be more if other tests left queues

    finally:
        # Clean up
        for queue_id in queue_ids:
            langchain_client.delete_annotation_queue(queue_id)


@pytest.mark.slow
def test_annotation_queue_runs(langchain_client: Client):
    """Test managing runs within an annotation queue."""
    queue_name = f"test_queue_{uuid7().hex[:8]}"
    project_name = f"test_project_{uuid7().hex[:8]}"
    # Create a queue
    queue = langchain_client.create_annotation_queue(
        name=queue_name, description="Test queue"
    )

    # Create some test runs
    run_ids = [uuid7() for _ in range(3)]
    for i in range(3):
        langchain_client.create_run(
            name=f"test_run_{i}",
            inputs={"input": f"test_{i}"},
            run_type="llm",
            project_name=project_name,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            id=run_ids[i],
        )

    def _get_run(run_id: ID_TYPE) -> bool:
        try:
            langchain_client.read_run(run_id)  # type: ignore
            return True
        except LangSmithError:
            return False

    wait_for(lambda: _get_run(run_ids[0]))
    wait_for(lambda: _get_run(run_ids[1]))
    wait_for(lambda: _get_run(run_ids[2]))
    # Add runs to queue
    langchain_client.add_runs_to_annotation_queue(queue_id=queue.id, run_ids=run_ids)

    # Test getting run at index
    run_info = langchain_client.get_run_from_annotation_queue(
        queue_id=queue.id, index=0
    )
    assert run_info.id in run_ids

    # Test deleting a run from queue
    langchain_client.delete_run_from_annotation_queue(
        queue_id=queue.id, run_id=run_ids[2]
    )

    # Test that runs are deleted
    with pytest.raises(LangSmithNotFoundError):
        langchain_client.get_run_from_annotation_queue(queue_id=queue.id, index=2)

    run_1 = langchain_client.get_run_from_annotation_queue(queue_id=queue.id, index=0)
    run_2 = langchain_client.get_run_from_annotation_queue(queue_id=queue.id, index=1)
    assert sorted([run_1.id, run_2.id]) == sorted(run_ids[:2])

    # Clean up
    langchain_client.delete_annotation_queue(queue.id)


def test_annotation_queue_with_rubric_instructions(langchain_client: Client):
    """Test CRUD operations on annotation queue with rubric instructions."""
    queue_name = f"test-queue-{str(uuid7())[:8]}"
    project_name = f"test-project-{str(uuid7())[:8]}"
    queue_id = uuid7()

    try:
        # 1. Create an annotation queue
        queue = langchain_client.create_annotation_queue(
            name=queue_name,
            description="Initial description",
            queue_id=queue_id,
            rubric_instructions="This is a rubric instruction",
        )
        assert queue is not None
        assert queue.name == queue_name

        # 1a. Get the annotation queue
        fetched_queue = langchain_client.read_annotation_queue(queue.id)
        assert fetched_queue is not None
        assert fetched_queue.name == queue_name
        assert fetched_queue.rubric_instructions == "This is a rubric instruction"

        # 1b. Update the annotation queue rubric instructions
        new_instructions = "Updated rubric instructions"
        langchain_client.update_annotation_queue(
            queue.id,
            name=queue_name,
            rubric_instructions=new_instructions,
        )
        updated_queue = langchain_client.read_annotation_queue(queue.id)
        assert updated_queue.rubric_instructions == new_instructions
    finally:
        # 6. Delete the annotation queue
        langchain_client.delete_annotation_queue(queue_id)

        # Clean up the project
        if langchain_client.has_project(project_name=project_name):
            langchain_client.delete_project(project_name=project_name)


def test_annotation_queue_with_rubric_instructions_2(langchain_client: Client):
    """Test CRUD operations on annotation queue with rubric instructions."""
    queue_name = f"test-queue-{str(uuid7())[:8]}"
    project_name = f"test-project-{str(uuid7())[:8]}"
    queue_id = uuid7()

    try:
        # 1. Create an annotation queue without rubric instructions
        queue = langchain_client.create_annotation_queue(
            name=queue_name,
            description="Initial description",
            queue_id=queue_id,
        )
        assert queue is not None
        assert queue.name == queue_name

        # 1a. Get the annotation queue
        fetched_queue = langchain_client.read_annotation_queue(queue.id)
        assert fetched_queue is not None
        assert fetched_queue.name == queue_name
        assert fetched_queue.rubric_instructions is None

        # 1b. Update the annotation queue rubric instructions
        new_instructions = "Updated rubric instructions"
        langchain_client.update_annotation_queue(
            queue.id,
            name=queue_name,
            rubric_instructions=new_instructions,
        )
        updated_queue = langchain_client.read_annotation_queue(queue.id)
        assert updated_queue.rubric_instructions == new_instructions
    finally:
        # 6. Delete the annotation queue
        langchain_client.delete_annotation_queue(queue_id)

        # Clean up the project
        if langchain_client.has_project(project_name=project_name):
            langchain_client.delete_project(project_name=project_name)


@pytest.mark.skip(reason="flaky")
def test_list_runs_with_child_runs(langchain_client: Client):
    """Test listing runs with child runs."""
    project_name = f"test-project-{str(uuid7())[:8]}"
    if langchain_client.has_project(project_name=project_name):
        langchain_client.delete_project(project_name=project_name)
    try:
        parent_run_id = uuid7()
        child_run_id = uuid7()

        @traceable(client=langchain_client, project_name=project_name)
        def parent():
            @traceable(client=langchain_client, project_name=project_name)
            def child():
                return "From child"

            return child(langsmith_extra={"run_id": child_run_id}) + "|From parent"

        result = parent(langsmith_extra={"run_id": parent_run_id})
        assert result == "From child|From parent"
        wait_for(
            lambda: _get_run(parent_run_id, langchain_client=langchain_client),
            max_sleep_time=10,
        )
        no_child_run = langchain_client.read_run(parent_run_id)
        assert no_child_run.id == parent_run_id
        assert no_child_run.child_runs is None
        run = langchain_client.read_run(parent_run_id, load_child_runs=True)
        assert run.child_runs is not None
        assert run.child_runs[0].id == child_run_id
        assert run.child_runs[0].outputs == {"output": "From child"}
    finally:
        if langchain_client.has_project(project_name=project_name):
            langchain_client.delete_project(project_name=project_name)


@pytest.mark.skip(reason="Flakey")
def test_run_ops_buffer_integration(langchain_client: Client) -> None:
    project_name = f"test-run-ops-buffer-{str(uuid7())[:8]}"

    # Clean up existing project if it exists
    if langchain_client.has_project(project_name=project_name):
        langchain_client.delete_project(project_name=project_name)

    # Create client with run_ops_buffer functionality
    def modify_runs(runs):
        """Modify run inputs/outputs by adding custom fields and transforming data."""
        for run in runs:
            # Add custom metadata
            if "extra" in run and isinstance(run["extra"], dict):
                run["extra"]["custom_processed"] = True
                run["extra"]["processing_timestamp"] = time.time()

            # Modify inputs if they exist
            if "inputs" in run and isinstance(run["inputs"], dict):
                run["inputs"]["processed"] = True
                run["inputs"]["original_input_count"] = len(run["inputs"])

            # Modify outputs if they exist
            if "outputs" in run and isinstance(run["outputs"], dict):
                run["outputs"]["processed"] = True
                run["outputs"]["original_output_count"] = len(run["outputs"])

        return runs

    buffer_client = Client(
        api_url=langchain_client.api_url,
        api_key=langchain_client.api_key,
        process_buffered_run_ops=modify_runs,
        run_ops_buffer_size=2,  # Small buffer for quick testing
        run_ops_buffer_timeout_ms=1000,  # 1 second timeout
    )

    try:
        # Create test runs that will be buffered and processed
        run_ids = []

        for i in range(3):
            run_id = uuid7()
            run_ids.append(run_id)
            start_time = datetime.datetime.now(datetime.timezone.utc)
            buffer_client.create_run(
                id=run_id,
                name=f"test_buffered_run_{i}",
                run_type="llm",
                inputs={"text": f"input_{i}", "index": i},
                project_name=project_name,
                trace_id=run_id,
                dotted_order=f"{start_time.strftime('%Y%m%dT%H%M%S%fZ')}{str(run_id)}",
                start_time=start_time,
                extra={},
            )

            # Update with outputs
            buffer_client.update_run(
                run_id,
                outputs={"result": f"output_{i}", "processed_index": i * 2},
                trace_id=run_id,
                dotted_order=f"{start_time.strftime('%Y%m%dT%H%M%S%fZ')}{str(run_id)}",
            )

        # Flush to ensure all runs are processed
        buffer_client.flush()

        # Wait for runs to be created and processed
        for run_id in run_ids:
            wait_for(
                lambda rid=run_id: _get_run(rid, langchain_client=langchain_client),
                max_sleep_time=30,
            )

        # Verify that the modifications were applied in LangSmith
        for i, run_id in enumerate(run_ids):
            stored_run = langchain_client.read_run(run_id)

            # Check that custom metadata was added
            assert stored_run.extra.get("custom_processed") is True
            assert "processing_timestamp" in stored_run.extra

            # Check that inputs were modified
            assert stored_run.inputs["processed"] is True
            assert stored_run.inputs["original_input_count"] == 3  # text + index
            assert stored_run.inputs["text"] == f"input_{i}"
            assert stored_run.inputs["index"] == i

            # Check that outputs were modified
            assert stored_run.outputs["processed"] is True
            assert (
                stored_run.outputs["original_output_count"] == 3
            )  # result + processed_index
            assert stored_run.outputs["result"] == f"output_{i}"
            assert stored_run.outputs["processed_index"] == i * 2

    finally:
        # Clean up
        if buffer_client.has_project(project_name=project_name):
            buffer_client.delete_project(project_name=project_name)


def test_otel_trace_attributes(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LANGSMITH_OTEL_ENABLED", "true")
    get_env_var.cache_clear()
    importlib.reload(langsmith.client)
    importlib.reload(langsmith._internal.otel._otel_client)
    importlib.reload(langsmith._internal.otel._otel_exporter)
    set_tracer_provider(get_otlp_tracer_provider())

    client = Client()

    future = queue.Queue()

    class MockOTELExporter:
        def __init__(self):
            self.original_otel_exporter = client.otel_exporter

        def export_batch(self, run_ops, otel_context_map):
            for op in run_ops:
                try:
                    run_info = self.original_otel_exporter._deserialize_run_info(op)
                    if not run_info:
                        continue
                    if op.operation == "post":
                        span = self.original_otel_exporter._create_span_for_run(
                            op, run_info, otel_context_map.get(op.id)
                        )
                        if span:
                            self.original_otel_exporter._span_info[op.id] = {
                                "span": span,
                                "created_at": time.time(),
                            }
                    else:
                        future.put(
                            self.original_otel_exporter._span_info[op.id]["span"]
                        )
                        self.original_otel_exporter._update_span_for_run(op, run_info)
                except Exception as e:
                    logger.exception(f"Error processing operation {op.id}: {e}")

    client.otel_exporter = MockOTELExporter()

    # Create test data
    run_id = uuid7()
    trace_id = uuid7()
    start_time = datetime.datetime.now(datetime.timezone.utc)
    post_run_data = {
        "id": run_id,
        "trace_id": trace_id,
        "dotted_order": f"{start_time.strftime('%Y%m%dT%H%M%S%fZ')}{str(trace_id)}",
        "session_name": "test-project",
        "name": "OTEL Export Test",
        "inputs": {"prompt": "Hello, OTEL!"},
        "run_type": "llm",
    }

    # Create test batch
    serialized_post_op = serialize_run_dict("post", post_run_data)
    batch = [TracingQueueItem("test_priority_1", serialized_post_op)]

    _otel_tracing_thread_handle_batch(
        client=client,
        tracing_queue=client.tracing_queue,
        batch=batch,
        mark_task_done=False,
    )

    patch_run_data = {
        "id": run_id,
        "trace_id": trace_id,
        "outputs": {"answer": "Hello, User!"},
        "extra": {"metadata": {"foo": "bar"}},
        "tags": ["otel", "test"],
        "dotted_order": f"{start_time.strftime('%Y%m%dT%H%M%S%fZ')}{str(trace_id)}",
    }

    serialized_patch_op = serialize_run_dict("patch", patch_run_data)

    batch = [TracingQueueItem("test_priority_2", serialized_patch_op)]

    _otel_tracing_thread_handle_batch(
        client=client,
        tracing_queue=client.tracing_queue,
        batch=batch,
        mark_task_done=False,
    )

    readable_span = future.get(timeout=0.1)
    readable_span = cast(ReadableSpan, readable_span)
    assert readable_span.attributes[_otel_exporter.GEN_AI_OPERATION_NAME] == "chat"
    assert (
        readable_span.attributes[_otel_exporter.GENAI_PROMPT]
        == '{"prompt":"Hello, OTEL!"}'
    )
    assert (
        readable_span.attributes[_otel_exporter.GENAI_COMPLETION]
        == '{"answer":"Hello, User!"}'
    )


def test_get_experiment_results(langchain_client: Client) -> None:
    """Test get_experiment_results method with evaluation data."""
    dataset_name = "__test_evaluate_attachments" + uuid7().hex
    dataset = _create_dataset(langchain_client, dataset_name)

    # Create example with attachments
    example = ExampleCreate(
        inputs={"question": "What is shown in the image?"},
        outputs={"answer": "test image"},
        attachments={
            "image": ("image/png", b"fake image data for testing"),
        },
    )

    langchain_client.upload_examples_multipart(dataset_id=dataset.id, uploads=[example])

    def target(inputs: Dict[str, Any], attachments: Dict[str, Any]) -> Dict[str, Any]:
        # Verify we receive the attachment data
        assert "image" in attachments
        assert "presigned_url" in attachments["image"]
        image_data = attachments["image"]["reader"]
        assert image_data.read() == b"fake image data for testing"
        return {"answer": "test image"}

    def evaluator(
        outputs: dict, reference_outputs: dict, attachments: dict
    ) -> Dict[str, Any]:
        assert "image" in attachments
        assert "presigned_url" in attachments["image"]
        image_data = attachments["image"]["reader"]
        assert image_data.read() == b"fake image data for testing"
        return {
            "score": float(
                reference_outputs.get("answer") == outputs.get("answer")  # type: ignore
            )
        }

    results = langchain_client.evaluate(
        target,
        data=dataset_name,
        evaluators=[evaluator],
        num_repetitions=2,
    )

    assert len(results) == 2

    experiment_name = results.experiment_name
    start = time.time()

    while time.time() - start < 15:
        try:
            experiment_results = langchain_client.get_experiment_results(
                name=experiment_name
            )

            # Test that we get run stats
            assert experiment_results["run_stats"] is not None
            run_stats = experiment_results["run_stats"]
            assert "run_count" in run_stats
            assert run_stats["run_count"] > 0

            # Test that we get feedback stats
            assert experiment_results["feedback_stats"] is not None
            feedback_stats = experiment_results["feedback_stats"]
            assert len(feedback_stats) > 0

            # Test that we get examples iterator
            examples_list = list(experiment_results["examples_with_runs"])
            assert len(examples_list) > 0
            # Test with limit parameter
            limited_results = langchain_client.get_experiment_results(
                name=experiment_name, limit=1
            )
            limited_examples = list(limited_results["examples_with_runs"])
            assert len(limited_examples) == 1

            # Test stats are the same (since stats come from project)
            assert (
                limited_results["run_stats"]["run_count"]
                == experiment_results["run_stats"]["run_count"]
            )

            # Test preview mode - should be faster and return preview data
            preview_results = langchain_client.get_experiment_results(
                name=experiment_name, preview=True
            )
            assert len(list(preview_results["examples_with_runs"])) > 0
        except AssertionError:
            if time.time() - start > 11:
                raise
            pass
        break

    safe_delete_dataset(langchain_client, dataset_name=dataset_name)


def test_create_insights_job(langchain_client: Client) -> None:
    chat_histories = [
        [
            {"role": "user", "content": "buy me a coffee"},
            {"role": "assistant", "content": "i dont wanna"},
        ],
        [
            {"role": "user", "content": "how are you?"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {"name": "existential_crisis", "args": {"trigger": "how am i"}}
                ],
            },
            {"role": "tool", "content": "you are panicking"},
            {"role": "assitant", "content": "i am panicking"},
        ],
    ]

    session_name = f"test-insights-{uuid7()})"
    insights_job = langchain_client.generate_insights(
        chat_histories=chat_histories, name=session_name
    )
    assert insights_job.name == session_name
    assert insights_job.status in ["queued", "running", "success"]


def test_feedback_formula_crud_flow(langchain_client: Client) -> None:
    dataset_name = f"feedback-formula-crud-{uuid7().hex}"
    feedback_key = f"overall-quality-{uuid7().hex[:8]}"
    initial_parts = [
        {"part_type": "weighted_key", "weight": 0.6, "key": "accuracy"},
        {"part_type": "weighted_key", "weight": 0.4, "key": "helpfulness"},
    ]
    updated_parts = [
        {"part_type": "weighted_key", "weight": 0.25, "key": "coverage"},
        {"part_type": "weighted_key", "weight": 0.75, "key": "relevance"},
    ]

    dataset = None
    feedback_formula_id = None
    try:
        dataset = langchain_client.create_dataset(dataset_name)
        created_formula = langchain_client.create_feedback_formula(
            feedback_key=feedback_key,
            aggregation_type="sum",
            formula_parts=initial_parts,
            dataset_id=dataset.id,
        )
        feedback_formula_id = created_formula.id

        assert created_formula.dataset_id == dataset.id
        assert created_formula.feedback_key == feedback_key
        assert [part.key for part in created_formula.formula_parts] == [
            part["key"] for part in initial_parts
        ]

        formulas = list(langchain_client.list_feedback_formulas(dataset_id=dataset.id))
        assert any(formula.id == feedback_formula_id for formula in formulas)

        updated_feedback_key = f"{feedback_key}-updated"
        updated_formula = langchain_client.update_feedback_formula(
            feedback_formula_id,
            feedback_key=updated_feedback_key,
            aggregation_type="avg",
            formula_parts=updated_parts,
        )
        assert updated_formula.id == feedback_formula_id
        assert updated_formula.feedback_key == updated_feedback_key
        assert updated_formula.aggregation_type == "avg"
        assert [part.key for part in updated_formula.formula_parts] == [
            part["key"] for part in updated_parts
        ]
        assert [part.weight for part in updated_formula.formula_parts] == [
            part["weight"] for part in updated_parts
        ]

        fetched_formula = langchain_client.get_feedback_formula_by_id(
            feedback_formula_id
        )
        assert fetched_formula.feedback_key == updated_feedback_key
        assert fetched_formula.aggregation_type == "avg"
        assert [part.key for part in fetched_formula.formula_parts] == [
            part["key"] for part in updated_parts
        ]

        langchain_client.delete_feedback_formula(feedback_formula_id)
        deleted_formula_id = feedback_formula_id
        feedback_formula_id = None

        wait_for(
            lambda: deleted_formula_id
            not in {
                formula.id
                for formula in langchain_client.list_feedback_formulas(
                    dataset_id=dataset.id
                )
            },
            max_sleep_time=30,
            sleep_time=1,
        )
    finally:
        if feedback_formula_id is not None:
            try:
                langchain_client.delete_feedback_formula(feedback_formula_id)
            except Exception:
                pass
        if dataset is not None:
            safe_delete_dataset(langchain_client, dataset_id=dataset.id)
