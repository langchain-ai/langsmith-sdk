/**
 * Sandbox class for interacting with a specific sandbox instance.
 */

import type { SandboxClient } from "./client.js";
import { traceable } from "../traceable.js";
import type {
  CaptureSnapshotOptions,
  ExecutionResult,
  RunOptions,
  SandboxData,
  Snapshot,
  StartSandboxOptions,
} from "./types.js";
import {
  LangSmithDataplaneNotConfiguredError,
  LangSmithSandboxNotReadyError,
} from "./errors.js";
import { handleSandboxHttpError } from "./helpers.js";
import { CommandHandle } from "./command_handle.js";
import { reconnectWsStream, runWsStream } from "./ws_execute.js";
import type { KVMap } from "../schemas.js";

/**
 * Represents an active sandbox for running commands and file operations.
 *
 * This class is typically obtained from SandboxClient.createSandbox() and
 * provides methods for command execution and file I/O within the sandbox
 * environment.
 *
 * @example
 * ```typescript
 * const sandbox = await client.createSandbox(snapshot.id);
 * try {
 *   const result = await sandbox.run("python --version");
 *   console.log(result.stdout);
 * } finally {
 *   await sandbox.delete();
 * }
 * ```
 */
export class Sandbox {
  /** Display name (can be updated). */
  readonly name: string;
  /** URL for data plane operations (file I/O, command execution). */
  dataplane_url?: string;
  /** Provisioning status ("provisioning", "ready", "failed", "stopped"). */
  status?: string;
  /** Human-readable status message (e.g., error details when failed). */
  readonly status_message?: string;
  /** Unique identifier (UUID). Remains constant even if name changes. */
  readonly id?: string;
  /** Timestamp when the sandbox was created. */
  readonly created_at?: string;
  /** Timestamp when the sandbox was last updated. */
  readonly updated_at?: string;
  /**
   * Idle timeout TTL in seconds (`0` means disabled).
   * New sandboxes receive a server-side default of `600` seconds (10 minutes)
   * when the caller did not set `idleTtlSeconds` explicitly. The launcher
   * stops the sandbox after this many idle seconds.
   */
  readonly idle_ttl_seconds?: number;
  /**
   * Seconds after the sandbox enters the `stopped` state before it (and
   * its filesystem clone) are permanently deleted (`0` means disabled).
   */
  readonly delete_after_stop_seconds?: number;
  /**
   * Timestamp when the sandbox transitioned to `stopped`, or `undefined`
   * while running. The deletion deadline is
   * `stopped_at + delete_after_stop_seconds`.
   */
  readonly stopped_at?: string;
  /** Snapshot ID used to create this sandbox. */
  readonly snapshot_id?: string;
  /** Number of vCPUs allocated. */
  readonly vCpus?: number;
  /** Memory allocation in bytes. */
  readonly mem_bytes?: number;
  /** Root filesystem capacity in bytes. */
  readonly fs_capacity_bytes?: number;

  private _client: SandboxClient;

  /** @internal */
  constructor(data: SandboxData, client: SandboxClient) {
    this.name = data.name;
    this.dataplane_url = data.dataplane_url;
    this.status = data.status;
    this.status_message = data.status_message;
    this.id = data.id;
    this.created_at = data.created_at;
    this.updated_at = data.updated_at;
    this.idle_ttl_seconds = data.idle_ttl_seconds;
    this.delete_after_stop_seconds = data.delete_after_stop_seconds;
    this.stopped_at = data.stopped_at ?? undefined;
    this.snapshot_id = data.snapshot_id;
    this.vCpus = data.vcpus;
    this.mem_bytes = data.mem_bytes;
    this.fs_capacity_bytes = data.fs_capacity_bytes;
    this._client = client;
  }

  /**
   * Validate and return the dataplane URL.
   * @throws LangSmithSandboxNotReadyError if sandbox status is not "ready".
   * @throws LangSmithDataplaneNotConfiguredError if dataplane_url is not configured.
   */
  private requireDataplaneUrl(): string {
    if (this.status && this.status !== "ready") {
      throw new LangSmithSandboxNotReadyError(
        `Sandbox '${this.name}' is not ready (status: ${this.status}). ` +
          "Use waitForSandbox() to wait for the sandbox to become ready.",
      );
    }
    if (!this.dataplane_url) {
      throw new LangSmithDataplaneNotConfiguredError(
        `Sandbox '${this.name}' does not have a dataplane_url configured. ` +
          "Runtime operations require a dataplane URL.",
      );
    }
    return this.dataplane_url;
  }

