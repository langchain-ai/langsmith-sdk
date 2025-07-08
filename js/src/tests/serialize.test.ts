/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, expect } from "@jest/globals";
import { serialize } from "../utils/fast-safe-stringify/index.js";

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
