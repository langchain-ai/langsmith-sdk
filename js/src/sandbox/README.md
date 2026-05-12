# LangSmith Sandbox (JavaScript/TypeScript)

Sandboxed code execution for LangSmith. Run untrusted code safely in isolated containers.

## Quick Start

Sandboxes are created from **snapshots**. A snapshot is a filesystem image you
build once from a Docker image (or capture from a running sandbox) and then
reuse to boot as many sandboxes as you need.

```typescript
import { SandboxClient } from "langsmith/sandbox";

// Client uses LANGSMITH_ENDPOINT and LANGSMITH_API_KEY from environment
const client = new SandboxClient();

// Build a snapshot from a Docker image (do this once)
const snapshot = await client.createSnapshot(
  "python",
  "python:3.12-slim",
  1_073_741_824, // 1 GiB filesystem
);

// Create a sandbox from the snapshot and run code
const sandbox = await client.createSandbox(snapshot.id);
try {
  const result = await sandbox.run("python -c 'print(2 + 2)'");
  console.log(result.stdout); // "4\n"
  console.log(result.exit_code); // 0
} finally {
  await sandbox.delete();
}

// Or reuse an existing sandbox by name
const existingSb = await client.getSandbox("your-sandbox");
const res = await existingSb.run("python -c 'print(2 + 2)'");
```

If you already have a snapshot ID (for example, listed with
`client.listSnapshots()`), you can skip the `createSnapshot` step and call
`client.createSandbox(snapshotId)` directly.

## Configuration

The client automatically uses LangSmith environment variables:

```typescript
import { SandboxClient } from "langsmith/sandbox";

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
const sandbox = await client.createSandbox(snapshot.id);
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
const sandbox = await client.createSandbox(snapshot.id);
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
const sandbox = await client.createSandbox(snapshot.id);
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
const sandbox = await client.createSandbox(snapshot.id);
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
const sandbox = await client.createSandbox(snapshot.id);
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
const sandbox = await client.createSandbox(snapshot.id);
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
const sandbox = await client.createSandbox(snapshot.id);
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

## Snapshots

Snapshots are the filesystem images sandboxes boot from. You can build one from
a Docker image or capture the state of a running sandbox.

```typescript
// Build a snapshot from a public Docker image
const snapshot = await client.createSnapshot(
  "python",
  "python:3.12-slim",
  1_073_741_824, // 1 GiB
);

// Build from a private registry (use registryId or explicit credentials)
const privateSnapshot = await client.createSnapshot(
  "internal-python",
  "registry.example.com/internal/python:3.12",
  2_147_483_648,
  {
    registryUrl: "https://registry.example.com",
    registryUsername: "me",
    registryPassword: process.env.REGISTRY_PASSWORD,
  },
);

// Capture the state of a running sandbox for later reuse. Persistent paths
// (`/usr/local`, `/root`, `/opt`, the home directory, etc.) are preserved;
// `/tmp` is a tmpfs and is NOT part of the capture.
const running = await client.createSandbox(snapshot.id);
await running.run("pip install --quiet requests", { timeout: 180 });
await running.write("/opt/prepared.txt", "preloaded");

// Either form works; the instance method just forwards to the client.
const captured = await running.captureSnapshot("with-data", { timeout: 300 });
// const captured = await client.captureSnapshot(running.name, "with-data");

console.log(captured.id, captured.source_sandbox_id);

// Boot a new sandbox from the captured snapshot
const resumed = await client.createSandbox(captured.id);

// Or resolve by snapshot name instead of ID — the server looks up the
// snapshot owned by your tenant. Exactly one of the positional `snapshotId`
// or `options.snapshotName` must be provided.
const byName = await client.createSandbox(undefined, {
  snapshotName: "with-data",
});

// List / fetch / delete snapshots. listSnapshots() accepts optional
// server-side filters and pagination; when omitted the server applies a
// default page size of 50, so calling it once will not necessarily return
// every snapshot. `limit` must be between 1 and 500 and `offset` must be
// >= 0.
const firstPage = await client.listSnapshots();
const firstPython = await client.listSnapshots({
  nameContains: "python",
  limit: 100,
  offset: 0,
});
const loaded = await client.getSnapshot(snapshot.id);
await client.deleteSnapshot(snapshot.id);
```

> **Note:** `captureSnapshot` preserves only the persistent filesystem. Running
> processes, open sockets, in-memory state, and anything under `/tmp` are not
> carried over — restart the processes you need in the new sandbox.

### Sizing and Resources

`createSandbox` accepts optional per-sandbox resource limits. If omitted, the
server-side defaults are used. `fsCapacityBytes` defaults to the snapshot's
size.

```typescript
const sandbox = await client.createSandbox(snapshot.id, {
  vCpus: 2,
  memBytes: 2_147_483_648,        // 2 GiB
  fsCapacityBytes: 5_368_709_120, // 5 GiB
});
```

## Reusing Existing Sandboxes

Get a sandbox that's already running:

```typescript
// Create a sandbox (requires explicit cleanup)
const sb = await client.createSandbox(snapshot.id);
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
} from "langsmith/sandbox";

