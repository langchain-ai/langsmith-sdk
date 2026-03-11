# LangSmith Sandbox (JavaScript/TypeScript)

Sandboxed code execution for LangSmith. Run untrusted code safely in isolated containers.

> ⚠️ **Warning**: This module is experimental (alpha). Features and APIs may change, and breaking changes are expected as we iterate.

## Quick Start

```typescript
import { SandboxClient } from "langsmith/experimental/sandbox";

// Client uses LANGSMITH_ENDPOINT and LANGSMITH_API_KEY from environment
const client = new SandboxClient();

// First, create a template (defines the container image)
await client.createTemplate("python-sandbox", { image: "python:3.12-slim" });

// Now create a sandbox from the template and run code
const sandbox = await client.createSandbox("python-sandbox");
try {
  const result = await sandbox.run("python -c 'print(2 + 2)'");
  console.log(result.stdout);    // "4\n"
  console.log(result.exit_code); // 0
} finally {
  await sandbox.delete();
}

// Or use an existing sandbox by name
const existingSb = await client.getSandbox("your-sandbox");
const res = await existingSb.run("python -c 'print(2 + 2)'");
```

## Configuration

The client automatically uses LangSmith environment variables:

```typescript
import { SandboxClient } from "langsmith/experimental/sandbox";

// Uses LANGSMITH_ENDPOINT and LANGSMITH_API_KEY
const client = new SandboxClient();

// Or configure explicitly
const client = new SandboxClient({
  apiEndpoint: "https://api.smith.langchain.com/v2/sandboxes",
  apiKey: "your-api-key",
  maxRetries: 3,        // Retries for transient failures (default: 3)
  maxConcurrency: 10,   // Max concurrent requests (default: Infinity)
});
```

## Running Commands

```typescript
// Assuming you've created a template called "my-sandbox"
const sandbox = await client.createSandbox("my-sandbox");
try {
  // Run a command
  const result = await sandbox.run("echo 'Hello, World!'");

  console.log(result.stdout);     // "Hello, World!\n"
  console.log(result.stderr);     // ""
  console.log(result.exit_code);  // 0

  // Commands that fail return non-zero exit codes
  const failed = await sandbox.run("exit 1");
  console.log(failed.exit_code);  // 1

  // Pass environment variables and working directory
  const envResult = await sandbox.run("echo $MY_VAR", {
    env: { MY_VAR: "test-value" },
    cwd: "/tmp",
  });
} finally {
  await sandbox.delete();
}
```

## Streaming Execution (WebSocket)

For long-running commands, you can stream output in real-time using WebSocket-based execution. This requires the optional `ws` package:

```bash
npm install ws
```

### Stream with callbacks

```typescript
// Stream stdout/stderr via callbacks (blocks until complete)
const result = await sandbox.run("make build", {
  onStdout: (data) => process.stdout.write(data),
  onStderr: (data) => process.stderr.write(data),
});
console.log(`Exit code: ${result.exit_code}`);
```

### Non-blocking with CommandHandle

```typescript
// Get a CommandHandle for full control over the stream
const handle = await sandbox.run("python train.py", {
  wait: false,
  timeout: 600,
});

console.log(`Command ID: ${handle.commandId}`);
console.log(`PID: ${handle.pid}`);

// Iterate over output chunks (auto-reconnects on transient errors)
for await (const chunk of handle) {
  if (chunk.stream === "stdout") {
    process.stdout.write(chunk.data);
  } else {
    process.stderr.write(chunk.data);
  }
}

// Get the final result
const result = await handle.result;
console.log(`Exit code: ${result.exit_code}`);
```

### Sending stdin and killing commands

```typescript
const handle = await sandbox.run("python -i", { wait: false });

// Send input to stdin
handle.sendInput("print(2 + 2)\n");
handle.sendInput("exit()\n");

for await (const chunk of handle) {
  process.stdout.write(chunk.data);
}
```

