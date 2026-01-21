# LangSmith Sandbox

Sandboxed code execution for LangSmith. Run untrusted code safely in isolated containers.

## Quick Start

```python
from langsmith import sandbox

# Client uses LANGSMITH_ENDPOINT and LANGSMITH_API_KEY from environment
client = sandbox.SandboxClient()

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
```

## Configuration

The client automatically uses LangSmith environment variables:

```python
# Uses LANGSMITH_ENDPOINT and LANGSMITH_API_KEY
client = sandbox.SandboxClient()

# Or configure explicitly
client = sandbox.SandboxClient(
    api_endpoint="https://api.smith.langchain.com/api/v2/sandboxes",
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

# Custom image from a registry
client.create_template(name="custom", image="myregistry.io/myimage:latest")
```

## Persistent Volumes

Use volumes to persist data across sandbox sessions:

```python
# Create a volume
volume = client.create_volume(name="my-data", size="1Gi")

# Create a template with the volume mounted
template = client.create_template(
    name="stateful-sandbox",
    image="python:3.12-slim",
    volume_mounts=[
        sandbox.VolumeMountSpec(volume_name="my-data", mount_path="/data")
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

## Connecting to Existing Sandboxes

Connect to a sandbox that's already running:

```python
# Create a sandbox without auto-delete
sb = client.create_sandbox(template_name="my-template", auto_delete=False)
print(sb.name)  # e.g., "sandbox-abc123"

# Later, reconnect to the same sandbox
sb = client.connect("sandbox-abc123")
result = sb.run("echo 'Still running!'")

# Clean up when done
client.delete_sandbox("sandbox-abc123")
```

## Async Support

Full async support for all operations:

```python
from langsmith import sandbox

async def main():
    async with sandbox.AsyncSandboxClient() as client:
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

## Error Handling

The module provides specific exceptions for different error types:

```python
from langsmith.sandbox import (
    SandboxClientError,      # Base exception for all sandbox errors
    SandboxNotFoundError,    # Sandbox doesn't exist
    SandboxTimeoutError,     # Operation timed out
    SandboxConnectionError,  # Network error
    TemplateNotFoundError,   # Template doesn't exist
    SandboxQuotaExceededError,  # Quota limit reached
)

try:
    # This will fail if "nonexistent" template doesn't exist
    with client.sandbox(template_name="nonexistent") as sb:
        pass
except TemplateNotFoundError:
    print("Template not found! Create it first with client.create_template()")
except SandboxTimeoutError as e:
    print(f"Timeout: {e}")
except SandboxClientError as e:
    print(f"Error: {e}")
```

## API Reference

### SandboxClient

| Method | Description |
|--------|-------------|
| `sandbox(template_name, ...)` | Create a new sandbox (context manager) |
| `create_sandbox(template_name, ...)` | Create a sandbox without context manager |
| `connect(name, auto_delete=False)` | Connect to an existing sandbox |
| `list_sandboxes()` | List all sandboxes |
| `get_sandbox(name)` | Get sandbox by name |
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
| `run(command, timeout=60)` | Execute a shell command |
| `write(path, content)` | Write file (str or bytes) |
| `read(path)` | Read file (returns bytes) |

### ExecutionResult

| Property | Description |
|----------|-------------|
| `stdout` | Standard output (str) |
| `stderr` | Standard error (str) |
| `exit_code` | Exit code (int) |
| `success` | True if exit_code == 0 |
