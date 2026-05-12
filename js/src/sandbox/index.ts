/**
 * LangSmith Sandbox Module.
 *
 * This module provides sandboxed code execution capabilities through the
 * LangSmith Sandbox API.
 *
 * @example
 * ```typescript
 * import { SandboxClient } from "langsmith/sandbox";
 *
 * // Uses LANGSMITH_ENDPOINT and LANGSMITH_API_KEY from environment
 * const client = new SandboxClient();
 *
 * const snapshot = await client.createSnapshot(
 *   "python",
 *   "python:3.12-slim",
 *   1_073_741_824
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
 * @packageDocumentation
 */

// Main classes
export { SandboxClient } from "./client.js";
export { Sandbox } from "./sandbox.js";
export { CommandHandle } from "./command_handle.js";

// Types
export type {
  ExecutionResult,
  OutputChunk,
  WsMessage,
  WsRunOptions,
  ResourceStatus,
  Snapshot,
  SandboxData,
  SandboxClientConfig,
  RunOptions,
  CreateSandboxOptions,
  SandboxAccessControl,
  SandboxProxyConfig,
  CreateSnapshotOptions,
  CaptureSnapshotOptions,
  ListSnapshotsOptions,
  WaitForSnapshotOptions,
  StartSandboxOptions,
  UpdateSandboxOptions,
  WaitForSandboxOptions,
} from "./types.js";

// Errors
export {
  // Base and connection errors
  LangSmithSandboxError,
  LangSmithSandboxAPIError,
  LangSmithSandboxAuthenticationError,
  LangSmithSandboxConnectionError,
  LangSmithSandboxServerReloadError,
  // Resource errors (type-based with resourceType attribute)
  LangSmithResourceNotFoundError,
  LangSmithResourceTimeoutError,
  LangSmithResourceInUseError,
  LangSmithResourceAlreadyExistsError,
  LangSmithResourceNameConflictError,
  // Validation and quota errors
  LangSmithValidationError,
  LangSmithQuotaExceededError,
  // Resource creation errors
  LangSmithResourceCreationError,
  // Sandbox-specific errors
  LangSmithSandboxCreationError,
  LangSmithSandboxNotReadyError,
  LangSmithSandboxOperationError,
  LangSmithCommandTimeoutError,
  LangSmithDataplaneNotConfiguredError,
} from "./errors.js";
