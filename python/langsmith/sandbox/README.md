# LangSmith Sandbox

Sandboxed code execution for LangSmith. Run untrusted code safely in isolated containers.

> ⚠️ **Warning**: This module is experimental. Features and APIs may change, and breaking changes are expected as we iterate.

## Quick Start

```python
from langsmith.sandbox import SandboxClient

# Client uses LANGSMITH_ENDPOINT and LANGSMITH_API_KEY from environment
client = SandboxClient()

# First, create a template (defines the container image)
client.create_template(
    name="python-sandbox",
    image="python:3.12-slim",
)

# Now create a sandbox from the template and run code
with client.sandbox(template_name="python-sandbox") as sb:
    result = sb.run("python -c 'print(2 + 2)'")
    print(result.stdout)  # "4\n"
    print(result.success)  # True

# Or create a sandbox to keep
sb = client.create_sandbox(template_name="python-sandbox")
result = sb.run("python -c 'print(2 + 2)'")
client.delete_sandbox(sb.name)  # Don't forget to clean up when done

# Or use an existing sandbox by ID
sb = client.get_sandbox(name="your-sandbox")
result = sb.run("python -c 'print(2 + 2)'")
```

## Installation

The sandbox module works out of the box for basic command execution (HTTP). For
**real-time output** (streaming, callbacks, and `timeout=0`), install the
optional dependency:

```bash
pip install 'langsmith[sandbox]'
```

This pulls in the `websockets` package. Without it, `sb.run()` falls back to
HTTP automatically.

## Configuration

The client automatically uses LangSmith environment variables:

```python
from langsmith.sandbox import SandboxClient

# Uses LANGSMITH_ENDPOINT and LANGSMITH_API_KEY
client = SandboxClient()

# Or configure explicitly
client = SandboxClient(
    api_endpoint="https://api.smith.langchain.com/v2/sandboxes",
    api_key="your-api-key",
    timeout=30.0,
)
```

## Running Commands

```python
# Assuming you've created a template called "my-sandbox"
with client.sandbox(template_name="my-sandbox") as sb:
    # Run a command
    result = sb.run("echo 'Hello, World!'")

    print(result.stdout)     # "Hello, World!\n"
    print(result.stderr)     # ""
    print(result.exit_code)  # 0
    print(result.success)    # True

    # Commands that fail return non-zero exit codes
    result = sb.run("exit 1")
    print(result.success)    # False
    print(result.exit_code)  # 1
```

## Streaming Output

For long-running commands, you can stream output in real time. This requires
the `websockets` package (`pip install 'langsmith[sandbox]'`).

### Callbacks

The simplest way to get real-time output. Blocks until the command completes.

```python
import sys

with client.sandbox(template_name="my-sandbox") as sb:
    result = sb.run(
        "make build",
        timeout=600,
        on_stdout=lambda s: print(s, end=""),
        on_stderr=lambda s: print(s, end="", file=sys.stderr),
    )
    print(f"\nBuild {'succeeded' if result.success else 'failed'}")
```

### Streaming with CommandHandle

For full control — access to the process handle, stream identity, kill, and
reconnection.

```python
with client.sandbox(template_name="my-sandbox") as sb:
    handle = sb.run("make build", timeout=600, wait=False)

    print(f"Command ID: {handle.command_id}")

    for chunk in handle:
        prefix = "OUT" if chunk.stream == "stdout" else "ERR"
        print(f"[{prefix}] {chunk.data}", end="")

    result = handle.result
    print(f"\nExit code: {result.exit_code}")
```

### Killing a Running Command

```python
import threading
import time

with client.sandbox(template_name="my-sandbox") as sb:
    handle = sb.run("sleep 3600", timeout=7200, wait=False)

    # Kill after 10 seconds from another thread
    def kill_after(h, seconds):
        time.sleep(seconds)
        h.kill()

    threading.Thread(target=kill_after, args=(handle, 10)).start()

    for chunk in handle:
        print(chunk.data, end="")

    result = handle.result
    print(f"Exit code: {result.exit_code}")  # non-zero (killed)
```

### Sending Stdin Input

```python
with client.sandbox(template_name="my-sandbox") as sb:
    handle = sb.run(
        "python -c 'name = input(\"Name: \"); print(f\"Hello {name}\")'",
        timeout=30,
        wait=False,
    )

    for chunk in handle:
        if "Name:" in chunk.data:
            handle.send_input("World\n")
        print(chunk.data, end="")

    result = handle.result
```

### Auto-Reconnect

`CommandHandle` (returned by `sb.run(wait=False)`) automatically
reconnects on transient disconnects — hot-reloads, network blips, etc. No user
code needed:

