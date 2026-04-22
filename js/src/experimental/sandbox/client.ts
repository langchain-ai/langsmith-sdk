/**
 * Main SandboxClient class for interacting with the sandbox server API.
 */

import { getLangSmithEnvironmentVariable } from "../../utils/env.js";
import { _getFetchImplementation } from "../../singletons/fetch.js";
import { AsyncCaller } from "../../utils/async_caller.js";
import type {
  CaptureSnapshotOptions,
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

/**
 * Sleep that can be interrupted by an AbortSignal.
 * Resolves after `ms` milliseconds or rejects immediately if the signal fires.
 */
function sleepWithSignal(ms: number, signal?: AbortSignal): Promise<void> {
  if (!signal) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
  signal.throwIfAborted();
  return new Promise<void>((resolve, reject) => {
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    function onAbort() {
      clearTimeout(timer);
      reject(signal!.reason);
    }
    signal.addEventListener("abort", onAbort, { once: true });
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

/**
 * Client for interacting with the Sandbox Server API.
 *
 * This client provides a simple interface for managing sandboxes and snapshots.
 *
 * @example
 * ```typescript
 * import { SandboxClient } from "langsmith/experimental/sandbox";
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
 * // Build a snapshot, then create a sandbox from it
 * const snapshot = await client.createSnapshot(
 *   "python",
 *   "python:3.12-slim",
 *   1_073_741_824 // 1 GiB
 * );
 * const sandbox = await client.createSandbox(snapshot.id);
 * try {
 *   const result = await sandbox.run("python --version");
 *   console.log(result.stdout);
 * } finally {
 *   await sandbox.delete();
 * }
 * ```
 *
 * @experimental This feature is experimental, and breaking changes are expected.
 */
export class SandboxClient {
  private _baseUrl: string;
  private _apiKey?: string;
  private _fetchImpl: typeof fetch;
  private _caller: AsyncCaller;

  constructor(config: SandboxClientConfig = {}) {
    this._baseUrl = (config.apiEndpoint ?? getDefaultApiEndpoint()).replace(
      /\/$/,
      ""
    );
    this._apiKey = config.apiKey ?? getDefaultApiKey();
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
    return this._caller.call(() =>
      this._fetchImpl(url, {
        ...init,
        headers,
      })
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
   * JSON POST helper. Sends JSON body, checks response status,
   * and returns the Response for further processing.
   * Throws on non-ok responses via handleClientHttpError.
   * Callers can add specific status checks (e.g. 404) before calling this.
   * @internal
   */
  private async _postJson(
    url: string,
    body: Record<string, unknown>,
    options?: { signal?: AbortSignal }
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
   * Create a new Sandbox from a snapshot.
   *
   * Remember to call `sandbox.delete()` when done to clean up resources.
   *
   * Exactly one of `snapshotId` (positional) or `options.snapshotName` must
   * be provided. When `snapshotName` is used, the server resolves it to a
   * snapshot owned by the caller's tenant.
   *
   * @param snapshotId - ID of the snapshot to boot from. Create one with
   *   `createSnapshot()` or `captureSnapshot()`, or pass an existing snapshot ID.
   *   Pass `undefined` when booting by name via `options.snapshotName`.
   * @param options - Creation options. Use `options.snapshotName` to boot
   *   by snapshot name instead of ID.
   * @returns Created Sandbox.
   * @throws ResourceTimeoutError if timeout waiting for sandbox to be ready.
   * @throws SandboxCreationError if sandbox creation fails.
   * @throws LangSmithValidationError if TTL values are invalid, or if neither
   *   (or both) of `snapshotId` / `options.snapshotName` are provided.
   *
   * @example
   * ```typescript
   * const snapshot = await client.createSnapshot(
   *   "python",
   *   "python:3.12-slim",
   *   1_073_741_824
   * );
   * const sandbox = await client.createSandbox(snapshot.id);
   * // Or, resolve by snapshot name:
   * const sandbox = await client.createSandbox(undefined, {
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
  async createSandbox(
    snapshotId?: string,
    options: CreateSandboxOptions = {}
  ): Promise<Sandbox> {
    const {
      snapshotName,
      name,
      timeout = 30,
      waitForReady = true,
      ttlSeconds,
      idleTtlSeconds,
      vCpus,
      memBytes,
      fsCapacityBytes,
      proxyConfig,
    } = options;

    if (!!snapshotId === !!snapshotName) {
      throw new LangSmithValidationError(
        "Exactly one of snapshotId or options.snapshotName must be set",
        "snapshotId"
      );
    }

    validateTtl(ttlSeconds, "ttlSeconds");
    validateTtl(idleTtlSeconds, "idleTtlSeconds");

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
    if (ttlSeconds !== undefined) {
      payload.ttl_seconds = ttlSeconds;
    }
    if (idleTtlSeconds !== undefined) {
      payload.idle_ttl_seconds = idleTtlSeconds;
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
    options?: { signal?: AbortSignal }
  ): Promise<Sandbox> {
    const url = `${this._baseUrl}/boxes/${encodeURIComponent(name)}`;

    const response = await this._fetch(url, { signal: options?.signal });

    if (!response.ok) {
      if (response.status === 404) {
        throw new LangSmithResourceNotFoundError(
          `Sandbox '${name}' not found`,
          "sandbox"
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
          `API endpoint not found: ${url}. Check that apiEndpoint is correct.`
        );
      }
      await handleClientHttpError(response);
    }

    const data = await response.json();
    return ((data.sandboxes ?? []) as SandboxData[]).map(
      (s) => new Sandbox(s, this)
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
   * Update a sandbox's name and/or TTL settings.
   *
   * @param name - Current sandbox name.
   * @param options - Fields to update. Omit a field to leave it unchanged.
   * @returns Updated Sandbox. If no fields are provided, returns the current sandbox.
   * @throws LangSmithResourceNotFoundError if sandbox not found.
   * @throws LangSmithResourceNameConflictError if newName is already in use.
   * @throws LangSmithValidationError if TTL values are invalid.
   */
  async updateSandbox(
    name: string,
    options: UpdateSandboxOptions
  ): Promise<Sandbox>;
  async updateSandbox(
    name: string,
    newNameOrOptions: string | UpdateSandboxOptions
  ): Promise<Sandbox> {
    const options: UpdateSandboxOptions =
      typeof newNameOrOptions === "string"
        ? { newName: newNameOrOptions }
        : newNameOrOptions;

    const { newName, ttlSeconds, idleTtlSeconds } = options;
    validateTtl(ttlSeconds, "ttlSeconds");
    validateTtl(idleTtlSeconds, "idleTtlSeconds");

    if (
      newName === undefined &&
      ttlSeconds === undefined &&
      idleTtlSeconds === undefined
    ) {
      return this.getSandbox(name);
    }

    const url = `${this._baseUrl}/boxes/${encodeURIComponent(name)}`;
    const payload: Record<string, unknown> = {};
    if (newName !== undefined) {
      payload.name = newName;
    }
    if (ttlSeconds !== undefined) {
      payload.ttl_seconds = ttlSeconds;
    }
    if (idleTtlSeconds !== undefined) {
      payload.idle_ttl_seconds = idleTtlSeconds;
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
          "sandbox"
        );
      }
      if (response.status === 409) {
        throw new LangSmithResourceNameConflictError(
          newName !== undefined
            ? `Sandbox name '${newName}' already in use`
            : "Sandbox update conflict (name may already be in use)",
          "sandbox"
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
          "sandbox"
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
    options?: { signal?: AbortSignal }
  ): Promise<ResourceStatus> {
    const url = `${this._baseUrl}/boxes/${encodeURIComponent(name)}/status`;

    const response = await this._fetch(url, { signal: options?.signal });

    if (!response.ok) {
      if (response.status === 404) {
        throw new LangSmithResourceNotFoundError(
          `Sandbox '${name}' not found`,
          "sandbox"
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
    options: WaitForSandboxOptions = {}
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
          "sandbox"
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
      lastStatus
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
    options: StartSandboxOptions = {}
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
    options: CreateSnapshotOptions = {}
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
    options: CaptureSnapshotOptions = {}
  ): Promise<Snapshot> {
    const { timeout = 60, signal } = options;
    const url = `${this._baseUrl}/boxes/${encodeURIComponent(
      sandboxName
    )}/snapshot`;

    const payload: Record<string, unknown> = { name };

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
    options?: { signal?: AbortSignal }
  ): Promise<Snapshot> {
    const url = `${this._baseUrl}/snapshots/${encodeURIComponent(snapshotId)}`;

    const response = await this._fetch(url, { signal: options?.signal });

    if (!response.ok) {
      if (response.status === 404) {
        throw new LangSmithResourceNotFoundError(
          `Snapshot '${snapshotId}' not found`,
          "snapshot"
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
    options: WaitForSnapshotOptions = {}
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
          "snapshot"
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
      lastStatus
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
      this._baseUrl
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