  /**
   * Execute a command in the sandbox.
   *
   * When `wait` is true (default) and no streaming callbacks are provided,
   * tries WebSocket first and falls back to HTTP POST.
   *
   * When `wait` is false or streaming callbacks are provided, uses WebSocket
   * (required). Returns a CommandHandle for streaming output.
   *
   * @param command - Shell command to execute.
   * @param options - Execution options.
   * @returns ExecutionResult when wait=true, CommandHandle when wait=false.
   *
   * @example
   * ```typescript
   * // Blocking (default)
   * const result = await sandbox.run("echo hello");
   * console.log(result.stdout);
   *
   * // Streaming with callbacks
   * const result = await sandbox.run("make build", {
   *   onStdout: (data) => process.stdout.write(data),
   * });
   *
   * // Non-blocking with CommandHandle
   * const handle = await sandbox.run("make build", { wait: false });
   * for await (const chunk of handle) {
   *   process.stdout.write(chunk.data);
   * }
   * const result = await handle.result;
   * ```
   */
  async run(
    command: string,
    options: RunOptions & { wait: false },
  ): Promise<CommandHandle>;
  async run(
    command: string,
    options?: RunOptions & { wait?: true },
  ): Promise<ExecutionResult>;
  async run(
    command: string,
    options?: RunOptions,
  ): Promise<ExecutionResult | CommandHandle>;
  async run(
    command: string,
    options: RunOptions = {},
  ): Promise<ExecutionResult | CommandHandle> {
    return this.traceDataplaneOperation(
      "Sandbox.run",
      this.traceInputs(command, options),
      () => this._runUntraced(command, options),
      (result) => this.traceOutputs(result),
    );
  }

  private async traceDataplaneOperation<T>(
    name: string,
    inputs: KVMap,
    operation: () => Promise<T>,
    processOutputs: (result: T) => KVMap = () => ({}),
  ): Promise<T> {
    let result: T | undefined;
    let hasResult = false;
    const tracedOperation = traceable(
      async () => {
        result = await operation();
        hasResult = true;
        return result;
      },
      {
        name,
        run_type: "tool",
        metadata: this.traceMetadata(),
        processInputs: () => inputs,
        processOutputs: () => (hasResult ? processOutputs(result as T) : {}),
      },
    );

    return tracedOperation();
  }

  private async _runUntraced(
    command: string,
    options: RunOptions = {},
  ): Promise<ExecutionResult | CommandHandle> {
    const {
      wait = true,
      onStdout,
      onStderr,
      idleTimeout,
      killOnDisconnect,
      ttlSeconds,
      pty,
      ...restOptions
    } = options;
    const hasCallbacks = onStdout !== undefined || onStderr !== undefined;

    if (!wait || hasCallbacks) {
      // WebSocket required for streaming / non-blocking
      const handle = await this._runWs(command, {
        ...restOptions,
        idleTimeout,
        killOnDisconnect,
        ttlSeconds,
        pty,
        onStdout,
        onStderr,
      });

      if (!wait) {
        return handle;
      }

      // wait=true with callbacks: drain stream and return result
      return handle.result;
    }

    // wait=true, no callbacks: try WS, fall back to HTTP
    try {
      const handle = await this._runWs(command, {
        ...restOptions,
        idleTimeout,
        killOnDisconnect,
        ttlSeconds,
        pty,
      });
      return await handle.result;
    } catch (e) {
      // Fall back to HTTP on connection errors or missing ws package
      const name = e != null && typeof e === "object" ? (e as Error).name : "";
      const message =
        e != null && typeof e === "object" ? ((e as Error).message ?? "") : "";
      if (
        name === "LangSmithSandboxConnectionError" ||
        name === "LangSmithSandboxServerReloadError" ||
        message.includes("'ws' package")
      ) {
        return this._runHttp(command, restOptions);
      }
      throw e;
    }
  }

  private traceMetadata(): KVMap {
    return {
      sandbox_name: this.name,
      ...(this.id ? { sandbox_id: this.id } : {}),
    };
  }

