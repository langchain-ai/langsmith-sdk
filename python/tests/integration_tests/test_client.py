"""LangChain+ langchain_client Integration Tests."""
import io
import random
import string
from uuid import uuid4

import pytest

from langchainplus_sdk.client import LangChainPlusClient


@pytest.fixture
def langchain_client(monkeypatch: pytest.MonkeyPatch) -> LangChainPlusClient:
    monkeypatch.setenv("LANGCHAIN_ENDPOINT", "http://localhost:1984")
    return LangChainPlusClient()


def test_sessions(
    langchain_client: LangChainPlusClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test sessions."""
    session_names = set([session.name for session in langchain_client.list_sessions()])
    new_session = f"Session {uuid4()}"
    assert new_session not in session_names

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

    with pytest.raises(ValueError):
        langchain_client.read_session(session_name=new_session)
    assert new_session not in set(
        [sess.name for sess in langchain_client.list_sessions()]
    )
    with pytest.raises(ValueError):
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
