/**
 * Off-thread serialization using Node worker_threads.
 *
 * Gated behind LANGSMITH_PERF_OPTIMIZATION=true. Falls back silently to
 * synchronous serialize() when:
 *   - worker_threads is unavailable (browsers, Deno, Bun without compat,
 *     Cloudflare Workers, Vercel Edge, React Native)
 *   - the worker cannot be constructed (bundler/runtime constraints)
 *   - DataCloneError is thrown for a payload containing non-cloneable
 *     values (functions, class instances with non-cloneable state, etc.)
 *   - the worker crashes or throws
 *
 * Protocol:
 *   main -> worker: { id, op, payload }
 *     op = "serialize" -> worker returns bytes as a transferable ArrayBuffer
 *   worker -> main: { id, bytes?: ArrayBuffer, error?: string }
 *
 * The worker source is inlined as a string so the library bundles cleanly
 * under webpack/esbuild/ncc without requiring a separate asset file.
 */

// The worker script: a self-contained mirror of the hot path of
// src/utils/fast-safe-stringify/index.ts#serialize(). We deliberately
// don't import the TS module -- the worker runs as a standalone script.
const WORKER_SOURCE = /* js */ `
const { parentPort } = require("worker_threads");

const CIRCULAR_REPLACE_NODE = { result: "[Circular]" };

function serializeWellKnownTypes(val) {
  if (val && typeof val === "object") {
    if (val instanceof Map) return Object.fromEntries(val);
    if (val instanceof Set) return Array.from(val);
    if (val instanceof Date) return val.toISOString();
    if (val instanceof RegExp) return val.toString();
    if (val instanceof Error) return { name: val.name, message: val.message };
  } else if (typeof val === "bigint") {
    return val.toString();
  }
  return val;
}

function defaultReplacer(_key, val) {
  return serializeWellKnownTypes(val);
}

// Decirculate in-place: replace circular refs with { result: "[Circular]" }
// then restore after stringify. Mirrors fast-safe-stringify's decirc().
const restoreStack = [];
function decirc(val, k, stack, parent) {
  if (typeof val === "object" && val !== null) {
    for (let i = 0; i < stack.length; i++) {
      if (stack[i] === val) {
        const orig = parent[k];
        parent[k] = CIRCULAR_REPLACE_NODE;
        restoreStack.push([parent, k, orig]);
        return;
      }
    }
    stack.push(val);
    if (Array.isArray(val)) {
      for (let i = 0; i < val.length; i++) decirc(val[i], i, stack, val);
    } else {
      const normalized = serializeWellKnownTypes(val);
      // Only recurse into normalized if it's still an object (arrays/objects),
      // else it was replaced with a primitive (e.g. Date -> string).
      if (normalized === val) {
        const keys = Object.keys(val);
        for (let i = 0; i < keys.length; i++) decirc(val[keys[i]], keys[i], stack, val);
      }
    }
    stack.pop();
  }
}

function serialize(obj) {
  try {
    return JSON.stringify(obj, defaultReplacer);
  } catch (e) {
    if (!String(e && e.message).includes("Converting circular structure to JSON")) {
      return "[Unserializable]";
    }
    decirc(obj, "", [], { "": obj });
    try {
      return JSON.stringify(obj, defaultReplacer);
    } catch (_) {
      return "[unable to serialize, circular reference is too complex to analyze]";
    } finally {
      while (restoreStack.length) {
        const [p, k, v] = restoreStack.pop();
        p[k] = v;
      }
    }
  }
}

parentPort.on("message", (msg) => {
  const { id, op, payload } = msg;
  try {
    if (op === "serialize") {
      const str = serialize(payload);
      const buf = Buffer.from(str, "utf8");
      // Slice into its own ArrayBuffer so we can transfer without dragging
      // unrelated bytes from any shared pool buffer.
      const ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
      parentPort.postMessage({ id, bytes: ab, length: buf.byteLength }, [ab]);
    } else if (op === "ping") {
      parentPort.postMessage({ id });
    } else {
      parentPort.postMessage({ id, error: "unknown op: " + op });
    }
  } catch (e) {
    parentPort.postMessage({ id, error: String((e && e.message) || e) });
  }
});
`;

type Pending = {
  resolve: (bytes: Uint8Array<ArrayBuffer>) => void;
  reject: (err: Error) => void;
};

