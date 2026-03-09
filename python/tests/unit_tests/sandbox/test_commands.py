"""Tests for command management methods on Sandbox and AsyncSandbox."""

import json

import pytest
from pytest_httpx import HTTPXMock

from langsmith.sandbox import (
    DataplaneNotConfiguredError,
    ResourceNotFoundError,
    SandboxClient,
    SandboxNotReadyError,
)
from langsmith.sandbox._models import CommandInfo
from langsmith.sandbox._sandbox import Sandbox


DATAPLANE_URL = "https://sandbox-router.example.com/sb-123"

SAMPLE_COMMAND = {
    "id": "cmd-abc-123",
    "command": "python train.py",
    "shell": "/bin/bash",
    "workdir": "/home/user",
    "pid": 42,
    "started_at": "2025-01-01T00:00:00Z",
    "timeout": 60,
    "idle_timeout": 3600,
    "is_pty": False,
    "finished": False,
    "exit_code": None,
    "finished_at": None,
}

SAMPLE_FINISHED_COMMAND = {
    "id": "cmd-def-456",
    "command": "echo hello",
    "shell": "/bin/bash",
    "workdir": "/home/user",
    "pid": 99,
    "started_at": "2025-01-01T00:00:00Z",
    "timeout": 60,
    "idle_timeout": None,
    "is_pty": False,
    "finished": True,
    "exit_code": 0,
    "finished_at": "2025-01-01T00:00:01Z",
}


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
            "template_name": "test-template",
            "dataplane_url": DATAPLANE_URL,
        },
        client=client,
        auto_delete=False,
    )


class TestListCommands:
    """Tests for Sandbox.list_commands."""

    def test_list_commands_success(self, sandbox, httpx_mock: HTTPXMock):
        """Test listing commands returns parsed CommandInfo list."""
        httpx_mock.add_response(
            method="GET",
            url=f"{DATAPLANE_URL}/commands",
            json=[SAMPLE_COMMAND, SAMPLE_FINISHED_COMMAND],
        )

        commands = sandbox.list_commands()

        assert len(commands) == 2
        assert isinstance(commands[0], CommandInfo)
        assert commands[0].id == "cmd-abc-123"
        assert commands[0].command == "python train.py"
        assert commands[0].pid == 42
        assert commands[0].finished is False
        assert commands[0].exit_code is None

        assert commands[1].id == "cmd-def-456"
        assert commands[1].finished is True
        assert commands[1].exit_code == 0

    def test_list_commands_empty(self, sandbox, httpx_mock: HTTPXMock):
        """Test listing commands when none exist."""
        httpx_mock.add_response(
            method="GET",
            url=f"{DATAPLANE_URL}/commands",
            json=[],
        )

        commands = sandbox.list_commands()

        assert commands == []

    def test_list_commands_no_dataplane_url(self, client: SandboxClient):
        """Test list_commands raises DataplaneNotConfiguredError."""
        sb = Sandbox.from_dict(
            data={
                "name": "test-sandbox",
                "template_name": "test-template",
                "dataplane_url": None,
            },
            client=client,
            auto_delete=False,
        )

        with pytest.raises(DataplaneNotConfiguredError):
            sb.list_commands()

    def test_list_commands_not_ready(self, client: SandboxClient):
        """Test list_commands raises SandboxNotReadyError for non-ready sandbox."""
        sb = Sandbox.from_dict(
            data={
                "name": "test-sandbox",
                "template_name": "test-template",
                "status": "provisioning",
                "dataplane_url": DATAPLANE_URL,
            },
            client=client,
            auto_delete=False,
        )

        with pytest.raises(SandboxNotReadyError):
            sb.list_commands()


