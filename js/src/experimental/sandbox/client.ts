/**
 * Main SandboxClient class for interacting with the sandbox server API.
 */

import { getLangSmithEnvironmentVariable } from "../../utils/env.js";
import { _getFetchImplementation } from "../../singletons/fetch.js";
import { AsyncCaller } from "../../utils/async_caller.js";
import type {
  CreatePoolOptions,
  CreateSandboxOptions,
  CreateTemplateOptions,
  CreateVolumeOptions,
  Pool,
  SandboxClientConfig,
  SandboxData,
  SandboxTemplate,
  UpdatePoolOptions,
  UpdateTemplateOptions,
  UpdateVolumeOptions,
  Volume,
} from "./types.js";
import { Sandbox } from "./sandbox.js";
import {
  LangSmithResourceNameConflictError,
  LangSmithResourceNotFoundError,
  LangSmithSandboxAPIError,
} from "./errors.js";
import {
  handleClientHttpError,
  handleConflictError,
  handlePoolError,
  handleResourceInUseError,
  handleSandboxCreationError,
  handleVolumeCreationError,
} from "./helpers.js";

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
 * This client provides a simple interface for managing sandboxes and templates.
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
 * // Create a sandbox and run commands
 * const sandbox = await client.createSandbox("python-sandbox");
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

  // =========================================================================
  // Volume Operations
  // =========================================================================

  /**
   * Create a new persistent volume.
   *
   * Creates a persistent storage volume that can be referenced in templates.
   *
   * @param name - Volume name.
   * @param options - Creation options including size and optional timeout.
   * @returns Created Volume.
   * @throws SandboxCreationError if volume provisioning fails.
   * @throws ResourceTimeoutError if volume doesn't become ready within timeout.
   */
  async createVolume(
    name: string,
    options: CreateVolumeOptions
  ): Promise<Volume> {
    const { size, timeout = 60 } = options;
    const url = `${this._baseUrl}/volumes`;
    const payload = {
      name,
      size,
      wait_for_ready: true,
      timeout,
    };

    const response = await this._fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout((timeout + 30) * 1000),
    });

    if (!response.ok) {
      await handleVolumeCreationError(response);
    }

    return (await response.json()) as Volume;
  }

  /**
   * Get a volume by name.
   *
   * @param name - Volume name.
   * @returns Volume.
   * @throws LangSmithResourceNotFoundError if volume not found.
   */
  async getVolume(name: string): Promise<Volume> {
    const url = `${this._baseUrl}/volumes/${encodeURIComponent(name)}`;

    const response = await this._fetch(url);

    if (!response.ok) {
      if (response.status === 404) {
        throw new LangSmithResourceNotFoundError(
          `Volume '${name}' not found`,
          "volume"
        );
      }
      await handleClientHttpError(response);
    }

    return (await response.json()) as Volume;
  }

  /**
   * List all volumes.
   *
   * @returns List of Volumes.
   */
  async listVolumes(): Promise<Volume[]> {
    const url = `${this._baseUrl}/volumes`;

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
    return (data.volumes ?? []) as Volume[];
  }

  /**
   * Delete a volume.
   *
   * @param name - Volume name.
   * @throws LangSmithResourceNotFoundError if volume not found.
   * @throws ResourceInUseError if volume is referenced by templates.
   */
  async deleteVolume(name: string): Promise<void> {
    const url = `${this._baseUrl}/volumes/${encodeURIComponent(name)}`;

    const response = await this._fetch(url, { method: "DELETE" });

    if (!response.ok) {
      if (response.status === 404) {
        throw new LangSmithResourceNotFoundError(
          `Volume '${name}' not found`,
          "volume"
        );
      }
      if (response.status === 409) {
        await handleResourceInUseError(response, "volume");
      }
      await handleClientHttpError(response);
    }
  }

  /**
   * Update a volume's name and/or size.
   *
   * You can update the display name, size, or both in a single request.
   * Only storage size increases are allowed (storage backend limitation).
   *
   * @param name - Current volume name.
   * @param options - Update options.
   * @returns Updated Volume.
   * @throws LangSmithResourceNotFoundError if volume not found.
   * @throws ValidationError if storage decrease attempted.
   * @throws LangSmithResourceNameConflictError if newName is already in use.
   */
  async updateVolume(
    name: string,
    options: UpdateVolumeOptions
  ): Promise<Volume> {
    const { newName, size } = options;

    if (newName === undefined && size === undefined) {
      // Nothing to update, just return the current volume
      return this.getVolume(name);
    }

    const url = `${this._baseUrl}/volumes/${encodeURIComponent(name)}`;
    const payload: Record<string, unknown> = {};
    if (newName !== undefined) {
      payload.name = newName;
    }
    if (size !== undefined) {
      payload.size = size;
    }

    const response = await this._fetch(url, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      if (response.status === 404) {
        throw new LangSmithResourceNotFoundError(
          `Volume '${name}' not found`,
          "volume"
        );
      }
      if (response.status === 409) {
        await handleConflictError(response, "volume");
      }
      await handleClientHttpError(response);
    }

    return (await response.json()) as Volume;
  }

  // =========================================================================
  // Template Operations
  // =========================================================================

  /**
   * Create a new SandboxTemplate.
   *
   * Only the container image, resource limits, and volume mounts can be
   * configured. All other container details are handled by the server.
   *
   * @param name - Template name.
   * @param options - Creation options including image and resource limits.
   * @returns Created SandboxTemplate.
   */
  async createTemplate(
    name: string,
    options: CreateTemplateOptions
  ): Promise<SandboxTemplate> {
    const {
      image,
      cpu = "500m",
      memory = "512Mi",
      storage,
      volumeMounts,
    } = options;
    const url = `${this._baseUrl}/templates`;

    const payload: Record<string, unknown> = {
      name,
      image,
      resources: {
        cpu,
        memory,
      },
    };
    if (storage) {
      (payload.resources as Record<string, unknown>).storage = storage;
    }
    if (volumeMounts && volumeMounts.length > 0) {
      payload.volume_mounts = volumeMounts.map((vm) => ({
        volume_name: vm.volume_name,
        mount_path: vm.mount_path,
      }));
    }

    const response = await this._fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      await handleClientHttpError(response);
    }

    return (await response.json()) as SandboxTemplate;
  }

  /**
   * Get a SandboxTemplate by name.
   *
   * @param name - Template name.
   * @returns SandboxTemplate.
   * @throws LangSmithResourceNotFoundError if template not found.
   */
  async getTemplate(name: string): Promise<SandboxTemplate> {
    const url = `${this._baseUrl}/templates/${encodeURIComponent(name)}`;

    const response = await this._fetch(url);

    if (!response.ok) {
      if (response.status === 404) {
        throw new LangSmithResourceNotFoundError(
          `Template '${name}' not found`,
          "template"
        );
      }
      await handleClientHttpError(response);
    }

    return (await response.json()) as SandboxTemplate;
  }

  /**
   * List all SandboxTemplates.
   *
   * @returns List of SandboxTemplates.
   */
  async listTemplates(): Promise<SandboxTemplate[]> {
    const url = `${this._baseUrl}/templates`;

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
    return (data.templates ?? []) as SandboxTemplate[];
  }

  /**
   * Update a template.
   *
   * @param name - Current template name.
   * @param options - Update options (e.g., newName).
   * @returns Updated SandboxTemplate.
   * @throws LangSmithResourceNotFoundError if template not found.
   * @throws LangSmithResourceNameConflictError if newName is already in use.
   */
  async updateTemplate(
    name: string,
    options: UpdateTemplateOptions
  ): Promise<SandboxTemplate> {
    const { newName } = options;

    if (newName === undefined) {
      // Nothing to update, just return the current template
      return this.getTemplate(name);
    }

    const url = `${this._baseUrl}/templates/${encodeURIComponent(name)}`;
    const payload = { name: newName };

    const response = await this._fetch(url, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      if (response.status === 404) {
        throw new LangSmithResourceNotFoundError(
          `Template '${name}' not found`,
          "template"
        );
      }
      if (response.status === 409) {
        await handleConflictError(response, "template");
      }
      await handleClientHttpError(response);
    }

    return (await response.json()) as SandboxTemplate;
  }

  /**
   * Delete a SandboxTemplate.
   *
   * @param name - Template name.
   * @throws LangSmithResourceNotFoundError if template not found.
   * @throws ResourceInUseError if template is referenced by sandboxes or pools.
   */
  async deleteTemplate(name: string): Promise<void> {
    const url = `${this._baseUrl}/templates/${encodeURIComponent(name)}`;

    const response = await this._fetch(url, { method: "DELETE" });

    if (!response.ok) {
      if (response.status === 404) {
        throw new LangSmithResourceNotFoundError(
          `Template '${name}' not found`,
          "template"
        );
      }
      if (response.status === 409) {
        await handleResourceInUseError(response, "template");
      }
      await handleClientHttpError(response);
    }
  }

  // =========================================================================
  // Pool Operations
  // =========================================================================

  /**
   * Create a new Sandbox Pool.
   *
   * Pools pre-provision sandboxes from a template for faster startup.
   *
   * @param name - Pool name (lowercase letters, numbers, hyphens; max 63 chars).
   * @param options - Creation options including templateName, replicas, and optional timeout.
   * @returns Created Pool.
   * @throws LangSmithResourceNotFoundError if template not found.
   * @throws ValidationError if template has volumes attached.
   * @throws ResourceAlreadyExistsError if pool with this name already exists.
   * @throws ResourceTimeoutError if pool doesn't reach ready state within timeout.
   * @throws QuotaExceededError if organization quota is exceeded.
   */
  async createPool(name: string, options: CreatePoolOptions): Promise<Pool> {
    const { templateName, replicas, timeout = 30 } = options;
    const url = `${this._baseUrl}/pools`;
    const payload = {
      name,
      template_name: templateName,
      replicas,
      wait_for_ready: true,
      timeout,
    };

    const response = await this._fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout((timeout + 30) * 1000),
    });

    if (!response.ok) {
      await handlePoolError(response);
    }

    return (await response.json()) as Pool;
  }

  /**
   * Get a Pool by name.
   *
   * @param name - Pool name.
   * @returns Pool.
   * @throws LangSmithResourceNotFoundError if pool not found.
   */
  async getPool(name: string): Promise<Pool> {
    const url = `${this._baseUrl}/pools/${encodeURIComponent(name)}`;

    const response = await this._fetch(url);

    if (!response.ok) {
      if (response.status === 404) {
        throw new LangSmithResourceNotFoundError(
          `Pool '${name}' not found`,
          "pool"
        );
      }
      await handleClientHttpError(response);
    }

    return (await response.json()) as Pool;
  }

  /**
   * List all Pools.
   *
   * @returns List of Pools.
   */
  async listPools(): Promise<Pool[]> {
    const url = `${this._baseUrl}/pools`;

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
    return (data.pools ?? []) as Pool[];
  }

  /**
   * Update a Pool's name and/or replica count.
   *
   * You can update the display name, replica count, or both.
   * The template reference cannot be changed after creation.
   *
   * @param name - Current pool name.
   * @param options - Update options.
   * @returns Updated Pool.
   * @throws LangSmithResourceNotFoundError if pool not found.
   * @throws ValidationError if template was deleted.
   * @throws LangSmithResourceNameConflictError if newName is already in use.
   * @throws QuotaExceededError if quota exceeded when scaling up.
   */
  async updatePool(name: string, options: UpdatePoolOptions): Promise<Pool> {
    const { newName, replicas } = options;

    if (newName === undefined && replicas === undefined) {
      // Nothing to update, just return the current pool
      return this.getPool(name);
    }

    const url = `${this._baseUrl}/pools/${encodeURIComponent(name)}`;
    const payload: Record<string, unknown> = {};
    if (newName !== undefined) {
      payload.name = newName;
    }
    if (replicas !== undefined) {
      payload.replicas = replicas;
    }

    const response = await this._fetch(url, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      if (response.status === 404) {
        throw new LangSmithResourceNotFoundError(
          `Pool '${name}' not found`,
          "pool"
        );
      }
      if (response.status === 409) {
        await handleConflictError(response, "pool");
      }
      await handlePoolError(response);
    }

    return (await response.json()) as Pool;
  }

  /**
   * Delete a Pool.
   *
   * This will terminate all sandboxes in the pool.
   *
   * @param name - Pool name.
   * @throws LangSmithResourceNotFoundError if pool not found.
   */
  async deletePool(name: string): Promise<void> {
    const url = `${this._baseUrl}/pools/${encodeURIComponent(name)}`;

    const response = await this._fetch(url, { method: "DELETE" });

    if (!response.ok) {
      if (response.status === 404) {
        throw new LangSmithResourceNotFoundError(
          `Pool '${name}' not found`,
          "pool"
        );
      }
      await handleClientHttpError(response);
    }
  }

  // =========================================================================
  // Sandbox Operations
  // =========================================================================

  /**
   * Create a new Sandbox.
   *
   * Remember to call `sandbox.delete()` when done to clean up resources.
   *
   * @param templateName - Name of the SandboxTemplate to use.
   * @param options - Creation options.
   * @returns Created Sandbox.
   * @throws ResourceTimeoutError if timeout waiting for sandbox to be ready.
   * @throws SandboxCreationError if sandbox creation fails.
   *
   * @example
   * ```typescript
   * const sandbox = await client.createSandbox("python-sandbox");
   * try {
   *   const result = await sandbox.run("echo hello");
   *   console.log(result.stdout);
   * } finally {
   *   await sandbox.delete();
   * }
   * ```
   */
  async createSandbox(
    templateName: string,
    options: CreateSandboxOptions = {}
  ): Promise<Sandbox> {
    const { name, timeout = 30 } = options;
    const url = `${this._baseUrl}/boxes`;

    const payload: Record<string, unknown> = {
      template_name: templateName,
      wait_for_ready: true,
      timeout,
    };
    if (name) {
      payload.name = name;
    }

    const response = await this._fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout((timeout + 30) * 1000),
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
  async getSandbox(name: string): Promise<Sandbox> {
    const url = `${this._baseUrl}/boxes/${encodeURIComponent(name)}`;

    const response = await this._fetch(url);

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
   * @returns Updated Sandbox.
   * @throws LangSmithResourceNotFoundError if sandbox not found.
   * @throws LangSmithResourceNameConflictError if newName is already in use.
   */
  async updateSandbox(name: string, newName: string): Promise<Sandbox> {
    const url = `${this._baseUrl}/boxes/${encodeURIComponent(name)}`;
    const payload = { name: newName };

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
          `Sandbox name '${newName}' already in use`,
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
}