  private traceInputs(command: string, options: RunOptions): KVMap {
    const {
      cwd,
      shell = "/bin/bash",
      timeout = 60,
      wait = true,
      onStdout,
      onStderr,
      idleTimeout,
      killOnDisconnect,
      ttlSeconds,
      pty,
    } = options;
    return {
      command,
      timeout,
      shell,
      has_stdout_callback: onStdout !== undefined,
      has_stderr_callback: onStderr !== undefined,
      ...(cwd !== undefined ? { cwd } : {}),
      ...(idleTimeout !== undefined ? { idle_timeout: idleTimeout } : {}),
      ...(killOnDisconnect !== undefined
        ? { kill_on_disconnect: killOnDisconnect }
        : {}),
      ...(ttlSeconds !== undefined ? { ttl_seconds: ttlSeconds } : {}),
      ...(pty !== undefined ? { pty } : {}),
      wait,
    };
  }

  private traceOutputs(
    result: ExecutionResult | CommandHandle | undefined,
  ): KVMap {
    if (result instanceof CommandHandle) {
      return {
        command_id: result.commandId,
        pid: result.pid,
      };
    }
    if (result) {
      return {
        stdout: result.stdout,
        stderr: result.stderr,
        exit_code: result.exit_code,
      };
    }
    return {};
  }

  /**
   * Execute a command via WebSocket streaming.
   * @internal
   */
  private async _runWs(
    command: string,
    options: Omit<RunOptions, "wait"> = {},
  ): Promise<CommandHandle> {
    const {
      timeout = 60,
      env,
      cwd,
      shell = "/bin/bash",
      onStdout,
      onStderr,
      idleTimeout,
      killOnDisconnect,
      ttlSeconds,
      pty,
    } = options;
    const dataplaneUrl = this.requireDataplaneUrl();

    const [stream, control] = await runWsStream(
      dataplaneUrl,
      this._client.getApiKey(),
      command,
      {
        timeout,
        env,
        cwd,
        shell,
        onStdout,
        onStderr,
        idleTimeout,
        killOnDisconnect,
        ttlSeconds,
        pty,
      },
    );

    const handle = new CommandHandle(stream, control, this);
    await handle._ensureStarted();
    return handle;
  }

