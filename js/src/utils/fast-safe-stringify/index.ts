/* eslint-disable */
// @ts-nocheck
import { getLangSmithEnvironmentVariable } from "../../utils/env.js";

var LIMIT_REPLACE_NODE = "[...]";
var CIRCULAR_REPLACE_NODE = { result: "[Circular]" };

var arr = [];
var replacerStack = [];

const encoder = new TextEncoder();

function defaultOptions() {
  return {
    depthLimit: Number.MAX_SAFE_INTEGER,
    edgesLimit: Number.MAX_SAFE_INTEGER,
  };
}

function encodeString(str: string): Uint8Array<ArrayBuffer> {
  return encoder.encode(str);
}

// Shared function to handle well-known types
function serializeWellKnownTypes(val) {
  if (val && typeof val === "object" && val !== null) {
    if (val instanceof Map) {
      return Object.fromEntries(val);
    } else if (val instanceof Set) {
      return Array.from(val);
    } else if (val instanceof Date) {
      return val.toISOString();
    } else if (val instanceof RegExp) {
      return val.toString();
    } else if (val instanceof Error) {
      return {
        name: val.name,
        message: val.message,
      };
    }
  } else if (typeof val === "bigint") {
    return val.toString();
  }
  return val;
}

// Default replacer function to handle well-known types
function createDefaultReplacer(userReplacer?) {
  return function (key, val) {
    // Apply user replacer first if provided
    if (userReplacer) {
      const userResult = userReplacer.call(this, key, val);
      // If user replacer returned undefined, fall back to our serialization
      if (userResult !== undefined) {
        return userResult;
      }
    }

    // Fall back to our well-known type handling
    return serializeWellKnownTypes(val);
  };
}

/**
 * Estimate the serialized JSON byte size of a value without actually
 * serializing it. Used on hot paths (enqueuing runs for batched tracing)
 * where the exact serialized size is not required -- only a reasonable
 * approximation for soft memory accounting.
 *
 * Walks the object graph in O(n) without allocating a JSON string,
 * avoiding the event-loop blocking that JSON.stringify causes on large
 * payloads.
 *
 * Accuracy notes (all estimates are approximate, never exact):
 * - Strings: UTF-8 byte length via Buffer.byteLength when available,
 *   falling back to code-unit length for non-Node environments. Does
 *   not account for escape expansion (\", \\, control chars, surrogate
 *   escapes) which is usually a small fraction of total size.
 * - Binary data (Buffer / typed arrays / ArrayBuffer / DataView): sized
 *   from their JSON.stringify representations where practical
 *   ({ type: "Buffer", data: [...] } for Buffer, keyed objects for typed
 *   arrays). DataView and ArrayBuffer themselves have no enumerable own
 *   properties and serialize as "{}". Each byte contributes ~3.5
 *   characters on average in Buffer's decimal-array representation
 *   (digit(s) + comma).
 * - Other objects with toJSON(): we invoke toJSON() once and estimate
 *   the result. This matches JSON.stringify semantics for libraries
 *   like Decimal.js, Moment, Luxon, Mongoose documents, etc.
 * - Cycles: detected via an ancestor-path set that is pushed/popped
 *   during recursion. This matches JSON.stringify semantics --
 *   repeated references that are *not* on the current ancestor chain
 *   (shared subobjects) are counted every time they appear, because
 *   JSON.stringify will serialize them every time.
 * - No depth limit (JSON.stringify has none either).
 */
export interface EstimatedSize {
  /** Approximate serialized JSON byte size. */
  size: number;
  /**
   * Length (in UTF-8 bytes) of the longest single string value encountered
   * anywhere in the payload graph. Callers can use this as a shape-aware
   * dispatch signal -- for example, to decide whether to offload serialize
   * to a worker thread (which only pays off when a payload contains one
   * or more large strings, since V8 shares string storage across isolates
   * via refcount).
   */
  maxStringLen: number;
}

