"""LangSmith langchain_client Integration Tests."""
import os
from datetime import datetime
from uuid import uuid4

import pytest
from freezegun import freeze_time

from langsmith.client import Client
from langsmith.utils import LangSmithConnectionError


@pytest.fixture
def langchain_client(monkeypatch: pytest.MonkeyPatch) -> Client:
    monkeypatch.setenv("LANGCHAIN_ENDPOINT", "http://localhost:1984")
    return Client()


@pytest.mark.asyncio
async def test_projects(
    langchain_client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test projects."""
    project_names = set([project.name for project in langchain_client.list_projects()])
    new_project = "__Test Project"
    if new_project in project_names:
        langchain_client.delete_project(project_name=new_project)
        project_names = set(
            [project.name for project in langchain_client.list_projects()]
        )
    assert new_project not in project_names

    monkeypatch.setenv("LANGCHAIN_ENDPOINT", "http://localhost:1984")
    await langchain_client.acreate_project(
        project_name=new_project,
        project_extra={"evaluator": "THE EVALUATOR"},
    )
    project = await langchain_client.aread_project(project_name=new_project)
    assert project.name == new_project
    project_names = set([sess.name for sess in langchain_client.list_projects()])
    assert new_project in project_names
    [run async for run in langchain_client.alist_runs(project_name=new_project)]
    [run async for run in langchain_client.alist_runs(project_id=project.id)]


@pytest.mark.asyncio
@freeze_time("2023-01-01")
async def test_persist_update_run(
    monkeypatch: pytest.MonkeyPatch, langchain_client: Client
) -> None:
    """Test the persist and update methods work as expected."""
    monkeypatch.setenv("LANGCHAIN_ENDPOINT", "http://localhost:1984")
    project_name = "__test_persist_update_run"
    if project_name in [sess.name for sess in langchain_client.list_projects()]:
        langchain_client.delete_project(project_name=project_name)
    start_time = datetime.now()
    run: dict = dict(
        id=uuid4(),
        name="test_run",
        run_type="llm",
        inputs={"text": "hello world"},
        project_name=project_name,
        api_url=os.getenv("LANGCHAIN_ENDPOINT"),
        execution_order=1,
        start_time=start_time,
        extra={"extra": "extra"},
    )
    await langchain_client.acreate_run(**run)
    run["outputs"] = {"output": ["Hi"]}
    run["extra"]["foo"] = "bar"
    await langchain_client.aupdate_run(run["id"], **run)


@pytest.mark.asyncio
@pytest.mark.parametrize("uri", ["http://localhost:1981", "http://api.langchain.minus"])
async def test_error_surfaced_invalid_uri(
    monkeypatch: pytest.MonkeyPatch, uri: str
) -> None:
    monkeypatch.setenv("LANGCHAIN_ENDPOINT", uri)
    monkeypatch.setenv("LANGCHAIN_API_KEY", "test")
    client = Client()
    # expect connect error
    with pytest.raises(LangSmithConnectionError):
        await client.acreate_run(
            "My Run", inputs={"text": "hello world"}, run_type="llm"
        )


@pytest.mark.asyncio
@freeze_time("2023-01-01")
async def test_create_run_with_masked_inputs_outputs(
    langchain_client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_name = "__test_create_run_with_masked_inputs_outputs"
    monkeypatch.setenv("LANGCHAIN_HIDE_INPUTS", "true")
    monkeypatch.setenv("LANGCHAIN_HIDE_OUTPUTS", "true")
    for project in langchain_client.list_projects():
        if project.name == project_name:
            langchain_client.delete_project(project_name=project_name)

    run_id = "8bac165f-470e-4bf8-baa0-15f2de4cc706"
    await langchain_client.acreate_run(
        id=run_id,
        project_name=project_name,
        name="test_run",
        run_type="llm",
        inputs={"prompt": "hello world"},
        outputs={"generation": "hi there"},
        start_time=datetime.utcnow(),
        end_time=datetime.utcnow(),
        hide_inputs=True,
        hide_outputs=True,
    )

    run_id2 = "8bac165f-490e-4bf8-baa0-15f2de4cc707"
    await langchain_client.acreate_run(
        id=run_id2,
        project_name=project_name,
        name="test_run_2",
        run_type="llm",
        inputs={"messages": "hello world 2"},
        start_time=datetime.utcnow(),
        hide_inputs=True,
    )

    await langchain_client.aupdate_run(
        run_id2,
        outputs={"generation": "hi there 2"},
        end_time=datetime.utcnow(),
        hide_outputs=True,
    )
