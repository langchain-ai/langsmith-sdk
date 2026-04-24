/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, expect } from "@jest/globals";
import mongoose from "mongoose";
import {
  serialize,
  estimateSerializedSize,
} from "../utils/fast-safe-stringify/index.js";
import { hasLargeString } from "../utils/serialize_worker.js";
import {
  HumanMessage,
  SystemMessage,
  AIMessage,
} from "@langchain/core/messages";

describe("serializeWellKnownTypes", () => {
  it("should handle Map objects", () => {
    const map = new Map([
      ["key1", "value1"],
      ["key2", "value2"],
    ]);
    const obj = { testMap: map };

    const result = serialize(obj);
    const parsed = JSON.parse(new TextDecoder().decode(result));

    expect(parsed.testMap).toEqual({ key1: "value1", key2: "value2" });
  });

  it("should handle Set objects", () => {
    const set = new Set([1, 2, 3, "hello"]);
    const obj = { testSet: set };

    const result = serialize(obj);
    const parsed = JSON.parse(new TextDecoder().decode(result));

    expect(parsed.testSet).toEqual([1, 2, 3, "hello"]);
  });

  it("should handle Date objects", () => {
    const date = new Date("2023-01-01T00:00:00.000Z");
    const obj = { testDate: date };

    const result = serialize(obj);
    const parsed = JSON.parse(new TextDecoder().decode(result));

    expect(parsed.testDate).toBe("2023-01-01T00:00:00.000Z");
  });

  it("should handle RegExp objects", () => {
    const regex = /test.*pattern/gi;
    const obj = { testRegex: regex };

    const result = serialize(obj);
    const parsed = JSON.parse(new TextDecoder().decode(result));

    expect(parsed.testRegex).toBe("/test.*pattern/gi");
  });

  it("should handle Error objects", () => {
    const error = new Error("Test error message");
    error.name = "TestError";
    const obj = { testError: error };

    const result = serialize(obj);
    const parsed = JSON.parse(new TextDecoder().decode(result));

    expect(parsed.testError).toEqual({
      name: "TestError",
      message: "Test error message",
    });
    // Should not include stack trace for security
    expect(parsed.testError.stack).toBeUndefined();
  });

  it("should handle bigint values", () => {
    const obj = { testBigint: BigInt(123456789012345678901234567890n) };

    const result = serialize(obj);
    const parsed = JSON.parse(new TextDecoder().decode(result));

    expect(parsed.testBigint).toBe("123456789012345678901234567890");
  });

  it("should handle nested well-known types", () => {
    const obj = {
      level1: {
        map: new Map([["nested", "value"]]),
        set: new Set([1, 2]),
        date: new Date("2023-01-01T00:00:00.000Z"),
        error: new Error("Nested error"),
        regex: /nested/g,
        bigint: BigInt(123),
      },
    };

    const result = serialize(obj);
    const parsed = JSON.parse(new TextDecoder().decode(result));

    expect(parsed.level1.map).toEqual({ nested: "value" });
    expect(parsed.level1.set).toEqual([1, 2]);
    expect(parsed.level1.date).toBe("2023-01-01T00:00:00.000Z");
    expect(parsed.level1.error).toEqual({
      name: "Error",
      message: "Nested error",
    });
    expect(parsed.level1.regex).toBe("/nested/g");
    expect(parsed.level1.bigint).toBe("123");
  });

  it("should handle mixed arrays with well-known types", () => {
    const obj = {
      mixedArray: [
        new Map([["key", "value"]]),
        new Set([1, 2, 3]),
        new Date("2023-01-01T00:00:00.000Z"),
        new Error("Array error"),
        /pattern/i,
        BigInt(456),
        "regular string",
        42,
      ],
    };

    const result = serialize(obj);
    const parsed = JSON.parse(new TextDecoder().decode(result));

    expect(parsed.mixedArray[0]).toEqual({ key: "value" });
    expect(parsed.mixedArray[1]).toEqual([1, 2, 3]);
    expect(parsed.mixedArray[2]).toBe("2023-01-01T00:00:00.000Z");
    expect(parsed.mixedArray[3]).toEqual({
      name: "Error",
      message: "Array error",
    });
    expect(parsed.mixedArray[4]).toBe("/pattern/i");
    expect(parsed.mixedArray[5]).toBe("456");
    expect(parsed.mixedArray[6]).toBe("regular string");
    expect(parsed.mixedArray[7]).toBe(42);
  });

  it("should not serialize functions", () => {
    const obj = {
      fn: function testFunction() {
        return "test";
      },
      arrow: () => "arrow",
      regularProp: "value",
    };

    const result = serialize(obj);
    const parsed = JSON.parse(new TextDecoder().decode(result));

    // Functions should remain as-is and be filtered out by JSON.stringify
    expect(parsed.fn).toBeUndefined();
    expect(parsed.arrow).toBeUndefined();
    expect(parsed.regularProp).toBe("value");
  });

  it("should not serialize symbols", () => {
    const sym = Symbol("test");
    const obj = {
      [sym]: "symbol value",
      regularProp: "value",
    };

    const result = serialize(obj);
    const parsed = JSON.parse(new TextDecoder().decode(result));

    // Symbols should be filtered out by JSON.stringify
    expect(Object.getOwnPropertySymbols(parsed)).toHaveLength(0);
    expect(parsed.regularProp).toBe("value");
  });

  it("should handle complex objects without modification", () => {
    class CustomClass {
      constructor(public value: string) {}
    }

    const obj = {
      custom: new CustomClass("test"),
      regularProp: "value",
    };

    const result = serialize(obj);
    const parsed = JSON.parse(new TextDecoder().decode(result));

    // Custom classes should remain as-is (just their enumerable properties)
    expect(parsed.custom).toEqual({ value: "test" });
    expect(parsed.regularProp).toBe("value");
  });

  it("should handle circular references", () => {
    const obj: any = { prop: "value" };
    obj.circular = obj;

    const result = serialize(obj);
    const parsed = JSON.parse(new TextDecoder().decode(result));

    expect(parsed.prop).toBe("value");
    expect(parsed.circular).toEqual({ result: "[Circular]" });
  });
});

