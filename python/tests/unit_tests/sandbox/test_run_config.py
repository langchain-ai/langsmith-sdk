"""Tests for sandbox run configuration."""

import json

import pytest
from pytest_httpx import HTTPXMock

from langsmith.sandbox import Sandbox, SandboxClient, Snapshot
from langsmith.sandbox._run_config import (
    validate_command_run_config,
    validate_run_config,
)

RUN_CONFIG = {"user": "app", "work_dir": "/srv", "env_vars": {"LANG": "C"}}


@pytest.fixture
def client():
    """Create a SandboxClient with retries disabled for test isolation."""
    return SandboxClient(api_endpoint="http://test-server:8080", max_retries=0)


@pytest.fixture
def sandbox(client: SandboxClient):
    """Create a Sandbox instance."""
    return Sandbox.from_dict(
        data={
            "name": "test-sandbox",
            "dataplane_url": "https://sandbox-router.example.com/sb-123",
        },
        client=client,
        auto_delete=False,
    )


class TestValidateRunConfig:
    """Client-side checks on the run config shape."""

    def test_accepts_full_config(self):
        assert validate_run_config(RUN_CONFIG) == RUN_CONFIG

    def test_accepts_none(self):
        assert validate_run_config(None) is None

    @pytest.mark.parametrize(
        ("run_config", "message"),
        [
            ({"workdir": "/srv"}, "unsupported keys: workdir"),
            ({"user": ""}, "must be a non-empty string"),
            ({"work_dir": "srv"}, "must be an absolute path"),
            ({"env_vars": ["LANG=C"]}, "must be a mapping"),
            ({"env_vars": {"PORT": 8080}}, "must be a string"),
        ],
    )
    def test_rejects_bad_config(self, run_config, message):
        with pytest.raises(ValueError, match=message):
            validate_run_config(run_config)

    @pytest.mark.parametrize(
        ("env", "cwd"),
        [({"LANG": "C"}, None), (None, "/srv"), ({"LANG": "C"}, "/srv")],
    )
    def test_rejects_deprecated_fields_alongside_run_config(self, env, cwd):
        with pytest.raises(ValueError, match="cannot be combined with"):
            validate_command_run_config(RUN_CONFIG, env, cwd)

    def test_allows_deprecated_fields_on_their_own(self):
        assert validate_command_run_config(None, {"LANG": "C"}, "/srv") is None


class TestClientForwardsRunConfig:
    """run_config reaches the wire on every request that accepts it."""

    def test_create_sandbox(self, client: SandboxClient, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/boxes",
            json={"name": "test-sandbox"},
            status_code=201,
        )

        client.create_sandbox(snapshot_id="snap-1", run_config=RUN_CONFIG)

        body = json.loads(httpx_mock.get_request().content)
        assert body["run_config"] == RUN_CONFIG

    def test_update_sandbox(self, client: SandboxClient, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="PATCH",
            url="http://test-server:8080/boxes/test-sandbox",
            json={"name": "test-sandbox", "run_config": RUN_CONFIG},
        )

        sandbox = client.update_sandbox("test-sandbox", run_config=RUN_CONFIG)

        body = json.loads(httpx_mock.get_request().content)
        assert body["run_config"] == RUN_CONFIG
        assert sandbox.run_config == RUN_CONFIG

    def test_create_snapshot(self, client: SandboxClient, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/snapshots",
            json={"id": "snap-1", "name": "snap", "status": "ready"},
            status_code=201,
        )
        httpx_mock.add_response(
            method="GET",
            url="http://test-server:8080/snapshots/snap-1",
            json={
                "id": "snap-1",
                "name": "snap",
                "status": "ready",
                "run_config": RUN_CONFIG,
            },
        )

        snapshot = client.create_snapshot(
            "snap", "python:3.12-slim", 1024, run_config=RUN_CONFIG
        )

        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["run_config"] == RUN_CONFIG
        assert snapshot.run_config == RUN_CONFIG

    def test_capture_snapshot(self, client: SandboxClient, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url="http://test-server:8080/boxes/test-sandbox/snapshot",
            json={"id": "snap-1", "name": "snap", "status": "ready"},
            status_code=201,
        )
        httpx_mock.add_response(
            method="GET",
            url="http://test-server:8080/snapshots/snap-1",
            json={"id": "snap-1", "name": "snap", "status": "ready"},
        )

        client.capture_snapshot("test-sandbox", "snap", run_config=RUN_CONFIG)

        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["run_config"] == RUN_CONFIG

    def test_rejects_bad_config_before_request(self, client: SandboxClient):
        with pytest.raises(ValueError, match="must be an absolute path"):
            client.create_sandbox(snapshot_id="snap-1", run_config={"work_dir": "srv"})


class TestModelsCarryRunConfig:
    """Responses surface the stored run config, and its absence."""

    def test_snapshot(self):
        assert Snapshot.from_dict({"run_config": RUN_CONFIG}).run_config == RUN_CONFIG

    def test_snapshot_without_run_config(self):
        assert Snapshot.from_dict({"id": "snap-1"}).run_config is None

    def test_sandbox(self, client: SandboxClient):
        sandbox = Sandbox.from_dict(
            {"name": "test-sandbox", "run_config": RUN_CONFIG}, client=client
        )
        assert sandbox.run_config == RUN_CONFIG

    def test_to_async_keeps_run_config(self, client: SandboxClient):
        sandbox = Sandbox.from_dict(
            {"name": "test-sandbox", "run_config": RUN_CONFIG}, client=client
        )
        assert sandbox.to_async().run_config == RUN_CONFIG


class TestPerCommandRunConfig:
    """run() over the HTTP fallback path."""

    @pytest.fixture(autouse=True)
    def _ws_unavailable(self, monkeypatch):
        monkeypatch.setattr("langsmith.sandbox._sandbox.WEBSOCKETS_AVAILABLE", False)

    def test_forwards_run_config(self, sandbox: Sandbox, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url="https://sandbox-router.example.com/sb-123/execute",
            json={"stdout": "", "stderr": "", "exit_code": 0},
        )

        sandbox.run("id", run_config=RUN_CONFIG)

        body = json.loads(httpx_mock.get_request().content)
        assert body["run_config"] == RUN_CONFIG
        assert "cwd" not in body and "env" not in body

    def test_rejects_run_config_with_cwd(self, sandbox: Sandbox):
        with pytest.raises(ValueError, match="cannot be combined with cwd"):
            sandbox.run("pwd", cwd="/tmp", run_config=RUN_CONFIG)