```typescript
const handle = await sandbox.run("sleep 300", { wait: false });

// Kill the running command
handle.kill();

const result = await handle.result;
console.log(result.exit_code); // non-zero
```

### Reconnecting to a running command

```typescript
// If a client disconnects, you can reconnect using the command ID
const handle = await sandbox.run("long-task", { wait: false });
const commandId = handle.commandId;

// ... later, or from a different client ...
const newHandle = await sandbox.reconnect(commandId);
for await (const chunk of newHandle) {
  process.stdout.write(chunk.data);
}
```

> **Note:** When `wait` is `true` (default) with no callbacks, `run()` automatically tries WebSocket first and falls back to HTTP POST if the `ws` package is not installed or the server doesn't support it.

## Command Lifecycle & TTL

The sandbox daemon automatically manages command session lifecycles with two
timeout mechanisms:

### Session TTL (finished commands)

After a command finishes (exits), its session remains in memory for a TTL
period. During this window you can still reconnect to retrieve output. After the
TTL expires, the session is cleaned up and `reconnect()` will throw an error.

```typescript
const sandbox = await client.createSandbox("my-sandbox");
try {
  const handle = await sandbox.run("make build", { wait: false });
  const commandId = handle.commandId;

  // Even after the command finishes, you can reconnect within the TTL window
  const newHandle = await sandbox.reconnect(commandId);
  const result = await newHandle.result;
  console.log(result.stdout);

  // After TTL expires, reconnect throws LangSmithSandboxOperationError
} finally {
  await sandbox.delete();
}
```

### Idle Timeout (running commands)

Running commands with no connected clients are killed after an idle timeout
(default: 5 minutes). The idle timer resets each time a client connects. This
prevents orphaned long-running processes from consuming resources indefinitely.

You can set a per-command idle timeout via the `idleTimeout` option.
Set to `-1` for no idle timeout (the command runs indefinitely until explicitly
killed or it exits on its own).

```typescript
const sandbox = await client.createSandbox("my-sandbox");
try {
  // Start a long-running command with a 30-minute idle timeout
  const handle = await sandbox.run("python server.py", {
    timeout: 0,
    idleTimeout: 1800,
    wait: false,
  });

  // As long as a client is connected (iterating), the idle timer is paused
  for await (const chunk of handle) {
    process.stdout.write(chunk.data);
    if (chunk.data.includes("Ready")) break;
  }

  // After disconnecting, the idle timer starts
  // If no client reconnects within idleTimeout seconds, the process is killed
} finally {
  await sandbox.delete();
}
```

### Kill on Disconnect

By default, commands continue running after a client disconnects and can be
reconnected to later. Set `killOnDisconnect: true` to kill the command
immediately when the last client disconnects:

```typescript
const sandbox = await client.createSandbox("my-sandbox");
try {
  // Command is killed as soon as the client disconnects
  const handle = await sandbox.run("python server.py", {
    killOnDisconnect: true,
    wait: false,
  });

  for await (const chunk of handle) {
    process.stdout.write(chunk.data);
    if (chunk.data.includes("Ready")) break;
  }
  // Command is killed here when iteration stops and the WS disconnects
} finally {
  await sandbox.delete();
}
```

### Combining Lifecycle Options

All lifecycle options can be combined:

```typescript
const sandbox = await client.createSandbox("my-sandbox");
try {
  // Long-running task: 30-min idle timeout, 1-hour session TTL
  const handle = await sandbox.run("python train.py", {
    timeout: 0,              // No command timeout
    idleTimeout: 1800,       // Kill after 30min with no clients
    ttlSeconds: 3600,        // Keep session for 1 hour after exit
    wait: false,
  });

  // Fire-and-forget: no idle timeout, infinite TTL
  const bg = await sandbox.run("python background_job.py", {
    timeout: 0,
    idleTimeout: -1,         // Never kill due to idle
    ttlSeconds: -1,          // Keep session forever
    wait: false,
  });
} finally {
  await sandbox.delete();
}
```

