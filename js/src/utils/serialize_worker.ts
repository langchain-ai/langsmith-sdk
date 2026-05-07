/**
 * Off-thread serialization using Node worker_threads.
 *
 * Falls back silently to synchronous serialize() when:
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

import {
  Worker as WorkerCtor,
  WORKER_THREADS_AVAILABLE,
  type WorkerLike,
} from "./worker_threads.js";

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

export class SerializeWorker {
  private worker: WorkerLike | null = null;
  private nextId = 1;
  private pending = new Map<number, Pending>();
  private disabled = false;
  private startPromise: Promise<boolean> | null = null;

  /**
   * Try to construct the worker. Returns false if the runtime can't support
   * it -- in that case callers must fall back to synchronous serialization.
   * Kept async so callers don't have to branch on runtime -- the promise
   * resolves synchronously on the microtask queue when the worker module
   * is available, which is the common Node CJS/ESM path.
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
    // In browser / edge builds the `worker_threads` module is swapped with
    // a stub that reports unavailability via the package.json `browser`
    // field. Bail out before touching any Node-only surface.
    if (!WORKER_THREADS_AVAILABLE || WorkerCtor === null) {
      this.disabled = true;
      return false;
    }
    try {
      const worker = new WorkerCtor(WORKER_SOURCE, { eval: true });
      worker.on(
        "message",
        (msg: {
          id: number;
          bytes?: ArrayBuffer;
          length?: number;
          error?: string;
        }) => {
          const p = this.pending.get(msg.id);
          if (!p) return;
          this.pending.delete(msg.id);
          if (msg.error) {
            p.reject(new Error(msg.error));
          } else if (msg.bytes && typeof msg.length === "number") {
            p.resolve(
              new Uint8Array(
                msg.bytes,
                0,
                msg.length,
              ) as Uint8Array<ArrayBuffer>,
            );
          } else {
            p.reject(new Error("worker returned malformed message"));
          }
        },
      );
      worker.on("error", (err: Error) => {
        // Reject all pending and disable; caller will fall back.
        for (const [, p] of this.pending) p.reject(err);
        this.pending.clear();
        this.disabled = true;
        this.worker = null;
      });
      worker.on("exit", (code: number) => {
        // Reject all pending requests regardless of exit code. Even a clean
        // exit (code 0) with in-flight requests means those promises would
        // otherwise hang forever.
        for (const [, p] of this.pending) {
          p.reject(new Error(`worker exited with code ${code}`));
        }
        this.pending.clear();
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
  async serialize(payload: unknown): Promise<Uint8Array<ArrayBuffer> | null> {
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

/**
 * Minimum string length (in UTF-16 code units) that justifies the overhead
 * of dispatching serialization to a worker thread.
 *
 * Rationale: V8's postMessage / structuredClone fast-paths large strings
 * across isolates by refcounting their underlying storage rather than
 * copying the bytes. This makes worker offload a big win for payloads
 * dominated by a handful of multi-hundred-KB strings (the classic case is
 * base64-encoded images or audio in LLM messages), but a net loss for
 * payloads whose bulk is structural -- thousands of keys, deep nesting,
 * many small strings -- because every object node must still be walked
 * and cloned.
 *
 * 64KB sits comfortably above typical "chunk of agent state" or "long
 * prompt" values (a few KB) and below typical base64 media payloads
 * (hundreds of KB to several MB).
 */
const LARGE_STRING_THRESHOLD = 64 * 1024;

/**
 * Maximum number of nodes to inspect before giving up and assuming the
 * payload is not worth offloading. Prevents the check itself from becoming
 * expensive on pathologically structural payloads (many thousands of small
 * keys / array elements).
 *
 * When the budget is exhausted without finding a large string we return
 * false (do not offload). This is the conservative choice: such payloads
 * are structural by nature and worker offload empirically regresses them.
 */
const NODE_BUDGET = 2048;

/**
 * Cheap, short-circuiting walk that returns true iff the payload contains
 * at least one string of length >= threshold anywhere in its graph.
 *
 * - Terminates immediately on the first qualifying string.
 * - Caps total nodes visited at `nodeBudget` so cost is bounded for huge
 *   structural payloads.
 * - Avoids allocation in the common path: uses an array as a stack and a
 *   Set only for cycle detection.
 * - Uses `string.length` (UTF-16 units), not UTF-8 byte length, because
 *   that's what V8's string-sharing fast path keys on and because it's
 *   an O(1) property access. For ASCII content this is identical to the
 *   UTF-8 byte count; for non-ASCII text the two differ by at most 4x,
 *   well within the safety margin of the threshold.
 */
export function hasLargeString(
  value: unknown,
  threshold: number = LARGE_STRING_THRESHOLD,
  nodeBudget: number = NODE_BUDGET,
): boolean {
  if (value === null || typeof value !== "object") {
    return typeof value === "string" && value.length >= threshold;
  }
  const stack: unknown[] = [value];
  const seen = new Set<object>();
  let visited = 0;
  while (stack.length > 0) {
    if (visited++ >= nodeBudget) return false;
    const cur = stack.pop();
    if (cur === null || cur === undefined) continue;
    const t = typeof cur;
    if (t === "string") {
      if ((cur as string).length >= threshold) return true;
      continue;
    }
    if (t !== "object") continue;
    const obj = cur as object;
    if (seen.has(obj)) continue;
    seen.add(obj);
    // Skip well-known opaque types -- none of their enumerable own
    // properties produce large strings in practice, and ArrayBuffer views
    // would inflate the node budget if iterated element by element.
    /* eslint-disable no-instanceof/no-instanceof */
    if (
      obj instanceof Date ||
      obj instanceof RegExp ||
      obj instanceof Error ||
      obj instanceof ArrayBuffer ||
      ArrayBuffer.isView(obj)
    ) {
      continue;
    }
    if (Array.isArray(obj)) {
      // Iterate in reverse so the first element is popped first (stable
      // left-to-right discovery order, harmless but nice for predictable
      // short-circuits in tests).
      for (let i = obj.length - 1; i >= 0; i--) stack.push(obj[i]);
      continue;
    }
    if (obj instanceof Map) {
      for (const [, v] of obj) stack.push(v);
      continue;
    }
    if (obj instanceof Set) {
      for (const v of obj) stack.push(v);
      continue;
    }
    /* eslint-enable no-instanceof/no-instanceof */
    // Push keys in reverse so they pop in declared order. Combined with
    // the similar reverse-push for arrays above, this makes discovery
    // order a stable depth-first walk in source order -- which matters
    // for predictable short-circuit behavior under a node budget.
    const keys = Object.keys(obj);
    for (let i = keys.length - 1; i >= 0; i--) {
      stack.push((obj as Record<string, unknown>)[keys[i]]);
    }
  }
  return false;
}