export function estimateSerializedSize(value: unknown): EstimatedSize {
  try {
    // Ancestor set for cycle detection. An object is only treated as
    // circular if it appears on the current recursion path, not merely
    // if it has been seen before elsewhere in the graph.
    const ancestors = new Set<object>();
    let maxStringLen = 0;

    // In Node / Bun, Buffer.byteLength is a fast native way to get UTF-8
    // byte length without allocating an encoded copy. In other runtimes
    // we fall back to code-unit length (a small under-estimate for
    // non-ASCII text, which is acceptable for soft limits).
    const byteLen: (s: string) => number =
      typeof Buffer !== "undefined" && typeof Buffer.byteLength === "function"
        ? (s) => Buffer.byteLength(s, "utf8")
        : (s) => s.length;

    function estimateString(s: string): number {
      // +2 for the surrounding quotes. Escape expansion is not counted.
      const n = byteLen(s);
      if (n > maxStringLen) maxStringLen = n;
      return n + 2;
    }

    // Size of a byte sequence when rendered as a JSON array of decimal
    // numbers: "[b0,b1,b2,...]". Each byte averages ~3.5 chars (value 0-9
    // => 1 char, 10-99 => 2 chars, 100-255 => 3 chars; weighted mean over
    // a uniform distribution is ~2.81, plus one comma per element except
    // the last). Round up to 4 bytes/element for a small safety margin.
    function estimateByteArrayJson(byteLength: number): number {
      if (byteLength === 0) return 2; // "[]"
      return 2 + byteLength * 4;
    }

    // Returns true for values that JSON.stringify drops when they appear
    // as an object property (as opposed to an array element, where they
    // become "null").
    function isDropped(v: unknown): boolean {
      return (
        v === undefined || typeof v === "function" || typeof v === "symbol"
      );
    }

    // In arrays, undefined / function / symbol become "null" (4 bytes).
    function estimateInArray(v: unknown): number {
      if (v === undefined || typeof v === "function" || typeof v === "symbol") {
        return 4;
      }
      return estimate(v);
    }

    function estimate(val: unknown): number {
      if (val === null) return 4; // "null"
      if (val === undefined) return 0; // top-level or property context; array handled separately
      const t = typeof val;
      if (t === "boolean") return 5; // "true" / "false" upper bound
      if (t === "number") {
        if (!Number.isFinite(val as number)) return 4; // "null"
        // Convert to string to get exact length. This is cheap for numbers
        // (V8 caches small-number strings) and makes the estimate far
        // tighter for common cases like integer arrays.
        return (val as number).toString().length;
      }
      if (t === "bigint") {
        // Our replacer renders BigInt via .toString(), then JSON.stringify
        // quotes it.
        return (val as bigint).toString().length + 2;
      }
      if (t === "string") return estimateString(val as string);
      if (t === "function" || t === "symbol") return 0;

      // Objects from here on.
      const obj = val as object;

      // Well-known types handled by our replacer.
      if (obj instanceof Date) return 26; // "2024-01-01T00:00:00.000Z"
      if (obj instanceof RegExp) return byteLen(obj.toString()) + 2;
      if (obj instanceof Error) {
        const name = obj.name ?? "";
        const message = obj.message ?? "";
        // {"name":"...","message":"..."}
        return 22 + byteLen(name) + byteLen(message);
      }

      // Binary data types. These commonly appear in LLM payloads (images,
      // audio) and their JSON representations vary widely.
      if (typeof Buffer !== "undefined" && obj instanceof Buffer) {
        // { "type": "Buffer", "data": [0, 1, 2, ...] }
        return 28 + estimateByteArrayJson(obj.byteLength);
      }
      if (ArrayBuffer.isView(obj)) {
        if (obj instanceof DataView) {
          // DataView has no enumerable own properties; serializes as "{}".
          return 2;
        }
        // Typed arrays serialize as {"0":v0,"1":v1,...} (keyed objects),
        // which is much larger than a plain array would be. Per element
        // cost: digits for index + digits for value + ":" + "," + quotes.
        const len = (obj as unknown as { length: number }).length ?? 0;
        const isFloat =
          obj instanceof Float32Array || obj instanceof Float64Array;
        // Index digits grow with len; worst-case per element:
        //   "NNN":V,   where NNN = log10(len) digits and V depends on type.
        // Loose but safe bounds: integer views ~12 chars/element, float
        // views ~30 chars/element (Float32 ToString can be up to ~17 chars).
        const perElement = isFloat ? 30 : 12;
        return 2 + len * perElement;
      }
      if (obj instanceof ArrayBuffer) {
        // Plain ArrayBuffer has no enumerable properties; serializes as "{}".
        return 2;
      }

      if (ancestors.has(obj)) {
        // Cycle: our decirc fallback replaces with { result: "[Circular]" }.
        return 24;
      }

      // Custom toJSON (Decimal.js, Moment, Luxon, Mongoose docs, etc.).
      // This runs after explicit built-in / binary cases above so known
      // types (for example Buffer) use their dedicated fast-path sizing
      // logic instead of duck-typing through toJSON().
      if (typeof (obj as { toJSON?: unknown }).toJSON === "function") {
        let projected: unknown;
        try {
          projected = (obj as { toJSON: (key?: string) => unknown }).toJSON("");
        } catch {
          // If toJSON throws, JSON.stringify would also throw and our
          // serializer would emit "[Unserializable]" (~16 bytes).
          return 16;
        }
        ancestors.add(obj);
        const size = estimate(projected);
        ancestors.delete(obj);
        return size;
      }

      ancestors.add(obj);
      let size: number;
      if (Array.isArray(obj)) {
        size = 2; // []
        const len = obj.length;
        for (let i = 0; i < len; i++) {
          size += estimateInArray(obj[i]);
          if (i < len - 1) size += 1; // comma
        }
      } else if (obj instanceof Map) {
        // Rendered as { k: v, ... } via Object.fromEntries.
        size = 2;
        let emitted = 0;
        for (const [k, v] of obj) {
          if (isDropped(v)) continue;
          if (emitted > 0) size += 1; // comma
          const keyStr = typeof k === "string" ? k : String(k);
          size += byteLen(keyStr) + 3; // "key":
          size += estimate(v);
          emitted++;
        }
      } else if (obj instanceof Set) {
        // Rendered as [v, ...] via Array.from.
        size = 2;
        let emitted = 0;
        for (const v of obj) {
          if (emitted > 0) size += 1; // comma
          size += estimateInArray(v);
          emitted++;
        }
      } else {
        size = 2; // {}
        let emitted = 0;
        // Object.keys only returns own enumerable string keys, matching
        // JSON.stringify.
        const keys = Object.keys(obj);
        for (let i = 0; i < keys.length; i++) {
          const key = keys[i];
          const v = (obj as Record<string, unknown>)[key];
          if (isDropped(v)) continue;
          if (emitted > 0) size += 1; // comma
          size += byteLen(key) + 3; // "key":
          size += estimate(v);
          emitted++;
        }
      }
      ancestors.delete(obj);
      return size;
    }

    const size = estimate(value);
    return { size, maxStringLen };
  } catch {
    // If the estimator itself hits an unexpected edge case, fall back to the
    // exact serialized size. This preserves correctness of queue-size
    // accounting at the cost of a slower hot path for that one payload.
    // We cannot cheaply recover maxStringLen here, so report 0: the worker
    // gate will then fall back to sync serialization, which is safe.
    return { size: serialize(value).length, maxStringLen: 0 };
  }
}