```python
with client.sandbox(template_name="my-sandbox") as sb:
    handle = sb.run("make build", timeout=600, wait=False)

    # Auto-reconnects on transient errors (hot-reload, network blips)
    for chunk in handle:
        print(chunk.data, end="")

    result = handle.result
```

For manual reconnection across process restarts:

```python
with client.sandbox(template_name="my-sandbox") as sb:
    handle = sb.run("make build", timeout=600, wait=False)
    command_id = handle.command_id

    # ... later, possibly in a different process ...

    handle = sb.reconnect(command_id)
    for chunk in handle:
        print(chunk.data, end="")
    result = handle.result
```

### No Timeout (`timeout=0`)

With WebSocket enabled, you can set `timeout=0` to let a command run
indefinitely with no server-side deadline. This works with both `wait=False`
and callbacks. Useful for long-lived processes like dev servers, file watchers,
or background tasks that you control via `kill()`.

```python
with client.sandbox(template_name="my-sandbox") as sb:
    handle = sb.run("python server.py", timeout=0, wait=False)

    for chunk in handle:
        print(chunk.data, end="")
        if "Ready" in chunk.data:
            break  # server is up, do other work

    handle.kill()  # stop when done
```

> **Note:** `timeout=0` requires WebSocket support
> (`pip install 'langsmith[sandbox]'`). Without WebSocket, `run()` falls
> back to HTTP which has its own request-level timeout.

## File Operations

Read and write files in the sandbox:

```python
# Assuming you've created a Python template
with client.sandbox(template_name="my-python") as sb:
    # Write a file
    sb.write("/app/script.py", "print('Hello from file!')")

    # Run the script
    result = sb.run("python /app/script.py")
    print(result.stdout)  # "Hello from file!\n"

    # Read a file (returns bytes)
    content = sb.read("/app/script.py")
    print(content.decode())  # "print('Hello from file!')"

    # Write binary files
    sb.write("/app/data.bin", b"\x00\x01\x02\x03")
```

## Templates

Templates define the container image and resources for sandboxes. **You must create a template before you can create sandboxes.**

```python
# Create a template (required before creating sandboxes)
template = client.create_template(
    name="my-python-env",
    image="python:3.12-slim",  # Any Docker image
    cpu="1",        # CPU limit (default: "500m")
    memory="1Gi",   # Memory limit (default: "512Mi")
)

# Now you can create sandboxes from this template
with client.sandbox(template_name="my-python-env") as sb:
    result = sb.run("python --version")

# List all templates
templates = client.list_templates()

# Get a specific template
template = client.get_template("my-python-env")

# Update a template's name
client.update_template("my-python-env", new_name="python-env-v2")

# Delete a template (fails if sandboxes or pools are using it)
client.delete_template("my-python-env")
```

### Common Template Images

```python
# Python
client.create_template(name="python", image="python:3.12-slim")

# Node.js
client.create_template(name="node", image="node:20-slim")

# Ubuntu (general purpose)
client.create_template(name="ubuntu", image="ubuntu:24.04")
```

## Persistent Volumes

Use volumes to persist data across sandbox sessions:

```python
from langsmith.sandbox import VolumeMountSpec

# Create a volume
volume = client.create_volume(name="my-data", size="1Gi")

# Create a template with the volume mounted
template = client.create_template(
    name="stateful-sandbox",
    image="python:3.12-slim",
    volume_mounts=[
        VolumeMountSpec(volume_name="my-data", mount_path="/data")
    ],
)

# Data written to /data persists across sandbox sessions
with client.sandbox(template_name="stateful-sandbox") as sb:
    sb.write("/data/state.txt", "persistent data")

# Later, in a new sandbox...
with client.sandbox(template_name="stateful-sandbox") as sb:
    content = sb.read("/data/state.txt")
    print(content.decode())  # "persistent data"
```

## Pools (Pre-warmed Sandboxes)

Pools pre-provision sandboxes for faster startup:

```python
# First create a template (without volumes - pools don't support volumes)
client.create_template(name="fast-python", image="python:3.12-slim")

# Create a pool with 5 warm sandboxes
pool = client.create_pool(
    name="python-pool",
    template_name="fast-python",
    replicas=2,
)

# Sandboxes from pooled templates start faster
with client.sandbox(template_name="fast-python") as sb:
    result = sb.run("python --version")

# Scale the pool
client.update_pool("python-pool", replicas=3)

# Delete the pool
client.delete_pool("python-pool")
```

> **Note:** Templates with volume mounts cannot be used in pools.

## Reusing Existing Sandboxes

Get a sandbox that's already running:

