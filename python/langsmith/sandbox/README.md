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

## Command Lifecycle & TTL

The sandbox daemon automatically manages command session lifecycles with two
timeout mechanisms:

### Session TTL (finished commands)

After a command finishes (exits), its session remains in memory for a TTL
period. During this window you can still reconnect to retrieve output. After the
TTL expires, the session is cleaned up and `reconnect()` will raise an error.

```python
with client.sandbox(template_name="my-sandbox") as sb:
    handle = sb.run("make build", wait=False)
    command_id = handle.command_id

    # Even after the command finishes, you can reconnect within the TTL window
    handle = sb.reconnect(command_id)
    result = handle.result
    print(result.stdout)

    # After TTL expires, reconnect raises SandboxOperationError
```

### Idle Timeout (running commands)

Running commands with no connected clients are killed after an idle timeout
(default: 5 minutes). The idle timer resets each time a client connects. This
prevents orphaned long-running processes from consuming resources indefinitely.

You can set a per-command idle timeout via the `idle_timeout` parameter.
Set to `-1` for no idle timeout (the command runs indefinitely until explicitly
killed or it exits on its own).

```python
with client.sandbox(template_name="my-sandbox") as sb:
    # Start a long-running command with a 30-minute idle timeout
    handle = sb.run(
        "python server.py",
        timeout=0,
        idle_timeout=1800,
        wait=False,
    )

    # As long as a client is connected (iterating), the idle timer is paused
    for chunk in handle:
        print(chunk.data, end="")
        if "Ready" in chunk.data:
            break

    # After disconnecting, the idle timer starts
    # If no client reconnects within idle_timeout seconds, the process is killed
```

### Kill on Disconnect

By default, commands continue running after a client disconnects and can be
reconnected to later. Set `kill_on_disconnect=True` to kill the command
immediately when the last client disconnects:

```python
with client.sandbox(template_name="my-sandbox") as sb:
    # Command is killed as soon as the client disconnects
    handle = sb.run(
        "python server.py",
        kill_on_disconnect=True,
        wait=False,
    )

    for chunk in handle:
        print(chunk.data, end="")
        if "Ready" in chunk.data:
            break
    # Command is killed here when iteration stops and the WS disconnects
```

### Combining Lifecycle Options

All lifecycle parameters can be combined:

```python
with client.sandbox(template_name="my-sandbox") as sb:
    # Long-running task: 30-min idle timeout, 1-hour session TTL
    handle = sb.run(
        "python train.py",
        timeout=0,              # No command timeout
        idle_timeout=1800,      # Kill after 30min with no clients
        ttl_seconds=3600,       # Keep session for 1 hour after exit
        wait=False,
    )

    # Fire-and-forget: no idle timeout, infinite TTL
    handle = sb.run(
        "python background_job.py",
        timeout=0,
        idle_timeout=-1,        # Never kill due to idle
        ttl_seconds=-1,         # Keep session forever
        wait=False,
    )
```

## PTY (Pseudo-Terminal)

Set `pty=True` to allocate a pseudo-terminal for the command. This is useful
for interactive programs and commands that detect terminal capabilities:

```python
with client.sandbox(template_name="my-sandbox") as sb:
    # Run an interactive Python REPL with PTY
    handle = sb.run("python", pty=True, wait=False)

    for chunk in handle:
        if ">>>" in chunk.data:
            handle.send_input("print('hello')\n")
            break

    for chunk in handle:
        if ">>>" in chunk.data:
            handle.send_input("exit()\n")
            break

    result = handle.result

    # Commands that require a TTY
    result = sb.run("top -b -n 1", pty=True)
```

> **Note:** PTY mode merges stdout and stderr into a single stream (stdout).
> Only use PTY when the command requires it — most commands work fine without it.

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

## TCP Tunnel

Access any TCP service running inside a sandbox (databases, Redis, HTTP servers,
etc.) as if it were running on your local machine. The tunnel opens a local TCP
port and forwards connections through a multiplexed WebSocket to the target port
inside the sandbox.

Requires the `websockets` package (`pip install 'langsmith[sandbox]'`).

### Basic Usage — PostgreSQL

Use a template with the `postgres:16` image. The entrypoint initializes and
starts Postgres automatically:

```python
import psycopg2

# Template uses the official postgres:16 image
sb = client.create_sandbox(template_name="my-postgres")
pg_handle = sb.run(
    "POSTGRES_HOST_AUTH_METHOD=trust docker-entrypoint.sh postgres",
    timeout=0,
    wait=False,
)
import time; time.sleep(6)  # wait for Postgres to initialize and start

try:
    with sb.tunnel(remote_port=5432, local_port=25432) as t:
        conn = psycopg2.connect(
            host="127.0.0.1",
            port=t.local_port,
            user="postgres",
        )
        cursor = conn.cursor()
        cursor.execute("SELECT version()")
        print(cursor.fetchone())
        conn.close()
finally:
    pg_handle.kill()
    client.delete_sandbox(sb.name)
```