// Regular stringify
export function serialize(
  obj,
  errorContext?,
  replacer?,
  spacer?,
  options?,
): Uint8Array<ArrayBuffer> {
  try {
    const str = JSON.stringify(obj, createDefaultReplacer(replacer), spacer);
    return encodeString(str);
  } catch (e: any) {
    // Fall back to more complex stringify if circular reference
    if (!e.message?.includes("Converting circular structure to JSON")) {
      console.warn(
        `[WARNING]: LangSmith received unserializable value.${
          errorContext ? `\nContext: ${errorContext}` : ""
        }`,
      );
      return encodeString("[Unserializable]");
    }
    getLangSmithEnvironmentVariable("SUPPRESS_CIRCULAR_JSON_WARNINGS") !==
      "true" &&
      console.warn(
        `[WARNING]: LangSmith received circular JSON. This will decrease tracer performance. ${
          errorContext ? `\nContext: ${errorContext}` : ""
        }`,
      );
    if (typeof options === "undefined") {
      options = defaultOptions();
    }

    decirc(obj, "", 0, [], undefined, 0, options);
    let res: string;
    try {
      if (replacerStack.length === 0) {
        res = JSON.stringify(obj, replacer, spacer);
      } else {
        res = JSON.stringify(obj, replaceGetterValues(replacer), spacer);
      }
    } catch (_) {
      return encodeString(
        "[unable to serialize, circular reference is too complex to analyze]",
      );
    } finally {
      while (arr.length !== 0) {
        const part = arr.pop();
        if (part.length === 4) {
          Object.defineProperty(part[0], part[1], part[3]);
        } else {
          part[0][part[1]] = part[2];
        }
      }
    }
    return encodeString(res);
  }
}

function setReplace(replace, val, k, parent) {
  var propertyDescriptor = Object.getOwnPropertyDescriptor(parent, k);
  if (propertyDescriptor.get !== undefined) {
    if (propertyDescriptor.configurable) {
      Object.defineProperty(parent, k, { value: replace });
      arr.push([parent, k, val, propertyDescriptor]);
    } else {
      replacerStack.push([val, k, replace]);
    }
  } else {
    parent[k] = replace;
    arr.push([parent, k, val]);
  }
}

