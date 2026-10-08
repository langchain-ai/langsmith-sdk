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
export {
  awsAuth,
  gcpAuth,
  opaqueSecret,
  proxyConfig,
  workspaceSecret,
} from "./proxy_config.js";
export { validateAccessDelegation } from "./access_delegation.js";
export {
  ServiceUrl,
  ServiceLoginUrl,
  SERVICE_TOKEN_HEADER,
} from "./service_url.js";
export {
  SandboxTokenVerifier,
  USER_TOKEN_HEADER,
  CALLBACK_SIGNATURE_HEADER,
} from "./verify.js";
export type {
  AudienceMatcher,
  SandboxCallback,
  SandboxCallbackIdentity,
  SandboxCallbackRequest,
  SandboxTokenVerifierConfig,
  SandboxUser,
  VerifyCallbackOptions,
  VerifyUserTokenOptions,
} from "./verify.js";
export {
  contextHubMount,
  gcsMount,
  gitMount,
  mountConfig,
  s3Mount,
} from "./mounts.js";

// Types
export type {
  AccessDelegation,
  AccessDelegationMode,
} from "./access_delegation.js";
export type { ServiceAccess, ServiceUrlData } from "./service_url.js";
export type {
  ExecutionResult,
  FileChunk,
  FileInfo,
  FileStat,
  GlobOptions,
  GlobResult,
  GrepMatch,
  GrepOptions,
  GrepResult,
  ReadRangeOptions,
  RunConfig,
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
  SandboxAwsAuthRule,
  SandboxAwsMountAuthConfig,
  SandboxGcpAuthRule,
  SandboxGcpMountAuthConfig,
  SandboxMountAuth,
  SandboxMountAuthConfig,
  SandboxMountConfig,
  SandboxProxyConfig,
  SandboxProxyRule,
  SandboxProxySecret,
  SandboxMount,
  MountCacheConfig,
  ContextHubMountConfig,
  ContextHubMountSpec,
  GCSMountConfig,
  GCSMountSpec,
  GitMountConfig,
  GitMountRefSpec,
  GitMountSpec,
  S3MountConfig,
  S3MountSpec,
  CreateSnapshotOptions,
  CreateDockerfileSnapshotOptions,
  CaptureSnapshotOptions,
  DownloadContentDisposition,
  DownloadURL,
  GenerateDownloadURLOptions,
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
  LangSmithSandboxRetryableConnectionError,
  LangSmithSandboxConnectTimeoutError,
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
  LangSmithSandboxTokenVerificationError,
} from "./errors.js";
