import uuid
from datetime import datetime
from unittest.mock import MagicMock, Mock

from langsmith.testing._internal import _get_example_id, _serde_example_values


def test__serde_example_values():
    class Foo:
        def __init__(self, a, b):
            self.a = a
            self.b = b

    results = _serde_example_values({"foo": Foo(1, 2)})
    assert "foo" in results
    assert isinstance(results["foo"], str)


def test__get_id():
    class Foo:
        bar: str = "baz"  # type: ignore

        def __init__(self, a: int, b: int):
            self.a = a
            self.b = b

    def foo(x: Foo):
        return x

    dataset_id = "4e32bff6-5762-4906-8d74-ee2bd0f1d234"
    inputs = {"x": Foo(1, 2)}
    outputs = {"y": Foo(3, 4)}

    result = _get_example_id(dataset_id, inputs, outputs)
    assert isinstance(result, uuid.UUID)


def test_sync_example_metadata_update():
    """Test that metadata updates are properly detected without
    mutating existing metadata.

    This is a regression test for a bug where example.metadata was being mutated
    during the comparison check, causing metadata updates to not be detected properly.
    """
    from langsmith.testing._internal import _LangSmithTestSuite

    # Create a mock client
    mock_client = MagicMock()

    # Create a mock existing example with metadata
    dataset_id = uuid.uuid4()
    existing_example = Mock()
    existing_example.id = uuid.uuid4()
    existing_example.inputs = {"x": 1, "y": 2}
    existing_example.outputs = {"sum": 3}
    existing_example.metadata = {
        "product_area": "supervisor",
        "dataset_split": ["test"],
    }
    existing_example.dataset_id = dataset_id
    existing_example.modified_at = datetime.now()

    # Mock client.read_example to return the existing example
    mock_client.read_example.return_value = existing_example

    # Create mock dataset and experiment
    mock_dataset = Mock()
    mock_dataset.id = dataset_id
    mock_dataset.name = "test_dataset"
    mock_dataset.modified_at = datetime.now()

    mock_experiment = Mock()
    mock_experiment.id = uuid.uuid4()
    mock_experiment.name = "test_experiment"
    mock_experiment.start_time = datetime.now()

    # Create a test suite
    test_suite = _LangSmithTestSuite(
        client=mock_client,
        experiment=mock_experiment,
        dataset=mock_dataset,
    )

    # Call sync_example with new metadata
    new_metadata = {"product_area": "guides"}
    test_suite.sync_example(
        example_id=existing_example.id,
        inputs={"x": 1, "y": 2},
        outputs={"sum": 3},
        metadata=new_metadata,
        split=["test"],
    )

    # Verify that the original example.metadata was not mutated
    assert existing_example.metadata == {
        "product_area": "supervisor",
        "dataset_split": ["test"],
    }

    # Verify that update_example was called because metadata changed
    mock_client.update_example.assert_called_once()

    # Verify the metadata passed to update_example includes dataset_split
    call_args = mock_client.update_example.call_args
    assert call_args[1]["metadata"] == {
        "product_area": "guides",
        "dataset_split": ["test"],
    }


def test_sync_example_metadata_update_without_split():
    """Test that metadata updates work when no split parameter is used.

    This tests the customer's exact scenario: changing metadata value from
    "supervisor" to "guides" without using the split parameter.
    """
    from langsmith.testing._internal import _LangSmithTestSuite

    # Create a mock client
    mock_client = MagicMock()

    # Create a mock existing example with metadata (no dataset_split key)
    dataset_id = uuid.uuid4()
    existing_example = Mock()
    existing_example.id = uuid.uuid4()
    existing_example.inputs = {"x": 1, "y": 2}
    existing_example.outputs = {"sum": 3}
    existing_example.metadata = {"product_area": "supervisor"}  # No dataset_split
    existing_example.dataset_id = dataset_id
    existing_example.modified_at = datetime.now()

    # Mock client.read_example to return the existing example
    mock_client.read_example.return_value = existing_example

    # Create mock dataset and experiment
    mock_dataset = Mock()
    mock_dataset.id = dataset_id
    mock_dataset.name = "test_dataset"
    mock_dataset.modified_at = datetime.now()

    mock_experiment = Mock()
    mock_experiment.id = uuid.uuid4()
    mock_experiment.name = "test_experiment"
    mock_experiment.start_time = datetime.now()

    # Create a test suite
    test_suite = _LangSmithTestSuite(
        client=mock_client,
        experiment=mock_experiment,
        dataset=mock_dataset,
    )

    # Call sync_example with new metadata (NO split parameter)
    new_metadata = {"product_area": "guides"}
    test_suite.sync_example(
        example_id=existing_example.id,
        inputs={"x": 1, "y": 2},
        outputs={"sum": 3},
        metadata=new_metadata,
        split=None,  # No split!
    )

    # Verify that the original example.metadata was not mutated
    assert existing_example.metadata == {"product_area": "supervisor"}

    # Verify that update_example was called because metadata changed
    mock_client.update_example.assert_called_once()

    # Verify the metadata passed to update_example does NOT include dataset_split
    call_args = mock_client.update_example.call_args
    assert call_args[1]["metadata"] == {"product_area": "guides"}
