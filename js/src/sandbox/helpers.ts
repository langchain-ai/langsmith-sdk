/**
 * Shared helper functions for error handling.
 *
 * These functions are used to parse error responses and raise appropriate
 * exceptions. They contain no I/O operations.
 */

import type {
  FileChunk,
  FileStat,
  ReadRangeOptions,
  RunConfig,
} from "./types.js";
import {
  LangSmithQuotaExceededError,
  LangSmithResourceNotFoundError,
  LangSmithResourceTimeoutError,
  LangSmithSandboxAPIError,
  LangSmithSandboxAuthenticationError,
  LangSmithSandboxError,
  LangSmithSandboxConnectionError,
  LangSmithSandboxCreationError,
  LangSmithSandboxNotReadyError,
  LangSmithSandboxOperationError,
  LangSmithValidationError,
} from "./errors.js";

// =============================================================================
// Input validation
// =============================================================================

/**
 * Validate TTL values for sandbox create/update (minute resolution).
 *
 * @param value - TTL in seconds (`undefined` means unset; `0` disables).
 * @param name - Parameter name for error messages.
 * @throws LangSmithValidationError if negative or not a multiple of 60 (when non-zero).
 */
export function validateTtl(value: number | undefined, name: string): void {
  if (value === undefined) {
    return;
  }
  if (value < 0) {
    throw new LangSmithValidationError(
      `${name} must be >= 0, got ${value}`,
      name,
    );
  }
  if (value !== 0 && value % 60 !== 0) {
    throw new LangSmithValidationError(
      `${name} must be a multiple of 60 seconds, got ${value}`,
      name,
    );
  }
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
  response: Response,
): Promise<ParsedError> {
  try {
    const data = await response.json();
    const detail = data?.detail;

    // Standardized format: {"detail": {"error": "...", "message": "..."}}
    if (detail && typeof detail === "object" && !Array.isArray(detail)) {
      const message =
        detail.message || `HTTP ${response.status}: ${response.statusText}`;
      return {
        errorType: detail.error,
        message:
          typeof detail.error_id === "string" && detail.error_id
            ? `${message} (error_id=${detail.error_id})`
            : message,
      };
    }

    // Pydantic validation error format: {"detail": [{"loc": [...], "msg": "..."}]}
    if (Array.isArray(detail) && detail.length > 0) {
      const messages = detail
        .filter(
          (d): d is ValidationDetail => typeof d === "object" && d !== null,
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
  response: Response,
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
 * - 408: LangSmithResourceTimeoutError (sandbox didn't become ready in time)
 * - 422: LangSmithValidationError (bad input) or LangSmithSandboxCreationError (runtime)
 * - 429: LangSmithQuotaExceededError (org limits exceeded)
 * - 503: LangSmithSandboxCreationError (no resources available)
 * - Other: Falls through to generic error handling
 */
export async function handleSandboxCreationError(
  response: Response,
): Promise<never> {
  const status = response.status;
  const clonedResponse = response.clone();
  const data = await parseErrorResponse(response);

  if (status === 408) {
    // Timeout - include the message which contains last known status
    throw new LangSmithResourceTimeoutError(data.message, "sandbox");
  } else if (status === 422) {
    // Check if this is a Pydantic validation error (bad input) vs creation error
    const details = await parseValidationError(clonedResponse);
    if (details.length > 0 && details.some((d) => d.type === "value_error")) {
      // Pydantic validation error (bad input - exceeds server limits)
      const field = details[0]?.loc?.slice(-1)[0] as string | undefined;
      throw new LangSmithValidationError(data.message, field, details);
    } else {
      // Sandbox creation failed (runtime error like image pull failure)
      throw new LangSmithSandboxCreationError(data.message, data.errorType);
    }
  } else if (status === 429) {
    // Organization quota exceeded - extract type or default to sandbox_count
    const quotaType = extractQuotaType(data.message) ?? "unknown";
    throw new LangSmithQuotaExceededError(data.message, quotaType);
  } else if (status === 503) {
    // Service Unavailable - scheduling failed
    throw new LangSmithSandboxCreationError(
      data.message,
      data.errorType || "Unschedulable",
    );
  }
  // Fall through to generic handling — pass clone since body is already consumed
  return handleClientHttpError(clonedResponse);
}

/**
 * Throw `LangSmithSandboxNotReadyError` when the API rejected a proxy-config
 * update because the sandbox is not `ready`.
 *
 * That status check is the sole source of `InvalidRequest` on the update
 * endpoint for the fields this client sends, so a typed error lets callers
 * start the sandbox and retry instead of matching on status codes. Reads a
 * clone so the caller's own error handling can still consume the body.
 */
export async function throwIfNotReady(
  response: Response,
  name: string,
): Promise<void> {
  if (response.status !== 400) {
    return;
  }
  const data = await parseErrorResponse(response.clone());
  if (data.errorType !== "InvalidRequest") {
    return;
  }
  throw new LangSmithSandboxNotReadyError(
    data.message || `Sandbox '${name}' is not ready`,
  );
}

/**
 * Handle HTTP errors and raise appropriate exceptions (for client operations).
 */
export async function handleClientHttpError(
  response: Response,
): Promise<never> {
  const status = response.status;
  // Only clone when we need to read the body twice (status 422 reads it again
  // for structured validation details after parseErrorResponse consumes it).
  const clonedResponse = status === 422 ? response.clone() : null;
  const data = await parseErrorResponse(response);
  const message = data.message;
  const errorType = data.errorType;

  if (status === 401 || status === 403) {
    throw new LangSmithSandboxAuthenticationError(message);
  }
  if (status === 404) {
    throw new LangSmithResourceNotFoundError(message);
  }

  // Handle validation errors (invalid resource values, formats, etc.)
  if (status === 422 && clonedResponse) {
    const details = await parseValidationError(clonedResponse);
    const field = details[0]?.loc?.slice(-1)[0] as string | undefined;
    throw new LangSmithValidationError(message, field, details);
  }

  // Handle quota exceeded errors (org limits)
  if (status === 429) {
    const quotaType = extractQuotaType(message);
    throw new LangSmithQuotaExceededError(message, quotaType);
  }

  if (status === 502 && errorType === "ConnectionError") {
    throw new LangSmithSandboxConnectionError(message);
  }
  if (status === 500) {
    throw new LangSmithSandboxAPIError(message);
  }
  throw new LangSmithSandboxError(message);
}

// =============================================================================
// Sandbox Operation Error Handlers
// =============================================================================

/**
 * Handle HTTP errors for sandbox operations (run, read, write).
 *
 * Maps API error types to specific exceptions:
 * - WriteError -> LangSmithSandboxOperationError (operation="write")
 * - ReadError -> LangSmithSandboxOperationError (operation="read")
 * - CommandError -> LangSmithSandboxOperationError (operation="command")
 * - ConnectionError (502) -> LangSmithSandboxConnectionError
 * - FileNotFound / 404 -> LangSmithResourceNotFoundError (resourceType="file")
 * - NotReady (400) -> LangSmithSandboxNotReadyError
 * - 403 -> LangSmithSandboxOperationError (permission denied)
 */
export async function handleSandboxHttpError(
  response: Response,
): Promise<never> {
  const data = await parseErrorResponse(response);
  const message = data.message;
  const errorType = data.errorType;
  const status = response.status;

  // Operation-specific errors (from sandbox runtime)
  if (errorType === "WriteError") {
    throw new LangSmithSandboxOperationError(message, "write", errorType);
  }
  if (errorType === "ReadError") {
    throw new LangSmithSandboxOperationError(message, "read", errorType);
  }
  if (errorType === "CommandError") {
    throw new LangSmithSandboxOperationError(message, "command", errorType);
  }

  // Permission denied
  if (status === 403) {
    throw new LangSmithSandboxOperationError(
      message,
      undefined,
      "PermissionDenied",
    );
  }

  // Connection to sandbox failed
  if (status === 502 && errorType === "ConnectionError") {
    throw new LangSmithSandboxConnectionError(message);
  }

  // Not ready / not found
  if (status === 400 && errorType === "NotReady") {
    throw new LangSmithSandboxNotReadyError(message);
  }
  if (status === 404 || errorType === "FileNotFound") {
    throw new LangSmithResourceNotFoundError(message, "file");
  }

  throw new LangSmithSandboxError(message);
}

// =============================================================================
// Run configuration
// =============================================================================

/**
 * Reject a per-command `runConfig` alongside the deprecated `env`/`cwd`.
 *
 * The server answers 400 for a request carrying both spellings rather than
 * letting one silently win, so refuse it here where the message can name the
 * replacement.
 */
export function assertRunConfigNotCombined(options: {
  runConfig?: RunConfig;
  env?: Record<string, string>;
  cwd?: string;
}): void {
  if (
    options.runConfig !== undefined &&
    (options.env !== undefined || options.cwd !== undefined)
  ) {
    throw new LangSmithValidationError(
      "Cannot combine runConfig with the deprecated env/cwd options. " +
        "Use runConfig.env_vars and runConfig.work_dir instead.",
    );
  }
}

/**
 * Whether to half-close stdin at spawn.
 *
 * Defaults on for a non-PTY command: a command that reads stdin otherwise
 * blocks on a pipe nobody writes to until the timeout kills it. A PTY has no
 * separate write end to close, so the server ignores the flag there.
 */
export function resolveCloseInput(
  closeInput: boolean | undefined,
  pty: boolean,
): boolean {
  if (pty) return false;
  return closeInput ?? true;
}

// =============================================================================
// Ranged downloads
// =============================================================================

/** Render a byte range as an RFC 9110 `Range` header value. */
export function buildRangeHeader(options: ReadRangeOptions): string {
  const { start, end, suffixBytes } = options;
  if (suffixBytes !== undefined) {
    if (start !== undefined || end !== undefined) {
      throw new LangSmithValidationError(
        "Cannot combine suffixBytes with start/end.",
      );
    }
    if (suffixBytes <= 0) {
      throw new LangSmithValidationError("suffixBytes must be positive.");
    }
    return `bytes=-${suffixBytes}`;
  }
  if (start === undefined) {
    throw new LangSmithValidationError(
      "Provide start (with optional end), or suffixBytes.",
    );
  }
  if (start < 0) {
    throw new LangSmithValidationError("start must not be negative.");
  }
  if (end === undefined) {
    return `bytes=${start}-`;
  }
  if (end < start) {
    throw new LangSmithValidationError("end must not precede start.");
  }
  return `bytes=${start}-${end}`;
}

/** Read the first byte offset and total size out of `Content-Range`. */
function parseContentRange(value: string | null): {
  start: number;
  total?: number;
} {
  if (!value || !value.startsWith("bytes ")) return { start: 0 };
  const spec = value.slice("bytes ".length).trim();
  const [rangePart, totalPart] = spec.split("/");
  const first = rangePart.split("-")[0].trim();
  const start = /^\d+$/.test(first) ? Number(first) : 0;
  const total = /^\d+$/.test((totalPart ?? "").trim())
    ? Number(totalPart)
    : undefined;
  return { start, total };
}

/** Build a FileStat from a HEAD response's headers. */
export function fileStatFromResponse(response: Response): FileStat {
  const length = response.headers.get("content-length");
  return {
    size_bytes: length && /^\d+$/.test(length) ? Number(length) : 0,
    etag: response.headers.get("etag") ?? undefined,
    last_modified: response.headers.get("last-modified") ?? undefined,
    content_type: response.headers.get("content-type") ?? undefined,
  };
}

/** Build a FileChunk from a ranged download response. */
export async function fileChunkFromResponse(
  response: Response,
): Promise<FileChunk> {
  const etag = response.headers.get("etag") ?? undefined;
  const lastModified = response.headers.get("last-modified") ?? undefined;
  if (response.status === 304) {
    return {
      content: new Uint8Array(0),
      etag,
      start: 0,
      partial: false,
      unchanged: true,
      last_modified: lastModified,
    };
  }
  const content = new Uint8Array(await response.arrayBuffer());
  const partial = response.status === 206;
  // A stale If-Range answers 200 with the whole file; the caller has to
  // restart rather than append, so report it from byte zero.
  const { start, total } = partial
    ? parseContentRange(response.headers.get("content-range"))
    : { start: 0, total: content.length };
  return {
    content,
    etag,
    total_bytes: total,
    start,
    partial,
    unchanged: false,
    last_modified: lastModified,
  };
}

/** Map a file-operation HTTP error, including the non-JSON 416. */
export async function handleFileHttpError(
  response: Response,
  path: string,
  sandboxName: string,
): Promise<never> {
  if (response.status === 404) {
    throw new LangSmithResourceNotFoundError(
      `File '${path}' not found in sandbox '${sandboxName}'`,
      "file",
    );
  }
  if (response.status === 416) {
    throw new LangSmithSandboxOperationError(
      `Requested range for '${path}' starts past the end of the file ` +
        `(${response.headers.get("content-range") ?? "unknown size"}).`,
      "read",
    );
  }
  return handleSandboxHttpError(response);
}
