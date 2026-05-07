/**
 * worker_threads abstraction (Node.js version).
 *
 * This file is swapped with worker_threads.browser.ts for browser / edge
 * builds via the package.json `browser` field. Node gets the real module;
 * browsers get a stub that signals unavailability.
 *
 * Only the surface actually used by SerializeWorker is re-exported.
 */

// eslint-disable-next-line import/no-unresolved
import { Worker as NodeWorker } from "node:worker_threads";

export type WorkerLike = InstanceType<typeof NodeWorker>;

export const Worker: typeof NodeWorker | null = NodeWorker;

export const WORKER_THREADS_AVAILABLE = true;