### Basic Usage — Redis

Use a template with the `redis:7` image. Redis self-daemonizes:

```python
import redis

with client.sandbox(template_name="my-redis") as sb:
    sb.run("redis-server --daemonize yes", timeout=10)

    with sb.tunnel(remote_port=6379, local_port=26379) as t:
        r = redis.Redis(host="127.0.0.1", port=t.local_port)
        r.set("key", "value")
        print(r.get("key"))  # b"value"
```

### HTTP Services

Works with any TCP service. Start long-running services with `wait=False` and
`timeout=0` so they stay alive across commands:

```python
sb = client.create_sandbox(template_name="my-sandbox")
http_handle = sb.run("python3 -m http.server 3000", timeout=0, wait=False)
import time; time.sleep(2)

try:
    with sb.tunnel(remote_port=3000, local_port=13000) as t:
        import urllib.request
        resp = urllib.request.urlopen(f"http://127.0.0.1:{t.local_port}/")
        print(resp.status)  # 200
finally:
    http_handle.kill()
    client.delete_sandbox(sb.name)
```

### Multiple Tunnels

Open several tunnels simultaneously to different services:

```python
http_handle2 = sb.run("python3 -m http.server 3001", timeout=0, wait=False)
import time; time.sleep(1)

with sb.tunnel(remote_port=3000, local_port=23000) as t1, \
     sb.tunnel(remote_port=3001, local_port=23001) as t2:
    resp1 = urllib.request.urlopen(f"http://127.0.0.1:{t1.local_port}/")
    resp2 = urllib.request.urlopen(f"http://127.0.0.1:{t2.local_port}/")

http_handle2.kill()
```

### Explicit Lifecycle

For notebooks or long-lived sessions where a context manager isn't convenient:

```python
t = sb.tunnel(remote_port=3000, local_port=23002)

print(t.local_port)
# ... use the tunnel as long as needed ...

t.close()
```

### Async Usage

```python
async with await client.sandbox(template_name="my-sandbox") as sb:
    async with await sb.tunnel(remote_port=5432) as t:
        conn = await asyncpg.connect(host="127.0.0.1", port=t.local_port)
```

## Service URLs

Access HTTP services running inside a sandbox without opening a TCP tunnel.
`service()` returns a `ServiceURL` object with a short-lived JWT that
auto-refreshes transparently. Built-in HTTP helpers inject the auth header
for you.

### Basic Usage

```python
with client.sandbox(template_name="my-sandbox") as sb:
    # Start a web server inside the sandbox
    handle = sb.run("python -m http.server 3000", timeout=0, wait=False)
    import time; time.sleep(2)

    # Get a service URL for port 3000
    svc = sb.service(port=3000)

    # Make requests — token is injected automatically
    resp = svc.get("/")
    print(resp.status_code)  # 200

    # POST with JSON body
    resp = svc.post("/api/data", json={"key": "value"})

    # Access the raw token or URLs directly
    print(svc.token)        # JWT (auto-refreshes near expiry)
    print(svc.service_url)  # base URL for programmatic access
    print(svc.browser_url)  # URL that sets a cookie in a browser

    handle.kill()
```

### Custom Token TTL

Tokens default to 10 minutes. Set `expires_in_seconds` for longer or shorter
lifetimes (1 second to 24 hours):

```python
# Token valid for 1 hour
svc = sb.service(port=3000, expires_in_seconds=3600)
```

### Auto-Refresh

The `ServiceURL` object automatically refreshes its token before it expires.
You never need to worry about token rotation — just keep using the object:

```python
svc = sb.service(port=3000, expires_in_seconds=60)

# Even after 60 seconds, this still works — token refreshes transparently
resp = svc.get("/api/status")
```

### Async Usage

```python
async with await client.sandbox(template_name="my-sandbox") as sb:
    svc = await sb.service(port=3000)

    # Async HTTP helpers
    resp = await svc.get("/api/data")

    # Async accessors for auto-refreshing properties
    token = await svc.get_token()
    url = await svc.get_service_url()
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

## Sandbox Lifetime & TTL

Control how long a sandbox stays alive with two optional TTL parameters:

- **`ttl_seconds`** — Maximum lifetime from creation. The sandbox is automatically
  deleted after this many seconds, regardless of activity.
- **`idle_ttl_seconds`** — Idle timeout. The sandbox is automatically deleted after
  this many seconds of inactivity. Activity (command execution, file I/O) resets
  the timer.

Both values must be multiples of 60 (minute-resolution). Pass `0` to explicitly
disable a TTL. When both are set, whichever deadline comes first wins.

```python
# Create a sandbox that expires after 1 hour
with client.sandbox(
    template_name="my-sandbox",
    ttl_seconds=3600,
) as sb:
    result = sb.run("echo hello")

