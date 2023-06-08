"""LangChain+ langchain_client Integration Tests."""
import io
import os
import random
import string
from typing import List, Optional

import pytest

from langchainplus_sdk.client import LangChainPlusClient
from langchainplus_sdk.evaluation import StringEvaluator
from langchainplus_sdk.run_trees import RunTree, await_all_runs
from langchainplus_sdk.schemas import Feedback
from langchainplus_sdk.utils import LangChainPlusError


@pytest.fixture
def langchain_client(monkeypatch: pytest.MonkeyPatch) -> LangChainPlusClient:
    monkeypatch.setenv("LANGCHAIN_ENDPOINT", "http://localhost:1984")
    return LangChainPlusClient()


def test_sessions(
    langchain_client: LangChainPlusClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test sessions."""
    session_names = set([session.name for session in langchain_client.list_sessions()])
    new_session = "__Test Session"
    if new_session in session_names:
        langchain_client.delete_session(session_name=new_session)
    monkeypatch.setenv("LANGCHAIN_ENDPOINT", "http://localhost:1984")
    langchain_client.create_session(session_name=new_session)
    session = langchain_client.read_session(session_name=new_session)
    assert session.name == new_session
    session_names = set([sess.name for sess in langchain_client.list_sessions()])
    assert new_session in session_names
    runs = list(langchain_client.list_runs(session_name=new_session))
    session_id_runs = list(langchain_client.list_runs(session_id=session.id))
    assert len(runs) == len(session_id_runs) == 0  # TODO: Add create_run method
    langchain_client.delete_session(session_name=new_session)

    with pytest.raises(LangChainPlusError):
        langchain_client.read_session(session_name=new_session)
    assert new_session not in set(
        [sess.name for sess in langchain_client.list_sessions()]
    )
    with pytest.raises(LangChainPlusError):
        langchain_client.delete_session(session_name=new_session)


def test_datasets(langchain_client: LangChainPlusClient) -> None:
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

    deleted_example = langchain_client.delete_example(example.id)
    assert deleted_example.id == example.id
    examples2 = list(
        langchain_client.list_examples(dataset_id=new_dataset.id)  # type: ignore
    )
    assert len(examples2) == 1

    deleted = langchain_client.delete_dataset(dataset_id=dataset_id)
    assert deleted.id == dataset_id


def test_run_tree(
    monkeypatch: pytest.MonkeyPatch, langchain_client: LangChainPlusClient
) -> None:
    """Test persisting runs and adding feedback."""
    monkeypatch.setenv("LANGCHAIN_ENDPOINT", "http://localhost:1984")
    session_name = "__test_run_tree"
    if session_name in [sess.name for sess in langchain_client.list_sessions()]:
        langchain_client.delete_session(session_name=session_name)
    parent_run = RunTree(
        name="parent_run",
        run_type="chain",
        inputs={"text": "hello world"},
        session_name=session_name,
        serialized={},
        api_url=os.getenv("LANGCHAIN_ENDPOINT"),
    )
    child_llm_run = parent_run.create_child(
        name="child_run", run_type="llm", inputs={"text": "hello world"}
    )
    child_chain_run = parent_run.create_child(
        name="child_chain_run", run_type="chain", inputs={"text": "hello world"}
    )
    grandchild_chain_run = child_chain_run.create_child(
        name="grandchild_chain_run", run_type="chain", inputs={"text": "hello world"}
    )
    grandchild_chain_run.end(outputs={"output": ["Hi"]})
    child_chain_run.end(error="AN ERROR")
    child_tool_run = parent_run.create_child(
        name="child_tool_run", run_type="tool", inputs={"text": "hello world"}
    )
    child_tool_run.end(outputs={"output": ["Hi"]})
    child_llm_run.end(outputs={"prompts": ["hello world"]})
    parent_run.end(outputs={"output": ["Hi"]})
    parent_run.post(exclude_child_runs=False)
    await_all_runs()

    runs = list(langchain_client.list_runs(session_name=session_name))
    assert len(runs) == 5
    run_map = {run.name: run for run in runs}
    assert run_map["parent_run"].execution_order == 1
    # The child run and child chain run are executed 'in parallel'
    assert run_map["child_run"].execution_order == 2
    assert run_map["child_chain_run"].execution_order == 2
    assert run_map["grandchild_chain_run"].execution_order == 3
    assert run_map["child_tool_run"].execution_order == 4

    assert run_map["child_run"].parent_run_id == run_map["parent_run"].id
    assert run_map["child_chain_run"].parent_run_id == run_map["parent_run"].id
    assert (
        run_map["grandchild_chain_run"].parent_run_id == run_map["child_chain_run"].id
    )
    assert run_map["child_tool_run"].parent_run_id == run_map["parent_run"].id
    assert run_map["parent_run"].parent_run_id is None

    langchain_client.create_feedback(
        runs[0].id,  # type: ignore
        "supermetric",
        value={"clarity": "good", "fluency": "good", "relevance": "very bad"},
        score=0.5,
    )
    langchain_client.create_feedback(runs[0].id, "a tag")  # type: ignore
    feedbacks = list(
        langchain_client.list_feedback(run_ids=[runs[0].id])  # type: ignore
    )
    assert len(feedbacks) == 2
    assert feedbacks[0].run_id == runs[0].id
    feedback = langchain_client.read_feedback(feedbacks[0].id)
    assert feedback.id == feedbacks[0].id
    langchain_client.delete_feedback(feedback.id)
    with pytest.raises(LangChainPlusError):
        langchain_client.read_feedback(feedback.id)
    assert len(list(langchain_client.list_feedback(run_ids=[runs[0].id]))) == 1

    langchain_client.delete_session(session_name=session_name)
    with pytest.raises(LangChainPlusError):
        langchain_client.read_session(session_name=session_name)


def test_evaluate_run(
    monkeypatch: pytest.MonkeyPatch, langchain_client: LangChainPlusClient
) -> None:
    """Test persisting runs and adding feedback."""
    monkeypatch.setenv("LANGCHAIN_ENDPOINT", "http://localhost:1984")
    session_name = "__test_evaluate_run"
    dataset_name = "__test_evaluate_run_dataset"
    if session_name in [sess.name for sess in langchain_client.list_sessions()]:
        langchain_client.delete_session(session_name=session_name)
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
        session_name=session_name,
        serialized={},
        api_url=os.getenv("LANGCHAIN_ENDPOINT"),
        reference_example_id=example.id,
    )
    parent_run.post()
    parent_run.end(outputs={"output": predicted})
    parent_run.patch()
    await_all_runs()
    run = langchain_client.read_run(str(parent_run.id))
    assert run.outputs == {"output": predicted}

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

    runs = langchain_client.list_runs(
        session_name=session_name,
        execution_order=1,
        error=False,
    )
    all_feedback: List[Feedback] = []
    for run in runs:
        all_feedback.append(langchain_client.evaluate_run(run, evaluator))
    assert len(all_feedback) == 1
    fetched_feedback = list(langchain_client.list_feedback(run_ids=[run.id]))
    assert fetched_feedback[0].id == all_feedback[0].id
    assert fetched_feedback[0].score == jaccard_chars(predicted, ground_truth)
    assert fetched_feedback[0].value == "INCORRECT"
    langchain_client.delete_dataset(dataset_id=dataset.id)
    langchain_client.delete_session(session_name=session_name)
