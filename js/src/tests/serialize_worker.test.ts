/* eslint-disable no-process-env */
import { SerializeWorker } from "../utils/serialize_worker.js";
import { serialize } from "../utils/fast-safe-stringify/index.js";

describe("SerializeWorker", () => {
  let worker: SerializeWorker;

  beforeEach(() => {
    worker = new SerializeWorker();
  });

  afterEach(async () => {
    await worker.terminate();
  });

  async function serializeToText(payload: unknown): Promise<string> {
    const bytes = await worker.serialize(payload);
    if (bytes === null) {
      throw new Error("worker returned null; expected bytes");
    }
    return Buffer.from(bytes).toString("utf8");
  }

  test("serializes a plain object to bytes matching JSON.stringify", async () => {
    const payload = { a: 1, b: "two", c: [true, false, null] };
    expect(JSON.parse(await serializeToText(payload))).toEqual(payload);
  });

  test("normalizes Date, RegExp, Map, Set, bigint consistently with main-thread serialize", async () => {
    const payload = {
      date: new Date("2024-01-01T00:00:00.000Z"),
      regex: /foo/gi,
      map: new Map([
        ["x", 1],
        ["y", 2],
      ]),
      set: new Set(["a", "b"]),
      big: BigInt("9007199254740999"),
    };
    const parsed = JSON.parse(await serializeToText(payload));
    expect(parsed.date).toBe("2024-01-01T00:00:00.000Z");
    expect(parsed.regex).toBe("/foo/gi");
    expect(parsed.map).toEqual({ x: 1, y: 2 });
    expect(parsed.set).toEqual(["a", "b"]);
    expect(parsed.big).toBe("9007199254740999");
  });

  test("rejects on DataCloneError for unclonable values (functions)", async () => {
    const payload = { fn: () => 42 };
    await expect(worker.serialize(payload)).rejects.toThrow();
  });

  test("handles large base64-heavy payloads (shape matches real images)", async () => {
    const img = "x".repeat(500 * 1024);
    const payload = {
      messages: [
        {
          role: "user",
          content: [
            {
              type: "image_url",
              image_url: { url: `data:image/png;base64,${img}` },
            },
          ],
        },
      ],
    };
    const parsed = JSON.parse(await serializeToText(payload));
    expect(parsed.messages[0].content[0].image_url.url).toHaveLength(
      "data:image/png;base64,".length + img.length,
    );
  });

  test("tolerates circular references by replacing with [Circular]", async () => {
    const payload: Record<string, unknown> = { a: 1 };
    payload.self = payload;
    expect(await serializeToText(payload)).toContain("[Circular]");
  });

  test("produces byte-identical output to main-thread serialize for well-known types", async () => {
    // This test ensures the worker's inlined serialize logic stays in sync
    // with the main-thread implementation. If this fails, the worker source
    // in serialize_worker.ts needs to be updated to match.
    const payloads = [
      // Primitives and simple structures
      { a: 1, b: "two", c: [true, false, null] },
      // Well-known types
      {
        date: new Date("2024-01-01T00:00:00.000Z"),
        regex: /foo/gi,
        map: new Map([
          ["x", 1],
          ["y", 2],
        ]),
        set: new Set(["a", "b"]),
        big: BigInt("9007199254740999"),
      },
      // Error objects
      { err: new Error("test error") },
      // Nested structures
      {
        level1: {
          level2: {
            level3: { data: "deep" },
            arr: [1, 2, 3],
          },
        },
      },
      // Large string (triggers worker path in client)
      { big: "x".repeat(100_000) },
    ];

    for (const payload of payloads) {
      const workerBytes = await worker.serialize(payload);
      if (workerBytes === null) {
        // Worker unavailable in this environment; skip comparison
        continue;
      }
      const workerStr = Buffer.from(workerBytes).toString("utf8");
      const mainStr = Buffer.from(serialize(payload)).toString("utf8");
      expect(workerStr).toBe(mainStr);
    }
  });
});
