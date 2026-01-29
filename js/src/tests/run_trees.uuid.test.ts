import { jest } from "@jest/globals";
import { v4 as uuidv4, v7 as uuidv7 } from "uuid";
import { RunTree } from "../run_trees.js";
import { traceable } from "../traceable.js";
import {
  getUuidVersion,
  nonCryptographicUuid7Deterministic,
} from "../utils/_uuid.js";
import { mockClient } from "./utils/mock_client.js";

function uuidV7Ms(uuidStr: string): number {
  // Remove dashes to parse
  const hex = uuidStr.replace(/-/g, "");
  // First 12 hex chars = 48 bits of Unix ms timestamp
  const tsHex = hex.slice(0, 12);
  return parseInt(tsHex, 16);
}

test("traceable produces UUIDv7 and start_time matches run id", async () => {
  const fixedMs = 1_700_000_123_456; // deterministic timestamp in ms
  const { client } = mockClient();
  const createSpy = jest.spyOn(client, "createRun");
  const updateSpy = jest.spyOn(client, "updateRun");

  const fn = traceable((x: number) => x + 1, {
    name: "traceable-v7",
    run_type: "chain",
    client,
    start_time: fixedMs,
    tracingEnabled: true,
  });

  const out = await fn(1);
  expect(out).toBe(2);

  await client.awaitPendingTraceBatches();

  // Ensure post and patch include run_type and start_time
  expect(createSpy).toHaveBeenCalled();
  const createdArg = createSpy.mock.calls[0][0];
  expect(createdArg.run_type).toBe("chain");
  expect(createdArg.start_time).toBeDefined();

  // patch happens after end
  expect(updateSpy).toHaveBeenCalled();
  const updatedArg = updateSpy.mock.calls[0][1];
  expect(updatedArg.run_type).toBe("chain");
  expect(updatedArg.start_time).toBeDefined();

  // UUID version v7
  const createdId: string = createdArg.id!;
  expect(getUuidVersion(createdId)).toBe(7);
  // start_time encoded in v7 should match provided ms
  expect(uuidV7Ms(createdId)).toBe(fixedMs);
});

test("RunTree default/regular behavior uses UUIDv7 and start_time matches id; post/patch include fields", async () => {
  const fixedMs = 1_700_111_222_333;
  const { client } = mockClient();
  const createSpy2 = jest.spyOn(client, "createRun");
  const updateSpy2 = jest.spyOn(client, "updateRun");

  const rt = new RunTree({
    name: "regular-v7",
    run_type: "tool",
    start_time: fixedMs,
    client,
    tracingEnabled: true,
  });

  await rt.postRun();
  await rt.patchRun();

  expect(createSpy2).toHaveBeenCalledTimes(1);
  const createdArg2 = createSpy2.mock.calls[0][0];
  expect(createdArg2.run_type).toBe("tool");
  expect(createdArg2.start_time).toBeDefined();

  expect(updateSpy2).toHaveBeenCalledTimes(1);
  const updatedArg2 = updateSpy2.mock.calls[0][1];
  expect(updatedArg2.run_type).toBe("tool");
  expect(updatedArg2.start_time).toBeDefined();

  // v7 id and encoded time
  expect(getUuidVersion(rt.id)).toBe(7);
  expect(uuidV7Ms(rt.id)).toBe(fixedMs);
});

test("nonCryptographicUuid7Deterministic produces valid, deterministic UUID7s", () => {
  const original = uuidv7();
  const key = "replica-project";

  const d1 = nonCryptographicUuid7Deterministic(original, key);
  const d2 = nonCryptographicUuid7Deterministic(original, key);

  // Valid UUID7
  expect(getUuidVersion(d1)).toBe(7);

  expect(d1).toBe(d2);

  // Different inputs -> different outputs
  expect(nonCryptographicUuid7Deterministic(original, "other-key")).not.toBe(
    d1
  );
  expect(nonCryptographicUuid7Deterministic(uuidv7(), key)).not.toBe(d1);
});

test("nonCryptographicUuid7Deterministic timestamp handling", async () => {
  // UUID7 input: timestamp preserved
  const originalV7 = uuidv7();
  const derivedV7 = nonCryptographicUuid7Deterministic(originalV7, "key");
  expect(uuidV7Ms(derivedV7)).toBe(uuidV7Ms(originalV7));

  // UUID4 input: gets fresh timestamp
  const beforeMs = Date.now();
  const derivedV4 = nonCryptographicUuid7Deterministic(uuidv4(), "key");
  await new Promise((resolve) => setTimeout(resolve, 10));
  const afterMs = Date.now();

  expect(getUuidVersion(derivedV4)).toBe(7);
  expect(uuidV7Ms(derivedV4)).toBeGreaterThanOrEqual(beforeMs);
  expect(uuidV7Ms(derivedV4)).toBeLessThanOrEqual(afterMs);
});

test("nonCryptographicUuid7Deterministic produces expected values", () => {
  // Test with hard-coded values to ensure compatibility across implementations
  // These values should match the Python implementation exactly

  const testCases = [
    {
      input: "019c0711-e1aa-7223-bf21-12119afe80f7",
      key: "other-key",
      expected: "019c0711-e1aa-7614-833c-500ba8e2e686",
    },
    {
      input: "019c0711-e1aa-7223-bf21-12119afe80f7",
      key: "replica-project",
      expected: "019c0711-e1aa-7817-8301-943c0df9a3cd",
    },
    {
      input: "01900000-0000-7000-8000-000000000000",
      key: "test",
      expected: "01900000-0000-7132-8131-f80e352488a3",
    },
  ];

  for (const { input, key, expected } of testCases) {
    const result = nonCryptographicUuid7Deterministic(input, key);
    expect(result).toBe(expected);
    expect(getUuidVersion(result)).toBe(7);
  }
});

test("nonCryptographicUuid7Deterministic is fast", async () => {
  const originalUuids = [];
  for (let i = 0; i < 100000; i++) {
    originalUuids.push(uuidv7());
  }
  const finalUuids = [];
  const startTime = new Date();
  for (let i = 0; i < originalUuids.length; i++) {
    finalUuids.push(
      nonCryptographicUuid7Deterministic(originalUuids[i], "key")
    );
  }
  const endTime = new Date();
  const duration = endTime.getTime() - startTime.getTime();
  expect(duration).toBeLessThan(10000); // 10k UUIDs/second to be conservative for CI, may be much higher

  // Check all UUIDs are valid v7
  for (let i = 0; i < finalUuids.length; i++) {
    expect(getUuidVersion(finalUuids[i])).toBe(7);
  }

  // Check uniqueness - different input UUIDs should produce different outputs
  const uniqueOutputs = new Set(finalUuids); // First 1000 should all be unique
  expect(uniqueOutputs.size).toBe(100000);
});
