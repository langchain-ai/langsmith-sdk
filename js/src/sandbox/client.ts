/**
 * Main SandboxClient class for interacting with the sandbox server API.
 */

import { getLangSmithEnvironmentVariable } from "../utils/env.js";
import { _getFetchImplementation } from "../singletons/fetch.js";
import { AsyncCaller } from "../utils/async_caller.js";
import type {
  CaptureSnapshotOptions,
  CreateDockerfileSnapshotOptions,
  CreateSandboxOptions,
  CreateSnapshotOptions,
  ListSnapshotsOptions,
  ResourceStatus,
  SandboxClientConfig,
  SandboxData,
  Snapshot,
  StartSandboxOptions,
  UpdateSandboxOptions,
  WaitForSandboxOptions,
  WaitForSnapshotOptions,
} from "./types.js";
import { Sandbox } from "./sandbox.js";
import {
  LangSmithResourceCreationError,
  LangSmithResourceNameConflictError,
  LangSmithResourceNotFoundError,
  LangSmithResourceTimeoutError,
  LangSmithSandboxAPIError,
  LangSmithValidationError,
} from "./errors.js";
import {
  handleClientHttpError,
  handleSandboxCreationError,
  validateTtl,
} from "./helpers.js";
import { v4 as uuidv4 } from "../utils/uuid/src/index.js";

/**
 * Sleep that can be interrupted by an AbortSignal.
 * Resolves after `ms` milliseconds or rejects immediately if the signal fires.
 */
