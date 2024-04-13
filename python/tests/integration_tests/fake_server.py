from fastapi import FastAPI, Request

from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree, trace, tracing_context

fake_app = FastAPI()


@traceable
def fake_function():
    span = get_current_run_tree()
    assert span is not None
    parent_run = span.parent_run
    assert parent_run is not None
    assert "did-propagate" in span.tags or []
    assert span.metadata["some-cool-value"] == 42
    return "Fake function response"


@traceable
def fake_function_two(foo: str):
    span = get_current_run_tree()
    assert span is not None
    parent_run = span.parent_run
    assert parent_run is not None
    assert "did-propagate" in (span.tags or [])
    assert span.metadata["some-cool-value"] == 42
    return "Fake function response"


@traceable
def fake_function_three(foo: str):
    span = get_current_run_tree()
    assert span is not None
    parent_run = span.parent_run
    assert parent_run is not None
    assert "did-propagate" in (span.tags or [])
    assert span.metadata["some-cool-value"] == 42
    return "Fake function response"


@fake_app.post("/fake-route")
async def fake_route(request: Request):
    with trace(
        "Trace",
        project_name="Definitely-not-your-grandpas-project",
        parent=request.headers,
    ):
        fake_function()
    fake_function_two("foo", langsmith_extra={"parent": request.headers})

    with tracing_context(parent=request.headers):
        fake_function_three("foo")
    return {"message": "Fake route response"}
