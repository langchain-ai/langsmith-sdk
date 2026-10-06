"""Run a dataset experiment, then resolve the experiment to its project to query it.

Needs LANGSMITH_API_KEY. Run it with `python experiment_traces.py`.
"""

import asyncio
import uuid

import langsmith as ls

client = ls.Client()

dataset = client.create_dataset(f"address-example-{uuid.uuid4().hex[:8]}")
client.create_examples(
    dataset_id=dataset.id,
    inputs=[{"question": "2 + 2"}, {"question": "3 + 3"}],
    outputs=[{"answer": "4"}, {"answer": "6"}],
)


def target(inputs: dict) -> dict:
    left, right = inputs["question"].split(" + ")
    return {"answer": str(int(left) + int(right))}


def exact_match(outputs: dict, reference_outputs: dict) -> bool:
    return outputs["answer"] == reference_outputs["answer"]


results = ls.evaluate(
    target,
    data=dataset.name,
    evaluators=[exact_match],
    experiment_prefix="address-example",
    client=client,
)
experiment = client.read_project(project_name=results.experiment_name)


async def main() -> None:
    address = ls.Experiment(str(experiment.id)).to_api_address()
    project = await client.sessions.resolve(address=address)

    async for run in client.runs.query_v2(
        project_ids=[str(project.session_id)], is_root=True, selects=["ID", "NAME"]
    ):
        print(run.id, run.name)


asyncio.run(main())
