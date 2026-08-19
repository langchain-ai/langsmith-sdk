/* eslint-disable @typescript-eslint/no-explicit-any */
import { Client } from "../../client.js";

/**
 * A `fetch` stand-in that resolves immediately, so benchmarks measure SDK work
 * only and never touch the network.
 */
export function mockFetch(): typeof fetch {
  return (async () =>
    ({
      ok: true,
      status: 200,
      statusText: "OK",
      text: async () => "",
      json: async () => ({}),
    }) as any) as typeof fetch;
}

export function benchClient(): Client {
  return new Client({
    apiKey: "MOCK",
    apiUrl: "http://localhost:1984",
    autoBatchTracing: false,
    callerOptions: { maxRetries: 0 },
    fetchImplementation: mockFetch(),
  });
}

/** A wide payload: many small homogeneous objects. */
export function largeArrayPayload(length: number): Record<string, unknown> {
  return {
    name: "Huge JSON",
    description: "A large JSON object used for benchmarking.",
    array: Array.from({ length }, (_, i) => ({
      index: i,
      data: `This is element number ${i}`,
      nested: { id: i, value: `Nested value for element ${i}` },
    })),
    metadata: {
      created_at: "2024-10-22T19:00:00Z",
      author: "benchmark",
      version: 1.0,
    },
  };
}

/** A payload dominated by a few very long strings (the worker-offload shape). */
export function largeStringPayload(length: number): Record<string, unknown> {
  const large = "a".repeat(length);
  return { key1: large, key2: large, key3: large, metadata: { version: 1 } };
}

/** A payload full of types that need the custom replacer. */
export function wellKnownTypesPayload(length: number): Record<string, unknown> {
  return {
    items: Array.from({ length }, (_, i) => ({
      map: new Map([
        ["key1", `value-${i}`],
        ["key2", `other-${i}`],
      ]),
      set: new Set([1, 2, 3, `hello-${i}`]),
      date: new Date(1620000000000 + i),
      big: BigInt(i),
      error: new Error(`boom ${i}`),
      regexp: /ab+c/g,
    })),
  };
}

/** A deeply nested object graph. */
export function nestedPayload(depth: number, width: number): unknown {
  const build = (level: number): unknown => {
    if (level === 0) {
      return { leaf: true, value: "x".repeat(32) };
    }
    const node: Record<string, unknown> = {};
    for (let i = 0; i < width; i += 1) {
      node[`key_${level}_${i}`] = build(level - 1);
    }
    return node;
  };
  return build(depth);
}
