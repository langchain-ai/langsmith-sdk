"""LangSmith langchain_client Integration Tests."""

import io
import os
import random
import string
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, cast
from uuid import uuid4

import pytest
from freezegun import freeze_time
from langchain.schema import FunctionMessage, HumanMessage

from langsmith.client import ID_TYPE, Client
from langsmith.schemas import DataType
from langsmith.utils import LangSmithConnectionError, LangSmithError


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
def langchain_client(monkeypatch: pytest.MonkeyPatch) -> Client:
    monkeypatch.setenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")
    return Client()


def test_projects(langchain_client: Client, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test projects."""
    new_project = "__Test Project"
    if langchain_client.has_project(new_project):
        langchain_client.delete_project(project_name=new_project)

    monkeypatch.setenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")
    langchain_client.create_project(
        project_name=new_project,
        project_extra={"evaluator": "THE EVALUATOR"},
    )
    project = langchain_client.read_project(project_name=new_project)
    assert project.name == new_project
    runs = list(langchain_client.list_runs(project_name=new_project))
    project_id_runs = list(langchain_client.list_runs(project_id=project.id))
    assert len(runs) == len(project_id_runs) == 0
    langchain_client.delete_project(project_name=new_project)

    with pytest.raises(LangSmithError):
        langchain_client.read_project(project_name=new_project)
    assert new_project not in set(
        [
            sess.name
            for sess in langchain_client.list_projects(name_contains=new_project)
        ]
    )
    with pytest.raises(LangSmithError):
        langchain_client.delete_project(project_name=new_project)


def test_datasets(langchain_client: Client) -> None:
    """Test datasets."""
    csv_content = "col1,col2\nval1,val2"
    blob_data = io.BytesIO(csv_content.encode("utf-8"))

    description = "Test Dataset"
    input_keys = ["col1"]
    output_keys = ["col2"]
    filename = "".join(random.sample(string.ascii_lowercase, 10)) + ".csv"
    new_dataset = langchain_client.upload_csv(
        csv_file=(filename, blob_data),
        description=description,
        input_keys=input_keys,
        output_keys=output_keys,
    )
    assert new_dataset.id is not None
    assert new_dataset.description == description

    dataset = langchain_client.read_dataset(dataset_id=new_dataset.id)
    dataset_id = dataset.id
    dataset2 = langchain_client.read_dataset(dataset_id=dataset_id)
    assert dataset.id == dataset2.id

    datasets = list(langchain_client.list_datasets())
    assert len(datasets) > 0
    assert dataset_id in [dataset.id for dataset in datasets]

    # Test Example CRD
    example = langchain_client.create_example(
        inputs={"col1": "addedExampleCol1"},
        outputs={"col2": "addedExampleCol2"},
        dataset_id=new_dataset.id,
    )
    example_value = langchain_client.read_example(example.id)
    assert example_value.inputs is not None
    assert example_value.inputs["col1"] == "addedExampleCol1"
    assert example_value.outputs is not None
    assert example_value.outputs["col2"] == "addedExampleCol2"

    examples = list(
        langchain_client.list_examples(dataset_id=new_dataset.id)  # type: ignore
    )
    assert len(examples) == 2
    assert example.id in [example.id for example in examples]

    langchain_client.update_example(
        example_id=example.id,
        inputs={"col1": "updatedExampleCol1"},
        outputs={"col2": "updatedExampleCol2"},
    )
    updated_example = langchain_client.read_example(example.id)
    assert updated_example.id == example.id
    updated_example_value = langchain_client.read_example(updated_example.id)
    assert updated_example_value.inputs["col1"] == "updatedExampleCol1"
    assert updated_example_value.outputs is not None
    assert updated_example_value.outputs["col2"] == "updatedExampleCol2"

    langchain_client.delete_example(example.id)
    examples2 = list(
        langchain_client.list_examples(dataset_id=new_dataset.id)  # type: ignore
    )
    assert len(examples2) == 1

    langchain_client.delete_dataset(dataset_id=dataset_id)


@pytest.mark.skip(reason="This test is flaky")
def test_persist_update_run(langchain_client: Client) -> None:
    """Test the persist and update methods work as expected."""
    project_name = "__test_persist_update_run" + uuid4().hex[:4]
    if langchain_client.has_project(project_name):
        langchain_client.delete_project(project_name=project_name)
    try:
        start_time = datetime.now()
        revision_id = uuid4()
        run: dict = dict(
            id=uuid4(),
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
        langchain_client.update_run(run["id"], **run)
        wait_for(lambda: langchain_client.read_run(run["id"]).end_time is not None)
        stored_run = langchain_client.read_run(run["id"])
        assert stored_run.id == run["id"]
        assert stored_run.outputs == run["outputs"]
        assert stored_run.start_time == run["start_time"]
        assert stored_run.revision_id == str(revision_id)
    finally:
        langchain_client.delete_project(project_name=project_name)


@pytest.mark.parametrize("uri", ["http://localhost:1981", "http://api.langchain.minus"])
def test_error_surfaced_invalid_uri(monkeypatch: pytest.MonkeyPatch, uri: str) -> None:
    monkeypatch.setenv("LANGCHAIN_ENDPOINT", uri)
    monkeypatch.setenv("LANGCHAIN_API_KEY", "test")
    client = Client()
    # expect connect error
    with pytest.raises(LangSmithConnectionError):
        client.create_run("My Run", inputs={"text": "hello world"}, run_type="llm")


@freeze_time("2023-01-01")
def test_create_project(
    monkeypatch: pytest.MonkeyPatch, langchain_client: Client
) -> None:
    """Test the project creation"""
    monkeypatch.setenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")
    project_name = "__test_create_project" + uuid4().hex[:4]
    if langchain_client.has_project(project_name):
        langchain_client.delete_project(project_name=project_name)
    try:
        project = langchain_client.create_project(project_name=project_name)
        assert project.name == project_name
    finally:
        langchain_client.delete_project(project_name=project_name)


@freeze_time("2023-01-01")
def test_create_dataset(
    monkeypatch: pytest.MonkeyPatch, langchain_client: Client
) -> None:
    """Test persisting runs and adding feedback."""
    monkeypatch.setenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")
    dataset_name = "__test_create_dataset"
    if langchain_client.has_dataset(dataset_name=dataset_name):
        langchain_client.delete_dataset(dataset_name=dataset_name)
    dataset = langchain_client.create_dataset(dataset_name, data_type=DataType.llm)
    ground_truth = "bcde"
    langchain_client.create_example(
        inputs={"input": "hello world"},
        outputs={"output": ground_truth},
        dataset_id=dataset.id,
    )
    loaded_dataset = langchain_client.read_dataset(dataset_name=dataset_name)
    assert loaded_dataset.data_type == DataType.llm
    langchain_client.delete_dataset(dataset_id=dataset.id)


@freeze_time("2023-01-01")
def test_list_datasets(langchain_client: Client) -> None:
    if langchain_client.has_dataset(dataset_name="___TEST dataset1"):
        langchain_client.delete_dataset(dataset_name="___TEST dataset1")
    if langchain_client.has_dataset(dataset_name="___TEST dataset2"):
        langchain_client.delete_dataset(dataset_name="___TEST dataset2")
    dataset1 = langchain_client.create_dataset(
        "___TEST dataset1", data_type=DataType.llm
    )
    dataset2 = langchain_client.create_dataset(
        "___TEST dataset2", data_type=DataType.kv
    )
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
            dataset_ids=[dataset1.id, dataset2.id], dataset_name="___TEST dataset1"
        )
    )
    assert len(datasets) == 1
    # Delete datasets
    langchain_client.delete_dataset(dataset_id=dataset1.id)
    langchain_client.delete_dataset(dataset_id=dataset2.id)


@pytest.mark.skip(reason="This test is flaky")
def test_create_run_with_masked_inputs_outputs(
    langchain_client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_name = "__test_create_run_with_masked_inputs_outputs" + uuid4().hex[:4]
    monkeypatch.setenv("LANGCHAIN_HIDE_INPUTS", "true")
    monkeypatch.setenv("LANGCHAIN_HIDE_OUTPUTS", "true")
    if langchain_client.has_project(project_name):
        langchain_client.delete_project(project_name=project_name)
    try:
        run_id = uuid4()
        langchain_client.create_run(
            id=run_id,
            project_name=project_name,
            name="test_run",
            run_type="llm",
            inputs={"prompt": "hello world"},
            outputs={"generation": "hi there"},
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            hide_inputs=True,
            hide_outputs=True,
        )

        run_id2 = uuid4()
        langchain_client.create_run(
            id=run_id2,
            project_name=project_name,
            name="test_run_2",
            run_type="llm",
            inputs={"messages": "hello world 2"},
            start_time=datetime.utcnow(),
            hide_inputs=True,
        )

        langchain_client.update_run(
            run_id2,
            outputs={"generation": "hi there 2"},
            end_time=datetime.utcnow(),
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
    langchain_client.delete_dataset(dataset_id=dataset.id)


@freeze_time("2023-01-01")
def test_batch_ingest_runs(langchain_client: Client) -> None:
    _session = "__test_batch_ingest_runs"
    trace_id = uuid4()
    run_id_2 = uuid4()
    current_time = datetime.utcnow().strftime("%Y%m%dT%H%M%S%fZ")
    later_time = (datetime.utcnow() + timedelta(seconds=1)).strftime("%Y%m%dT%H%M%S%fZ")
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
            "outputs": {"output1": 7, "output2": 8},
        },
    ]
    langchain_client.batch_ingest_runs(create=runs_to_create, update=runs_to_update)
    runs = []
    wait = 2
    for _ in range(15):
        try:
            runs = list(
                langchain_client.list_runs(
                    project_name=_session, run_ids=[str(trace_id), str(run_id_2)]
                )
            )
            if len(runs) == 2:
                break
            raise LangSmithError("Runs not created yet")
        except LangSmithError:
            time.sleep(wait)
    else:
        raise ValueError("Runs not created in time")
    assert len(runs) == 2
    # Write all the assertions here
    runs = sorted(runs, key=lambda x: cast(str, x.dotted_order))
    assert len(runs) == 2

    # Assert inputs and outputs of run 1
    run1 = runs[0]
    assert run1.inputs == {"input1": 1, "input2": 2}
    assert run1.outputs == {"output1": 3, "output2": 4}

    # Assert inputs and outputs of run 2
    run2 = runs[1]
    assert run2.inputs == {"input1": 5, "input2": 6}
    assert run2.outputs == {"output1": 7, "output2": 8}

    langchain_client.delete_project(project_name=_session)


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
    run_id = uuid4()
    run: Dict[str, Any] = {
        "id": run_id,
        "name": "run 1",
        "start_time": datetime.utcnow(),
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
    revision_id = uuid4()
    langchain_client.create_run(**run, revision_id=revision_id)  # type: ignore

    def _get_run(run_id: ID_TYPE, has_end: bool = False) -> bool:
        try:
            r = langchain_client.read_run(run_id)  # type: ignore
            if has_end:
                return r.end_time is not None
            return True
        except LangSmithError:
            return False

    wait_for(lambda: _get_run(run_id))
    created_run = langchain_client.read_run(run_id)
    assert created_run.metadata["foo"] == "bar"
    assert created_run.metadata["revision_id"] == str(revision_id)
    # Update the run
    if add_metadata:
        run["extra"]["metadata"]["foo2"] = "baz"  # type: ignore
        run["tags"] = ["tag3"]
    langchain_client.update_run(run_id, **run)  # type: ignore
    wait_for(lambda: _get_run(run_id, has_end=True))
    updated_run = langchain_client.read_run(run_id)
    assert updated_run.metadata["foo"] == "bar"  # type: ignore
    assert updated_run.revision_id == str(revision_id)
    if add_metadata:
        updated_run.metadata["foo2"] == "baz"  # type: ignore
        assert updated_run.tags == ["tag3"]
    else:
        assert updated_run.tags == ["tag1", "tag2"]
    assert updated_run.extra["runtime"] == created_run.extra["runtime"]  # type: ignore
