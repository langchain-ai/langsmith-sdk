/**
 * Sandbox class for interacting with a specific sandbox instance.
 */

import type { SandboxClient } from "./client.js";
import type { ExecutionResult, RunOptions, SandboxData } from "./types.js";
import { LangSmithDataplaneNotConfiguredError } from "./errors.js";
import { handleSandboxHttpError } from "./helpers.js";

/**
 * Represents an active sandbox for running commands and file operations.
 *
 * This class is typically obtained from SandboxClient.createSandbox() and
 * provides methods for command execution and file I/O within the sandbox
 * environment.
 *
 * @example
 * ```typescript
 * const sandbox = await client.createSandbox("python-sandbox");
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
  /** Name of the template used to create this sandbox. */
  readonly template_name: string;
  /** URL for data plane operations (file I/O, command execution). */
  readonly dataplane_url?: string;
  /** Unique identifier (UUID). Remains constant even if name changes. */
  readonly id?: string;
  /** Timestamp when the sandbox was created. */
  readonly created_at?: string;
  /** Timestamp when the sandbox was last updated. */
  readonly updated_at?: string;

  private _client: SandboxClient;

  /** @internal */
  constructor(data: SandboxData, client: SandboxClient) {
    this.name = data.name;
    this.template_name = data.template_name;
    this.dataplane_url = data.dataplane_url;
    this.id = data.id;
    this.created_at = data.created_at;
    this.updated_at = data.updated_at;
    this._client = client;
  }

  /**
   * Validate and return the dataplane URL.
   * @throws LangSmithDataplaneNotConfiguredError if dataplane_url is not configured.
   */
  private requireDataplaneUrl(): string {
    if (!this.dataplane_url) {
      throw new LangSmithDataplaneNotConfiguredError(
        `Sandbox '${this.name}' does not have a dataplane_url configured. ` +
          "Runtime operations require a dataplane URL."
      );
    }
    return this.dataplane_url;
  }

  /**
   * Execute a command in the sandbox.
   *
   * @param command - Shell command to execute.
   * @param options - Execution options.
   * @returns ExecutionResult with stdout, stderr, and exit_code.
   * @throws LangSmithDataplaneNotConfiguredError if dataplane_url is not configured.
   * @throws SandboxOperationError if command execution fails.
   * @throws SandboxConnectionError if connection to sandbox fails.
   * @throws SandboxNotReadyError if sandbox is not ready.
   *
   * @example
   * ```typescript
   * const result = await sandbox.run("echo hello");
   * console.log(result.stdout); // "hello\n"
   * console.log(result.exit_code); // 0
   * ```
   */
  async run(
    command: string,
    options: RunOptions = {}
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
   * Write content to a file in the sandbox.
   *
   * @param path - Target file path in the sandbox.
   * @param content - File content (string or bytes).
   * @param timeout - Request timeout in seconds.
   * @throws LangSmithDataplaneNotConfiguredError if dataplane_url is not configured.
   * @throws SandboxOperationError if file write fails.
   * @throws SandboxConnectionError if connection to sandbox fails.
   *
   * @example
   * ```typescript
   * await sandbox.write("/tmp/script.py", 'print("Hello!")');
   * ```
   */
  async write(
    path: string,
    content: string | Uint8Array,
    timeout = 60
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
   * @param path - File path to read. Supports both absolute paths (e.g., /tmp/file.txt)
   *               and relative paths (resolved from /home/user/).
   * @param timeout - Request timeout in seconds.
   * @returns File contents as Uint8Array.
   * @throws LangSmithDataplaneNotConfiguredError if dataplane_url is not configured.
   * @throws ResourceNotFoundError if the file doesn't exist.
   * @throws SandboxOperationError if file read fails.
   * @throws SandboxConnectionError if connection to sandbox fails.
   *
   * @example
   * ```typescript
   * const content = await sandbox.read("/tmp/output.txt");
   * const text = new TextDecoder().decode(content);
   * console.log(text);
   * ```
   */
  async read(path: string, timeout = 60): Promise<Uint8Array> {
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
   * Call this when you're done using the sandbox to clean up resources.
   *
   * @example
   * ```typescript
   * const sandbox = await client.createSandbox("python-sandbox");
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
}
