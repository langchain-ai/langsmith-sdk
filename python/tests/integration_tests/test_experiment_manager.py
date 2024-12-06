import uuid

from langsmith.client import Client
from langsmith.evaluation._runner import _ExperimentManager


def test_experiment_manager_existing_name():
    client = Client()
    dataset_name = f"Test Dups: {str(uuid.uuid4())}"
    ds = client.create_dataset(dataset_name)
    client.create_example(inputs={"un": "important"}, dataset_id=ds.id)
    prefix = "Some Test Prefix"
    try:
        manager = _ExperimentManager(dataset_name, experiment=prefix, client=client)
        assert manager is not None
        original_name = manager._experiment_name
        assert original_name.startswith(prefix)
        client.create_project(original_name, reference_dataset_id=ds.id)
        manager.start()
        new_name = manager._experiment_name
        assert new_name.startswith(prefix)
        assert new_name != original_name

    finally:
        client.delete_dataset(dataset_id=ds.id)
