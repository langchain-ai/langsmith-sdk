import { __version__ } from "../index.js";

/**
 * Single source of the SDK's `User-Agent`.
 *
 * The tracing client and the sandbox data-plane clients issue requests through
 * different machinery, so they cannot share a session — but a server should
 * still see one token identifying the SDK and its version. Keeping the token
 * here is what stops a second path from silently shipping without one.
 */
export function userAgent(): string {
  return `langsmith-js/${__version__}`;
}