## PTY (Pseudo-Terminal)

Set `pty: true` to allocate a pseudo-terminal for the command. This is useful
for interactive programs and commands that detect terminal capabilities:

```typescript
const sandbox = await client.createSandbox("my-sandbox");
try {
  // Run an interactive Python REPL with PTY
  const handle = await sandbox.run("python", { pty: true, wait: false });

  for await (const chunk of handle) {
    if (chunk.data.includes(">>>")) {
      handle.sendInput("print('hello')\n");
      break;
    }
  }

  for await (const chunk of handle) {
    if (chunk.data.includes(">>>")) {
      handle.sendInput("exit()\n");
      break;
    }
  }

  const result = await handle.result;

  // Commands that require a TTY
  const topResult = await sandbox.run("top -b -n 1", { pty: true });
} finally {
  await sandbox.delete();
}
```

> **Note:** PTY mode merges stdout and stderr into a single stream (stdout).
> Only use PTY when the command requires it — most commands work fine without it.

## File Operations

Read and write files in the sandbox:

```typescript
// Assuming you've created a Python template
const sandbox = await client.createSandbox("my-python");
try {
  // Write a file (string content)
  await sandbox.write("/app/script.py", "print('Hello from file!')");

  // Run the script
  const result = await sandbox.run("python /app/script.py");
  console.log(result.stdout);  // "Hello from file!\n"

  // Read a file (returns Uint8Array)
  const content = await sandbox.read("/app/script.py");
  console.log(new TextDecoder().decode(content));  // "print('Hello from file!')"

  // Write binary files
  await sandbox.write("/app/data.bin", new Uint8Array([0x00, 0x01, 0x02, 0x03]));
} finally {
  await sandbox.delete();
}
```

## Templates

Templates define the container image and resources for sandboxes. **You must create a template before you can create sandboxes.**

```typescript
// Create a template (required before creating sandboxes)
const template = await client.createTemplate("my-python-env", {
  image: "python:3.12-slim",  // Any Docker image
  cpu: "1",        // CPU limit (default: "500m")
  memory: "1Gi",   // Memory limit (default: "512Mi")
});

// Now you can create sandboxes from this template
const sandbox = await client.createSandbox("my-python-env");
try {
  const result = await sandbox.run("python --version");
} finally {
  await sandbox.delete();
}

// List all templates
const templates = await client.listTemplates();

// Get a specific template
const tmpl = await client.getTemplate("my-python-env");

// Update a template's name
await client.updateTemplate("my-python-env", { newName: "python-env-v2" });

// Delete a template (fails if sandboxes or pools are using it)
await client.deleteTemplate("my-python-env");
```

### Common Template Images

```typescript
// Python
await client.createTemplate("python", { image: "python:3.12-slim" });

// Node.js
await client.createTemplate("node", { image: "node:20-slim" });

// Ubuntu (general purpose)
await client.createTemplate("ubuntu", { image: "ubuntu:24.04" });
```

## Persistent Volumes

Use volumes to persist data across sandbox sessions:

```typescript
import { SandboxClient } from "langsmith/experimental/sandbox";
import type { VolumeMountSpec } from "langsmith/experimental/sandbox";

const client = new SandboxClient();

// Create a volume
const volume = await client.createVolume("my-data", { size: "1Gi" });

// Create a template with the volume mounted
const volumeMounts: VolumeMountSpec[] = [
  { volume_name: "my-data", mount_path: "/data" }
];

const template = await client.createTemplate("stateful-sandbox", {
  image: "python:3.12-slim",
  volumeMounts,
});

// Data written to /data persists across sandbox sessions
{
  const sandbox = await client.createSandbox("stateful-sandbox");
  await sandbox.write("/data/state.txt", "persistent data");
  await sandbox.delete();
}

// Later, in a new sandbox...
{
  const sandbox = await client.createSandbox("stateful-sandbox");
  const content = await sandbox.read("/data/state.txt");
  console.log(new TextDecoder().decode(content));  // "persistent data"
  await sandbox.delete();
}
```

