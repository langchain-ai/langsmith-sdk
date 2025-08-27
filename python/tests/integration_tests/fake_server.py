from fastapi import FastAPI, Request

from langsmith import traceable
from langsmith.middleware import TracingMiddleware
from langsmith.run_helpers import get_current_run_tree, trace, tracing_context

fake_app = FastAPI()
fake_app.add_middleware(TracingMiddleware)


@traceable
def fake_function():
    span = get_current_run_tree()
    assert span is not None
    assert span.parent_dotted_order
    assert "did-propagate" in span.tags or []
    assert span.metadata["some-cool-value"] == 42
    assert span.session_name == "distributed-tracing"
    return "Fake function response"


@traceable
def fake_function_two(foo: str):
    span = get_current_run_tree()
    assert span is not None
    assert span.parent_dotted_order
    assert "did-propagate" in (span.tags or [])
    assert span.metadata["some-cool-value"] == 42
    assert span.session_name == "distributed-tracing"
    return "Fake function response"


@traceable
def fake_function_three(foo: str):
    span = get_current_run_tree()
    assert span is not None
    assert span.parent_dotted_order
    assert "did-propagate" in (span.tags or [])
    assert span.metadata["some-cool-value"] == 42
    assert span.session_name == "distributed-tracing"
    return "Fake function response"


@fake_app.post("/fake-route")
async def fake_route(request: Request):
    with trace(
        "Trace",
        project_name="Definitely-not-your-grandpas-project",
    ):
        fake_function()
    fake_function_two(
        "foo",
        langsmith_extra={
            "project_name": "Definitely-not-your-grandpas-project",
        },
    )

    with tracing_context(
        parent=request.headers, project_name="Definitely-not-your-grandpas-project"
    ):
        fake_function_three("foo")
    return {"message": "Fake route response"}