function sleepWithSignal(ms: number, signal?: AbortSignal): Promise<void> {
  if (!signal) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
  const abortSignal = signal;
  abortSignal.throwIfAborted();
  return new Promise<void>((resolve, reject) => {
    const timer = setTimeout(() => {
      abortSignal.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    function onAbort() {
      clearTimeout(timer);
      reject(abortSignal.reason);
    }
    abortSignal.addEventListener("abort", onAbort, { once: true });
  });
}

/**
 * Get the default sandbox API endpoint from environment.
 *
 * Derives the endpoint from LANGSMITH_ENDPOINT (or LANGCHAIN_ENDPOINT).
 */
function getDefaultApiEndpoint(): string {
  const base =
    getLangSmithEnvironmentVariable("ENDPOINT") ??
    "https://api.smith.langchain.com";
  return `${base.replace(/\/$/, "")}/v2/sandboxes`;
}

/**
 * Get the default API key from environment.
 */
function getDefaultApiKey(): string | undefined {
  return getLangSmithEnvironmentVariable("API_KEY");
}

function shellQuote(value: string): string {
  return `'${value.replace(/'/g, "'\\''")}'`;
}

function writeString(
  header: Buffer,
  value: string,
  offset: number,
  length: number,
): void {
  header.write(value.slice(0, length), offset, length, "utf8");
}

function writeOctal(
  header: Buffer,
  value: number,
  offset: number,
  length: number,
): void {
  const octal = value.toString(8).padStart(length - 1, "0");
  header.write(octal.slice(-length + 1) + "\0", offset, length, "ascii");
}

function splitTarPath(name: string): { name: string; prefix: string } {
  if (Buffer.byteLength(name) <= 100) {
    return { name, prefix: "" };
  }
  const parts = name.split("/");
  for (let i = 1; i < parts.length; i += 1) {
    const prefix = parts.slice(0, i).join("/");
    const basename = parts.slice(i).join("/");
    if (
      Buffer.byteLength(prefix) <= 155 &&
      Buffer.byteLength(basename) <= 100
    ) {
      return { name: basename, prefix };
    }
  }
  throw new Error(`Docker build context path is too long for tar: ${name}`);
}

function makeTarHeader(args: {
  name: string;
  mode: number;
  size: number;
  type: "file" | "directory" | "symlink";
  linkName?: string;
  mtimeMs: number;
}): Buffer {
  const header = Buffer.alloc(512, 0);
  const split = splitTarPath(args.name);
  writeString(header, split.name, 0, 100);
  writeOctal(header, args.mode, 100, 8);
  writeOctal(header, 0, 108, 8);
  writeOctal(header, 0, 116, 8);
  writeOctal(header, args.size, 124, 12);
  writeOctal(header, Math.floor(args.mtimeMs / 1000), 136, 12);
  header.fill(" ", 148, 156);
  writeString(
    header,
    args.type === "directory" ? "5" : args.type === "symlink" ? "2" : "0",
    156,
    1,
  );
  if (args.linkName) {
    writeString(header, args.linkName, 157, 100);
  }
  writeString(header, "ustar", 257, 6);
  writeString(header, "00", 263, 2);
  if (split.prefix) {
    writeString(header, split.prefix, 345, 155);
  }
  let checksum = 0;
  for (const byte of header) {
    checksum += byte;
  }
  header.write(checksum.toString(8).padStart(6, "0") + "\0 ", 148, 8, "ascii");
  return header;
}

async function makeDockerContextTar(contextPath: string): Promise<Uint8Array> {
  const fs = await import("node:fs/promises");
  const path = await import("node:path");
  const contextRoot = path.resolve(contextPath);
  const chunks: Buffer[] = [];

  async function addEntry(absPath: string): Promise<void> {
    const rel = path.relative(contextRoot, absPath);
    if (!rel || rel.split(path.sep).includes(".git")) {
      return;
    }
    const tarPath = rel.split(path.sep).join("/");
    const stat = await fs.lstat(absPath);
    if (stat.isDirectory()) {
      chunks.push(
        makeTarHeader({
          name: tarPath.endsWith("/") ? tarPath : `${tarPath}/`,
          mode: stat.mode & 0o777,
          size: 0,
          type: "directory",
          mtimeMs: stat.mtimeMs,
        }),
      );
      const entries = await fs.readdir(absPath);
      for (const entry of entries.sort()) {
        await addEntry(path.join(absPath, entry));
      }
      return;
    }
    if (stat.isSymbolicLink()) {
      chunks.push(
        makeTarHeader({
          name: tarPath,
          mode: stat.mode & 0o777,
          size: 0,
          type: "symlink",
          linkName: await fs.readlink(absPath),
          mtimeMs: stat.mtimeMs,
        }),
      );
      return;
    }
    if (!stat.isFile()) {
      return;
    }
    const content = await fs.readFile(absPath);
    chunks.push(
      makeTarHeader({
        name: tarPath,
        mode: stat.mode & 0o777,
        size: content.byteLength,
        type: "file",
        mtimeMs: stat.mtimeMs,
      }),
      content,
    );
    const padding = (512 - (content.byteLength % 512)) % 512;
    if (padding) {
      chunks.push(Buffer.alloc(padding, 0));
    }
  }

  const rootEntries = await fs.readdir(contextRoot);
  for (const entry of rootEntries.sort()) {
    await addEntry(path.join(contextRoot, entry));
  }
  chunks.push(Buffer.alloc(1024, 0));
  return new Uint8Array(Buffer.concat(chunks));
}

async function resolveDockerfileContext(
  dockerfile: string,
  context: string,
): Promise<{ contextPath: string; dockerfileRel: string }> {
  const fs = await import("node:fs/promises");
  const path = await import("node:path");
  const contextPath = path.resolve(context);
  const dockerfilePath = path.resolve(contextPath, dockerfile);
  const contextStat = await fs.stat(contextPath);
  if (!contextStat.isDirectory()) {
    throw new Error(`context must be a directory: ${contextPath}`);
  }
  const dockerfileStat = await fs.stat(dockerfilePath);
  if (!dockerfileStat.isFile()) {
    throw new Error(`dockerfile must be a file: ${dockerfilePath}`);
  }
  const dockerfileRel = path.relative(contextPath, dockerfilePath);
  if (
    dockerfileRel === "" ||
    dockerfileRel.startsWith("..") ||
    path.isAbsolute(dockerfileRel)
  ) {
    throw new Error("dockerfile must be inside context");
  }
  return {
    contextPath,
    dockerfileRel: dockerfileRel.split(path.sep).join("/"),
  };
}

function makeDockerfileBuildCommand(args: {
  remoteContext: string;
  dockerfileRel: string;
  imageRef: string;
  buildkitRoot: string;
  buildkitRun: string;
  buildArgs?: Record<string, string>;
  target?: string;
}): string {
  const dockerfileRemote = `${args.remoteContext}/${args.dockerfileRel}`;
  const dockerfileDir = dockerfileRemote.split("/").slice(0, -1).join("/");
  const dockerfileName = dockerfileRemote.split("/").at(-1) ?? "Dockerfile";
  const socketPath = `${args.buildkitRun}/buildkitd.sock`;
  const buildctl = [
    "buildctl",
    "--addr",
    `unix://${socketPath}`,
    "build",
    "--progress=plain",
    "--frontend",
    "dockerfile.v0",
    "--local",
    `context=${args.remoteContext}`,
    "--local",
    `dockerfile=${dockerfileDir}`,
    "--opt",
    `filename=${dockerfileName}`,
    "--output",
    `type=docker,name=${args.imageRef}`,
  ];
  if (args.target !== undefined) {
    buildctl.push("--opt", `target=${args.target}`);
  }
  for (const [key, value] of Object.entries(args.buildArgs ?? {}).sort()) {
    buildctl.push("--opt", `build-arg:${key}=${value}`);
  }
  return [
    "set -euo pipefail",
    `mkdir -p ${shellQuote(args.buildkitRoot)} ${shellQuote(args.buildkitRun)}`,
    `buildkitd --addr ${shellQuote(`unix://${socketPath}`)} --root ${shellQuote(
      args.buildkitRoot,
    )} --oci-worker=true --containerd-worker=false --oci-worker-snapshotter=native --oci-worker-binary buildkit-runc > ${shellQuote(
      `${args.buildkitRun}/buildkitd.log`,
    )} 2>&1 &`,
    "buildkitd_pid=$!",
    'cleanup() { kill "$buildkitd_pid" >/dev/null 2>&1 || true; }',
    "trap cleanup EXIT",
    "for i in $(seq 1 300); do",
    `  if buildctl --addr ${shellQuote(
      `unix://${socketPath}`,
    )} debug workers >/dev/null 2>&1; then break; fi`,
    `  if ! kill -0 "$buildkitd_pid" >/dev/null 2>&1; then cat ${shellQuote(
      `${args.buildkitRun}/buildkitd.log`,
    )}; exit 1; fi`,
    `  if [ "$i" = 300 ]; then cat ${shellQuote(
      `${args.buildkitRun}/buildkitd.log`,
    )}; exit 1; fi`,
    "  sleep 0.1",
    "done",
    "for i in $(seq 1 300); do",
    "  if docker info >/dev/null 2>&1; then break; fi",
    '  if [ "$i" = 300 ]; then docker info; exit 1; fi',
    "  sleep 0.1",
    "done",
    `${buildctl.map(shellQuote).join(" ")} | docker load`,
    `rm -rf ${shellQuote(args.buildkitRoot)} || true`,
    "",
  ].join("\n");
}

/**
 * Client for interacting with the Sandbox Server API.
 *
 * This client provides a simple interface for managing sandboxes and snapshots.
 *
 * @example
 * ```typescript
 * import { SandboxClient } from "langsmith/sandbox";
 *
 * // Uses LANGSMITH_ENDPOINT and LANGSMITH_API_KEY from environment
 * const client = new SandboxClient();
 *
 * // Or with explicit configuration
 * const client = new SandboxClient({
 *   apiEndpoint: "https://api.smith.langchain.com/v2/sandboxes",
 *   apiKey: "your-api-key",
 * });
 *
 * // Create a sandbox with the default runtime
 * const sandbox = await client.createSandbox();
 * try {
 *   const result = await sandbox.run("python --version");
 *   console.log(result.stdout);
 * } finally {
 *   await sandbox.delete();
 * }
 * ```
 */
export class SandboxClient {
  private _baseUrl: string;
  private _apiKey?: string;
  private _defaultHeaders: Record<string, string>;
  private _fetchImpl: typeof fetch;
  private _caller: AsyncCaller;

  constructor(config: SandboxClientConfig = {}) {
    this._baseUrl = (config.apiEndpoint ?? getDefaultApiEndpoint()).replace(
      /\/$/,
      "",
    );
    this._apiKey = config.apiKey ?? getDefaultApiKey();
    this._defaultHeaders = { ...(config.headers ?? {}) };
    this._fetchImpl = _getFetchImplementation();
    this._caller = new AsyncCaller({
      maxRetries: config.maxRetries ?? 3,
      maxConcurrency: config.maxConcurrency ?? Infinity,
    });
  }

  /**
   * Internal fetch method that adds authentication headers.
   *
   * Uses AsyncCaller to handle retries for transient failures
   * (network errors, 5xx, 429).
   *
   * @internal
   */
  async _fetch(url: string, init: RequestInit = {}): Promise<Response> {
    const headers = new Headers(init.headers);
    if (this._apiKey) {
      headers.set("X-Api-Key", this._apiKey);
    }
    for (const [name, value] of Object.entries(this._defaultHeaders)) {
      if (!headers.has(name)) {
        headers.set(name, value);
      }
    }
    return this._caller.call(() =>
      this._fetchImpl(url, {
        ...init,
        headers,
      }),
    );
  }

  /**
   * Get the API key for WebSocket authentication.
   * @internal
   */
  getApiKey(): string | undefined {
    return this._apiKey;
  }

  /**
   * Get the constructor-supplied default headers. Used by the WebSocket exec
   * path so headers like `X-Service-Key` set on the client are attached to
   * the WS upgrade request.
   * @internal
   */
  getDefaultHeaders(): Record<string, string> {
    return { ...this._defaultHeaders };
  }

  /**
   * JSON POST helper. Sends JSON body, checks response status,
   * and returns the Response for further processing.
   * Throws on non-ok responses via handleClientHttpError.
   * Callers can add specific status checks (e.g. 404) before calling this.
   * @internal
   */
  private async _postJson(
    url: string,
    body: Record<string, unknown>,
    options?: { signal?: AbortSignal },
  ): Promise<Response> {
    const response = await this._fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: options?.signal,
    });
    if (!response.ok) {
      await handleClientHttpError(response);
    }
    return response;
  }

  // =========================================================================
  // Sandbox Operations
  // =========================================================================

  /**
   * Create a new Sandbox.
   *
   * Remember to call `sandbox.delete()` when done to clean up resources.
   *
   * @param snapshotId - Optional snapshot ID to boot from.
   * @param options - Creation options. Use `options.snapshotName` to boot from
   *   a named snapshot instead of the default runtime.
   * @returns Created Sandbox.
   * @throws ResourceTimeoutError if timeout waiting for sandbox to be ready.
   * @throws SandboxCreationError if sandbox creation fails.
   * @throws LangSmithValidationError if TTL values are invalid, or if both
   *   `snapshotId` and `options.snapshotName` are provided.
   *
   * @example
   * ```typescript
   * const sandbox = await client.createSandbox();
   * // Or, resolve by snapshot name:
   * const sandbox = await client.createSandbox({
   *   snapshotName: "python",
   * });
   * try {
   *   const result = await sandbox.run("echo hello");
   *   console.log(result.stdout);
   * } finally {
   *   await sandbox.delete();
   * }
   * ```
   */
  async createSandbox(options?: CreateSandboxOptions): Promise<Sandbox>;
  async createSandbox(
    snapshotId?: string,
    options?: CreateSandboxOptions,
  ): Promise<Sandbox>;
  async createSandbox(
    snapshotIdOrOptions?: string | CreateSandboxOptions,
    options: CreateSandboxOptions = {},
  ): Promise<Sandbox> {
    const snapshotId =
      typeof snapshotIdOrOptions === "string" ? snapshotIdOrOptions : undefined;
    const resolvedOptions =
      typeof snapshotIdOrOptions === "object" && snapshotIdOrOptions !== null
        ? snapshotIdOrOptions
        : options;
    const {
      snapshotName,
      name,
      timeout = 30,
      waitForReady = true,
      idleTtlSeconds,
      deleteAfterStopSeconds,
      vCpus,
      memBytes,
      fsCapacityBytes,
      proxyConfig,
    } = resolvedOptions;

    if (snapshotId && snapshotName) {
      throw new LangSmithValidationError(
        "At most one of snapshotId or options.snapshotName may be set",
        "snapshotId",
      );
    }

    validateTtl(idleTtlSeconds, "idleTtlSeconds");
    validateTtl(deleteAfterStopSeconds, "deleteAfterStopSeconds");

    const url = `${this._baseUrl}/boxes`;

    const payload: Record<string, unknown> = {
      wait_for_ready: waitForReady,
    };
    if (snapshotId) {
      payload.snapshot_id = snapshotId;
    }
    if (snapshotName) {
      payload.snapshot_name = snapshotName;
    }
    if (waitForReady) {
      payload.timeout = timeout;
    }
    if (name) {
      payload.name = name;
    }
    if (idleTtlSeconds !== undefined) {
      payload.idle_ttl_seconds = idleTtlSeconds;
    }
    if (deleteAfterStopSeconds !== undefined) {
      payload.delete_after_stop_seconds = deleteAfterStopSeconds;
    }
    if (vCpus !== undefined) {
      payload.vcpus = vCpus;
    }
    if (memBytes !== undefined) {
      payload.mem_bytes = memBytes;
    }
    if (fsCapacityBytes !== undefined) {
      payload.fs_capacity_bytes = fsCapacityBytes;
    }
    if (proxyConfig !== undefined) {
      payload.proxy_config = proxyConfig;
    }

    const httpTimeout = waitForReady ? (timeout + 30) * 1000 : 30 * 1000;

    const response = await this._fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(httpTimeout),
    });

    if (!response.ok) {
      await handleSandboxCreationError(response);
    }

    const data = (await response.json()) as SandboxData;
    return new Sandbox(data, this);
  }

  /**
   * Get a Sandbox by name.
   *
   * The sandbox is NOT automatically deleted. Use deleteSandbox() for cleanup.
   *
   * @param name - Sandbox name.
   * @returns Sandbox.
   * @throws LangSmithResourceNotFoundError if sandbox not found.
   */
  async getSandbox(
    name: string,
    options?: { signal?: AbortSignal },
  ): Promise<Sandbox> {
    const url = `${this._baseUrl}/boxes/${encodeURIComponent(name)}`;

    const response = await this._fetch(url, { signal: options?.signal });

    if (!response.ok) {
      if (response.status === 404) {
        throw new LangSmithResourceNotFoundError(
          `Sandbox '${name}' not found`,
          "sandbox",
        );
      }
      await handleClientHttpError(response);
    }

    const data = (await response.json()) as SandboxData;
    return new Sandbox(data, this);
  }

  /**
   * List all Sandboxes.
   *
   * @returns List of Sandboxes.
   */
  async listSandboxes(): Promise<Sandbox[]> {
    const url = `${this._baseUrl}/boxes`;

    const response = await this._fetch(url);

    if (!response.ok) {
      if (response.status === 404) {
        throw new LangSmithSandboxAPIError(
          `API endpoint not found: ${url}. Check that apiEndpoint is correct.`,
        );
      }
      await handleClientHttpError(response);
    }

    const data = await response.json();
    return ((data.sandboxes ?? []) as SandboxData[]).map(
      (s) => new Sandbox(s, this),
    );
  }

  /**
   * Update a sandbox's display name.
   *
   * @param name - Current sandbox name.
   * @param newName - New display name.
   */
  async updateSandbox(name: string, newName: string): Promise<Sandbox>;
  /**
   * Update a sandbox's name and/or retention settings (idle stop and
   * delete-after-stop).
   *
   * @param name - Current sandbox name.
   * @param options - Fields to update. Omit a field to leave it unchanged.
   * @returns Updated Sandbox. If no fields are provided, returns the current sandbox.
   * @throws LangSmithResourceNotFoundError if sandbox not found.
   * @throws LangSmithResourceNameConflictError if newName is already in use.
   * @throws LangSmithValidationError if retention values are invalid.
   */
  async updateSandbox(
    name: string,
    options: UpdateSandboxOptions,
  ): Promise<Sandbox>;
  async updateSandbox(
    name: string,
    newNameOrOptions: string | UpdateSandboxOptions,
  ): Promise<Sandbox> {
    const options: UpdateSandboxOptions =
      typeof newNameOrOptions === "string"
        ? { newName: newNameOrOptions }
        : newNameOrOptions;

    const { newName, idleTtlSeconds, deleteAfterStopSeconds } = options;
    validateTtl(idleTtlSeconds, "idleTtlSeconds");
    validateTtl(deleteAfterStopSeconds, "deleteAfterStopSeconds");

    if (
      newName === undefined &&
      idleTtlSeconds === undefined &&
      deleteAfterStopSeconds === undefined
    ) {
      return this.getSandbox(name);
    }

    const url = `${this._baseUrl}/boxes/${encodeURIComponent(name)}`;
    const payload: Record<string, unknown> = {};
    if (newName !== undefined) {
      payload.name = newName;
    }
    if (idleTtlSeconds !== undefined) {
      payload.idle_ttl_seconds = idleTtlSeconds;
    }
    if (deleteAfterStopSeconds !== undefined) {
      payload.delete_after_stop_seconds = deleteAfterStopSeconds;
    }

    const response = await this._fetch(url, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      if (response.status === 404) {
        throw new LangSmithResourceNotFoundError(
          `Sandbox '${name}' not found`,
          "sandbox",
        );
      }
      if (response.status === 409) {
        throw new LangSmithResourceNameConflictError(
          newName !== undefined
            ? `Sandbox name '${newName}' already in use`
            : "Sandbox update conflict (name may already be in use)",
          "sandbox",
        );
      }
      await handleClientHttpError(response);
    }

    const data = (await response.json()) as SandboxData;
    return new Sandbox(data, this);
  }

  /**
   * Delete a Sandbox.
   *
   * @param name - Sandbox name.
   * @throws LangSmithResourceNotFoundError if sandbox not found.
   */
  async deleteSandbox(name: string): Promise<void> {
    const url = `${this._baseUrl}/boxes/${encodeURIComponent(name)}`;

    const response = await this._fetch(url, { method: "DELETE" });

    if (!response.ok) {
      if (response.status === 404) {
        throw new LangSmithResourceNotFoundError(
          `Sandbox '${name}' not found`,
          "sandbox",
        );
      }
      await handleClientHttpError(response);
    }
  }

  /**
   * Get the provisioning status of a sandbox.
   *
   * This is a lightweight endpoint designed for polling during async creation.
   * Use this instead of getSandbox() when you only need the status.
   *
   * @param name - Sandbox name.
   * @returns ResourceStatus with status and optional status_message.
   * @throws LangSmithResourceNotFoundError if sandbox not found.
   */
  async getSandboxStatus(
    name: string,
    options?: { signal?: AbortSignal },
  ): Promise<ResourceStatus> {
    const url = `${this._baseUrl}/boxes/${encodeURIComponent(name)}/status`;

    const response = await this._fetch(url, { signal: options?.signal });

    if (!response.ok) {
      if (response.status === 404) {
        throw new LangSmithResourceNotFoundError(
          `Sandbox '${name}' not found`,
          "sandbox",
        );
      }
      await handleClientHttpError(response);
    }

    return (await response.json()) as ResourceStatus;
  }

  /**
   * Wait for a sandbox to become ready.
   *
   * Polls getSandboxStatus() until the sandbox reaches "ready" or "failed" status,
   * then returns the full Sandbox object.
   *
   * @param name - Sandbox name.
   * @param options - Polling options (timeout, pollInterval).
   * @returns Ready Sandbox.
   * @throws LangSmithResourceCreationError if sandbox status becomes "failed".
   * @throws LangSmithResourceTimeoutError if timeout expires while still provisioning.
   * @throws LangSmithResourceNotFoundError if sandbox not found.
   *
   * @example
   * ```typescript
   * const sandbox = await client.createSandbox(snapshot.id, { waitForReady: false });
   * // ... do other work ...
   * const readySandbox = await client.waitForSandbox(sandbox.name);
   * ```
   */
  async waitForSandbox(
    name: string,
    options: WaitForSandboxOptions = {},
  ): Promise<Sandbox> {
    const { timeout = 120, pollInterval = 1.0, signal } = options;
    const deadline = Date.now() + timeout * 1000;
    let lastStatus = "provisioning";

    while (Date.now() < deadline) {
      signal?.throwIfAborted();

      const statusResult = await this.getSandboxStatus(name, { signal });
      lastStatus = statusResult.status;

      if (statusResult.status === "ready") {
        return this.getSandbox(name, { signal });
      }

      if (statusResult.status === "failed") {
        throw new LangSmithResourceCreationError(
          statusResult.status_message ?? `Sandbox '${name}' creation failed`,
          "sandbox",
        );
      }

      // Wait before polling again, capped to remaining time + jitter
      const remaining = deadline - Date.now();
      const jitter = pollInterval * 200 * (Math.random() - 0.5); // ±10%
      const delay = Math.min(pollInterval * 1000 + jitter, remaining);
      if (delay > 0) {
        await sleepWithSignal(delay, signal);
      }
    }

    throw new LangSmithResourceTimeoutError(
      `Sandbox '${name}' did not become ready within ${timeout}s`,
      "sandbox",
      lastStatus,
    );
  }

  /**
   * Start a stopped sandbox and wait until ready.
   *
   * @param name - Sandbox name.
   * @param options - Options with timeout.
   * @returns Sandbox in "ready" status.
   */
  async startSandbox(
    name: string,
    options: StartSandboxOptions = {},
  ): Promise<Sandbox> {
    const { timeout = 120, signal } = options;
    const url = `${this._baseUrl}/boxes/${encodeURIComponent(name)}/start`;

    await this._postJson(url, {}, { signal });
    return this.waitForSandbox(name, { timeout, signal });
  }

  /**
   * Stop a running sandbox (preserves sandbox files for later restart).
   *
   * @param name - Sandbox name.
   */
  async stopSandbox(name: string): Promise<void> {
    const url = `${this._baseUrl}/boxes/${encodeURIComponent(name)}/stop`;
    await this._postJson(url, {});
  }

  // =========================================================================
  // Snapshot Operations
  // =========================================================================

  /**
   * Build a snapshot from a Docker image.
   *
   * Blocks until the snapshot is ready (polls with 2s interval).
   *
   * @param name - Snapshot name.
   * @param dockerImage - Docker image to build from (e.g., "python:3.12-slim").
   * @param fsCapacityBytes - Filesystem capacity in bytes.
   * @param options - Additional options (registry credentials, timeout).
   * @returns Snapshot in "ready" status.
   */
  async createSnapshot(
    name: string,
    dockerImage: string,
    fsCapacityBytes: number,
    options: CreateSnapshotOptions = {},
  ): Promise<Snapshot> {
    const {
      registryId,
      registryUrl,
      registryUsername,
      registryPassword,
      timeout = 60,
      signal,
    } = options;
    const url = `${this._baseUrl}/snapshots`;

    const payload: Record<string, unknown> = {
      name,
      docker_image: dockerImage,
      fs_capacity_bytes: fsCapacityBytes,
    };
    if (registryId !== undefined) {
      payload.registry_id = registryId;
    }
    if (registryUrl !== undefined) {
      payload.registry_url = registryUrl;
    }
    if (registryUsername !== undefined) {
      payload.registry_username = registryUsername;
    }
    if (registryPassword !== undefined) {
      payload.registry_password = registryPassword;
    }

    const response = await this._postJson(url, payload, { signal });
    const snapshot = (await response.json()) as Snapshot;
    return this.waitForSnapshot(snapshot.id, { timeout, signal });
  }

  /**
   * Build a snapshot from a local Dockerfile context.
   *
   * Creates a temporary builder sandbox, uploads the Docker build context,
   * runs BuildKit inside the sandbox, and captures the built image as a
   * LangSmith snapshot.
   *
   * @param name - Snapshot name.
   * @param dockerfile - Local Dockerfile path, relative to context by default.
   * @param fsCapacityBytes - Filesystem capacity in bytes.
   * @param options - Build context, args, target, build log callback, builder
   *   vCPUs/memory, timeout.
   * @returns Snapshot in "ready" status.
   */
  async createSnapshotFromDockerfile(
    name: string,
    dockerfile: string,
    fsCapacityBytes: number,
    options: CreateDockerfileSnapshotOptions = {},
  ): Promise<Snapshot> {
    const {
      context = ".",
      buildArgs,
      target,
      onBuildLog,
      vCpus,
      memBytes,
      timeout = 60,
    } = options;
    const { contextPath, dockerfileRel } = await resolveDockerfileContext(
      dockerfile,
      context,
    );

    const builderName = `snapshot-builder-${uuidv4().replace(/-/g, "").slice(0, 12)}`;
    // Stage the build on the capacity-backed root filesystem, not /tmp.
    // Inside the sandbox /tmp is a RAM-backed tmpfs that fsCapacityBytes does
    // not size, and BuildKit's native snapshotter writes a full copy of every
    // layer under its root, so a /tmp build exhausts guest RAM and fails with
    // "No space left on device".
    const buildRoot = `/var/lib/langsmith-build/${uuidv4()
      .replace(/-/g, "")
      .slice(0, 12)}`;
    const remoteContext = `${buildRoot}/context`;
    const remoteTar = `${buildRoot}/context.tar`;
    const imageRef = `langsmith-snapshot-build:${uuidv4().replace(/-/g, "")}`;
    const buildkitRoot = `${buildRoot}/buildkit-root`;
    const buildkitRun = `${buildRoot}/buildkit-run`;

    const builder = await this.createSandbox({
      name: builderName,
      timeout,
      vCpus,
      memBytes,
      fsCapacityBytes,
    });
    try {
      await builder.write(
        remoteTar,
        await makeDockerContextTar(contextPath),
        timeout,
      );
      await builder.run(
        [
          `rm -rf ${shellQuote(remoteContext)}`,
          `mkdir -p ${shellQuote(remoteContext)}`,
          `tar -xf ${shellQuote(remoteTar)} -C ${shellQuote(remoteContext)}`,
        ].join(" && "),
        { timeout },
      );

      const result = await builder.run(
        makeDockerfileBuildCommand({
          remoteContext,
          dockerfileRel,
          imageRef,
          buildkitRoot,
          buildkitRun,
          buildArgs,
          target,
        }),
        {
          timeout,
          onStdout: onBuildLog,
          onStderr: onBuildLog,
        },
      );
      if (result.exit_code !== 0) {
        throw new LangSmithResourceCreationError(
          "Dockerfile snapshot build failed",
          "snapshot",
        );
      }
      return await this.captureSnapshot(builder.name, name, {
        dockerImage: imageRef,
        fsCapacityBytes,
        timeout,
      });
    } finally {
      await builder.delete();
    }
  }

  /**
   * Capture a snapshot from a running sandbox.
   *
   * Blocks until the snapshot is ready (polls with 2s interval).
   *
   * @param sandboxName - Name of the sandbox to capture from.
   * @param name - Snapshot name.
   * @param options - Capture options (timeout).
   * @returns Snapshot in "ready" status.
   */
  async captureSnapshot(
    sandboxName: string,
    name: string,
    options: CaptureSnapshotOptions = {},
  ): Promise<Snapshot> {
    const { dockerImage, fsCapacityBytes, timeout = 60, signal } = options;
    const url = `${this._baseUrl}/boxes/${encodeURIComponent(
      sandboxName,
    )}/snapshot`;

    const payload: Record<string, unknown> = { name };
    if (dockerImage !== undefined) {
      payload.docker_image = dockerImage;
    }
    if (fsCapacityBytes !== undefined) {
      payload.fs_capacity_bytes = fsCapacityBytes;
    }

    const response = await this._postJson(url, payload, { signal });
    const snapshot = (await response.json()) as Snapshot;
    return this.waitForSnapshot(snapshot.id, { timeout, signal });
  }

  /**
   * Get a snapshot by ID.
   *
   * @param snapshotId - Snapshot UUID.
   * @returns Snapshot.
   */
  async getSnapshot(
    snapshotId: string,
    options?: { signal?: AbortSignal },
  ): Promise<Snapshot> {
    const url = `${this._baseUrl}/snapshots/${encodeURIComponent(snapshotId)}`;

    const response = await this._fetch(url, { signal: options?.signal });

    if (!response.ok) {
      if (response.status === 404) {
        throw new LangSmithResourceNotFoundError(
          `Snapshot '${snapshotId}' not found`,
          "snapshot",
        );
      }
      await handleClientHttpError(response);
    }

    return (await response.json()) as Snapshot;
  }

  /**
   * List snapshots, optionally filtered and paginated server-side.
   *
   * The backend always paginates this endpoint. When `limit` is omitted the
   * server applies a default page size (currently 50), so a single call is
   * not guaranteed to return every snapshot visible to the tenant. To iterate
   * through all results, repeat the call with increasing `offset` values (or
   * an explicit `limit`) until fewer than `limit` snapshots come back.
   *
   * @param options - Optional filter/pagination options.
   *   - `nameContains`: case-insensitive substring match on snapshot name.
   *   - `limit`: page size; must be between 1 and 500 (inclusive). Defaults
   *     to 50 server-side when omitted.
   *   - `offset`: number of snapshots to skip; must be `>= 0`.
   *
   *   Values outside those ranges are rejected by the server.
   * @returns A single page of Snapshots matching the provided filters.
   *
   * @example
   * ```typescript
   * const firstPage = await client.listSnapshots();
   * const page = await client.listSnapshots({
   *   nameContains: "python",
   *   limit: 100,
   *   offset: 0,
   * });
   * ```
   */
  async listSnapshots(options: ListSnapshotsOptions = {}): Promise<Snapshot[]> {
    const { nameContains, limit, offset, signal } = options;

    const params = new URLSearchParams();
    if (nameContains !== undefined) {
      params.set("name_contains", nameContains);
    }
    if (limit !== undefined) {
      params.set("limit", String(limit));
    }
    if (offset !== undefined) {
      params.set("offset", String(offset));
    }

    const query = params.toString();
    const url = query
      ? `${this._baseUrl}/snapshots?${query}`
      : `${this._baseUrl}/snapshots`;

    const response = await this._fetch(url, { signal });

    if (!response.ok) {
      await handleClientHttpError(response);
    }

    const data = await response.json();
    return (data.snapshots ?? []) as Snapshot[];
  }

  /**
   * Delete a snapshot.
   *
   * @param snapshotId - Snapshot UUID.
   */
  async deleteSnapshot(snapshotId: string): Promise<void> {
    const url = `${this._baseUrl}/snapshots/${encodeURIComponent(snapshotId)}`;

    const response = await this._fetch(url, { method: "DELETE" });

    if (!response.ok) {
      await handleClientHttpError(response);
    }
  }

  /**
   * Poll until a snapshot reaches "ready" or "failed" status.
   *
   * @param snapshotId - Snapshot UUID.
   * @param options - Polling options (timeout, pollInterval).
   * @returns Snapshot in "ready" status.
   */
  async waitForSnapshot(
    snapshotId: string,
    options: WaitForSnapshotOptions = {},
  ): Promise<Snapshot> {
    const { timeout = 300, pollInterval = 2.0, signal } = options;
    const deadline = Date.now() + timeout * 1000;
    let lastStatus = "building";

    while (Date.now() < deadline) {
      signal?.throwIfAborted();

      const snapshot = await this.getSnapshot(snapshotId, { signal });
      lastStatus = snapshot.status;

      if (snapshot.status === "ready") {
        return snapshot;
      }

      if (snapshot.status === "failed") {
        throw new LangSmithResourceCreationError(
          snapshot.status_message ?? `Snapshot '${snapshotId}' build failed`,
          "snapshot",
        );
      }

      // Cap sleep to remaining time + jitter
      const remaining = deadline - Date.now();
      const jitter = pollInterval * 200 * (Math.random() - 0.5); // ±10%
      const delay = Math.min(pollInterval * 1000 + jitter, remaining);
      if (delay > 0) {
        await sleepWithSignal(delay, signal);
      }
    }

    throw new LangSmithResourceTimeoutError(
      `Snapshot '${snapshotId}' did not become ready within ${timeout}s`,
      "snapshot",
      lastStatus,
    );
  }

  /**
   * Returns a string representation of the SandboxClient instance.
   * This method is called when the object is converted to a string
   * or logged, ensuring sensitive information like API keys is not exposed.
   *
   * @returns A string representation of the SandboxClient.
   */
  public toString(): string {
    return `[LangSmithSandboxClient apiEndpoint=${JSON.stringify(
      this._baseUrl,
    )}]`;
  }

  /**
   * Custom inspect method for Node.js.
   * This method is called when the object is inspected in the Node.js REPL
   * or with console.log, ensuring sensitive information like API keys is not exposed.
   *
   * @returns A string representation of the SandboxClient for inspection.
   */
  public [Symbol.for("nodejs.util.inspect.custom")](): string {
    return this.toString();
  }
}
