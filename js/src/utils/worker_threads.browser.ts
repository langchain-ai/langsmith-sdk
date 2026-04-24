/**
 * worker_threads abstraction (browser / edge stub).
 *
 * Selected in browser / edge builds via the package.json `browser` field.
 * Worker is null and WORKER_THREADS_AVAILABLE is false, so callers can
 * bail out at construction time without referencing `node:worker_threads`.
 *
 * Intentionally does not import `node:worker_threads` -- bundlers that
 * honor the browser field will never traverse the Node variant, so this
 * file is what determines the browser-bundle surface.
 */

export type WorkerLike = unknown;

export const Worker = null;

export const WORKER_THREADS_AVAILABLE = false;
