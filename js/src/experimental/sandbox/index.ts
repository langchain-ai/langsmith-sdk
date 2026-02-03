/**
 * LangSmith Sandbox Module.
 *
 * This module provides sandboxed code execution capabilities through the
 * LangSmith Sandbox API.
 *
 * @example
 * ```typescript
 * import { SandboxClient } from "langsmith/experimental/sandbox";
 *
 * // Uses LANGSMITH_ENDPOINT and LANGSMITH_API_KEY from environment
 * const client = new SandboxClient();
 *
 * const sandbox = await client.createSandbox("python-sandbox");
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

// Emit warning on import (alpha feature)
console.warn(
  "langsmith/experimental/sandbox is in alpha. " +
    "This feature is experimental, and breaking changes are expected."
);

// Main classes
export { SandboxClient } from "./client.js";
export { Sandbox } from "./sandbox.js";

// Types
export type {
  ExecutionResult,
  ResourceSpec,
  VolumeMountSpec,
  Volume,
  SandboxTemplate,
  Pool,
  SandboxData,
  SandboxClientConfig,
  RunOptions,
  CreateSandboxOptions,
  CreateVolumeOptions,
  CreateTemplateOptions,
  UpdateTemplateOptions,
  CreatePoolOptions,
  UpdateVolumeOptions,
  UpdatePoolOptions,
} from "./types.js";

// Errors
export {
  // Base and connection errors
  SandboxClientError,
  SandboxAPIError,
  SandboxAuthenticationError,
  SandboxConnectionError,
  // Resource errors (type-based with resourceType attribute)
  ResourceNotFoundError,
  ResourceTimeoutError,
  ResourceInUseError,
  ResourceAlreadyExistsError,
  ResourceNameConflictError,
  // Validation and quota errors
  ValidationError,
  QuotaExceededError,
  // Sandbox-specific errors
  SandboxCreationError,
  SandboxNotReadyError,
  SandboxOperationError,
  DataplaneNotConfiguredError,
} from "./errors.js";
