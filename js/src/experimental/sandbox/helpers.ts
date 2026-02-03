/**
 * Shared helper functions for error handling.
 *
 * These functions are used to parse error responses and raise appropriate
 * exceptions. They contain no I/O operations.
 */

import {
  QuotaExceededError,
  ResourceAlreadyExistsError,
  ResourceInUseError,
  ResourceNameConflictError,
  ResourceNotFoundError,
  ResourceTimeoutError,
  SandboxAPIError,
  SandboxAuthenticationError,
  SandboxClientError,
  SandboxConnectionError,
  SandboxCreationError,
  SandboxNotReadyError,
  SandboxOperationError,
  ValidationError,
} from "./errors.js";

// =============================================================================
// Network Error Detection
// =============================================================================

const objectToString = Object.prototype.toString;
const isError = (value: unknown): value is Error =>
  objectToString.call(value) === "[object Error]";

const networkErrorMessages = new Set([
  "network error", // Chrome
  "Failed to fetch", // Chrome
  "NetworkError when attempting to fetch resource.", // Firefox
  "The Internet connection appears to be offline.", // Safari 16
  "Network request failed", // `cross-fetch`
  "fetch failed", // Undici (Node.js)
  "terminated", // Undici (Node.js)
  "A network error occurred.", // Bun (WebKit)
  "Network connection lost", // Cloudflare Workers (fetch)
]);

/**
 * Check if an error is a network/fetch error.
 *
 * This is used instead of `instanceof TypeError` to avoid ESLint errors.
 */
export function isNetworkError(error: unknown): boolean {
  const isValid =
    error &&
    isError(error) &&
    error.name === "TypeError" &&
    typeof error.message === "string";

  if (!isValid) {
    return false;
  }

  const { message, stack } = error;

  // Safari 17+ has generic message but no stack for network errors
  if (message === "Load failed") {
    return stack === undefined;
  }

  // Deno network errors start with specific text
  if (message.startsWith("error sending request for url")) {
    return true;
  }

  // Check for generic fetch error messages
  if (message.includes("fetch")) {
    return true;
  }

  // Standard network error messages
  return networkErrorMessages.has(message);
}

// =============================================================================
// Error Response Parsing
// =============================================================================

interface ParsedError {
  errorType?: string;
  message: string;
}

interface ValidationDetail {
  loc?: unknown[];
  msg?: string;
  type?: string;
  [key: string]: unknown;
}

/**
 * Parse standardized error response.
 *
 * Expected format: {"detail": {"error": "...", "message": "..."}}
 */
export async function parseErrorResponse(
  response: Response
): Promise<ParsedError> {
  try {
    const data = await response.json();
    const detail = data?.detail;

    // Standardized format: {"detail": {"error": "...", "message": "..."}}
    if (detail && typeof detail === "object" && !Array.isArray(detail)) {
      return {
        errorType: detail.error,
        message:
          detail.message || `HTTP ${response.status}: ${response.statusText}`,
      };
    }

    // Pydantic validation error format: {"detail": [{"loc": [...], "msg": "..."}]}
    if (Array.isArray(detail) && detail.length > 0) {
      const messages = detail
        .filter(
          (d): d is ValidationDetail => typeof d === "object" && d !== null
        )
        .map((d) => d.msg || String(d))
        .filter(Boolean);
      return {
        errorType: undefined,
        message:
          messages.length > 0
            ? messages.join("; ")
            : `HTTP ${response.status}: ${response.statusText}`,
      };
    }

    // Fallback for plain string detail
    return {
      errorType: undefined,
      message: detail || `HTTP ${response.status}: ${response.statusText}`,
    };
  } catch {
    return {
      errorType: undefined,
      message: `HTTP ${response.status}: ${response.statusText}`,
    };
  }
}

/**
 * Parse Pydantic validation error response.
 *
 * Returns a list of validation error details.
 */
export async function parseValidationError(
  response: Response
): Promise<ValidationDetail[]> {
  try {
    const data = await response.json();
    const detail = data?.detail;
    if (Array.isArray(detail)) {
      return detail;
    }
    return [];
  } catch {
    return [];
  }
}

/**
 * Extract quota type from error message.
 */
