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
  LangSmithSandboxError,           // Base exception for all sandbox errors
  LangSmithResourceNotFoundError,  // Resource doesn't exist (check resourceType)
  LangSmithResourceTimeoutError,   // Operation timed out (check resourceType)
  LangSmithSandboxConnectionError, // Network error
  LangSmithQuotaExceededError,     // Quota limit reached
  LangSmithValidationError,        // Invalid input
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
| `run(command, options?)` | Execute a shell command |
| `write(path, content, timeout?)` | Write file (string or Uint8Array) |
| `read(path, timeout?)` | Read file (returns Uint8Array) |
| `delete()` | Delete the sandbox |

### ExecutionResult

| Property | Description |
|----------|-------------|
| `stdout` | Standard output (string) |
| `stderr` | Standard error (string) |
| `exit_code` | Exit code (number) |

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
| `env?` | Environment variables for the command |
| `cwd?` | Working directory |
| `timeout?` | Execution timeout in seconds (default: 60) |
