# server.py
import asyncio
import json
import os
import threading

import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from langsmith.run_helpers import get_current_run_tree, tracing_context

load_dotenv(dotenv_path=".env.local", override=True)
os.environ["LANGSMITH_PROJECT"] = "distributed-parent"

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


# Server (Child) ------------------------------------------------------------ #
class ChildState(TypedDict):
    value: int


async def child_node(state: ChildState):
    # First, call the grandchild
    headers: dict[str, str] = {}
    run_tree = get_current_run_tree()
    from langsmith.run_helpers import _get_tracing_context

    distributed_parent_ids = _get_tracing_context().get("distributed_parent_ids", {})
    headers.update(run_tree.to_headers())
    headers["x-distributed-parent-ids"] = json.dumps(distributed_parent_ids)
    async with httpx.AsyncClient(base_url="http://localhost:8001") as client:
        response = await client.post(
            "/tracing", headers=headers, json={"value": state["value"]}
        )
        grandchild_result = response.json()
        print(f"Grandchild graph returned: {grandchild_result['value']}")

    # Then process the result
    generation = llm.invoke(
        "What is "
        + str(grandchild_result["value"])
        + " 1? Respond with a single number, no extra text."
    )
    return {"value": int(generation.content)}


child_builder = StateGraph(ChildState)
child_builder.add_node("child_node", child_node)
child_builder.add_edge(START, "child_node")
child_builder.add_edge("child_node", END)
child_graph = child_builder.compile()

child_app = FastAPI()


@child_app.post("/tracing")
async def child_tracing(request: Request):
    parent_headers = {
        "langsmith-trace": request.headers.get("langsmith-trace"),
        "baggage": request.headers.get("baggage"),
    }
    # THIS IS THE DIFFERENCE
    with tracing_context(
        parent=parent_headers,
        replicas=[
            ("distributed-parent", None),
            ("distributed-child", {"reroot": True}),
        ],
    ):
        data = await request.json()
        result = await child_graph.ainvoke({"value": data["value"]})
        return result


def run_child_server():
    uvicorn.run(child_app, host="0.0.0.0", port=8000)


# Server (Grandchild) ------------------------------------------------------------ #
class GrandchildState(TypedDict):
    value: int


async def grandchild_node(state: GrandchildState):
    generation = llm.invoke(
        "What is "
        + str(state["value"])
        + " 2? Respond with a single number, no extra text."
    )
    return {"value": int(generation.content)}


grandchild_builder = StateGraph(GrandchildState)
grandchild_builder.add_node("grandchild_node", grandchild_node)
grandchild_builder.add_edge(START, "grandchild_node")
grandchild_builder.add_edge("grandchild_node", END)
grandchild_graph = grandchild_builder.compile()

grandchild_app = FastAPI()


@grandchild_app.post("/tracing")
async def grandchild_tracing(request: Request):
    parent_headers = {
        "langsmith-trace": request.headers.get("langsmith-trace"),
        "baggage": request.headers.get("baggage"),
    }
    distributed_parent_ids = {}
    if request.headers.get("x-distributed-parent-ids"):
        distributed_parent_ids = json.loads(request.headers["x-distributed-parent-ids"])
    with tracing_context(
        parent=parent_headers,
        replicas=[
            ("distributed-parent", None),
            ("distributed-child", {"distributed": True}),
            ("distributed-grandchild", {"distributed": True}),
        ],
        distributed_parent_ids=distributed_parent_ids,
    ):
        data = await request.json()
        result = await grandchild_graph.ainvoke({"value": data["value"]})
        return result


def run_grandchild_server():
    uvicorn.run(grandchild_app, host="0.0.0.0", port=8001)


# Client (Parent) ------------------------------------------------------------ #


class ParentState(TypedDict):
    input_value: int
    output_value: int


async def parent_node(state: ParentState) -> ParentState:
    print(f"Parent graph received input: {state['input_value']}")
    headers = {}
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        run_tree = get_current_run_tree()
        headers.update(run_tree.to_headers())
        response = await client.post(
            "/tracing", headers=headers, json={"value": state["input_value"]}
        )
        result = response.json()
        print(f"Child graph returned: {result['value']}")
        return {"input_value": state["input_value"], "output_value": result["value"]}


parent_builder = StateGraph(ParentState)
parent_builder.add_node("parent_node", parent_node)
parent_builder.add_edge(START, "parent_node")
parent_builder.add_edge("parent_node", END)
parent_graph = parent_builder.compile()


async def run_client():
    # Run the parent graph with initial input
    with tracing_context(
        replicas=[
            ("distributed-parent", None),
        ]
    ):
        result = await parent_graph.ainvoke({"input_value": 10, "output_value": 0})
        return result["output_value"]


# ---------- Main ---------- #
async def main():
    # Start child server
    child_thread = threading.Thread(target=run_child_server, daemon=True)
    child_thread.start()

    # Start grandchild server
    grandchild_thread = threading.Thread(target=run_grandchild_server, daemon=True)
    grandchild_thread.start()

    await asyncio.sleep(2)  # Give servers time to start

    result = await run_client()
    print("Server replied:", result)
    await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