## Pools (Pre-warmed Sandboxes)

Pools pre-provision sandboxes for faster startup:

```typescript
// First create a template (without volumes - pools don't support volumes)
await client.createTemplate("fast-python", { image: "python:3.12-slim" });

// Create a pool with 2 warm sandboxes
const pool = await client.createPool("python-pool", {
  templateName: "fast-python",
  replicas: 2,
});

// Sandboxes from pooled templates start faster
const sandbox = await client.createSandbox("fast-python");
try {
  const result = await sandbox.run("python --version");
} finally {
  await sandbox.delete();
}

// Scale the pool
await client.updatePool("python-pool", { replicas: 3 });

// Delete the pool
await client.deletePool("python-pool");
```

> **Note:** Templates with volume mounts cannot be used in pools.

## Reusing Existing Sandboxes

Get a sandbox that's already running:

```typescript
// Create a sandbox (requires explicit cleanup)
const sb = await client.createSandbox("my-template");
console.log(sb.name);  // e.g., "sandbox-abc123"

// Later, get the same sandbox
const existingSb = await client.getSandbox("sandbox-abc123");
const result = await existingSb.run("echo 'Still running!'");

// Clean up when done
await client.deleteSandbox("sandbox-abc123");
```

## Error Handling

The module provides typed exceptions for specific error handling:

```typescript
import {
  SandboxClient,
  LangSmithSandboxError,              // Base exception for all sandbox errors
  LangSmithResourceNotFoundError,     // Resource doesn't exist (check resourceType)
  LangSmithResourceTimeoutError,      // Operation timed out (check resourceType)
  LangSmithSandboxConnectionError,    // Network error
  LangSmithSandboxServerReloadError,  // Server hot-reload (auto-reconnects)
  LangSmithCommandTimeoutError,       // Command exceeded its timeout
  LangSmithQuotaExceededError,        // Quota limit reached
  LangSmithValidationError,           // Invalid input
} from "langsmith/experimental/sandbox";

const client = new SandboxClient();

try {
  // This will fail if "nonexistent" template doesn't exist
  const sandbox = await client.createSandbox("nonexistent");
  await sandbox.delete();
} catch (e) {
  if (e instanceof LangSmithResourceNotFoundError) {
    // e.resourceType tells you what wasn't found: "sandbox", "template", "volume", etc.
    console.log(`${e.resourceType} not found: ${e.message}`);
  } else if (e instanceof LangSmithResourceTimeoutError) {
    console.log(`Timeout waiting for ${e.resourceType}: ${e.message}`);
  } else if (e instanceof LangSmithSandboxError) {
    console.log(`Error: ${e.message}`);
  }
}
```

## API Reference

### SandboxClient

| Method | Description |
|--------|-------------|
| `createSandbox(templateName, options?)` | Create a sandbox |
| `getSandbox(name)` | Get an existing sandbox by name |
| `listSandboxes()` | List all sandboxes |
| `deleteSandbox(name)` | Delete a sandbox |
| `createTemplate(name, options)` | Create a template |
| `listTemplates()` | List all templates |
| `getTemplate(name)` | Get template by name |
| `updateTemplate(name, options)` | Update a template |
| `deleteTemplate(name)` | Delete a template |
| `createVolume(name, options)` | Create a persistent volume |
| `listVolumes()` | List all volumes |
| `getVolume(name)` | Get volume by name |
| `updateVolume(name, options)` | Update a volume |
| `deleteVolume(name)` | Delete a volume |
| `createPool(name, options)` | Create a pool |
| `listPools()` | List all pools |
| `getPool(name)` | Get pool by name |
| `updatePool(name, options)` | Update pool (rename or scale) |
| `deletePool(name)` | Delete a pool |

