/**
 * Custom error classes for the sandbox module.
 *
 * All sandbox errors extend LangSmithSandboxError for unified error handling.
 * The errors are organized by type rather than resource type, with additional
 * properties for specific handling when needed.
 */

/**
 * Base exception for sandbox client errors.
 */
export class LangSmithSandboxError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "LangSmithSandboxError";
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
export class LangSmithSandboxAPIError extends LangSmithSandboxError {
  constructor(message: string) {
    super(message);
    this.name = "LangSmithSandboxAPIError";
  }
}

/**
 * Raised when authentication fails (invalid or missing API key).
 */
export class LangSmithSandboxAuthenticationError extends LangSmithSandboxError {
  constructor(message: string) {
    super(message);
    this.name = "LangSmithSandboxAuthenticationError";
  }
}

/**
 * Raised when connection to the sandbox server fails.
 */
export class LangSmithSandboxConnectionError extends LangSmithSandboxError {
  constructor(message: string) {
    super(message);
    this.name = "LangSmithSandboxConnectionError";
  }
}

// =============================================================================
// Resource Errors (type-based, with resourceType property)
// =============================================================================

/**
 * Raised when a resource is not found.
 */
export class LangSmithResourceNotFoundError extends LangSmithSandboxError {
  resourceType?: string;

  constructor(message: string, resourceType?: string) {
    super(message);
    this.name = "LangSmithResourceNotFoundError";
    this.resourceType = resourceType;
  }
}

/**
 * Raised when an operation times out.
 */
export class LangSmithResourceTimeoutError extends LangSmithSandboxError {
  resourceType?: string;
  lastStatus?: string;

  constructor(message: string, resourceType?: string, lastStatus?: string) {
    super(message);
    this.name = "LangSmithResourceTimeoutError";
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
export class LangSmithResourceInUseError extends LangSmithSandboxError {
  resourceType?: string;

  constructor(message: string, resourceType?: string) {
    super(message);
    this.name = "LangSmithResourceInUseError";
    this.resourceType = resourceType;
  }
}

/**
 * Raised when creating a resource that already exists.
 */
export class LangSmithResourceAlreadyExistsError extends LangSmithSandboxError {
  resourceType?: string;

  constructor(message: string, resourceType?: string) {
    super(message);
    this.name = "LangSmithResourceAlreadyExistsError";
    this.resourceType = resourceType;
  }
}

/**
 * Raised when updating a resource name to one that already exists.
 */
export class LangSmithResourceNameConflictError extends LangSmithSandboxError {
  resourceType?: string;

  constructor(message: string, resourceType?: string) {
    super(message);
    this.name = "LangSmithResourceNameConflictError";
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
export class LangSmithValidationError extends LangSmithSandboxError {
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
    this.name = "LangSmithValidationError";
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
export class LangSmithQuotaExceededError extends LangSmithSandboxError {
  quotaType?: string;

  constructor(message: string, quotaType?: string) {
    super(message);
    this.name = "LangSmithQuotaExceededError";
    this.quotaType = quotaType;
  }
}

// =============================================================================
// Sandbox Creation Errors
// =============================================================================

/**
 * Raised when sandbox creation fails.
 */
export class LangSmithSandboxCreationError extends LangSmithSandboxError {
  /**
   * Machine-readable error type (ImagePull, CrashLoop, SandboxConfig, Unschedulable).
   */
  errorType?: string;

  constructor(message: string, errorType?: string) {
    super(message);
    this.name = "LangSmithSandboxCreationError";
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
export class LangSmithDataplaneNotConfiguredError extends LangSmithSandboxError {
  constructor(message: string) {
    super(message);
    this.name = "LangSmithDataplaneNotConfiguredError";
  }
}

/**
 * Raised when attempting to interact with a sandbox that is not ready.
 */
export class LangSmithSandboxNotReadyError extends LangSmithSandboxError {
  constructor(message: string) {
    super(message);
    this.name = "LangSmithSandboxNotReadyError";
  }
}

/**
 * Raised when a sandbox operation fails (run, read, write).
 */
export class LangSmithSandboxOperationError extends LangSmithSandboxError {
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
    this.name = "LangSmithSandboxOperationError";
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
