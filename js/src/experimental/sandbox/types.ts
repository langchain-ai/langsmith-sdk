/**
 * TypeScript interfaces for the sandbox module.
 *
 * Field names use snake_case to match API response format.
 */

/**
 * Result of executing a command in a sandbox.
 */
export interface ExecutionResult {
  stdout: string;
  stderr: string;
  exit_code: number;
}

/**
 * Resource specification for a sandbox.
 */
export interface ResourceSpec {
  cpu?: string;
  memory?: string;
  storage?: string;
}

/**
 * Specification for mounting a volume in a sandbox template.
 */
export interface VolumeMountSpec {
  volume_name: string;
  mount_path: string;
}

/**
 * Represents a persistent volume.
 */
export interface Volume {
  id?: string;
  name: string;
  size: string;
  storage_class: string;
  created_at?: string;
  updated_at?: string;
}

/**
 * Represents a SandboxTemplate.
 *
 * Templates define the image, resource limits, and volume mounts for sandboxes.
 */
export interface SandboxTemplate {
  id?: string;
  name: string;
  image: string;
  resources: ResourceSpec;
  volume_mounts?: VolumeMountSpec[];
  created_at?: string;
  updated_at?: string;
}

/**
 * Represents a Sandbox Pool for pre-provisioned sandboxes.
 *
 * Pools pre-provision sandboxes from a template for faster startup.
 */
export interface Pool {
  id?: string;
  name: string;
  template_name: string;
  replicas: number;
  created_at?: string;
  updated_at?: string;
}

/**
 * Data representing a sandbox instance from the API.
 */
export interface SandboxData {
  id?: string;
  name: string;
  template_name: string;
  dataplane_url?: string;
  created_at?: string;
  updated_at?: string;
}

/**
 * Configuration options for the SandboxClient.
 */
export interface SandboxClientConfig {
  /**
   * Full URL of the sandbox API endpoint.
   * If not provided, derived from LANGSMITH_ENDPOINT environment variable.
   */
  apiEndpoint?: string;
  /**
   * API key for authentication.
   * If not provided, uses LANGSMITH_API_KEY environment variable.
   */
  apiKey?: string;
  /**
   * Default HTTP timeout in milliseconds.
   */
  timeoutMs?: number;
  /**
   * Maximum number of retries for transient failures (network errors, 5xx, 429).
   * Defaults to 3.
   */
  maxRetries?: number;
  /**
   * Maximum number of concurrent requests.
   * Defaults to Infinity (no limit).
   */
  maxConcurrency?: number;
}

/**
 * Options for running a command in a sandbox.
 */
export interface RunOptions {
  /**
   * Command timeout in seconds.
   */
  timeout?: number;
  /**
   * Environment variables to set for the command.
   */
  env?: Record<string, string>;
  /**
   * Working directory for command execution.
   */
  cwd?: string;
  /**
   * Shell to use for command execution. Defaults to "/bin/bash".
   */
  shell?: string;
}

/**
 * Options for creating a sandbox.
 */
export interface CreateSandboxOptions {
  /**
   * Optional sandbox name (auto-generated if not provided).
   */
  name?: string;
  /**
   * Timeout in seconds when waiting for ready.
   */
  timeout?: number;
}

/**
 * Options for creating a volume.
 */
export interface CreateVolumeOptions {
  /**
   * Storage size (e.g., "1Gi", "10Gi").
   */
  size: string;
  /**
   * Timeout in seconds when waiting for volume to be ready. Default: 60.
   */
  timeout?: number;
}

/**
 * Options for creating a template.
 */
export interface CreateTemplateOptions {
  /**
   * Container image (e.g., "python:3.12-slim", "node:20-slim").
   */
  image: string;
  /**
   * CPU limit (e.g., "500m", "1", "2"). Default: "500m".
   */
  cpu?: string;
  /**
   * Memory limit (e.g., "256Mi", "1Gi"). Default: "512Mi".
   */
  memory?: string;
  /**
   * Ephemeral storage limit (e.g., "1Gi"). Optional.
   */
  storage?: string;
  /**
   * List of volumes to mount in the sandbox. Optional.
   */
  volumeMounts?: VolumeMountSpec[];
}

/**
 * Options for updating a template.
 */
export interface UpdateTemplateOptions {
  /**
   * New display name (optional).
   */
  newName?: string;
}

/**
 * Options for creating a pool.
 */
export interface CreatePoolOptions {
  /**
   * Name of the template to use for sandboxes in this pool.
   */
  templateName: string;
  /**
   * Number of pre-warmed sandboxes to maintain (0-100).
   */
  replicas: number;
  /**
   * Timeout in seconds when waiting for pool to be ready. Default: 30.
   */
  timeout?: number;
}

/**
 * Options for updating a volume.
 */
export interface UpdateVolumeOptions {
  /**
   * New display name (optional).
   */
  newName?: string;
  /**
   * New storage size (must be >= current size). Optional.
   */
  size?: string;
}

/**
 * Options for updating a pool.
 */
export interface UpdatePoolOptions {
  /**
   * New display name (optional).
   */
  newName?: string;
  /**
   * New number of replicas (0-100). Set to 0 to pause.
   */
  replicas?: number;
}
