import { bench, describe } from "vitest";

import {
  estimateSerializedSize,
  serialize,
} from "../../utils/fast-safe-stringify/index.js";
import { hasLargeString } from "../../utils/serialize_worker.js";
import {
  chatPayload,
  largeStringPayload,
  structuralPayload,
  wellKnownTypesPayload,
} from "./payloads.js";

/**
 * Serialization is on the hot path of every traced run: inputs and outputs are
 * serialized before being queued, and the queue-size accounting calls the
 * estimator for each payload.
 */
describe("serialize", () => {
  const chat = chatPayload(200);
  const structural = structuralPayload(6, 4);
  const large = largeStringPayload(200_000);
  const wellKnown = wellKnownTypesPayload(200);

  bench("serialize chat payload", () => {
    serialize(chat);
  });

  bench("serialize structural payload", () => {
    serialize(structural);
  });

  bench("serialize large string payload", () => {
    serialize(large);
  });

  bench("serialize well-known types", () => {
    serialize(wellKnown);
  });
});

describe("estimateSerializedSize", () => {
  const chat = chatPayload(200);
  const structural = structuralPayload(6, 4);
  const large = largeStringPayload(200_000);

  bench("estimate chat payload", () => {
    estimateSerializedSize(chat);
  });

  bench("estimate structural payload", () => {
    estimateSerializedSize(structural);
  });

  bench("estimate large string payload", () => {
    estimateSerializedSize(large);
  });
});

describe("hasLargeString", () => {
  const structural = structuralPayload(6, 4);
  const large = largeStringPayload(200_000);

  bench("structural payload (no large string)", () => {
    hasLargeString(structural);
  });

  bench("large string payload", () => {
    for (let i = 0; i < 1_000; i += 1) {
      hasLargeString(large);
    }
  });
});
