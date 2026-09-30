"""End-to-end tests for the SSE exec transport against a live LangSmith API.

Opt-in: these boot real sandboxes, so they only run with
``LANGSMITH_SANDBOX_E2E=1``. Without it they skip, which keeps them out of the
shared integration suite, where they would create a sandbox per shard on every
push.

They run against whatever ``LANGSMITH_ENDPOINT`` points at, using the public
``/v2/sandboxes`` API and the default snapshot. Credentials come from
``LANGSMITH_API_KEY``, or from ``LANGSMITH_SANDBOX_E2E_BEARER`` for an OAuth
access token (``langsmith auth token``), which also needs
``LANGSMITH_WORKSPACE_ID`` to name the tenant:

    LANGSMITH_SANDBOX_E2E=1 \\
    LANGSMITH_WORKSPACE_ID=<workspace> \\
    LANGSMITH_SANDBOX_E2E_BEARER="$(langsmith auth token --profile prod)" \\
    uv run pytest tests/integration_tests/test_sandbox_sse_exec.py

The point of these cases is the part a mock cannot prove: that the ack/resume
loop delivers every byte exactly once across however many resumes the sandbox's
1 MiB output buffer forces.
"""

import os
from collections.abc import Callable

import pytest

from langsmith import _features
from langsmith.sandbox import SandboxClient

pytestmark = pytest.mark.skipif(
    not os.environ.get("LANGSMITH_SANDBOX_E2E"),
    reason="Set LANGSMITH_SANDBOX_E2E=1 to boot real sandboxes",
)

# Comfortably more than the sandbox's 1 MiB output buffer, so the server has to
# stop for an ack several times before the command can finish.
LARGE_OUTPUT_BYTES = 5 * 1024 * 1024


def _auth() -> dict:
    workspace = os.environ.get("LANGSMITH_WORKSPACE_ID")
    tenant = {"X-Tenant-Id": workspace} if workspace else {}
    api_key = os.environ.get("LANGSMITH_API_KEY")
    if api_key:
        return {"api_key": api_key, "headers": tenant}
    bearer = os.environ.get("LANGSMITH_SANDBOX_E2E_BEARER")
    if bearer:
        if not workspace:
            pytest.skip("Bearer auth also needs LANGSMITH_WORKSPACE_ID")
        return {"headers": {"Authorization": f"Bearer {bearer}", **tenant}}
    pytest.skip(
        "Set LANGSMITH_API_KEY or LANGSMITH_SANDBOX_E2E_BEARER to run the "
        "sandbox SSE end-to-end tests"
    )


@pytest.fixture(scope="module")
def sandbox():
    """A live sandbox on the default snapshot, kept if a test fails."""
    with SandboxClient(timeout=120, **_auth()) as client:
        box = client.create_sandbox(
            name=f"sse-exec-e2e-{os.getpid()}",
            idle_ttl_seconds=900,
            wait_for_ready=True,
            timeout=300,
        )
        yield box
        # Deliberately unconditional: a leaked sandbox idles out on its TTL,
        # and keeping it on failure would hide the leak rather than help.
        client.delete_sandbox(box.name)


@pytest.fixture
def resume_count(sandbox) -> Callable[[], int]:
    """How many times the transport has re-requested the stream so far."""
    seen = 0

    def count(request) -> None:
        nonlocal seen
        if request.url.path.endswith("/execute/stream/resume"):
            seen += 1

    hooks = sandbox._client._http.event_hooks
    hooks["request"] = [*hooks.get("request", []), count]
    yield lambda: seen
    hooks["request"] = [hook for hook in hooks["request"] if hook is not count]


@pytest.fixture(autouse=True)
def sse_exec(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(_features.ENV_VAR, _features.SANDBOX_SSE_EXEC)


def test_echo(sandbox):
    result = sandbox.run("echo hello from sse")

    assert result.stdout == "hello from sse\n"
    assert result.stderr == ""
    assert result.exit_code == 0


def test_stderr_and_nonzero_exit(sandbox):
    result = sandbox.run("echo out; echo err >&2; exit 3")

    assert result.stdout == "out\n"
    assert result.stderr == "err\n"
    assert result.exit_code == 3


def test_run_config_is_applied(sandbox):
    result = sandbox.run(
        "pwd; echo $E2E_VAR",
        run_config={"work_dir": "/tmp", "env_vars": {"E2E_VAR": "set"}},
    )

    assert result.stdout == "/tmp\nset\n"
    assert result.exit_code == 0


def test_large_output_survives_the_ack_loop(sandbox, resume_count):
    """Every byte arrives exactly once across the forced resumes."""
    result = sandbox.run(
        f"head -c {LARGE_OUTPUT_BYTES} /dev/zero | tr '\\0' a",
        timeout=300,
    )

    assert result.exit_code == 0
    assert len(result.stdout) == LARGE_OUTPUT_BYTES
    assert result.stdout.count("a") == LARGE_OUTPUT_BYTES
    # Without this the case would also pass against a server that never asked
    # for an ack, which is the whole thing under test. The exact count depends
    # on the sandbox's buffer size and how fast it drains, so only "the loop ran
    # repeatedly" is asserted.
    assert resume_count() >= 2


def test_streaming_handle_yields_chunks(sandbox):
    handle = sandbox.run(
        "for i in $(seq 1 5); do echo line-$i; done", wait=False, timeout=120
    )

    assert handle.command_id
    assert handle.pid

    chunks = [chunk for chunk in handle]

    assert "".join(c.data for c in chunks if c.stream == "stdout") == "".join(
        f"line-{i}\n" for i in range(1, 6)
    )
    assert handle.result.exit_code == 0


def test_multibyte_output_is_not_split_mid_character(sandbox, resume_count):
    """A chunk boundary inside a multi-byte character must not corrupt it."""
    # Enough two-byte characters to fill the 1 MiB output buffer several times,
    # so chunk boundaries land inside them. The bytes are written as octal
    # escapes because the sandbox's printf does not implement \\u.
    count = 600_000
    result = sandbox.run(
        f"for i in $(seq 1 {count}); do printf '\\303\\251'; done", timeout=600
    )

    assert result.exit_code == 0
    assert result.stdout == "é" * count
    assert resume_count() >= 1


def test_reconnect_resumes_from_an_offset(sandbox):
    handle = sandbox.run("echo first; echo second", wait=False, timeout=120)
    assert handle.result.stdout == "first\nsecond\n"

    resumed = sandbox.reconnect(handle.command_id, stdout_offset=len("first\n"))

    assert resumed.result.stdout == "second\n"


def test_callbacks_receive_output(sandbox):
    seen: list[str] = []

    result = sandbox.run("echo streamed", on_stdout=seen.append)

    assert "".join(seen) == "streamed\n"
    assert result.stdout == "streamed\n"


def test_unsupported_options_are_rejected(sandbox):
    with pytest.raises(ValueError, match="exec WebSocket"):
        sandbox.run("cat", pty=True)


@pytest.mark.asyncio
async def test_async_run(sandbox):
    async_box = sandbox.to_async()

    result = await async_box.run("echo async hello")

    assert result.stdout == "async hello\n"
    assert result.exit_code == 0
