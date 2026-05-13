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
 * Lightweight provisioning status for any async-created resource.
 */
export interface ResourceStatus {
  /** One of "provisioning", "ready", "failed". */
  status: string;
  /** Human-readable details when failed. */
  status_message?: string;
}

/**
 * Represents a sandbox snapshot.
 *
 * Snapshots are built from Docker images or captured from running sandboxes.
 * They are used to create new sandboxes.
 */
export interface Snapshot {
  id: string;
  name: string;
  /** One of "building", "ready", "failed". */
  status: string;
  fs_capacity_bytes: number;
  docker_image?: string;
  image_digest?: string;
  source_sandbox_id?: string;
  status_message?: string;
  fs_used_bytes?: number;
  created_by?: string;
  registry_id?: string;
  created_at?: string;
  updated_at?: string;
}

/**
 * Data representing a sandbox instance from the API.
 */
export interface SandboxData {
  id?: string;
  name: string;
  dataplane_url?: string;
  status?: string;
  status_message?: string;
  created_at?: string;
  updated_at?: string;
  /**
   * Idle timeout in seconds. The launcher stops the sandbox after this
   * many seconds of inactivity. `0` disables the idle stop;
   * omitted/`undefined` means not set (the server applies a default).
   */
  idle_ttl_seconds?: number;
  /**
   * Seconds after a sandbox enters the `stopped` state before it (and its
   * filesystem clone) are permanently deleted. `0` disables stop-anchored
   * deletion; omitted/`undefined` falls back to the server default.
   */
  delete_after_stop_seconds?: number;
  /**
   * Timestamp when the sandbox transitioned to the `stopped` state, or
   * `undefined` while running. The deletion deadline is
   * `stopped_at + delete_after_stop_seconds`.
   */
  stopped_at?: string;
  /** Snapshot ID used to create this sandbox. */
  snapshot_id?: string;
  /** Number of vCPUs allocated. */
  vcpus?: number;
  /** Memory allocation in bytes. */
  mem_bytes?: number;
  /** Root filesystem capacity in bytes. */
  fs_capacity_bytes?: number;
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
 * A single chunk of streaming output from command execution.
 */
export interface OutputChunk {
  /** Either "stdout" or "stderr". */
  stream: "stdout" | "stderr";
  /** The text content of this chunk. */
  data: string;
  /** Byte offset within the stream. Used internally for reconnection. */
  offset: number;
}

/**
 * Internal WebSocket message type from the server.
 */
export interface WsMessage {
  type: "started" | "stdout" | "stderr" | "exit" | "error";
  [key: string]: unknown;
}

/**
 * Options for the low-level WebSocket stream functions.
 */
export interface WsRunOptions {
  /** Command timeout in seconds. Default: 60. */
  timeout?: number;
  /** Environment variables to set for the command. */
  env?: Record<string, string>;
  /** Working directory for command execution. */
  cwd?: string;
  /** Shell to use. Default: "/bin/bash". */
  shell?: string;
  /** Callback invoked with each stdout chunk. */
  onStdout?: (data: string) => void;
  /** Callback invoked with each stderr chunk. */
  onStderr?: (data: string) => void;
  /** Client-assigned command ID. */
  commandId?: string;
  /**
   * Idle timeout in seconds. If the command has no connected clients for
   * this duration, it is killed. Defaults to 300 (5 minutes).
   * Set to -1 for no idle timeout.
   */
  idleTimeout?: number;
  /**
   * If true, kill the command immediately when the last client disconnects.
   * Defaults to false (command continues running and can be reconnected to).
   */
  killOnDisconnect?: boolean;
  /**
   * How long (in seconds) a finished command's session is kept for
   * reconnection. Defaults to 600 (10 minutes). Set to -1 to keep indefinitely.
   */
  ttlSeconds?: number;
  /** Whether to allocate a PTY. */
  pty?: boolean;
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
  /**
   * Whether to wait for the command to complete before returning.
   * When true (default), returns an ExecutionResult.
   * When false, returns a CommandHandle for streaming output.
   */
  wait?: boolean;
  /**
   * Callback invoked with each stdout chunk during streaming execution.
   * When provided, WebSocket streaming is used.
   */
  onStdout?: (data: string) => void;
  /**
   * Callback invoked with each stderr chunk during streaming execution.
   * When provided, WebSocket streaming is used.
   */
  onStderr?: (data: string) => void;
  /**
   * Idle timeout in seconds. If the command has no connected clients for
   * this duration, it is killed. Defaults to 300 (5 minutes).
   * Set to -1 for no idle timeout.
   */
  idleTimeout?: number;
  /**
   * If true, kill the command immediately when the last client disconnects.
   * Defaults to false (command continues running and can be reconnected to).
   */
  killOnDisconnect?: boolean;
  /**
   * How long (in seconds) a finished command's session is kept for
   * reconnection. Defaults to 600 (10 minutes). Set to -1 to keep indefinitely.
   */
  ttlSeconds?: number;
  /**
   * If true, allocate a pseudo-terminal (PTY) for the command.
   * Useful for commands that require a TTY (e.g., interactive programs,
   * commands that use terminal control codes). Defaults to false.
   */
  pty?: boolean;
}

/**
 * Network access-control rules for a sandbox's proxy sidecar.
 *
 * Supported pattern types: exact domains, globs (e.g. `*.example.com`),
 * IPs, CIDR ranges (e.g. `10.0.0.0/8`), and regex (`~pattern`).
 *
 * Only one of `allow_list` and `deny_list` may be populated.
 */
export interface SandboxAccessControl {
  /** Hosts the sandbox is allowed to reach. */
  allow_list?: string[];
  /** Hosts the sandbox is blocked from reaching. */
  deny_list?: string[];
}

/**
 * Full proxy configuration forwarded to the sandbox server as-is (snake_case
 * so it's wire-compatible with the backend). Mirrors the server's
 * `ProxyConfig` type.
 */
export interface SandboxProxyConfig {
  /** Header-injection rules keyed by host pattern. */
  rules?: unknown[];
  /** Hosts that bypass the proxy entirely. */
  no_proxy?: string[];
  /** Allow/deny list enforced at the proxy sidecar. */
  access_control?: SandboxAccessControl;
}

/**
 * Options for creating a sandbox.
 */
export interface CreateSandboxOptions {
  /**
   * Optional snapshot name to boot from. Omit this and the positional
   * `snapshotId` for the normal default-runtime sandbox.
   * Resolved server-side to a snapshot owned by the caller's tenant.
   */
  snapshotName?: string;
  /**
   * Optional sandbox name (auto-generated if not provided).
   */
  name?: string;
  /**
   * Timeout in seconds when waiting for ready.
   */
  timeout?: number;
  /**
   * Whether to wait for the sandbox to be ready before returning.
   * When false, returns immediately with status "provisioning".
   * Use getSandboxStatus() or waitForSandbox() to poll for readiness.
   * Default: true.
   */
  waitForReady?: boolean;
  /**
   * Idle timeout in seconds. The launcher stops the sandbox after this many
   * seconds of inactivity. Must be a multiple of 60. Pass `0` to disable
   * the idle stop. When omitted, the server applies a default of `600`
   * seconds (10 minutes).
   */
  idleTtlSeconds?: number;
  /**
   * Seconds after the sandbox enters the `stopped` state before it (and
   * its filesystem clone) are permanently deleted. Must be a multiple of
   * 60. Pass `0` to disable stop-anchored deletion (manual cleanup
   * required). When omitted, the server applies its configured default
   * (typically 14 days).
   */
  deleteAfterStopSeconds?: number;
  /** Number of vCPUs. */
  vCpus?: number;
  /** Memory in bytes. */
  memBytes?: number;
  /** Root filesystem capacity in bytes. */
  fsCapacityBytes?: number;
  /**
   * Per-sandbox proxy configuration. Use
   * `{ access_control: { allow_list: ["github.com", "*.example.com"] } }`
   * to restrict outbound HTTPS to a set of host patterns. Forwarded to the
   * server as-is on the wire.
   */
  proxyConfig?: SandboxProxyConfig;
}

/**
 * Options for creating a snapshot from a Docker image.
 */
export interface CreateSnapshotOptions {
  /** Private registry ID (alternative to URL/credentials). */
  registryId?: string;
  /** Registry URL for private images. */
  registryUrl?: string;
  /** Registry username. */
  registryUsername?: string;
  /** Registry password. */
  registryPassword?: string;
  /** Timeout in seconds when waiting for ready. Default: 60. */
  timeout?: number;
  /** AbortSignal for cancellation. */
  signal?: AbortSignal;
}

/**
 * Options for capturing a snapshot from a running sandbox.
 */
export interface CaptureSnapshotOptions {
  /** Timeout in seconds when waiting for ready. Default: 60. */
  timeout?: number;
  /** AbortSignal for cancellation. */
  signal?: AbortSignal;
}

/**
 * Options for listing snapshots. All fields are optional and independent.
 *
 * The backend always paginates: when `limit` is omitted the server applies
 * a default page size (currently 50), so a single call will not necessarily
 * return every snapshot visible to the caller's tenant.
 */
export interface ListSnapshotsOptions {
  /**
   * Case-insensitive substring filter applied server-side to snapshot
   * names.
   */
  nameContains?: string;
  /**
   * Maximum number of snapshots to return for a single request. Must be
   * between 1 and 500 (inclusive); the server rejects values outside that
   * range. Defaults to 50 server-side when omitted.
   */
  limit?: number;
  /**
   * Number of snapshots to skip before returning results. Must be `>= 0`.
   * Useful for paginating through large result sets in combination with
   * `limit`.
   */
  offset?: number;
  /** AbortSignal for cancellation. */
  signal?: AbortSignal;
}

/**
 * Options for waiting for a snapshot to become ready.
 */
export interface WaitForSnapshotOptions {
  /** Maximum time in seconds to wait. Default: 300. */
  timeout?: number;
  /** Time in seconds between status polls. Default: 2.0. */
  pollInterval?: number;
  /** AbortSignal for cancellation. */
  signal?: AbortSignal;
}

/**
 * Options for starting a stopped sandbox.
 */
export interface StartSandboxOptions {
  /** Timeout in seconds when waiting for ready. Default: 120. */
  timeout?: number;
  /** AbortSignal for cancellation. */
  signal?: AbortSignal;
}

/**
 * Options for updating a sandbox (name and/or retention settings).
 */
export interface UpdateSandboxOptions {
  /** New display name. */
  newName?: string;
  /**
   * Idle timeout in seconds. Must be a multiple of 60. Pass `0` to disable
   * the idle stop. Omit (or pass `undefined`) to leave the existing value
   * unchanged.
   */
  idleTtlSeconds?: number;
  /**
   * Seconds after entering `stopped` before deletion. Must be a multiple
   * of 60. Pass `0` to disable stop-anchored deletion. Omit (or pass
   * `undefined`) to leave the existing value unchanged.
   */
  deleteAfterStopSeconds?: number;
}

/**
 * Options for waiting for a sandbox to become ready.
 */
export interface WaitForSandboxOptions {
  /**
   * Maximum time in seconds to wait for the sandbox to become ready.
   * Default: 120.
   */
  timeout?: number;
  /**
   * Time in seconds between status polls.
   * Default: 1.0.
   */
  pollInterval?: number;
  /** AbortSignal for cancellation. */
  signal?: AbortSignal;
}
