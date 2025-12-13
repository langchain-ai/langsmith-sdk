import { jest } from "@jest/globals";
import { RunTree } from "../run_trees.js";
import { traceable } from "../traceable.js";
import { getUuidVersion } from "../utils/_uuid.js";
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