class TestGetCommand:
    """Tests for Sandbox.get_command."""

    def test_get_command_success(self, sandbox, httpx_mock: HTTPXMock):
        """Test getting a specific command."""
        httpx_mock.add_response(
            method="GET",
            url=f"{DATAPLANE_URL}/commands/cmd-abc-123",
            json=SAMPLE_COMMAND,
        )

        info = sandbox.get_command("cmd-abc-123")

        assert isinstance(info, CommandInfo)
        assert info.id == "cmd-abc-123"
        assert info.command == "python train.py"
        assert info.shell == "/bin/bash"
        assert info.workdir == "/home/user"
        assert info.pid == 42
        assert info.is_pty is False
        assert info.finished is False

    def test_get_command_not_found(self, sandbox, httpx_mock: HTTPXMock):
        """Test getting a non-existent command raises ResourceNotFoundError."""
        httpx_mock.add_response(
            method="GET",
            url=f"{DATAPLANE_URL}/commands/nonexistent",
            json={"detail": {"error": "NotFound", "message": "command not found"}},
            status_code=404,
        )

        with pytest.raises(ResourceNotFoundError) as exc_info:
            sandbox.get_command("nonexistent")

        assert exc_info.value.resource_type == "command"

    def test_get_command_no_dataplane_url(self, client: SandboxClient):
        """Test get_command raises DataplaneNotConfiguredError."""
        sb = Sandbox.from_dict(
            data={
                "name": "test-sandbox",
                "template_name": "test-template",
                "dataplane_url": None,
            },
            client=client,
            auto_delete=False,
        )

        with pytest.raises(DataplaneNotConfiguredError):
            sb.get_command("cmd-abc-123")


class TestKillCommand:
    """Tests for Sandbox.kill_command."""

    def test_kill_command_success(self, sandbox, httpx_mock: HTTPXMock):
        """Test killing a running command."""
        killed = {**SAMPLE_COMMAND, "finished": True, "exit_code": -9}
        httpx_mock.add_response(
            method="DELETE",
            url=f"{DATAPLANE_URL}/commands/cmd-abc-123",
            json=killed,
        )

        info = sandbox.kill_command("cmd-abc-123")

        assert isinstance(info, CommandInfo)
        assert info.id == "cmd-abc-123"
        assert info.finished is True
        assert info.exit_code == -9

    def test_kill_command_not_found(self, sandbox, httpx_mock: HTTPXMock):
        """Test killing a non-existent command raises ResourceNotFoundError."""
        httpx_mock.add_response(
            method="DELETE",
            url=f"{DATAPLANE_URL}/commands/nonexistent",
            json={"detail": {"error": "NotFound", "message": "command not found"}},
            status_code=404,
        )

        with pytest.raises(ResourceNotFoundError) as exc_info:
            sandbox.kill_command("nonexistent")

        assert exc_info.value.resource_type == "command"

    def test_kill_command_no_dataplane_url(self, client: SandboxClient):
        """Test kill_command raises DataplaneNotConfiguredError."""
        sb = Sandbox.from_dict(
            data={
                "name": "test-sandbox",
                "template_name": "test-template",
                "dataplane_url": None,
            },
            client=client,
            auto_delete=False,
        )

        with pytest.raises(DataplaneNotConfiguredError):
            sb.kill_command("cmd-abc-123")


class TestCommandInfoModel:
    """Tests for the CommandInfo dataclass."""

    def test_from_dict_full(self):
        """Test CommandInfo.from_dict with all fields."""
        info = CommandInfo.from_dict(SAMPLE_COMMAND)

        assert info.id == "cmd-abc-123"
        assert info.command == "python train.py"
        assert info.shell == "/bin/bash"
        assert info.workdir == "/home/user"
        assert info.pid == 42
        assert info.started_at == "2025-01-01T00:00:00Z"
        assert info.timeout == 60
        assert info.idle_timeout == 3600
        assert info.is_pty is False
        assert info.finished is False
        assert info.exit_code is None
        assert info.finished_at is None

    def test_from_dict_minimal(self):
        """Test CommandInfo.from_dict with minimal fields."""
        info = CommandInfo.from_dict({"id": "cmd-1", "command": "ls"})

        assert info.id == "cmd-1"
        assert info.command == "ls"
        assert info.shell == "/bin/bash"
        assert info.workdir == ""
        assert info.pid is None
        assert info.finished is False
        assert info.exit_code is None