export function extractQuotaType(message: string): string | undefined {
  const messageLower = message.toLowerCase();

  // Check for sandbox count quota
  if (
    messageLower.includes("sandbox") &&
    (messageLower.includes("count") || messageLower.includes("limit"))
  ) {
    return "sandbox_count";
  } else if (messageLower.includes("cpu")) {
    return "cpu";
  } else if (messageLower.includes("memory")) {
    return "memory";
  }
  // Check for volume count quota
  else if (
    messageLower.includes("volume") &&
    (messageLower.includes("count") || messageLower.includes("limit"))
  ) {
    return "volume_count";
  } else if (messageLower.includes("storage")) {
    return "storage";
  }
  return undefined;
}

// =============================================================================
// Client Error Handlers
// =============================================================================

/**
 * Handle HTTP errors specific to sandbox creation.
 *
 * Maps API error responses to specific exception types:
 * - 408: ResourceTimeoutError (sandbox didn't become ready in time)
 * - 422: ValidationError (bad input) or SandboxCreationError (runtime)
 * - 429: QuotaExceededError (org limits exceeded)
 * - 503: SandboxCreationError (no resources available)
 * - Other: Falls through to generic error handling
 */
export async function handleSandboxCreationError(
  response: Response
): Promise<never> {
  const status = response.status;
  const data = await parseErrorResponse(response);

  if (status === 408) {
    // Timeout - include the message which contains last known status
    throw new ResourceTimeoutError(data.message, "sandbox");
  } else if (status === 422) {
    // Check if this is a Pydantic validation error (bad input) vs creation error
    const clonedResponse = response.clone();
    const details = await parseValidationError(clonedResponse);
    if (details.length > 0 && details.some((d) => d.type === "value_error")) {
      // Pydantic validation error (bad input - exceeds server limits)
      const field = details[0]?.loc?.slice(-1)[0] as string | undefined;
      throw new ValidationError(data.message, field, details);
    } else {
      // Sandbox creation failed (runtime error like image pull failure)
      throw new SandboxCreationError(data.message, data.errorType);
    }
  } else if (status === 429) {
    // Organization quota exceeded - extract type or default to sandbox_count
    const quotaType = extractQuotaType(data.message) ?? "unknown";
    throw new QuotaExceededError(data.message, quotaType);
  } else if (status === 503) {
    // Service Unavailable - scheduling failed
    throw new SandboxCreationError(
      data.message,
      data.errorType || "Unschedulable"
    );
  }
  // Fall through to generic handling
  return handleClientHttpError(response);
}

/**
 * Handle HTTP errors specific to volume creation.
 *
 * Maps API error responses to specific exception types:
 * - 429: QuotaExceededError (org limits exceeded)
 * - 503: SandboxCreationError (provisioning failed)
 * - 504: ResourceTimeoutError (volume didn't become ready in time)
 * - Other: Falls through to generic error handling
 */
export async function handleVolumeCreationError(
  response: Response
): Promise<never> {
  const status = response.status;
  const data = await parseErrorResponse(response);

  if (status === 429) {
    // Organization quota exceeded - extract type or default to volume_count
    const quotaType = extractQuotaType(data.message) ?? "unknown";
    throw new QuotaExceededError(data.message, quotaType);
  } else if (status === 503) {
    // Provisioning failed (invalid storage class, quota exceeded)
    throw new SandboxCreationError(data.message, "VolumeProvisioning");
  } else if (status === 504) {
    // Timeout - volume didn't become ready in time
    throw new ResourceTimeoutError(data.message, "volume");
  }
  // Fall through to generic handling
  return handleClientHttpError(response);
}

/**
 * Handle HTTP errors specific to pool creation/update.
 *
 * Maps API error responses to specific exception types:
 * - 400: ResourceNotFoundError or ValidationError (template has volumes)
 * - 409: ResourceAlreadyExistsError
 * - 429: QuotaExceededError (org limits exceeded)
 * - 504: ResourceTimeoutError (timeout waiting for ready replicas)
 * - Other: Falls through to generic error handling
 */
