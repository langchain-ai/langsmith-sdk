import asyncio
import json
from unittest import mock
from uuid import uuid4

import pytest
from agents import Agent, Runner, set_trace_processors

import langsmith
from langsmith.wrappers import OpenAIAgentsTracingProcessor
from tests.integration_tests.test_client import safe_delete_dataset


def _collect_trace_requests(mock_session: mock.MagicMock):
    """Collect and parse trace data from mock session requests."""
    collected_requests = {}
    mock_requests = mock_session.request.call_args_list

    for call in mock_requests:
        if json_bytes := call.kwargs.get("data"):
            json_str = json_bytes.decode("utf-8")
            collected_requests.update(json.loads(json_str))

    return collected_requests


@pytest.mark.asyncio
async def test_openai_agents_tracing_processor():
    """Test that OpenAIAgentsTracingProcessor correctly traces agent runs."""
    mock_session = mock.MagicMock()
    client = langsmith.Client(session=mock_session)

    processor = OpenAIAgentsTracingProcessor(client=client)
    set_trace_processors([processor])

    agent = Agent(
        name="Captain Obvious",
        instructions="You are Captain Obvious, the world's"
        + " most literal technical support agent.",
    )

    question = (
        "Why is my code failing when I try to divide by zero?"
        " I keep getting this error message."
    )

    result = await Runner.run(agent, question)

    # Verify we got a result
    assert result is not None
    assert hasattr(result, "final_output")
    assert result.final_output is not None

    # Give the background thread time to process traces
    await asyncio.sleep(0.5)

    # Verify that trace calls were made to the mock session
    assert mock_session.request.call_count > 0

    # Collect and verify trace data was sent
    collected_requests = _collect_trace_requests(mock_session)

    # Verify we have trace events
    all_events = [
        *collected_requests.get("post", []),
        *collected_requests.get("patch", []),
    ]

    assert len(all_events) > 0, "No trace events were recorded"

    # Verify that we have both start and end events (at least one should have end_time)
    has_start_event = any(event.get("start_time") for event in all_events)
    has_end_event = any(event.get("end_time") for event in all_events)

    assert has_start_event, "No trace start events found"
    assert has_end_event, "No trace end events found"

    # Verify trace contains expected agent information
    agent_runs = [
        event for event in all_events if event.get("name") == "Agent workflow"
    ]
    assert len(agent_runs) > 0, "No agent workflow runs found in trace"


@pytest.mark.xfail(reason="Flaky test - may fail intermittently")
async def test_openai_agents_with_evaluate():
    client = langsmith.Client()

    processor = OpenAIAgentsTracingProcessor(client=client)
    set_trace_processors([processor])

    agent = Agent(
        name="Captain Obvious",
        instructions="You are Captain Obvious, the world's"
        + " most literal technical support agent.",
    )

    question = (
        "Why is my code failing when I try to divide by zero?"
        " I keep getting this error message."
    )

    # Example: Cat image validation
    question = "What type of cat is shown in this image?"
    provided_answer = "This is a tuxedo cat with black and white fur pattern."
    image_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b7/George%2C_a_perfect_example_of_a_tuxedo_cat.jpg/1250px-George%2C_a_perfect_example_of_a_tuxedo_cat.jpg"

    dataset_name = "OpenAI Agent Testing" + str(uuid4().hex[:4])

    if client.has_dataset(dataset_name=dataset_name):
        safe_delete_dataset(client, dataset_name=dataset_name)
    try:
        dataset = client.create_dataset(dataset_name=dataset_name)
        client.create_examples(
            inputs=[
                {
                    "question": question,
                    "answer": provided_answer,
                    "image_url": image_url,
                }
            ],
            outputs=[{"is_correct": True}],
            dataset_id=dataset.id,
        )

        async def run_agent(inputs: dict):
            """Run agent and track the final response."""
            await Runner.run(agent, question)
            return {"result": "foo"}

        async def alignment(outputs: dict, reference_outputs: dict) -> bool:
            """Check if the agent chose the correct route."""
            return True

        experiment = await client.aevaluate(
            run_agent,
            data=dataset_name,
            evaluators=[alignment],
            experiment_prefix="agent-gpt-5-mini",
            max_concurrency=2,
            blocking=True,
        )
        await asyncio.sleep(5)
        experiment_results = client.get_experiment_results(
            name=experiment.experiment_name
        )
        assert experiment_results["stats"].run_count == 1
        assert (
            experiment_results["stats"].feedback_stats.get("alignment", {}).get("n")
            == 1
        )
        assert (
            experiment_results["stats"].feedback_stats.get("alignment", {}).get("avg")
            == 1
        )
        examples = list(experiment_results["examples_with_runs"])
        assert len(examples) == 1
        run = client.read_run(examples[0].runs[0].id, load_child_runs=True)
        assert len(run.child_runs) == 1
        assert run.child_runs[0].name == "Agent workflow"
        assert len(run.child_runs[0].child_runs) == 1
        assert run.child_runs[0].child_runs[0].name == "Captain Obvious"
    finally:
        safe_delete_dataset(client, dataset_name=dataset_name)