```python
# Create a sandbox (requires explicit cleanup)
sb = client.create_sandbox(template_name="my-template")
print(sb.name)  # e.g., "sandbox-abc123"

# Later, get the same sandbox
sb = client.get_sandbox("sandbox-abc123")
result = sb.run("echo 'Still running!'")

# Clean up when done
client.delete_sandbox("sandbox-abc123")
```

## Async Support

Full async support for all operations:

```python
from langsmith.sandbox import AsyncSandboxClient

async def main():
    async with AsyncSandboxClient() as client:
        # Create a template first
        await client.create_template(name="async-python", image="python:3.12-slim")

        # Use the template
        async with await client.sandbox(template_name="async-python") as sb:
            result = await sb.run("python -c 'print(1 + 1)'")
            print(result.stdout)  # "2\n"

            await sb.write("/app/test.txt", "async content")
            content = await sb.read("/app/test.txt")
            print(content.decode())
```

### Async Streaming

```python
async with await client.sandbox(template_name="async-python") as sb:
    handle = await sb.run("make build", timeout=600, wait=False)

    async for chunk in handle:
        print(chunk.data, end="")

    result = await handle.result
```

## Error Handling

The module provides type-based exceptions with a `resource_type` attribute for specific handling:

```python
from langsmith.sandbox import (
    SandboxClientError,       # Base exception for all sandbox errors
    ResourceNotFoundError,    # Resource doesn't exist (check resource_type)
    ResourceTimeoutError,     # Operation timed out (check resource_type)
    SandboxConnectionError,   # Network/WebSocket error
    CommandTimeoutError,      # Command exceeded its timeout (extends SandboxOperationError)
    QuotaExceededError,       # Quota limit reached
)

try:
    with client.sandbox(template_name="my-sandbox") as sb:
        result = sb.run("sleep 999", timeout=10)
except CommandTimeoutError as e:
    print(f"Command timed out: {e}")
except ResourceNotFoundError as e:
    print(f"{e.resource_type} not found: {e}")
except ResourceTimeoutError as e:
    print(f"Timeout waiting for {e.resource_type}: {e}")
except SandboxConnectionError as e:
    print(f"Connection error: {e}")
except SandboxClientError as e:
    print(f"Error: {e}")
```

## API Reference

### SandboxClient

| Method | Description |
|--------|-------------|
| `sandbox(template_name, ...)` | Create a sandbox (auto-deleted on context exit) |
| `create_sandbox(template_name, ...)` | Create a sandbox (requires explicit delete) |
| `get_sandbox(name)` | Get an existing sandbox by name |
| `list_sandboxes()` | List all sandboxes |
| `delete_sandbox(name)` | Delete a sandbox |
| `create_template(name, image, ...)` | Create a template |
| `list_templates()` | List all templates |
| `get_template(name)` | Get template by name |
| `delete_template(name)` | Delete a template |
| `create_volume(name, size)` | Create a persistent volume |
| `list_volumes()` | List all volumes |
| `delete_volume(name)` | Delete a volume |
| `create_pool(name, template_name, replicas)` | Create a pool |
| `list_pools()` | List all pools |
| `update_pool(name, replicas=...)` | Update pool replicas |
| `delete_pool(name)` | Delete a pool |

### Sandbox

| Method | Description |
|--------|-------------|
| `run(command, *, timeout=60, on_stdout=None, on_stderr=None, wait=True)` | Execute a shell command. Returns `ExecutionResult` or `CommandHandle` (when `wait=False`). |
| `reconnect(command_id, *, stdout_offset=0, stderr_offset=0)` | Reconnect to a running command. Returns `CommandHandle`. |
| `write(path, content)` | Write file (str or bytes) |
| `read(path)` | Read file (returns bytes) |

### ExecutionResult

| Property | Description |
|----------|-------------|
| `stdout` | Standard output (str) |
| `stderr` | Standard error (str) |
| `exit_code` | Exit code (int) |
| `success` | True if exit_code == 0 |

### CommandHandle

Returned by `sb.run(wait=False)`. Iterable, yielding `OutputChunk` objects.

| Property / Method | Description |
|-------------------|-------------|
| `command_id` | Server-assigned command ID |
| `pid` | Process ID on the sandbox |
| `result` | Final `ExecutionResult` (blocks until complete) |
| `kill()` | Send SIGKILL to the running command |
| `send_input(data)` | Write string data to the command's stdin |
| `reconnect()` | Reconnect from last known offsets |

### OutputChunk

| Property | Description |
|----------|-------------|
| `stream` | `"stdout"` or `"stderr"` |
| `data` | Text content of this chunk (str) |
| `offset` | Byte offset within the stream (int) |