export async function handlePoolError(response: Response): Promise<never> {
  const status = response.status;
  const data = await parseErrorResponse(response);
  const errorType = data.errorType;

  if (status === 400) {
    // Check the error type to determine the specific exception
    if (errorType === "TemplateNotFound") {
      throw new ResourceNotFoundError(data.message, "template");
    } else if (errorType === "ValidationError") {
      // Template has volumes attached
      throw new ValidationError(data.message, undefined, undefined, errorType);
    }
    // Generic bad request - fall through to generic handling
  } else if (status === 409) {
    // Pool already exists
    throw new ResourceAlreadyExistsError(data.message, "pool");
  } else if (status === 429) {
    // Organization quota exceeded - extract type or default to pool_count
    const quotaType = extractQuotaType(data.message) ?? "unknown";
    throw new QuotaExceededError(data.message, quotaType);
  } else if (status === 504) {
    // Timeout waiting for pool to be ready
    throw new ResourceTimeoutError(data.message, "pool");
  }
  // Fall through to generic handling
  return handleClientHttpError(response);
}

/**
 * Handle HTTP errors and raise appropriate exceptions (for client operations).
 */
export async function handleClientHttpError(
  response: Response
): Promise<never> {
  const data = await parseErrorResponse(response);
  const message = data.message;
  const errorType = data.errorType;
  const status = response.status;

  if (status === 401 || status === 403) {
    throw new SandboxAuthenticationError(message);
  }
  if (status === 404) {
    throw new ResourceNotFoundError(message);
  }

  // Handle validation errors (invalid resource values, formats, etc.)
  if (status === 422) {
    const clonedResponse = response.clone();
    const details = await parseValidationError(clonedResponse);
    const field = details[0]?.loc?.slice(-1)[0] as string | undefined;
    throw new ValidationError(message, field, details);
  }

  // Handle quota exceeded errors (org limits)
  if (status === 429) {
    const quotaType = extractQuotaType(message);
    throw new QuotaExceededError(message, quotaType);
  }

  if (status === 502 && errorType === "ConnectionError") {
    throw new SandboxConnectionError(message);
  }
  if (status === 500) {
    throw new SandboxAPIError(message);
  }
  throw new SandboxClientError(message);
}

// =============================================================================
// Sandbox Operation Error Handlers
// =============================================================================

/**
 * Handle HTTP errors for sandbox operations (run, read, write).
 *
 * Maps API error types to specific exceptions:
 * - WriteError -> SandboxOperationError (operation="write")
 * - ReadError -> SandboxOperationError (operation="read")
 * - CommandError -> SandboxOperationError (operation="command")
 * - ConnectionError (502) -> SandboxConnectionError
 * - FileNotFound / 404 -> ResourceNotFoundError (resourceType="file")
 * - NotReady (400) -> SandboxNotReadyError
 * - 403 -> SandboxOperationError (permission denied)
 */
export async function handleSandboxHttpError(
  response: Response
): Promise<never> {
  const data = await parseErrorResponse(response);
  const message = data.message;
  const errorType = data.errorType;
  const status = response.status;

  // Operation-specific errors (from sandbox runtime)
  if (errorType === "WriteError") {
    throw new SandboxOperationError(message, "write", errorType);
  }
  if (errorType === "ReadError") {
    throw new SandboxOperationError(message, "read", errorType);
  }
  if (errorType === "CommandError") {
    throw new SandboxOperationError(message, "command", errorType);
  }

  // Permission denied
  if (status === 403) {
    throw new SandboxOperationError(message, undefined, "PermissionDenied");
  }

  // Connection to sandbox failed
  if (status === 502 && errorType === "ConnectionError") {
    throw new SandboxConnectionError(message);
  }

  // Not ready / not found
  if (status === 400 && errorType === "NotReady") {
    throw new SandboxNotReadyError(message);
  }
  if (status === 404 || errorType === "FileNotFound") {
    throw new ResourceNotFoundError(message, "file");
  }

  throw new SandboxClientError(message);
}

/**
 * Handle 409 Conflict errors for resource name conflicts.
 */
export async function handleConflictError(
  response: Response,
  resourceType: string
): Promise<never> {
  const data = await parseErrorResponse(response);
  throw new ResourceNameConflictError(data.message, resourceType);
}

/**
 * Handle 409 Conflict errors for resources in use.
 */
export async function handleResourceInUseError(
  response: Response,
  resourceType: string
): Promise<never> {
  const data = await parseErrorResponse(response);
  throw new ResourceInUseError(data.message, resourceType);
}
