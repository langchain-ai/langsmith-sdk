import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Generator, Optional

import pytest

from langchainplus_sdk.client import LangChainPlusClient
from langchainplus_sdk.run_helpers import traceable
from langchainplus_sdk.run_trees import RunTree
from langchainplus_sdk.schemas import RunTypeEnum


@pytest.fixture
def langchain_client() -> Generator[LangChainPlusClient, None, None]:
    original = os.environ.get("LANGCHAIN_ENDPOINT")
    os.environ["LANGCHAIN_ENDPOINT"] = "http://localhost:1984"
    yield LangChainPlusClient()
    if original is None:
        os.environ.pop("LANGCHAIN_ENDPOINT")
    else:
        os.environ["LANGCHAIN_ENDPOINT"] = original


def test_nested_runs(
    langchain_client: LangChainPlusClient,
):
    session_name = "__My Tracer Session - test_nested_runs"
    if session_name in [session.name for session in langchain_client.list_sessions()]:
        langchain_client.delete_session(session_name=session_name)

    executor = ThreadPoolExecutor(max_workers=1)

    @traceable(run_type="chain")
    def my_run(text: str):
        my_llm_run(text)
        return text

    @traceable(run_type="llm")
    def my_llm_run(text: str):
        # The function needn't accept a run
        return f"Completed: {text}"

    @traceable(run_type="chain", executor=executor)
    def my_chain_run(text: str):
        return my_run(text)

    my_chain_run("foo", session_name=session_name)
    executor.shutdown(wait=True)
    runs = list(langchain_client.list_runs(session_name=session_name))
    assert len(runs) == 3
    runs_dict = {run.name: run for run in runs}
    assert runs_dict["my_chain_run"].parent_run_id is None
    assert runs_dict["my_chain_run"].run_type == "chain"
    assert runs_dict["my_run"].parent_run_id == runs_dict["my_chain_run"].id
    assert runs_dict["my_run"].run_type == "chain"
    assert runs_dict["my_llm_run"].parent_run_id == runs_dict["my_run"].id
    assert runs_dict["my_llm_run"].run_type == "llm"
    assert runs_dict["my_llm_run"].inputs == {"args": ["foo"], "kwargs": {}}
    langchain_client.delete_session(session_name=session_name)


@pytest.mark.asyncio
async def test_nested_async_runs(langchain_client: LangChainPlusClient):
    """Test nested runs with a mix of async and sync functions."""
    session_name = "__My Tracer Session - test_nested_async_runs"
    if session_name in [session.name for session in langchain_client.list_sessions()]:
        langchain_client.delete_session(session_name=session_name)
    executor = ThreadPoolExecutor(max_workers=1)

    @traceable(run_type="chain")
    async def my_run(text: str):
        await my_llm_run(text)
        my_sync_tool(text, my_arg=20)
        return text

    @traceable(run_type="llm")
    async def my_llm_run(text: str):
        # The function needn't accept a run
        return f"Completed: {text}"

    @traceable(run_type="tool")
    def my_sync_tool(text: str, *, my_arg: int = 10):
        return f"Completed: {text} {my_arg}"

    @traceable(run_type="chain", executor=executor)
    async def my_chain_run(text: str):
        return await my_run(text)

    await my_chain_run("foo", session_name=session_name)
    executor.shutdown(wait=True)
    runs = list(langchain_client.list_runs(session_name=session_name))
    assert len(runs) == 4
    runs_dict = {run.name: run for run in runs}
    assert runs_dict["my_chain_run"].parent_run_id is None
    assert runs_dict["my_chain_run"].run_type == "chain"
    assert runs_dict["my_chain_run"].execution_order == 1
    assert runs_dict["my_run"].parent_run_id == runs_dict["my_chain_run"].id
    assert runs_dict["my_run"].run_type == "chain"
    assert runs_dict["my_run"].execution_order == 2
    assert runs_dict["my_llm_run"].parent_run_id == runs_dict["my_run"].id
    assert runs_dict["my_llm_run"].run_type == "llm"
    assert runs_dict["my_llm_run"].inputs == {"args": ["foo"], "kwargs": {}}
    assert runs_dict["my_llm_run"].execution_order == 3
    assert runs_dict["my_sync_tool"].parent_run_id == runs_dict["my_run"].id
    assert runs_dict["my_sync_tool"].run_type == "tool"
    assert runs_dict["my_sync_tool"].inputs == {
        "args": ["foo"],
        "kwargs": {"my_arg": 20},
    }
    assert runs_dict["my_sync_tool"].execution_order == 4
    langchain_client.delete_session(session_name=session_name)


@pytest.mark.asyncio
async def test_nested_async_runs_with_threadpool(langchain_client: LangChainPlusClient):
    """Test nested runs with a mix of async and sync functions."""
    session_name = "__My Tracer Session - test_nested_async_runs_with_threadpol"
    if session_name in [session.name for session in langchain_client.list_sessions()]:
        langchain_client.delete_session(session_name=session_name)

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
            thread_pool.submit(my_tool_run, f"Child Tool {i}", run_tree=run_tree)
        thread_pool.shutdown(wait=True)
        return llm_run_result

    executor = ThreadPoolExecutor(max_workers=1)

    @traceable(run_type="chain", executor=executor)
    async def my_chain_run(text: str, run_tree: RunTree):
        thread_pool = ThreadPoolExecutor(max_workers=3)
        for i in range(2):
            thread_pool.submit(my_run, f"Child {i}", run_tree=run_tree)
        thread_pool.shutdown(wait=True)
        return text

    await my_chain_run("foo", session_name=session_name)
    executor.shutdown(wait=True)
    runs = list(langchain_client.list_runs(session_name=session_name))
    assert len(runs) == 17
    assert sum([run.run_type == RunTypeEnum.llm for run in runs]) == 8
    assert sum([run.name == "async_llm" for run in runs]) == 6
    assert sum([run.name == "my_llm_run" for run in runs]) == 2
    assert sum([run.run_type == RunTypeEnum.tool for run in runs]) == 6
    assert sum([run.run_type == RunTypeEnum.chain for run in runs]) == 3
    langchain_client.delete_session(session_name=session_name)