  /**
   * Execute a command via HTTP POST (blocking).
   * @internal
   */
  private async _runHttp(
    command: string,
    options: Omit<RunOptions, "wait" | "onStdout" | "onStderr"> = {},
  ): Promise<ExecutionResult> {
    const { timeout = 60, env, cwd, shell = "/bin/bash" } = options;
    const dataplaneUrl = this.requireDataplaneUrl();
    const url = `${dataplaneUrl}/execute`;

    const payload: Record<string, unknown> = {
      command,
      timeout,
      shell,
    };
    if (env !== undefined) {
      payload.env = env;
    }
    if (cwd !== undefined) {
      payload.cwd = cwd;
    }

    const response = await this._client._fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout((timeout + 10) * 1000),
    });

    if (!response.ok) {
      await handleSandboxHttpError(response);
    }

    const data = await response.json();
    return {
      stdout: data.stdout ?? "",
      stderr: data.stderr ?? "",
      exit_code: data.exit_code ?? -1,
    };
  }

  /**
   * Reconnect to a running command by its command ID.
   *
   * Returns a new CommandHandle that resumes output from the given offsets.
   *
   * @param commandId - The server-assigned command ID.
   * @param options - Reconnection options with byte offsets.
   * @returns A new CommandHandle.
   */
  async reconnect(
    commandId: string,
    options: {
      stdoutOffset?: number;
      stderrOffset?: number;
    } = {},
  ): Promise<CommandHandle> {
    const { stdoutOffset = 0, stderrOffset = 0 } = options;
    return this.traceDataplaneOperation(
      "Sandbox.reconnect",
      {
        command_id: commandId,
        stdout_offset: stdoutOffset,
        stderr_offset: stderrOffset,
      },
      () => this._reconnectUntraced(commandId, options),
      (handle) => ({ command_id: handle.commandId, pid: handle.pid }),
    );
  }

  private async _reconnectUntraced(
    commandId: string,
    options: {
      stdoutOffset?: number;
      stderrOffset?: number;
    } = {},
  ): Promise<CommandHandle> {
    const { stdoutOffset = 0, stderrOffset = 0 } = options;
    const dataplaneUrl = this.requireDataplaneUrl();

    const [stream, control] = await reconnectWsStream(
      dataplaneUrl,
      this._client.getApiKey(),
      commandId,
      { stdoutOffset, stderrOffset },
    );

    return new CommandHandle(stream, control, this, {
      commandId,
      stdoutOffset,
      stderrOffset,
    });
  }

  /**
   * Write content to a file in the sandbox.
   *
   * @param path - Target file path in the sandbox.
   * @param content - File content (string or bytes).
   * @param timeout - Request timeout in seconds.
   *
   * @example
   * ```typescript
   * await sandbox.write("/tmp/script.py", 'print("Hello!")');
   * ```
   */
  async write(
    path: string,
    content: string | Uint8Array,
    timeout = 60,
  ): Promise<void> {
    const contentBytes =
      typeof content === "string"
        ? new TextEncoder().encode(content).byteLength
        : content.byteLength;
    return this.traceDataplaneOperation(
      "Sandbox.write",
      { path, timeout, content_bytes: contentBytes },
      () => this._writeUntraced(path, content, timeout),
      () => ({ path, bytes: contentBytes }),
    );
  }

  private async _writeUntraced(
    path: string,
    content: string | Uint8Array,
    timeout = 60,
  ): Promise<void> {
    const dataplaneUrl = this.requireDataplaneUrl();
    const url = `${dataplaneUrl}/upload?path=${encodeURIComponent(path)}`;

    // Ensure content is bytes for multipart upload
    const bytes =
      typeof content === "string" ? new TextEncoder().encode(content) : content;

    const formData = new FormData();
    // Create a copy to ensure we have a plain ArrayBuffer (not SharedArrayBuffer)
    const buffer = new Uint8Array(bytes).buffer as ArrayBuffer;
    const blob = new Blob([buffer], { type: "application/octet-stream" });
    formData.append("file", blob, "file");

    const response = await this._client._fetch(url, {
      method: "POST",
      body: formData,
      signal: AbortSignal.timeout(timeout * 1000),
    });

    if (!response.ok) {
      await handleSandboxHttpError(response);
    }
  }

  /**
   * Read a file from the sandbox.
   *
   * @param path - File path to read.
   * @param timeout - Request timeout in seconds.
   * @returns File contents as Uint8Array.
   *
   * @example
   * ```typescript
   * const content = await sandbox.read("/tmp/output.txt");
   * const text = new TextDecoder().decode(content);
   * console.log(text);
   * ```
   */
  async read(path: string, timeout = 60): Promise<Uint8Array> {
    return this.traceDataplaneOperation(
      "Sandbox.read",
      { path, timeout },
      () => this._readUntraced(path, timeout),
      (content) => ({ path, bytes: content.byteLength }),
    );
  }

  private async _readUntraced(path: string, timeout = 60): Promise<Uint8Array> {
    const dataplaneUrl = this.requireDataplaneUrl();
    const url = `${dataplaneUrl}/download?path=${encodeURIComponent(path)}`;

    const response = await this._client._fetch(url, {
      method: "GET",
      signal: AbortSignal.timeout(timeout * 1000),
    });

    if (!response.ok) {
      await handleSandboxHttpError(response);
    }

    const buffer = await response.arrayBuffer();
    return new Uint8Array(buffer);
  }

  /**
   * Delete this sandbox.
   *
   * @example
   * ```typescript
   * const sandbox = await client.createSandbox(snapshot.id);
   * try {
   *   await sandbox.run("echo hello");
   * } finally {
   *   await sandbox.delete();
   * }
   * ```
   */
  async delete(): Promise<void> {
    await this._client.deleteSandbox(this.name);
  }

  /**
   * Start a stopped sandbox and wait until ready.
   *
   * Updates this sandbox's status and dataplane_url in place.
   *
   * @param timeout - Timeout in seconds when waiting for ready. Default: 120.
   */
  async start(options: StartSandboxOptions = {}): Promise<void> {
    const refreshed = await this._client.startSandbox(this.name, options);
    this.status = refreshed.status;
    this.dataplane_url = refreshed.dataplane_url;
  }

  /**
   * Stop a running sandbox (preserves sandbox files for later restart).
   */
  async stop(): Promise<void> {
    await this._client.stopSandbox(this.name);
    this.status = "stopped";
    this.dataplane_url = undefined;
  }

  /**
   * Capture a snapshot from this sandbox.
   *
   * @param name - Snapshot name.
   * @param options - Capture options (timeout).
   * @returns Snapshot in "ready" status.
   */
  async captureSnapshot(
    name: string,
    options: CaptureSnapshotOptions = {},
  ): Promise<Snapshot> {
    return this._client.captureSnapshot(this.name, name, options);
  }
}