# Create a sandbox that expires after 10 min of inactivity
sb = client.create_sandbox(
    template_name="my-sandbox",
    idle_ttl_seconds=600,
)

# Combine both: 2-hour max lifetime, 15-min idle timeout
sb = client.create_sandbox(
    template_name="my-sandbox",
    ttl_seconds=7200,
    idle_ttl_seconds=900,
)

# Check expiration
print(sb.ttl_seconds)       # 7200
print(sb.idle_ttl_seconds)  # 900
print(sb.expires_at)        # e.g. "2026-03-24T14:00:00Z"
```

### Updating TTL on Existing Sandboxes

You can update TTL values on an already-running sandbox:

```python
# Extend the idle timeout to 30 minutes
sb = client.update_sandbox("my-sandbox", idle_ttl_seconds=1800)

# Disable the absolute TTL (sandbox runs indefinitely, idle TTL still applies)
sb = client.update_sandbox("my-sandbox", ttl_seconds=0)

# Update name and TTL together
sb = client.update_sandbox(
    "my-sandbox",
    new_name="my-sandbox-v2",
    ttl_seconds=3600,
)
```

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

## Async Sandbox Creation

By default, `create_sandbox()` blocks until the sandbox is ready. For
non-blocking creation, pass `wait_for_ready=False`:

```python
# Returns immediately with status="provisioning"
sb = client.create_sandbox(template_name="my-template", wait_for_ready=False)
print(sb.status)  # "provisioning"

# Poll until ready using the lightweight status endpoint
sb = client.wait_for_sandbox(sb.name, timeout=120, poll_interval=1.0)
print(sb.status)  # "ready"

# Now the sandbox is usable
result = sb.run("echo hello")
```

You can also poll manually for more control:

```python
sb = client.create_sandbox(template_name="my-template", wait_for_ready=False)

while True:
    status = client.get_sandbox_status(sb.name)
    if status.status == "ready":
        sb = client.get_sandbox(sb.name)
        break
    if status.status == "failed":
        print(f"Failed: {status.status_message}")
        break
    time.sleep(1)