describe("estimateSerializedSize", () => {
  // Helper: estimate must be within a tolerance of the real size.
  // Direction matters: for soft limits on the ingest queue, over-estimating
  // is safer than under-estimating (we may flush slightly earlier than we
  // would otherwise). We allow a wide band here because the point of the
  // estimator is speed, not precision.
  function expectClose(
    value: unknown,
    opts: { minRatio?: number; maxRatio?: number } = {}
  ) {
    const { minRatio = 0.9, maxRatio = 3.0 } = opts;
    const real = serialize(value).length;
    const estimate = estimateSerializedSize(value).size;
    const ratio = estimate / real;
    if (ratio < minRatio || ratio > maxRatio) {
      throw new Error(
        `estimate out of range: real=${real}, estimate=${estimate}, ratio=${ratio.toFixed(
          3
        )} (expected between ${minRatio} and ${maxRatio})`
      );
    }
  }

  it("handles shared references without treating them as circular", () => {
    // The repeated `shared` object is serialized twice by JSON.stringify,
    // so the estimate should count it twice.
    const shared = { text: "x".repeat(1000) };
    const payload = { a: shared, b: shared };
    expectClose(payload, { minRatio: 0.95, maxRatio: 1.05 });
  });

  it("handles deeply shared subtrees (system prompt pattern)", () => {
    const systemPrompt = "You are a helpful assistant. ".repeat(100);
    const payload = {
      messages: [
        { role: "system", content: systemPrompt },
        { role: "user", content: "hi" },
      ],
      metadata: { systemPrompt },
    };
    expectClose(payload, { minRatio: 0.95, maxRatio: 1.05 });
  });

  it("counts Buffer by its JSON representation, not a constant", () => {
    const buf = Buffer.alloc(10000, "x");
    expectClose(buf, { minRatio: 0.95, maxRatio: 1.1 });
  });

  it("prefers Buffer's dedicated sizing path over generic toJSON duck-typing", () => {
    const buf = Buffer.alloc(32, 7);
    const originalToJSON = buf.toJSON.bind(buf);
    let calls = 0;
    buf.toJSON = (() => {
      calls += 1;
      return originalToJSON();
    }) as typeof buf.toJSON;

    const estimate = estimateSerializedSize(buf).size;
    expect(estimate).toBeGreaterThan(0);
    expect(calls).toBe(0);
  });

  it("counts typed arrays by their (expensive) JSON representation", () => {
    // Uint8Array stringifies as {"0":v,"1":v,...}, not [v,v,...].
    const arr = new Uint8Array(1000).fill(5);
    expectClose(arr, { minRatio: 0.9, maxRatio: 2.0 });
  });

  it("counts ArrayBuffer as an empty object", () => {
    // ArrayBuffer itself has no enumerable properties -> "{}"
    const buf = new ArrayBuffer(1000);
    expectClose(buf, { minRatio: 0.5, maxRatio: 1.5 });
  });

  it("invokes toJSON for custom types", () => {
    class Money {
      amount: number;
      constructor(n: number) {
        this.amount = n;
      }
      toJSON() {
        return { amount: this.amount, currency: "USD" };
      }
    }
    // Small object -> allow looser ratio for constant overheads.
    expectClose(new Money(42), { minRatio: 0.5, maxRatio: 3.0 });
  });

  it("handles real mongoose documents via toJSON", () => {
    // Mongoose documents carry extensive internal state ($__, $isNew,
    // prototype methods, getters, etc.) but expose toJSON() for
    // serialization. The estimator must invoke toJSON() to match
    // JSON.stringify semantics.
    const UserSchema = new mongoose.Schema({
      name: String,
      age: Number,
      tags: [String],
      nested: { city: String, active: Boolean },
    });
    const User =
      mongoose.models.EstUser ?? mongoose.model("EstUser", UserSchema);

    const doc = new User({
      name: "Alice",
      age: 30,
      tags: ["admin", "beta"],
      nested: { city: "SF", active: true },
    });

    expectClose(doc, { minRatio: 0.95, maxRatio: 1.1 });
  });

  it("handles real mongoose documents with nested subdocuments and arrays", () => {
    const PostSchema = new mongoose.Schema({
      title: String,
      body: String,
      comments: [{ text: String, votes: Number }],
    });
    const Post =
      mongoose.models.EstPost ?? mongoose.model("EstPost", PostSchema);

    const post = new Post({
      title: "Hello",
      body: "x".repeat(500),
      comments: [
        { text: "nice", votes: 3 },
        { text: "ok", votes: 1 },
      ],
    });

    expectClose(post, { minRatio: 0.95, maxRatio: 1.1 });
  });

  it("falls back to exact serialization if estimation throws", () => {
    const originalKeys = Object.keys;
    try {
      // Simulate an unexpected edge case inside the estimator traversal.
      Object.keys = ((obj: object) => {
        if ((obj as any).__explode) {
          throw new Error("boom");
        }
        return originalKeys(obj);
      }) as typeof Object.keys;

      const payload = {
        ok: true,
        nested: { __explode: true, value: "x".repeat(100) },
      };

      expect(estimateSerializedSize(payload).size).toBe(
        serialize(payload).length
      );
    } finally {
      Object.keys = originalKeys;
    }
  });

  it("falls back to exact serialization if byte-length calculation throws", () => {
    if (typeof Buffer === "undefined") {
      return;
    }

    const originalByteLength = Buffer.byteLength;
    try {
      Buffer.byteLength = ((str: string, encoding?: BufferEncoding) => {
        if (str.includes("explode-byte-length")) {
          throw new Error("boom");
        }
        return originalByteLength(str, encoding);
      }) as typeof Buffer.byteLength;

      const payload = { text: "explode-byte-length" };
      expect(estimateSerializedSize(payload).size).toBe(
        serialize(payload).length
      );
    } finally {
      Buffer.byteLength = originalByteLength;
    }
  });

  it("counts UTF-8 byte length for non-ASCII strings", () => {
    // Chinese: each character is 3 UTF-8 bytes but 1 code unit.
    expectClose({ text: "你好世界".repeat(100) });
    // Emoji outside BMP: 4 UTF-8 bytes, 2 code units.
    expectClose({ text: "🎉".repeat(100) });
  });

  it("detects real cycles but not shared siblings", () => {
    const shared = { x: 1 };
    const cyc: any = { shared, other: shared };
    cyc.self = cyc;
    const real = serialize(cyc).length;
    const estimate = estimateSerializedSize(cyc).size;
    // Should be finite (no infinite recursion), and in the ballpark.
    expect(Number.isFinite(estimate)).toBe(true);
    expect(estimate).toBeGreaterThan(0);
    // Cycle handling uses a placeholder; we just want sanity.
    expect(estimate / real).toBeGreaterThan(0.5);
    expect(estimate / real).toBeLessThan(3.0);
  });

  it("handles typical traced-run payloads accurately", () => {
    const runish = {
      id: "abc-123",
      name: "test_run",
      run_type: "llm",
      inputs: {
        messages: [{ role: "user", content: "hello " + "x".repeat(1000) }],
      },
      extra: { metadata: { model: "gpt-4", temperature: 0.7 } },
    };
    expectClose(runish, { minRatio: 0.95, maxRatio: 1.1 });
  });

  it("handles well-known types (Map, Set, Date, RegExp, Error)", () => {
    expectClose(
      new Map([
        ["a", 1],
        ["b", 2],
      ]),
      {
        minRatio: 0.5,
        maxRatio: 2.0,
      }
    );
    expectClose(new Set([1, 2, 3, "hi"]), { minRatio: 0.5, maxRatio: 3.0 });
    expectClose(new Date(), { minRatio: 0.9, maxRatio: 1.2 });
    expectClose(/foo/g, { minRatio: 0.5, maxRatio: 2.0 });
    expectClose(new Error("boom"), { minRatio: 0.5, maxRatio: 3.0 });
  });

  it("does not throw on BigInt", () => {
    expect(() =>
      estimateSerializedSize({ big: 123456789012345678901234567890n })
    ).not.toThrow();
  });

  it("treats undefined/function/symbol as dropped in object properties", () => {
    const v = { a: 1, b: undefined, c: () => 1, d: Symbol(), e: 2 };
    const real = serialize(v).length;
    const estimate = estimateSerializedSize(v).size;
    // Dropped keys shouldn't blow up the estimate significantly.
    expect(estimate).toBeLessThan(real * 6);
  });

  it("treats undefined/function/symbol as null inside arrays", () => {
    // JSON.stringify renders these as "null" in arrays.
    const v = [1, undefined, () => 1, Symbol(), 2];
    const real = serialize(v).length;
    const estimate = estimateSerializedSize(v).size;
    expect(estimate).toBeGreaterThan(real * 0.5);
  });

  it("reports the UTF-8 byte length of the longest string encountered", () => {
    const short = "hi";
    const long = "x".repeat(5000);
    const payload = { a: short, nested: { b: long, c: "medium".repeat(100) } };
    const { maxStringLen } = estimateSerializedSize(payload);
    expect(maxStringLen).toBe(5000);
  });

  it("tracks maxStringLen across arrays and well-known containers", () => {
    const big = "y".repeat(2048);
    const payload = {
      list: ["a", big, "b"],
      map: new Map([["k", big]]),
      set: new Set(["short", big]),
    };
    expect(estimateSerializedSize(payload).maxStringLen).toBe(2048);
  });

  it("reports zero maxStringLen for payloads with no strings", () => {
    expect(
      estimateSerializedSize({ a: 1, b: [2, 3], c: true }).maxStringLen
    ).toBe(0);
    expect(estimateSerializedSize(null).maxStringLen).toBe(0);
    expect(estimateSerializedSize(42).maxStringLen).toBe(0);
  });

  it("handles LangChain message objects", () => {
    // LangChain message classes have a toJSON() method that returns
    // a serializable representation. The estimator must invoke it.
    const messages = [
      new SystemMessage("You are a helpful assistant."),
      new HumanMessage("What is the capital of France?"),
      new AIMessage("The capital of France is Paris."),
    ];

    expectClose({ messages }, { minRatio: 0.95, maxRatio: 1.1 });
  });

  it("handles LangChain message objects with complex content", () => {
    // Multi-modal message with text and image
    const message = new HumanMessage({
      content: [
        { type: "text", text: "What's in this image?" },
        {
          type: "image_url",
          image_url: { url: "data:image/png;base64," + "x".repeat(1000) },
        },
      ],
    });

    expectClose({ message }, { minRatio: 0.95, maxRatio: 1.1 });
  });
});

