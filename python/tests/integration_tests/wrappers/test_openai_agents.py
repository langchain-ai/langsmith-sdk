import asyncio
import json
from unittest import mock
from uuid import uuid4

import pytest
from agents import Agent, Runner, function_tool, set_trace_processors

import langsmith
from langsmith.wrappers import OpenAIAgentsTracingProcessor, wrap_openai
from tests.integration_tests.test_client import safe_delete_dataset

LS_TEST_CLIENT_INFO = {
    "batch_ingest_config": {
        "use_multipart_endpoint": False,
        "scale_up_qsize_trigger": 1000,
        "scale_up_nthreads_limit": 16,
        "scale_down_nempty_trigger": 4,
        "size_limit": 100,
        "size_limit_bytes": 20971520,
    },
}


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
    import openai

    mock_session = mock.MagicMock()
    client = langsmith.Client(session=mock_session, info=LS_TEST_CLIENT_INFO)

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
    try:
        result = await Runner.run(agent, question)
    except openai.APIConnectionError as e:
        pytest.skip(reason="Openai is having issues" + str(e))

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


@pytest.mark.asyncio
async def test_wrap_openai_nests_under_agent_trace():
    """Test that wrap_openai calls from function tools nest under agent traces."""
    mock_session = mock.MagicMock()
    client = langsmith.Client(session=mock_session, info=LS_TEST_CLIENT_INFO)

    try:
        import openai

        openai_client = wrap_openai(openai.OpenAI(api_key="test-key"))
    except ImportError:
        pytest.skip("openai package not installed")

    # Create a function tool that uses wrap_openai
    @function_tool
    def call_openai_helper(query: str) -> str:
        """A helper function that calls OpenAI using wrap_openai."""
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": query}],
            )
            return response.choices[0].message.content or "No response"
        except Exception as e:
            return f"Error: {e}"

    # Set up the tracing processor
    processor = OpenAIAgentsTracingProcessor(client=client)
    set_trace_processors([processor])

    agent = Agent(
        name="Test Agent",
        instructions="You are a helpful assistant.",
        tools=[call_openai_helper],
    )

    # Run the agent
    try:
        await Runner.run(
            agent, "Use the call_openai_helper tool to answer: What is 2+2?"
        )
    except Exception:
        pass

    await asyncio.sleep(0.5)

    collected_requests = _collect_trace_requests(mock_session)

    all_events = [
        *collected_requests.get("post", []),
        *collected_requests.get("patch", []),
    ]

    assert len(all_events) > 0, "No trace events were recorded"

    runs_by_id = {event["id"]: event for event in all_events if "id" in event}

    agent_runs = [
        event for event in all_events if event.get("name") == "Agent workflow"
    ]
    assert len(agent_runs) > 0, "No agent workflow runs found"

    chat_runs = [event for event in all_events if "ChatOpenAI" in event.get("name", "")]

    if chat_runs:
        for chat_run in chat_runs:
            assert chat_run.get("parent_run_id") is not None, (
                "ChatOpenAI run should have a parent"
            )

            current_id = chat_run.get("parent_run_id")
            found_agent = False
            depth = 0
            max_depth = 10

            while current_id and depth < max_depth:
                parent_run = runs_by_id.get(current_id)
                if not parent_run:
                    break

                if parent_run.get("name") == "Agent workflow":
                    found_agent = True
                    break

                current_id = parent_run.get("parent_run_id")
                depth += 1

            assert found_agent, "ChatOpenAI run should be nested under Agent workflow"

    trace_ids = {event.get("trace_id") for event in all_events if "trace_id" in event}
    assert len(trace_ids) <= 2, (
        f"Expected at most 2 trace_ids (one for the trace, possibly one for root), "
        f"but found {len(trace_ids)}: {trace_ids}"
    )

    # Verify invocation_params with tools are present in trace events
    events_with_tools = [
        event
        for event in all_events
        if event.get("extra", {}).get("invocation_params", {}).get("tools")
    ]
    assert len(events_with_tools) > 0, (
        "No trace events found with invocation_params.tools - "
        "tools should be captured in invocation_params"
    )


@pytest.mark.asyncio
async def test_traceable_decorator_nests_under_agent_trace():
    """Test that @traceable decorated functions nest under agent traces."""
    mock_session = mock.MagicMock()
    client = langsmith.Client(session=mock_session, info=LS_TEST_CLIENT_INFO)

    @langsmith.traceable
    def helper_function(x: int, y: int) -> int:
        return x + y

    @function_tool
    def calculate_sum(a: int, b: int) -> str:
        result = helper_function(a, b)
        return f"The sum is {result}"

    processor = OpenAIAgentsTracingProcessor(client=client)
    set_trace_processors([processor])

    agent = Agent(
        name="Calculator Agent",
        instructions="You are a calculator.",
        tools=[calculate_sum],
    )

    try:
        await Runner.run(agent, "Calculate 5 + 3")
    except Exception:
        pass

    await asyncio.sleep(0.5)

    collected_requests = _collect_trace_requests(mock_session)

    all_events = [
        *collected_requests.get("post", []),
        *collected_requests.get("patch", []),
    ]

    assert len(all_events) > 0, "No trace events were recorded"

    runs_by_id = {event["id"]: event for event in all_events if "id" in event}

    agent_runs = [
        event for event in all_events if event.get("name") == "Agent workflow"
    ]
    assert len(agent_runs) > 0, "No agent workflow runs found"

    helper_runs = [
        event for event in all_events if event.get("name") == "helper_function"
    ]

    if helper_runs:
        for helper_run in helper_runs:
            assert helper_run.get("parent_run_id") is not None, (
                "helper_function run should have a parent"
            )

            current_id = helper_run.get("parent_run_id")
            found_agent = False
            depth = 0
            max_depth = 10

            while current_id and depth < max_depth:
                parent_run = runs_by_id.get(current_id)
                if not parent_run:
                    break

                if parent_run.get("name") == "Agent workflow":
                    found_agent = True
                    break

                current_id = parent_run.get("parent_run_id")
                depth += 1

            assert found_agent, (
                "helper_function run should be nested under Agent workflow"
            )
