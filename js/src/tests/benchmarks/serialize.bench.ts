/**
 * Benchmarks for payload serialization.
 *
 * Every traced run has its inputs and outputs serialized before it is queued,
 * and the queue-size accounting calls `estimateSerializedSize` / `hasLargeString`
 * on the same payloads. All three run inline in the user's process.
 */
import { bench, describe } from "vitest";

import {
  estimateSerializedSize,
  serialize,
} from "../../utils/fast-safe-stringify/index.js";
import { hasLargeString } from "../../utils/serialize_worker.js";
import {
  largeArrayPayload,
  largeStringPayload,
  nestedPayload,
  wellKnownTypesPayload,
} from "./utils.js";

const largeArray = largeArrayPayload(1_000);
const largeStrings = largeStringPayload(50_000);
const wellKnown = wellKnownTypesPayload(200);
const nested = nestedPayload(5, 5);

describe("serialize", () => {
  bench("large array payload", () => {
    serialize(largeArray);
  });

  bench("large string payload", () => {
    serialize(largeStrings);
  });

  bench("well-known types payload", () => {
    serialize(wellKnown);
  });

  bench("deeply nested payload", () => {
    serialize(nested);
  });

  bench("circular payload", () => {
    const circular: Record<string, unknown> = { ...largeArray };
    circular.self = circular;
    serialize(circular);
  });
});

describe("estimateSerializedSize", () => {
  bench("large array payload", () => {
    estimateSerializedSize(largeArray);
  });

  bench("deeply nested payload", () => {
    estimateSerializedSize(nested);
  });
});

describe("hasLargeString", () => {
  bench("large string payload", () => {
    hasLargeString(largeStrings);
  });

  bench("large array payload", () => {
    hasLargeString(largeArray);
  });
});