const client = new SandboxClient();

try {
  // This will fail if the snapshot doesn't exist
  const sandbox = await client.createSandbox("nonexistent");
  await sandbox.delete();
} catch (e) {
  if (e instanceof LangSmithResourceNotFoundError) {
    // e.resourceType tells you what wasn't found: "sandbox", "snapshot", "file"
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
| `createSandbox(snapshotId?, options?)` | Create a sandbox from a snapshot. Exactly one of the positional `snapshotId` or `options.snapshotName` must be provided. |
| `getSandbox(name)` | Get an existing sandbox by name |
| `listSandboxes()` | List all sandboxes |
| `updateSandbox(name, options)` | Rename or adjust retention (idle stop, delete-after-stop) on a sandbox |
| `deleteSandbox(name)` | Delete a sandbox |
| `startSandbox(name, options?)` | Start a stopped sandbox and wait until ready |
| `stopSandbox(name)` | Stop a running sandbox (preserves files) |
| `getSandboxStatus(name)` | Lightweight status poll for async creation |
| `waitForSandbox(name, options?)` | Poll until a sandbox becomes ready |
| `createSnapshot(name, dockerImage, fsCapacityBytes, options?)` | Build a snapshot from a Docker image |
| `captureSnapshot(sandboxName, name, options?)` | Capture a snapshot from a running sandbox |
| `getSnapshot(snapshotId)` | Get a snapshot by ID |
| `listSnapshots(options?)` | List a page of snapshots with optional server-side filters and pagination (server paginates, default limit 50, max 500). |
| `deleteSnapshot(snapshotId)` | Delete a snapshot |
| `waitForSnapshot(snapshotId, options?)` | Poll until a snapshot becomes ready |

### Sandbox

| Method | Description |
|--------|-------------|
| `run(command, options?)` | Execute a shell command (returns `ExecutionResult` or `CommandHandle`). Supports `idleTimeout` option. |
| `reconnect(commandId, options?)` | Reconnect to a running command by ID |
| `write(path, content, timeout?)` | Write file (string or Uint8Array) |
| `read(path, timeout?)` | Read file (returns Uint8Array) |
| `start(options?)` | Start this sandbox (if stopped) |
| `stop()` | Stop this sandbox |
| `captureSnapshot(name, options?)` | Capture a snapshot from this sandbox |
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
| `snapshotName?` | Snapshot name to boot from. Mutually exclusive with the positional `snapshotId` argument on `createSandbox`; exactly one must be set. |
| `name?` | Custom sandbox name |
| `timeout?` | Wait timeout in seconds |
| `waitForReady?` | Wait for the sandbox to be ready before returning (default: `true`) |
| `idleTtlSeconds?` | Idle timeout in seconds (multiple of 60; `0` disables idle stop). When omitted, the server applies a default of `600` seconds (10 minutes). |
| `deleteAfterStopSeconds?` | Seconds after the sandbox enters `stopped` before deletion (multiple of 60; `0` disables stop-anchored deletion). When omitted, the server applies its configured default. |
| `vCpus?` | Number of vCPUs |
| `memBytes?` | Memory allocation in bytes |
| `fsCapacityBytes?` | Root filesystem capacity in bytes |
| `proxyConfig?` | Per-sandbox proxy configuration (access control, rules, `no_proxy`) |

### ListSnapshotsOptions

| Property | Description |
|----------|-------------|
| `nameContains?` | Case-insensitive substring filter applied server-side to snapshot names |
| `limit?` | Page size; must be in `[1, 500]`. Server defaults to 50 when omitted |
| `offset?` | Number of snapshots to skip before returning results (must be `>= 0`, pairs with `limit`) |
| `signal?` | `AbortSignal` for cancellation |

### CreateSnapshotOptions

| Property | Description |
|----------|-------------|
| `registryId?` | Private registry ID |
| `registryUrl?` | Registry URL for private images |
| `registryUsername?` | Registry username |
| `registryPassword?` | Registry password |
| `timeout?` | Wait timeout in seconds (default: 60) |
| `signal?` | `AbortSignal` for cancellation |

### UpdateSandboxOptions

| Property | Description |
|----------|-------------|
| `newName?` | New display name |
| `idleTtlSeconds?` | Idle timeout in seconds (multiple of 60; `0` disables idle stop). Omit to leave the existing value unchanged. |
| `deleteAfterStopSeconds?` | Seconds after the sandbox enters `stopped` before deletion (multiple of 60; `0` disables). Omit to leave the existing value unchanged. |

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
