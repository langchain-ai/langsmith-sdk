"""Integration tests for Client.projects (AsyncSessionsResource)."""

from __future__ import annotations

import datetime
import random
import string
import time
from typing import Callable

import pytest

from langsmith._openapi_client._exceptions import NotFoundError
from langsmith import uuid7
from langsmith.client import Client


def _rand_name(prefix: str = "__sdk_test_project_") -> str:
    return prefix + "".join(random.sample(string.ascii_lowercase, 10))


def _wait_for(condition: Callable[[], bool], max_seconds: int = 30, interval: int = 2) -> None:
    deadline = time.time() + max_seconds
    while time.time() < deadline:
        try:
            if condition():
                return
        except Exception:
            pass
        time.sleep(interval)
    raise TimeoutError("Condition not met within timeout")


@pytest.fixture
def client() -> Client:
    return Client()


async def test_projects_create(client: Client) -> None:
    """create() returns a project with the given name and description."""
    name = _rand_name()
    project_id = None
    try:
        created = await client.projects.create(name=name, description="sdk test")
        project_id = created.id
        assert project_id is not None
        assert created.name == name
    finally:
        if project_id is not None:
            await client.projects.delete(str(project_id))


async def test_projects_retrieve(client: Client) -> None:
    """retrieve() returns the project matching the given session_id."""
    name = _rand_name()
    project_id = None
    try:
        created = await client.projects.create(name=name)
        project_id = created.id
        retrieved = await client.projects.retrieve(str(project_id))
        assert str(retrieved.id) == str(project_id)
        assert retrieved.name == name
    finally:
        if project_id is not None:
            await client.projects.delete(str(project_id))


async def test_projects_update(client: Client) -> None:
    """update() applies the given fields to an existing project."""
    name = _rand_name()
    project_id = None
    try:
        created = await client.projects.create(name=name)
        project_id = created.id
        updated_name = name + "_updated"
        updated = await client.projects.update(
            str(project_id),
            name=updated_name,
            description="updated description",
        )
        assert updated.id == project_id
        assert updated.name == updated_name
    finally:
        if project_id is not None:
            await client.projects.delete(str(project_id))


async def test_projects_list(client: Client) -> None:
    """list() returns an async iterable that includes the created project."""
    name = _rand_name()
    project_id = None
    try:
        created = await client.projects.create(name=name)
        project_id = created.id
        results = [
            p
            async for p in client.projects.list(name=name, limit=10)
        ]
        assert any(str(p.id) == str(project_id) for p in results)
    finally:
        if project_id is not None:
            await client.projects.delete(str(project_id))


async def test_projects_delete(client: Client) -> None:
    """delete() removes the project so a subsequent retrieve raises."""
    name = _rand_name()
    created = await client.projects.create(name=name)
    project_id = str(created.id)
    await client.projects.delete(project_id)
    with pytest.raises(NotFoundError):
        await client.projects.retrieve(project_id)
