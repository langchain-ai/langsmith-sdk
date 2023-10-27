"""LangSmith langchain_client Integration Tests."""
import io
import os
import random
import string
import time
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

import pytest
from freezegun import freeze_time
from langchain.schema import FunctionMessage, HumanMessage

from langsmith.client import Client
from langsmith.evaluation import EvaluationResult, StringEvaluator
from langsmith.run_trees import RunTree
from langsmith.schemas import DataType
from langsmith.utils import LangSmithConnectionError, LangSmithError


@pytest.fixture
def langchain_client(monkeypatch: pytest.MonkeyPatch) -> Client:
    monkeypatch.setenv("LANGCHAIN_ENDPOINT", "http://localhost:1984")
    return Client()


def test_projects(langchain_client: Client, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test projects."""
    project_names = set([project.name for project in langchain_client.list_projects()])
    new_project = "__Test Project"
    if new_project in project_names:
        langchain_client.delete_project(project_name=new_project)
        project_names = set(
            [project.name for project in langchain_client.list_projects()]
        )
    assert new_project not in project_names

    monkeypatch.setenv("LANGCHAIN_ENDPOINT", "http://localhost:1984")
    langchain_client.create_project(
        project_name=new_project,
        project_extra={"evaluator": "THE EVALUATOR"},
    )
    project = langchain_client.read_project(project_name=new_project)
    assert project.name == new_project
    project_names = set([sess.name for sess in langchain_client.list_projects()])
    assert new_project in project_names
    runs = list(langchain_client.list_runs(project_name=new_project))
    project_id_runs = list(langchain_client.list_runs(project_id=project.id))
    assert len(runs) == len(project_id_runs) == 0  # TODO: Add create_run method
    langchain_client.delete_project(project_name=new_project)

    with pytest.raises(LangSmithError):
        langchain_client.read_project(project_name=new_project)
    assert new_project not in set(
        [sess.name for sess in langchain_client.list_projects()]
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


@freeze_time("2023-01-01")
def test_persist_update_run(
    monkeypatch: pytest.MonkeyPatch, langchain_client: Client
) -> None:
    """Test the persist and update methods work as expected."""
    monkeypatch.setenv("LANGCHAIN_ENDPOINT", "http://localhost:1984")
    project_name = "__test_persist_update_run"
    if project_name in [sess.name for sess in langchain_client.list_projects()]:
        langchain_client.delete_project(project_name=project_name)
    start_time = datetime.now()
    run: dict = dict(
        id=uuid4(),
        name="test_run",
        run_type="llm",
        inputs={"text": "hello world"},
        project_name=project_name,
        api_url=os.getenv("LANGCHAIN_ENDPOINT"),
        execution_order=1,
        start_time=start_time,
        extra={"extra": "extra"},
    )
    langchain_client.create_run(**run)
    run["outputs"] = {"output": ["Hi"]}
    run["extra"]["foo"] = "bar"
    langchain_client.update_run(run["id"], **run)
    for _ in range(5):
        try:
            stored_run = langchain_client.read_run(run["id"])
            break
        except LangSmithError:
            time.sleep(2)

    assert stored_run.id == run["id"]
    assert stored_run.outputs == run["outputs"]
    assert stored_run.start_time == run["start_time"]
    langchain_client.delete_project(project_name=project_name)


@freeze_time("2023-01-01")
def test_evaluate_run(
    monkeypatch: pytest.MonkeyPatch, langchain_client: Client
) -> None:
    """Test persisting runs and adding feedback."""
    monkeypatch.setenv("LANGCHAIN_ENDPOINT", "http://localhost:1984")
    project_name = "__test_evaluate_run"
    dataset_name = "__test_evaluate_run_dataset"
    if project_name in [sess.name for sess in langchain_client.list_projects()]:
        langchain_client.delete_project(project_name=project_name)
    if dataset_name in [dataset.name for dataset in langchain_client.list_datasets()]:
        langchain_client.delete_dataset(dataset_name=dataset_name)

    dataset = langchain_client.create_dataset(dataset_name)
    predicted = "abcd"
    ground_truth = "bcde"
    example = langchain_client.create_example(
        inputs={"input": "hello world"},
        outputs={"output": ground_truth},
        dataset_id=dataset.id,
    )
    parent_run = RunTree(
        name="parent_run",
        run_type="chain",
        inputs={"input": "hello world"},
        project_name=project_name,
        serialized={},
        start_time=datetime.now(),
        reference_example_id=example.id,
    )
    parent_run.post()
    parent_run.end(outputs={"output": predicted})
    parent_run.patch()
    parent_run.wait()

    def jaccard_chars(output: str, answer: str) -> float:
        """Naive Jaccard similarity between two strings."""
        prediction_chars = set(output.strip().lower())
        answer_chars = set(answer.strip().lower())
        intersection = prediction_chars.intersection(answer_chars)
        union = prediction_chars.union(answer_chars)
        return len(intersection) / len(union)

    def grader(run_input: str, run_output: str, answer: Optional[str]) -> dict:
        """Compute the score and/or label for this run."""
        if answer is None:
            value = "AMBIGUOUS"
            score = 0.5
        else:
            score = jaccard_chars(run_output, answer)
            value = "CORRECT" if score > 0.9 else "INCORRECT"
        return dict(score=score, value=value)

    evaluator = StringEvaluator(evaluation_name="Jaccard", grading_function=grader)
    runs = None
    for _ in range(5):
        try:
            runs = list(
                langchain_client.list_runs(
                    project_name=project_name,
                    execution_order=1,
                    error=False,
                )
            )
            break
        except LangSmithError:
            time.sleep(2)
    assert runs is not None
    all_eval_results: List[EvaluationResult] = []
    for run in runs:
        all_eval_results.append(langchain_client.evaluate_run(run, evaluator))


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
    monkeypatch.setenv("LANGCHAIN_ENDPOINT", "http://localhost:1984")
    try:
        langchain_client.read_project(project_name="__test_create_project")
        langchain_client.delete_project(project_name="__test_create_project")
    except LangSmithError:
        pass
    project_name = "__test_create_project"
    project = langchain_client.create_project(project_name=project_name)
    assert project.name == project_name
    langchain_client.delete_project(project_id=project.id)


@freeze_time("2023-01-01")
def test_create_dataset(
    monkeypatch: pytest.MonkeyPatch, langchain_client: Client
) -> None:
    """Test persisting runs and adding feedback."""
    monkeypatch.setenv("LANGCHAIN_ENDPOINT", "http://localhost:1984")
    dataset_name = "__test_create_dataset"
    if dataset_name in [dataset.name for dataset in langchain_client.list_datasets()]:
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
    for name in ["___TEST dataset1", "___TEST dataset2"]:
        datasets = list(langchain_client.list_datasets(dataset_name=name))
        if datasets:
            for dataset in datasets:
                langchain_client.delete_dataset(dataset_id=dataset.id)
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
    assert len(datasets) == 1
    assert datasets[0].id == dataset1.id
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
    assert (
        len(
            list(langchain_client.list_datasets(dataset_ids=[dataset1.id, dataset2.id]))
        )
        == 0
    )


@freeze_time("2023-01-01")
def test_create_run_with_masked_inputs_outputs(
    langchain_client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_name = "__test_create_run_with_masked_inputs_outputs"
    monkeypatch.setenv("LANGCHAIN_HIDE_INPUTS", "true")
    monkeypatch.setenv("LANGCHAIN_HIDE_OUTPUTS", "true")
    for project in langchain_client.list_projects():
        if project.name == project_name:
            langchain_client.delete_project(project_name=project_name)

    run_id = "8bac165f-470e-4bf8-baa0-15f2de4cc706"
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

    run_id2 = "8bac165f-490e-4bf8-baa0-15f2de4cc707"
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

    # Delete dataset
    langchain_client.delete_dataset(dataset_id=dataset.id)