```

> **Note:** Operations like `run()`, `write()`, and `read()` will raise
> `SandboxNotReadyError` if called on a sandbox that isn't ready yet.

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
    ResourceCreationError,    # Resource provisioning failed (check resource_type, error_type)
    ResourceNotFoundError,    # Resource doesn't exist (check resource_type)
    ResourceTimeoutError,     # Operation timed out (check resource_type)
    SandboxNotReadyError,     # Sandbox not ready for operations yet
    SandboxConnectionError,   # Network/WebSocket error
    CommandTimeoutError,      # Command exceeded its timeout (extends SandboxOperationError)
    QuotaExceededError,       # Quota limit reached
    TunnelError,              # Base for tunnel errors
    TunnelPortNotAllowedError,       # Port blocked by daemon allowlist
    TunnelConnectionRefusedError,    # Nothing listening on remote port
    TunnelUnsupportedVersionError,   # Client/daemon protocol mismatch
)

try:
    with client.sandbox(template_name="my-sandbox") as sb:
        result = sb.run("sleep 999", timeout=10)
except CommandTimeoutError as e:
    print(f"Command timed out: {e}")
except ResourceCreationError as e:
    print(f"{e.resource_type} creation failed: {e}")
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
| `sandbox(template_name, *, ttl_seconds=None, idle_ttl_seconds=None, ...)` | Create a sandbox (auto-deleted on context exit) |
| `create_sandbox(template_name, *, wait_for_ready=True, ttl_seconds=None, idle_ttl_seconds=None, ...)` | Create a sandbox (requires explicit delete). Pass `wait_for_ready=False` for async creation. |
| `get_sandbox(name)` | Get an existing sandbox by name |
| `get_sandbox_status(name)` | Get lightweight provisioning status (`ResourceStatus`) |
| `wait_for_sandbox(name, *, timeout=120, poll_interval=1.0)` | Poll until sandbox is ready or failed |
| `service(name, port, *, expires_in_seconds=600)` | Get a `ServiceURL` for an HTTP service on the given port |
| `list_sandboxes()` | List all sandboxes |
| `update_sandbox(name, *, new_name=None, ttl_seconds=None, idle_ttl_seconds=None)` | Update a sandbox's name or TTL settings |
| `delete_sandbox(name)` | Delete a sandbox |
| `create_template(name, image, ...)` | Create a template |
| `list_templates()` | List all templates |
| `get_template(name)` | Get template by name |
| `update_template(name, *, new_name)` | Update a template's display name |
| `delete_template(name)` | Delete a template |
| `create_volume(name, size)` | Create a persistent volume |
| `list_volumes()` | List all volumes |
| `update_volume(name, *, new_name, size)` | Update a volume's name or size |
| `delete_volume(name)` | Delete a volume |
| `create_pool(name, template_name, replicas)` | Create a pool |
| `list_pools()` | List all pools |
| `update_pool(name, *, replicas, new_name)` | Update pool replicas or name |
| `delete_pool(name)` | Delete a pool |

### Sandbox

| Property | Description |
|----------|-------------|
| `name` | Display name |
| `template_name` | Template used to create this sandbox |
| `status` | Lifecycle status: `"provisioning"`, `"ready"`, or `"failed"` |
| `status_message` | Human-readable details when status is `"failed"`, `None` otherwise |
| `dataplane_url` | URL for runtime operations (only functional when status is `"ready"`) |
| `id` | Unique identifier (UUID) |
| `ttl_seconds` | Maximum lifetime TTL in seconds (`0` means disabled, `None` means not set) |
| `idle_ttl_seconds` | Idle timeout TTL in seconds (`0` means disabled, `None` means not set) |
| `expires_at` | Computed expiration timestamp, or `None` if no TTL is active |

| Method | Description |
|--------|-------------|
| `run(command, *, timeout=60, on_stdout=None, on_stderr=None, idle_timeout=300, kill_on_disconnect=False, ttl_seconds=600, pty=False, wait=True)` | Execute a shell command. Returns `ExecutionResult` or `CommandHandle` (when `wait=False`). |
| `reconnect(command_id, *, stdout_offset=0, stderr_offset=0)` | Reconnect to a running command. Returns `CommandHandle`. |
| `write(path, content)` | Write file (str or bytes) |
| `read(path)` | Read file (returns bytes) |
| `tunnel(remote_port, *, local_port=0)` | Open a TCP tunnel. Returns `Tunnel` (context manager). |
| `service(port, *, expires_in_seconds=600)` | Get a `ServiceURL` for an HTTP service. Auto-refreshes token. |

### ExecutionResult

| Property | Description |
|----------|-------------|
| `stdout` | Standard output (str) |
| `stderr` | Standard error (str) |
| `exit_code` | Exit code (int) |
| `success` | True if exit_code == 0 |

### ResourceStatus

Returned by `client.get_sandbox_status()`.

| Property | Description |
|----------|-------------|
| `status` | Lifecycle status: `"provisioning"`, `"ready"`, or `"failed"` |
| `status_message` | Human-readable details when `"failed"`, `None` otherwise |

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

### Tunnel

Returned by `sb.tunnel(remote_port)`. Context manager that opens a local TCP
listener forwarding to a port inside the sandbox.

| Property / Method | Description |
|-------------------|-------------|
| `local_port` | Local port the tunnel is listening on (int) |
| `remote_port` | Target port inside the sandbox (int) |
| `close()` | Shut down the tunnel and all connections |

### ServiceURL

Returned by `sb.service(port)`. Holds a short-lived JWT for accessing an HTTP
service in the sandbox. Properties auto-refresh the token near expiry.

| Property | Description |
|----------|-------------|
| `token` | Raw JWT for programmatic use (auto-refreshes) |
| `service_url` | Base URL for programmatic HTTP access (auto-refreshes) |
| `browser_url` | URL that exchanges the JWT for a cookie in a browser (auto-refreshes) |
| `expires_at` | ISO 8601 expiration timestamp (auto-refreshes) |

| Method | Description |
|--------|-------------|
| `request(method, path="/", **kwargs)` | Make an HTTP request with auth header injected. Returns `httpx.Response`. |
| `get(path="/", **kwargs)` | HTTP GET |
| `post(path="/", **kwargs)` | HTTP POST |
| `put(path="/", **kwargs)` | HTTP PUT |
| `patch(path="/", **kwargs)` | HTTP PATCH |
| `delete(path="/", **kwargs)` | HTTP DELETE |

`AsyncServiceURL` is the async variant. Use `await svc.get_token()`,
`await svc.get_service_url()`, etc. for auto-refreshing access, and
`await svc.get(path)` for async HTTP helpers.
