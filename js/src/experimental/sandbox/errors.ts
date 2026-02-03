/**
 * Custom error classes for the sandbox module.
 *
 * All sandbox errors extend SandboxClientError for unified error handling.
 * The errors are organized by type rather than resource type, with additional
 * properties for specific handling when needed.
 */

/**
 * Base exception for sandbox client errors.
 */
export class SandboxClientError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SandboxClientError";
  }
}

// =============================================================================
// Connection and Authentication Errors
// =============================================================================

/**
 * Raised when the API endpoint returns an unexpected error.
 *
 * For example, this is raised for wrong URL or path.
 */
export class SandboxAPIError extends SandboxClientError {
  constructor(message: string) {
    super(message);
    this.name = "SandboxAPIError";
  }
}

/**
 * Raised when authentication fails (invalid or missing API key).
 */
export class SandboxAuthenticationError extends SandboxClientError {
  constructor(message: string) {
    super(message);
    this.name = "SandboxAuthenticationError";
  }
}

/**
 * Raised when connection to the sandbox server fails.
 */
export class SandboxConnectionError extends SandboxClientError {
  constructor(message: string) {
    super(message);
    this.name = "SandboxConnectionError";
  }
}

// =============================================================================
// Resource Errors (type-based, with resourceType property)
// =============================================================================

/**
 * Raised when a resource is not found.
 */
export class ResourceNotFoundError extends SandboxClientError {
  resourceType?: string;

  constructor(message: string, resourceType?: string) {
    super(message);
    this.name = "ResourceNotFoundError";
    this.resourceType = resourceType;
  }
}

/**
 * Raised when an operation times out.
 */
export class ResourceTimeoutError extends SandboxClientError {
  resourceType?: string;
  lastStatus?: string;

  constructor(message: string, resourceType?: string, lastStatus?: string) {
    super(message);
    this.name = "ResourceTimeoutError";
    this.resourceType = resourceType;
    this.lastStatus = lastStatus;
  }

  override toString(): string {
    const base = super.toString();
    if (this.lastStatus) {
      return `${base} (last_status: ${this.lastStatus})`;
    }
    return base;
  }
}

/**
 * Raised when deleting a resource that is still in use.
 */
export class ResourceInUseError extends SandboxClientError {
  resourceType?: string;

  constructor(message: string, resourceType?: string) {
    super(message);
    this.name = "ResourceInUseError";
    this.resourceType = resourceType;
  }
}

/**
 * Raised when creating a resource that already exists.
 */
export class ResourceAlreadyExistsError extends SandboxClientError {
  resourceType?: string;

  constructor(message: string, resourceType?: string) {
    super(message);
    this.name = "ResourceAlreadyExistsError";
    this.resourceType = resourceType;
  }
}

/**
 * Raised when updating a resource name to one that already exists.
 */
export class ResourceNameConflictError extends SandboxClientError {
  resourceType?: string;

  constructor(message: string, resourceType?: string) {
    super(message);
    this.name = "ResourceNameConflictError";
    this.resourceType = resourceType;
  }
}

// =============================================================================
// Validation and Quota Errors
// =============================================================================

/**
 * Raised when request validation fails.
 *
 * This includes:
 * - Resource values exceeding server-defined limits (CPU, memory, storage)
 * - Invalid resource units
 * - Invalid name formats
 * - Pool validation failures (e.g., template has volumes)
 */
export class ValidationError extends SandboxClientError {
  field?: string;
  details?: Array<Record<string, unknown>>;
  errorType?: string;

  constructor(
    message: string,
    field?: string,
    details?: Array<Record<string, unknown>>,
    errorType?: string
  ) {
    super(message);
    this.name = "ValidationError";
    this.field = field;
    this.details = details;
    this.errorType = errorType;
  }
}

/**
 * Raised when organization quota limits are exceeded.
 *
 * Users should contact support@langchain.dev to increase quotas.
 */
export class QuotaExceededError extends SandboxClientError {
  quotaType?: string;

  constructor(message: string, quotaType?: string) {
    super(message);
    this.name = "QuotaExceededError";
    this.quotaType = quotaType;
  }
}

// =============================================================================
// Sandbox Creation Errors
// =============================================================================

/**
 * Raised when sandbox creation fails.
 */
export class SandboxCreationError extends SandboxClientError {
  /**
   * Machine-readable error type (ImagePull, CrashLoop, SandboxConfig, Unschedulable).
   */
  errorType?: string;

  constructor(message: string, errorType?: string) {
    super(message);
    this.name = "SandboxCreationError";
    this.errorType = errorType;
  }

  override toString(): string {
    if (this.errorType) {
      return `${super.toString()} [${this.errorType}]`;
    }
    return super.toString();
  }
}

// =============================================================================
// Sandbox Operation Errors (runtime errors during sandbox interaction)
// =============================================================================

/**
 * Raised when dataplane_url is not available for the sandbox.
 *
 * This occurs when the sandbox-router URL is not configured for the cluster.
 */
export class DataplaneNotConfiguredError extends SandboxClientError {
  constructor(message: string) {
    super(message);
    this.name = "DataplaneNotConfiguredError";
  }
}

/**
 * Raised when attempting to interact with a sandbox that is not ready.
 */
export class SandboxNotReadyError extends SandboxClientError {
  constructor(message: string) {
    super(message);
    this.name = "SandboxNotReadyError";
  }
}

/**
 * Raised when a sandbox operation fails (run, read, write).
 */
export class SandboxOperationError extends SandboxClientError {
  /**
   * The operation that failed (command, read, write).
   */
  operation?: string;
  /**
   * Machine-readable error type from the API.
   */
  errorType?: string;

  constructor(message: string, operation?: string, errorType?: string) {
    super(message);
    this.name = "SandboxOperationError";
    this.operation = operation;
    this.errorType = errorType;
  }

  override toString(): string {
    if (this.errorType) {
      return `${super.toString()} [${this.errorType}]`;
    }
    return super.toString();
  }
}
