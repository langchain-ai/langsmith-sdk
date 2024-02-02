import asyncio
import os
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncGenerator, Generator, Optional

import pytest

from langsmith import utils as ls_utils
from langsmith.client import Client
from langsmith.run_helpers import trace, traceable
from langsmith.run_trees import RunTree


@pytest.fixture
def langchain_client() -> Generator[Client, None, None]:
    original = os.environ.get("LANGCHAIN_ENDPOINT")
    os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
    yield Client()
    if original is None:
        os.environ.pop("LANGCHAIN_ENDPOINT")
    else:
        os.environ["LANGCHAIN_ENDPOINT"] = original


def poll_runs_until_count(
    langchain_client: Client,
    project_name: str,
    count: int,
    max_retries: int = 10,
    sleep_time: int = 2,
    require_success: bool = True,
):
    retries = 0
    while retries < max_retries:
        try:
            runs = list(langchain_client.list_runs(project_name=project_name))
            if len(runs) == count:
                if not require_success or all(
                    [run.status == "success" for run in runs]
                ):
                    return runs
        except ls_utils.LangSmithError:
            pass
        time.sleep(sleep_time)
        retries += 1
    raise AssertionError(f"Failed to get {count} runs after {max_retries} attempts.")


def test_nested_runs(
    langchain_client: Client,
):
    project_name = "__My Tracer Project - test_nested_runs"
    if project_name in [project.name for project in langchain_client.list_projects()]:
        langchain_client.delete_project(project_name=project_name)

    executor = ThreadPoolExecutor(max_workers=1)

    @traceable(run_type="chain")
    def my_run(text: str):
        my_llm_run(text)
        return text

    @traceable(run_type="llm")
    def my_llm_run(text: str):
        return f"Completed: {text}"

    @traceable(run_type="chain", executor=executor, tags=["foo", "bar"])
    def my_chain_run(text: str):
        return my_run(text)

    my_chain_run("foo", langsmith_extra=dict(project_name=project_name))
    executor.shutdown(wait=True)
    for _ in range(15):
        try:
            runs = list(langchain_client.list_runs(project_name=project_name))
            assert len(runs) == 3
            break
        except (ls_utils.LangSmithError, AssertionError):
            time.sleep(1)
    else:
        raise AssertionError("Failed to get runs after 15 attempts.")
    assert len(runs) == 3
    runs_dict = {run.name: run for run in runs}
    assert runs_dict["my_chain_run"].parent_run_id is None
    assert runs_dict["my_chain_run"].run_type == "chain"
    assert runs_dict["my_chain_run"].tags == ["foo", "bar"]
    assert runs_dict["my_run"].parent_run_id == runs_dict["my_chain_run"].id
    assert runs_dict["my_run"].run_type == "chain"
    assert runs_dict["my_llm_run"].parent_run_id == runs_dict["my_run"].id
    assert runs_dict["my_llm_run"].run_type == "llm"
    assert runs_dict["my_llm_run"].inputs == {"text": "foo"}
    try:
        langchain_client.delete_project(project_name=project_name)
    except Exception:
        pass


async def test_nested_async_runs(langchain_client: Client):
    """Test nested runs with a mix of async and sync functions."""
    project_name = "__My Tracer Project - test_nested_async_runs"
    if project_name in [project.name for project in langchain_client.list_projects()]:
        langchain_client.delete_project(project_name=project_name)
    executor = ThreadPoolExecutor(max_workers=1)

    @traceable(run_type="chain")
    async def my_run(text: str):
        await my_llm_run(text)
        my_sync_tool(text, my_arg=20)
        return text

    @traceable(run_type="llm")
    async def my_llm_run(text: str):
        # The function needn't accept a run
        await asyncio.sleep(0.2)
        return f"Completed: {text}"

    @traceable(run_type="tool")
    def my_sync_tool(text: str, *, my_arg: int = 10):
        return f"Completed: {text} {my_arg}"

    @traceable(run_type="chain", executor=executor)
    async def my_chain_run(text: str):
        return await my_run(text)

    await my_chain_run("foo", langsmith_extra=dict(project_name=project_name))
    executor.shutdown(wait=True)
    poll_runs_until_count(langchain_client, project_name, 4)
    runs = list(langchain_client.list_runs(project_name=project_name))
    assert len(runs) == 4
    runs_dict = {run.name: run for run in runs}
    assert runs_dict["my_chain_run"].parent_run_id is None
    assert runs_dict["my_chain_run"].run_type == "chain"
    assert runs_dict["my_run"].parent_run_id == runs_dict["my_chain_run"].id
    assert runs_dict["my_run"].run_type == "chain"
    assert runs_dict["my_llm_run"].parent_run_id == runs_dict["my_run"].id
    assert runs_dict["my_llm_run"].run_type == "llm"
    assert runs_dict["my_llm_run"].inputs == {"text": "foo"}
    assert runs_dict["my_sync_tool"].parent_run_id == runs_dict["my_run"].id
    assert runs_dict["my_sync_tool"].run_type == "tool"
    assert runs_dict["my_sync_tool"].inputs == {
        "text": "foo",
        "my_arg": 20,
    }
    langchain_client.delete_project(project_name=project_name)