function decirc(val, k, edgeIndex, stack, parent, depth, options) {
  depth += 1;
  var i;
  if (typeof val === "object" && val !== null) {
    for (i = 0; i < stack.length; i++) {
      if (stack[i] === val) {
        setReplace(CIRCULAR_REPLACE_NODE, val, k, parent);
        return;
      }
    }

    if (
      typeof options.depthLimit !== "undefined" &&
      depth > options.depthLimit
    ) {
      setReplace(LIMIT_REPLACE_NODE, val, k, parent);
      return;
    }

    if (
      typeof options.edgesLimit !== "undefined" &&
      edgeIndex + 1 > options.edgesLimit
    ) {
      setReplace(LIMIT_REPLACE_NODE, val, k, parent);
      return;
    }

    stack.push(val);
    // Optimize for Arrays. Big arrays could kill the performance otherwise!
    if (Array.isArray(val)) {
      for (i = 0; i < val.length; i++) {
        decirc(val[i], i, i, stack, val, depth, options);
      }
    } else {
      // Handle well-known types before Object.keys iteration
      val = serializeWellKnownTypes(val);

      var keys = Object.keys(val);
      for (i = 0; i < keys.length; i++) {
        var key = keys[i];
        decirc(val[key], key, i, stack, val, depth, options);
      }
    }
    stack.pop();
  }
}

// Stable-stringify
function compareFunction(a, b) {
  if (a < b) {
    return -1;
  }
  if (a > b) {
    return 1;
  }
  return 0;
}

function deterministicStringify(obj, replacer, spacer, options) {
  if (typeof options === "undefined") {
    options = defaultOptions();
  }

  var tmp = deterministicDecirc(obj, "", 0, [], undefined, 0, options) || obj;
  var res;
  try {
    if (replacerStack.length === 0) {
      res = JSON.stringify(tmp, replacer, spacer);
    } else {
      res = JSON.stringify(tmp, replaceGetterValues(replacer), spacer);
    }
  } catch (_) {
    return JSON.stringify(
      "[unable to serialize, circular reference is too complex to analyze]",
    );
  } finally {
    // Ensure that we restore the object as it was.
    while (arr.length !== 0) {
      var part = arr.pop();
      if (part.length === 4) {
        Object.defineProperty(part[0], part[1], part[3]);
      } else {
        part[0][part[1]] = part[2];
      }
    }
  }
  return res;
}

function deterministicDecirc(val, k, edgeIndex, stack, parent, depth, options) {
  depth += 1;
  var i;
  if (typeof val === "object" && val !== null) {
    for (i = 0; i < stack.length; i++) {
      if (stack[i] === val) {
        setReplace(CIRCULAR_REPLACE_NODE, val, k, parent);
        return;
      }
    }
    try {
      if (typeof val.toJSON === "function") {
        return;
      }
    } catch (_) {
      return;
    }

    if (
      typeof options.depthLimit !== "undefined" &&
      depth > options.depthLimit
    ) {
      setReplace(LIMIT_REPLACE_NODE, val, k, parent);
      return;
    }

    if (
      typeof options.edgesLimit !== "undefined" &&
      edgeIndex + 1 > options.edgesLimit
    ) {
      setReplace(LIMIT_REPLACE_NODE, val, k, parent);
      return;
    }

    stack.push(val);
    // Optimize for Arrays. Big arrays could kill the performance otherwise!
    if (Array.isArray(val)) {
      for (i = 0; i < val.length; i++) {
        deterministicDecirc(val[i], i, i, stack, val, depth, options);
      }
    } else {
      // Handle well-known types before Object.keys iteration
      val = serializeWellKnownTypes(val);

      // Create a temporary object in the required way
      var tmp = {};
      var keys = Object.keys(val).sort(compareFunction);
      for (i = 0; i < keys.length; i++) {
        var key = keys[i];
        deterministicDecirc(val[key], key, i, stack, val, depth, options);
        tmp[key] = val[key];
      }
      if (typeof parent !== "undefined") {
        arr.push([parent, k, val]);
        parent[k] = tmp;
      } else {
        return tmp;
      }
    }
    stack.pop();
  }
}

// wraps replacer function to handle values we couldn't replace
// and mark them as replaced value
function replaceGetterValues(replacer) {
  replacer =
    typeof replacer !== "undefined"
      ? replacer
      : function (k, v) {
          return v;
        };
  return function (key, val) {
    if (replacerStack.length > 0) {
      for (var i = 0; i < replacerStack.length; i++) {
        var part = replacerStack[i];
        if (part[1] === key && part[0] === val) {
          val = part[2];
          replacerStack.splice(i, 1);
          break;
        }
      }
    }
    return replacer.call(this, key, val);
  };
}