/**
 * Synchronously obtain the `worker_threads` module in both CJS and ESM
 * Node builds. Throws if the runtime does not support it (browsers, edge
 * runtimes, Deno without compat). We can only do this synchronously in
 * CJS; ESM consumers pay a one-time async cost on the very first call
 * which is handled by making `ensureStarted()` async.
 */
async function loadWorkerThreads(): Promise<
  typeof import("node:worker_threads")
> {
  // CJS path: `require` is defined at module scope.
  // Guard with `typeof` so ESM's ReferenceError becomes a falsy check.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const g = globalThis as any;
  if (typeof g.require === "function") {
    return g.require("node:worker_threads");
  }
  // ESM path: use a dynamic import (resolved by Node, skipped by
  // browser bundlers that treat node: imports as externals).
  return (await import("node:worker_threads")) as typeof import("node:worker_threads");
}

export class SerializeWorker {
  private worker: unknown | null = null;
  private nextId = 1;
  private pending = new Map<number, Pending>();
  private disabled = false;
  private startPromise: Promise<boolean> | null = null;

  /**
   * Try to construct the worker. Returns false if the runtime can't support
   * it -- in that case callers must fall back to synchronous serialization.
   * Async because ESM's `import("node:worker_threads")` is a Promise; in
   * practice CJS callers resolve synchronously.
   */
  private async ensureStarted(): Promise<boolean> {
    if (this.disabled) return false;
    if (this.worker !== null) return true;
    if (this.startPromise !== null) return this.startPromise;
    this.startPromise = this._start();
    try {
      return await this.startPromise;
    } finally {
      this.startPromise = null;
    }
  }

  private async _start(): Promise<boolean> {
    let wt: typeof import("node:worker_threads");
    try {
      wt = await loadWorkerThreads();
    } catch {
      this.disabled = true;
      return false;
    }
    try {
      const worker = new wt.Worker(WORKER_SOURCE, { eval: true });
      worker.on(
        "message",
        (msg: { id: number; bytes?: ArrayBuffer; length?: number; error?: string }) => {
          const p = this.pending.get(msg.id);
          if (!p) return;
          this.pending.delete(msg.id);
          if (msg.error) {
            p.reject(new Error(msg.error));
          } else if (msg.bytes && typeof msg.length === "number") {
            p.resolve(
              new Uint8Array(msg.bytes, 0, msg.length) as Uint8Array<ArrayBuffer>
            );
          } else {
            p.reject(new Error("worker returned malformed message"));
          }
        }
      );
      worker.on("error", (err: Error) => {
        // Reject all pending and disable; caller will fall back.
        for (const [, p] of this.pending) p.reject(err);
        this.pending.clear();
        this.disabled = true;
        this.worker = null;
      });
      worker.on("exit", (code: number) => {
        if (code !== 0) {
          for (const [, p] of this.pending) {
            p.reject(new Error(`worker exited with code ${code}`));
          }
          this.pending.clear();
        }
        this.worker = null;
      });
      // Don't let the worker keep the process alive.
      worker.unref();
      this.worker = worker;
      return true;
    } catch {
      this.disabled = true;
      return false;
    }
  }

  /**
   * Serialize a payload off-thread. Rejects with DataCloneError (or similar)
   * if the payload contains non-cloneable values -- callers must catch and
   * fall back to synchronous serialize().
   *
   * Resolves with null if the worker subsystem is unavailable entirely,
   * so the caller can fall back without paying try/catch overhead.
   */
  async serialize(
    payload: unknown
  ): Promise<Uint8Array<ArrayBuffer> | null> {
    const ok = await this.ensureStarted();
    if (!ok) return null;
    const id = this.nextId++;
    return new Promise<Uint8Array<ArrayBuffer>>((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      try {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (this.worker as any).postMessage({ id, op: "serialize", payload });
      } catch (e) {
        // postMessage throws synchronously for DataCloneError, unclonable
        // values, detached buffers, etc.
        this.pending.delete(id);
        reject(e as Error);
      }
    });
  }

  async terminate(): Promise<void> {
    if (this.worker) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      await (this.worker as any).terminate();
      this.worker = null;
    }
    for (const [, p] of this.pending) {
      p.reject(new Error("worker terminated"));
    }
    this.pending.clear();
  }
}

let sharedWorker: SerializeWorker | null = null;

/**
 * Process-wide shared worker. One worker serves all Client instances to
 * avoid spawning multiple threads per process.
 */
export function getSharedSerializeWorker(): SerializeWorker {
  if (sharedWorker === null) sharedWorker = new SerializeWorker();
  return sharedWorker;
}