describe("hasLargeString", () => {
  it("returns false for null / undefined / primitives below threshold", () => {
    expect(hasLargeString(null)).toBe(false);
    expect(hasLargeString(undefined)).toBe(false);
    expect(hasLargeString(0)).toBe(false);
    expect(hasLargeString("hi")).toBe(false);
    expect(hasLargeString(true)).toBe(false);
  });

  it("returns true for a single string at or above threshold", () => {
    expect(hasLargeString("x".repeat(100), 100)).toBe(true);
    expect(hasLargeString("x".repeat(99), 100)).toBe(false);
  });

  it("finds a large string nested deep inside a payload", () => {
    const payload = {
      a: 1,
      b: [{ c: "short" }, { d: { e: { f: "y".repeat(200) } } }],
    };
    expect(hasLargeString(payload, 100)).toBe(true);
    expect(hasLargeString(payload, 1000)).toBe(false);
  });

  it("finds a large string inside Map and Set values", () => {
    const big = "z".repeat(500);
    expect(hasLargeString(new Map([["k", big]]), 100)).toBe(true);
    expect(hasLargeString(new Set([big]), 100)).toBe(true);
  });

  it("short-circuits before visiting the entire graph", () => {
    // Put the large string at the front; if we didn't short-circuit, we
    // would visit many nodes after it. With short-circuit we should find
    // it in O(1) nodes regardless of the rest of the graph.
    const big = "a".repeat(200);
    const huge = Array.from({ length: 100_000 }, (_, i) => ({ i, v: "x" }));
    const payload = { first: big, rest: huge };
    // Budget of 5 is more than enough to reach `first` but far too small
    // to scan `rest`. If short-circuit works, we should still return true.
    expect(hasLargeString(payload, 100, 5)).toBe(true);
  });

  it("respects the node budget and returns false when exhausted", () => {
    // Build a wide payload of small strings; no string exceeds threshold.
    const wide: Record<string, string> = {};
    for (let i = 0; i < 1000; i++) wide[`k${i}`] = "tiny";
    // With a small budget and nothing large to find, we bail out early.
    expect(hasLargeString(wide, 100, 50)).toBe(false);
    // With a generous budget we still return false (correctly).
    expect(hasLargeString(wide, 100, 10_000)).toBe(false);
  });

  it("handles cycles without infinite looping", () => {
    const a: any = { name: "a" };
    const b: any = { name: "b", other: a };
    a.other = b;
    expect(() => hasLargeString(a, 100)).not.toThrow();
    expect(hasLargeString(a, 100)).toBe(false);
    b.big = "q".repeat(200);
    expect(hasLargeString(a, 100)).toBe(true);
  });

  it("does not iterate into opaque binary containers", () => {
    // A Buffer's .toString() is a huge string but its enumerable own
    // properties are few; we should not treat its bytes as a string.
    const buf = Buffer.alloc(200_000, "x");
    expect(hasLargeString(buf, 100_000)).toBe(false);
    expect(hasLargeString(new Uint8Array(200_000), 100_000)).toBe(false);
    expect(hasLargeString(new ArrayBuffer(200_000), 100_000)).toBe(false);
  });

  it("skips Date / RegExp / Error without inspection", () => {
    expect(hasLargeString(new Date(), 10)).toBe(false);
    expect(hasLargeString(/foo/, 10)).toBe(false);
    expect(hasLargeString(new Error("boom"), 10)).toBe(false);
  });
});