async def test_nested_async_runs_with_threadpool(langchain_client: Client):
    """Test nested runs with a mix of async and sync functions."""
    project_name = "__My Tracer Project - test_nested_async_runs_with_threadpol"
    if project_name in [project.name for project in langchain_client.list_projects()]:
        langchain_client.delete_project(project_name=project_name)

    @traceable(run_type="llm")
    async def async_llm(text: str):
        return f"Baby LLM: {text}"

    @traceable(run_type="llm")
    def my_llm_run(text: str):
        # The function needn't accept a run
        return f"Completed: {text}"

    @traceable(run_type="tool")
    def my_tool_run(text: str):
        val = asyncio.run(async_llm(text))
        return f"Completed: {text} - val: {val}"

    @traceable(run_type="chain")
    def my_run(text: str, *, run_tree: Optional[RunTree] = None):
        llm_run_result = my_llm_run(text)
        thread_pool = ThreadPoolExecutor(max_workers=1)
        for i in range(3):
            thread_pool.submit(
                my_tool_run, f"Child Tool {i}", langsmith_extra={"run_tree": run_tree}
            )
        thread_pool.shutdown(wait=True)
        return llm_run_result

    executor = ThreadPoolExecutor(max_workers=1)

    @traceable(run_type="chain", executor=executor)
    async def my_chain_run(text: str, run_tree: RunTree):
        thread_pool = ThreadPoolExecutor(max_workers=3)
        for i in range(2):
            thread_pool.submit(
                my_run, f"Child {i}", langsmith_extra=dict(run_tree=run_tree)
            )
        thread_pool.shutdown(wait=True)
        return text

    await my_chain_run("foo", langsmith_extra=dict(project_name=project_name))
    executor.shutdown(wait=True)
    poll_runs_until_count(langchain_client, project_name, 17)
    runs = list(langchain_client.list_runs(project_name=project_name))
    assert len(runs) == 17
    assert sum([run.run_type == "llm" for run in runs]) == 8
    assert sum([run.name == "async_llm" for run in runs]) == 6
    assert sum([run.name == "my_llm_run" for run in runs]) == 2
    assert sum([run.run_type == "tool" for run in runs]) == 6
    assert sum([run.run_type == "chain" for run in runs]) == 3
    # Check that all instances of async_llm have a parent with
    # the same name (my_tool_run)
    name_to_ids_map = defaultdict(list)
    for run in runs:
        name_to_ids_map[run.name].append(run.id)
    for run in runs:
        if run.name == "async_llm":
            assert run.parent_run_id in name_to_ids_map["my_tool_run"]
        if run.name == "my_tool_run":
            assert run.parent_run_id in name_to_ids_map["my_run"]
        if run.name == "my_llm_run":
            assert run.parent_run_id in name_to_ids_map["my_run"]
        if run.name == "my_run":
            assert run.parent_run_id in name_to_ids_map["my_chain_run"]
        if run.name == "my_chain_run":
            assert run.parent_run_id is None


async def test_context_manager(langchain_client: Client) -> None:
    project_name = "__My Tracer Project - test_context_manager"
    if project_name in [project.name for project in langchain_client.list_projects()]:
        langchain_client.delete_project(project_name=project_name)

    @traceable(run_type="llm")
    async def my_llm(prompt: str) -> str:
        return f"LLM {prompt}"

    executor = ThreadPoolExecutor(max_workers=1)
    with trace(
        "my_context", "chain", project_name=project_name, executor=executor
    ) as run_tree:
        await my_llm("foo")
        with trace("my_context2", "chain", run_tree=run_tree) as run_tree2:
            runs = [my_llm("baz"), my_llm("qux")]
            with trace("my_context3", "chain", run_tree=run_tree2):
                await my_llm("quux")
                await my_llm("corge")
            await asyncio.gather(*runs)
        run_tree.end(outputs={"End val": "my_context2"})
    executor.shutdown(wait=True)
    poll_runs_until_count(langchain_client, project_name, 8)
    runs = list(langchain_client.list_runs(project_name=project_name))
    assert len(runs) == 8


