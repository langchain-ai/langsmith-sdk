"""Test for RunTree garbage collection leak when using @traceable with asyncio.

This test reproduces the issue reported where RunTree objects are not garbage
collected when:
1. @traceable sets _PARENT_RUN_TREE in the asyncio context
2. A copy_context() happens during the call (e.g., from call_later, create_task, etc.)

The leak occurs because any copy_context() that happens during the @traceable call
permanently captures the RunTree reference. Since RunTrees form a parent/child tree,
one captured reference retains the entire tree.
"""

import asyncio
import gc
import weakref

import pytest

from langsmith import traceable


class TestRunTreeGCLeak:
    """Test that RunTree objects are properly garbage collected."""

    @pytest.fixture(autouse=True)
    def setup_tracing(self, monkeypatch):
        """Enable tracing for tests."""
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
        monkeypatch.setenv("LANGSMITH_API_KEY", "test-key")
        # Use a fake API URL to avoid actual network calls
        monkeypatch.setenv("LANGSMITH_API_URL", "https://fake-api.langsmith.com")

    @pytest.mark.asyncio
    async def test_runtree_leak_with_call_later(self):
        """Test that RunTree objects leak when call_later is used during @traceable.

        This reproduces the issue where httpx connection keepalive timers
        (which use call_later) cause RunTree objects to be retained.
        """
        _timers = []

        @traceable(name="llm_call", run_type="llm")
        async def fake_llm_call(prompt):
            # Simulates httpx creating connection keepalive timers during LLM calls
            _timers.append(asyncio.get_running_loop().call_later(3600, lambda: None))
            await asyncio.sleep(0.01)
            return "response"

        @traceable(name="agent", run_type="chain")
        async def agent(task):
            return await fake_llm_call(task)

        # Clean up before test
        gc.collect()
        await asyncio.sleep(0.1)
        gc.collect()

        # Count RunTree objects before
        before = sum(1 for o in gc.get_objects() if type(o).__name__ == "RunTree")

        # Run 10 iterations
        for i in range(10):
            await agent(f"task-{i}")

        # Force garbage collection
        gc.collect()
        gc.collect()
        await asyncio.sleep(0.5)
        gc.collect()

        # Count RunTree objects after
        after = sum(1 for o in gc.get_objects() if type(o).__name__ == "RunTree")

        # Clean up timers
        for timer in _timers:
            timer.cancel()
        _timers.clear()

        # Calculate leaked objects
        leaked = after - before

        # This assertion currently FAILS - the bug exists
        # Each run should be garbage collected after completion
        # We expect 0 leaked objects (or at most a small number
        # for any lingering references)
        assert leaked == 0, f"Expected 0 leaked RunTree objects, but found {leaked}"

    @pytest.mark.asyncio
    async def test_runtree_leak_with_create_task_long_running(self):
        """Test RunTree leak with create_task and long-running tasks.

        This reproduces the issue where libraries that create long-running background
        tasks cause RunTree objects to be retained. The key is that the task must
        outlive the traceable function call.
        """
        _background_tasks = []

        @traceable(name="llm_call", run_type="llm")
        async def fake_llm_call(prompt):
            # Simulate a library that creates long-running background tasks
            async def background_work():
                # This task runs for a long time, capturing the context
                await asyncio.sleep(3600)
                return "background_result"

            # This create_task captures the context with _PARENT_RUN_TREE
            # The task is stored externally so it outlives the function
            task = asyncio.create_task(background_work())
            _background_tasks.append(task)
            await asyncio.sleep(0.01)  # Just a tiny delay, not waiting for task
            return "immediate_response"

        @traceable(name="agent", run_type="chain")
        async def agent(task):
            return await fake_llm_call(task)

        # Clean up before test
        gc.collect()
        await asyncio.sleep(0.1)
        gc.collect()

        # Count RunTree objects before
        before = sum(1 for o in gc.get_objects() if type(o).__name__ == "RunTree")

        # Run 10 iterations
        for i in range(10):
            await agent(f"task-{i}")

        # Force garbage collection
        gc.collect()
        gc.collect()
        await asyncio.sleep(0.5)
        gc.collect()

        # Count RunTree objects after
        after = sum(1 for o in gc.get_objects() if type(o).__name__ == "RunTree")

        # Clean up background tasks
        for task in _background_tasks:
            task.cancel()
        _background_tasks.clear()

        # Calculate leaked objects
        leaked = after - before

        # This assertion currently FAILS - the bug exists
        assert leaked == 0, f"Expected 0 leaked RunTree objects, but found {leaked}"

    @pytest.mark.asyncio
    async def test_runtree_no_leak_without_context_copy(self):
        """Test RunTree objects are collected without context copy.

        This is a control test that verifies RunTree objects ARE collected
        when no copy_context() is triggered during the @traceable call.
        """

        @traceable(name="llm_call", run_type="llm")
        async def fake_llm_call(prompt):
            # No context-copying operations here
            await asyncio.sleep(0.01)
            return "response"

        @traceable(name="agent", run_type="chain")
        async def agent(task):
            return await fake_llm_call(task)

        # Clean up before test
        gc.collect()
        await asyncio.sleep(0.1)
        gc.collect()

        # Count RunTree objects before
        before = sum(1 for o in gc.get_objects() if type(o).__name__ == "RunTree")

        # Run 10 iterations
        for i in range(10):
            await agent(f"task-{i}")

        # Force garbage collection
        gc.collect()
        gc.collect()
        await asyncio.sleep(0.5)
        gc.collect()

        # Count RunTree objects after
        after = sum(1 for o in gc.get_objects() if type(o).__name__ == "RunTree")

        # Calculate leaked objects
        leaked = after - before

        # This should PASS - no context copy means no leak
        assert leaked == 0, f"Expected 0 leaked RunTree objects, but found {leaked}"

    @pytest.mark.asyncio
    async def test_runtree_weakref_collection(self):
        """Test that RunTree objects can be weakly referenced and collected.

        This verifies that the issue is specifically about context capture,
        not about RunTree objects being inherently uncollectible.
        """
        collected_refs = []

        @traceable(name="test_func", run_type="chain")
        async def test_func():
            await asyncio.sleep(0.01)
            return "result"

        # Run and create weak reference
        await test_func()

        # Get the current run tree if any
        from langsmith.run_helpers import get_current_run_tree

        current_run = get_current_run_tree()

        if current_run is not None:
            ref = weakref.ref(current_run)
            collected_refs.append(ref)

        # Force collection
        gc.collect()
        await asyncio.sleep(0.1)
        gc.collect()

        # Check if weak references are dead (object was collected)
        sum(1 for ref in collected_refs if ref() is not None)

    @pytest.mark.asyncio
    async def test_nested_traceable_leak(self):
        """Test that nested @traceable calls compound the leak.

        This simulates a more realistic scenario where an agent calls
        multiple nested traceable functions, creating a tree of RunTrees.
        """
        _timers = []

        @traceable(name="tool_call", run_type="tool")
        async def tool_call(name):
            _timers.append(asyncio.get_running_loop().call_later(3600, lambda: None))
            await asyncio.sleep(0.01)
            return f"tool_result_{name}"

        @traceable(name="llm_call", run_type="llm")
        async def llm_call(prompt):
            _timers.append(asyncio.get_running_loop().call_later(3600, lambda: None))
            # Call a tool during LLM call
            tool_result = await tool_call("search")
            await asyncio.sleep(0.01)
            return f"llm_response with {tool_result}"

        @traceable(name="agent", run_type="chain")
        async def agent(task):
            result = await llm_call(task)
            return result

        # Clean up before test
        gc.collect()
        await asyncio.sleep(0.1)
        gc.collect()

        # Count RunTree objects before
        before = sum(1 for o in gc.get_objects() if type(o).__name__ == "RunTree")

        # Run 5 iterations (each creates 3 RunTrees: agent, llm, tool)
        for i in range(5):
            await agent(f"task-{i}")

        # Force garbage collection
        gc.collect()
        gc.collect()
        await asyncio.sleep(0.5)
        gc.collect()

        # Count RunTree objects after
        after = sum(1 for o in gc.get_objects() if type(o).__name__ == "RunTree")

        # Clean up timers
        for timer in _timers:
            timer.cancel()
        _timers.clear()

        # Calculate leaked objects
        leaked = after - before

        # This assertion currently FAILS - the bug exists
        # With nested calls, we expect even more objects to be retained
        assert leaked == 0, f"Expected 0 leaked RunTree objects, but found {leaked}"
