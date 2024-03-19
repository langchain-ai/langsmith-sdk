"""Beta utility functions to assist in common eval workflows.

These functions may change in the future.
"""

import datetime
import uuid
from typing import List, Optional, Sequence

import langsmith.beta._utils as beta_utils
import langsmith.schemas as ls_schemas
from langsmith.client import Client


def _convert_ids(run_dict: dict, id_map: dict):
    """Convert the IDs in the run dictionary using the provided ID map.

    Parameters:
    - run_dict (dict): The dictionary representing a run.
    - id_map (dict): The dictionary mapping old IDs to new IDs.

    Returns:
    - dict: The updated run dictionary.
    """
    do = run_dict["dotted_order"]
    for k, v in id_map.items():
        do = do.replace(str(k), str(v))
    run_dict["dotted_order"] = do

    if run_dict.get("parent_run_id"):
        run_dict["parent_run_id"] = id_map[run_dict["parent_run_id"]]
    if not run_dict.get("extra"):
        run_dict["extra"] = {}
    return run_dict


def _convert_root_run(root: ls_schemas.Run, run_to_example_map: dict) -> List[dict]:
    """Convert the root run and its child runs to a list of dictionaries.

    Parameters:
    - root (ls_schemas.Run): The root run to convert.
    - run_to_example_map (dict): The dictionary mapping run IDs to example IDs.

    Returns:
    - List[dict]: The list of converted run dictionaries.
    """
    runs_ = [root]
    trace_id = uuid.uuid4()
    id_map = {root.trace_id: trace_id}
    results = []
    while runs_:
        src = runs_.pop()
        src_dict = src.dict(exclude={"parent_run_ids", "child_run_ids", "session_id"})
        id_map[src_dict["id"]] = id_map.get(src_dict["id"], uuid.uuid4())
        src_dict["id"] = id_map[src_dict["id"]]
        src_dict["trace_id"] = id_map[src_dict["trace_id"]]
        if src.child_runs:
            runs_.extend(src.child_runs)
        results.append(src_dict)
    result = [_convert_ids(r, id_map) for r in results]
    result[0]["reference_example_id"] = run_to_example_map[root.id]
    return result


@beta_utils.warn_beta
def convert_runs_to_test(
    runs: Sequence[ls_schemas.Run],
    *,
    dataset_name: str,
    test_project_name: Optional[str] = None,
    client: Optional[Client] = None,
    load_child_runs: bool = False,
    include_outputs: bool = False,
) -> ls_schemas.TracerSession:
    """Convert the following runs to a dataset + test.

    This makes it easy to sample prod runs into a new regression testing
    workflow and compare against a candidate system.

    Internally, this function does the following:
        1. Create a dataset from the provided production run inputs.
        2. Create a new test project.
        3. Clone the production runs and re-upload against the dataset.

    Parameters:
    - runs (Sequence[ls_schemas.Run]): A sequence of runs to be executed as a test.
    - dataset_name (str): The name of the dataset to associate with the test runs.
    - client (Optional[Client]): An optional LangSmith client instance. If not provided,
        a new client will be created.
    - load_child_runs (bool): Whether to load child runs when copying runs.
        Defaults to False.

    Returns:
    - ls_schemas.TracerSession: The project containing the cloned runs.

    Examples:
    --------
    .. code-block:: python

        import langsmith
        import random

        client = langsmith.Client()

        # Randomly sample 100 runs from a prod project
        runs = list(client.list_runs(project_name="My Project", execution_order=1))
        sampled_runs = random.sample(runs, min(len(runs), 100))

        runs_as_test(runs, dataset_name="Random Runs")

        # Select runs named "extractor" whose root traces received good feedback
        runs = client.list_runs(
            project_name="<your_project>",
            filter='eq(name, "extractor")',
            trace_filter='and(eq(feedback_key, "user_score"), eq(feedback_score, 1))'
        )
        runs_as_test(runs, dataset_name="Extraction Good")
    """
    client = client or Client()
    ds = client.create_dataset(dataset_name=dataset_name)
    outputs = [r.outputs for r in runs] if include_outputs else None
    client.create_examples(
        inputs=[r.inputs for r in runs],
        outputs=outputs,
        source_run_ids=[r.id for r in runs],
        dataset_id=ds.id,
    )

    if not load_child_runs:
        runs_to_copy = runs
    else:
        runs_to_copy = [
            client.read_run(r.id, load_child_runs=load_child_runs) for r in runs
        ]

    test_project_name = test_project_name or f"prod-baseline-{uuid.uuid4().hex[:6]}"

    run_to_example_map = {
        e.source_run_id: e.id for e in client.list_examples(dataset_name=dataset_name)
    }

    to_create = [
        run_dict
        for root_run in runs_to_copy
        for run_dict in _convert_root_run(root_run, run_to_example_map)
    ]

    project = client.create_project(
        project_name=test_project_name,
        reference_dataset_id=ds.id,
        metadata={
            "which": "prod-baseline",
        },
    )

    for new_run in to_create:
        client.create_run(**new_run, project_name=test_project_name)

    _ = client.update_project(
        project.id, end_time=datetime.datetime.now(tz=datetime.timezone.utc)
    )
    return project