async def test_sync_generator(langchain_client: Client):
    project_name = "__My Tracer Project - test_sync_generator"
    if project_name in [project.name for project in langchain_client.list_projects()]:
        langchain_client.delete_project(project_name=project_name)

    @traceable(run_type="chain")
    def my_generator(num: int) -> Generator[str, None, None]:
        for i in range(num):
            yield f"Yielded {i}"

    results = list(my_generator(5, langsmith_extra=dict(project_name=project_name)))
    assert results == ["Yielded 0", "Yielded 1", "Yielded 2", "Yielded 3", "Yielded 4"]
    poll_runs_until_count(langchain_client, project_name, 1, max_retries=20)
    runs = list(langchain_client.list_runs(project_name=project_name))
    run = runs[0]
    assert run.run_type == "chain"
    assert run.name == "my_generator"
    assert run.outputs == {
        "output": ["Yielded 0", "Yielded 1", "Yielded 2", "Yielded 3", "Yielded 4"]
    }


async def test_sync_generator_reduce_fn(langchain_client: Client):
    project_name = "__My Tracer Project - test_sync_generator_reduce_fn"
    if project_name in [project.name for project in langchain_client.list_projects()]:
        langchain_client.delete_project(project_name=project_name)

    def reduce_fn(outputs: list) -> dict:
        return {"my_output": " ".join(outputs)}

    @traceable(run_type="chain", reduce_fn=reduce_fn)
    def my_generator(num: int) -> Generator[str, None, None]:
        for i in range(num):
            yield f"Yielded {i}"

    results = list(my_generator(5, langsmith_extra=dict(project_name=project_name)))
    assert results == ["Yielded 0", "Yielded 1", "Yielded 2", "Yielded 3", "Yielded 4"]
    poll_runs_until_count(langchain_client, project_name, 1, max_retries=20)
    runs = list(langchain_client.list_runs(project_name=project_name))
    run = runs[0]
    assert run.run_type == "chain"
    assert run.name == "my_generator"
    assert run.outputs == {
        "my_output": " ".join(
            ["Yielded 0", "Yielded 1", "Yielded 2", "Yielded 3", "Yielded 4"]
        )
    }


async def test_async_generator(langchain_client: Client):
    project_name = "__My Tracer Project - test_async_generator"
    if project_name in [project.name for project in langchain_client.list_projects()]:
        langchain_client.delete_project(project_name=project_name)

    @traceable(run_type="chain")
    async def my_async_generator(num: int) -> AsyncGenerator[str, None]:
        for i in range(num):
            await asyncio.sleep(0.1)
            yield f"Async yielded {i}"

    results = [
        item
        async for item in my_async_generator(
            5, langsmith_extra=dict(project_name=project_name)
        )
    ]
    assert results == [
        "Async yielded 0",
        "Async yielded 1",
        "Async yielded 2",
        "Async yielded 3",
        "Async yielded 4",
    ]
    poll_runs_until_count(langchain_client, project_name, 1, max_retries=20)
    runs = list(langchain_client.list_runs(project_name=project_name))
    run = runs[0]
    assert run.run_type == "chain"
    assert run.name == "my_async_generator"
    assert run.outputs == {
        "output": [
            "Async yielded 0",
            "Async yielded 1",
            "Async yielded 2",
            "Async yielded 3",
            "Async yielded 4",
        ]
    }


async def test_async_generator_reduce_fn(langchain_client: Client):
    project_name = "__My Tracer Project - test_async_generator_reduce_fn"
    if project_name in [project.name for project in langchain_client.list_projects()]:
        langchain_client.delete_project(project_name=project_name)

    def reduce_fn(outputs: list) -> dict:
        return {"my_output": " ".join(outputs)}

    @traceable(run_type="chain", reduce_fn=reduce_fn)
    async def my_async_generator(num: int) -> AsyncGenerator[str, None]:
        for i in range(num):
            await asyncio.sleep(0.1)
            yield f"Async yielded {i}"

    results = [
        item
        async for item in my_async_generator(
            5, langsmith_extra=dict(project_name=project_name)
        )
    ]
    assert results == [
        "Async yielded 0",
        "Async yielded 1",
        "Async yielded 2",
        "Async yielded 3",
        "Async yielded 4",
    ]

    poll_runs_until_count(langchain_client, project_name, 1, max_retries=20)
    runs = list(langchain_client.list_runs(project_name=project_name))
    run = runs[0]
    assert run.run_type == "chain"
    assert run.name == "my_async_generator"
    assert run.outputs == {
        "my_output": " ".join(
            [
                "Async yielded 0",
                "Async yielded 1",
                "Async yielded 2",
                "Async yielded 3",
                "Async yielded 4",
            ]
        )
    }