### Sandbox

| Method | Description |
|--------|-------------|
| `run(command, options?)` | Execute a shell command (returns `ExecutionResult` or `CommandHandle`). Supports `idleTimeout` option. |
| `reconnect(commandId, options?)` | Reconnect to a running command by ID |
| `write(path, content, timeout?)` | Write file (string or Uint8Array) |
| `read(path, timeout?)` | Read file (returns Uint8Array) |
| `delete()` | Delete the sandbox |

### CommandHandle

| Property/Method | Description |
|-----------------|-------------|
| `commandId` | Server-assigned command ID |
| `pid` | Process ID on the sandbox |
| `result` | Final `ExecutionResult` (drains stream if needed) |
| `kill()` | Send SIGKILL to the running command |
| `sendInput(data)` | Write string data to the command's stdin |
| `reconnect()` | Reconnect from the last known offsets |
| `lastStdoutOffset` | Last stdout byte offset (for manual reconnection) |
| `lastStderrOffset` | Last stderr byte offset (for manual reconnection) |
| `[Symbol.asyncIterator]` | Yields `OutputChunk` objects with auto-reconnect |

### ExecutionResult

| Property | Description |
|----------|-------------|
| `stdout` | Standard output (string) |
| `stderr` | Standard error (string) |
| `exit_code` | Exit code (number) |

### OutputChunk

| Property | Description |
|----------|-------------|
| `stream` | `"stdout"` or `"stderr"` |
| `data` | Text content of the chunk |
| `offset` | Byte offset within the stream |

### CreateSandboxOptions

| Property | Description |
|----------|-------------|
| `name?` | Custom sandbox name |
| `timeout?` | Wait timeout in seconds |

### CreateVolumeOptions

| Property | Description |
|----------|-------------|
| `size` | Storage size (e.g., "1Gi") |
| `timeout?` | Wait timeout in seconds (default: 60) |

### CreateTemplateOptions

| Property | Description |
|----------|-------------|
| `image` | Container image (e.g., "python:3.12-slim") |
| `cpu?` | CPU limit (default: "500m") |
| `memory?` | Memory limit (default: "512Mi") |
| `storage?` | Storage size |
| `volumeMounts?` | Array of volume mount specs |

### UpdateTemplateOptions

| Property | Description |
|----------|-------------|
| `newName?` | New template name |

### CreatePoolOptions

| Property | Description |
|----------|-------------|
| `templateName` | Template to use for sandboxes |
| `replicas` | Number of pre-warmed sandboxes (1-100) |
| `timeout?` | Wait timeout in seconds (default: 30) |

### UpdatePoolOptions

| Property | Description |
|----------|-------------|
| `newName?` | New pool name |
| `replicas?` | New replica count |

### RunOptions

| Property | Description |
|----------|-------------|
| `timeout?` | Execution timeout in seconds (default: 60) |
| `env?` | Environment variables for the command |
| `cwd?` | Working directory |
| `shell?` | Shell to use (default: `"/bin/bash"`) |
| `wait?` | Wait for completion (default: `true`). When `false`, returns `CommandHandle` |
| `onStdout?` | Callback invoked with each stdout chunk (triggers WS streaming) |
| `onStderr?` | Callback invoked with each stderr chunk (triggers WS streaming) |
| `idleTimeout?` | Idle timeout in seconds (default: 300). Set to -1 for no timeout. Kills the command if no clients are connected for this duration |
| `killOnDisconnect?` | If true, kill the command immediately when the last client disconnects (default: false) |
| `ttlSeconds?` | How long a finished command's session is kept for reconnection (default: 600). Set to -1 to keep indefinitely |
| `pty?` | Allocate a pseudo-terminal (default: false). Merges stderr into stdout |
