from fastapi import FastAPI, Request

from langsmith import traceable
from langsmith.run_helpers import get_current_span, tracing_context

fake_app = FastAPI()


@traceable
def fake_function():
    span = get_current_span()
    assert span is not None
    parent_run = span.parent_run
    assert parent_run is not None
    assert "did-propagate" in span.tags
    assert span.metadata["some-cool-value"] == 42
    return "Fake function response"


@fake_app.post("/fake-route")
async def fake_route(request: Request):
    with tracing_context(
        project_name="Definitely-not-your-grandpas-project", headers=request.headers
    ):
        fake_function()
    return {"message": "Fake route response"}
