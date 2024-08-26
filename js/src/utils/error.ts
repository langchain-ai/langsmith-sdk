function getErrorStackTrace(e: unknown) {
  if (typeof e !== "object" || e == null) return undefined;
  if (!("stack" in e) || typeof e.stack !== "string") return undefined;

  let stack = e.stack;

  const prevLine = `${e}`;
  if (stack.startsWith(prevLine)) {
    stack = stack.slice(prevLine.length);
  }

  if (stack.startsWith("\n")) {
    stack = stack.slice(1);
  }

  return stack;
}

export function printErrorStackTrace(e: unknown) {
  const stack = getErrorStackTrace(e);
  if (stack == null) return;
  console.error(stack);
}

/**
 * LangSmithConflictError
 *
 * Represents an error that occurs when there's a conflict during an operation,
 * typically corresponding to HTTP 409 status code responses.
 *
 * This error is thrown when an attempt to create or modify a resource conflicts
 * with the current state of the resource on the server. Common scenarios include:
 * - Attempting to create a resource that already exists
 * - Trying to update a resource that has been modified by another process
 * - Violating a uniqueness constraint in the data
 *
 * @extends Error
 *
 * @example
 * try {
 *   await createProject("existingProject");
 * } catch (error) {
 *   if (error instanceof ConflictError) {
 *     console.log("A conflict occurred:", error.message);
 *     // Handle the conflict, e.g., by suggesting a different project name
 *   } else {
 *     // Handle other types of errors
 *   }
 * }
 *
 * @property {string} name - Always set to 'ConflictError' for easy identification
 * @property {string} message - Detailed error message including server response
 *
 * @see https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/409
 */
export class LangSmithConflictError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "LangSmithConflictError";
  }
}

/**
 * Throws an appropriate error based on the response status and body.
 *
 * @param response - The fetch Response object
 * @param context - Additional context to include in the error message (e.g., operation being performed)
 * @throws {LangSmithConflictError} When the response status is 409
 * @throws {Error} For all other non-ok responses
 */
export async function raiseForStatus(
  response: Response,
  context: string,
  consume?: boolean
): Promise<void> {
  // consume the response body to release the connection
  // https://undici.nodejs.org/#/?id=garbage-collection
  let errorBody;
  if (response.ok) {
    if (consume) {
      errorBody = await response.text();
    }
    return;
  }
  errorBody = await response.text();
  const fullMessage = `Failed to ${context}. Received status [${response.status}]: ${response.statusText}. Server response: ${errorBody}`;

  if (response.status === 409) {
    throw new LangSmithConflictError(fullMessage);
  }

  throw new Error(fullMessage);
}
