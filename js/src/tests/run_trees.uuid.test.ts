import { RunTree } from "../run_trees.js";
import { traceable } from "../traceable.js";
import { getUuidVersion } from "../utils/_uuid.js";

function uuidV7Ms(uuidStr: string): number {
  // Remove dashes to parse
  const hex = uuidStr.replace(/-/g, "");
  // First 12 hex chars = 48 bits of Unix ms timestamp
  const tsHex = hex.slice(0, 12);
  return parseInt(tsHex, 16);
}

class FakeClient {
  public creates: any[] = [];
  public updates: any[] = [];

  async createRun(payload: any): Promise<void> {
    this.creates.push(payload);
  }

  async updateRun(_id: string, payload: any): Promise<void> {
    this.updates.push(payload);
  }
}

test("traceable produces UUIDv7 and start_time matches run id", async () => {
  const fixedMs = 1_700_000_123_456; // deterministic timestamp in ms
  const client = new FakeClient();

  const fn = traceable((x: number) => x + 1, {
    name: "traceable-v7",
    run_type: "chain",
    client,
    start_time: fixedMs,
    tracingEnabled: true,
  });

  const out = await fn(1);
  expect(out).toBe(2);
  // Ensure post and patch include run_type and start_time
  expect(client.creates.length).toBeGreaterThan(0);
  expect(client.creates[0].run_type).toBe("chain");
  expect(client.creates[0].start_time).toBeDefined();

  // patch happens after end
  expect(client.updates.length).toBeGreaterThan(0);
  expect(client.updates[0].run_type).toBe("chain");
  expect(client.updates[0].start_time).toBeDefined();

  // UUID version v7
  const createdId: string = client.creates[0].id;
  expect(getUuidVersion(createdId)).toBe(7);
  // start_time encoded in v7 should match provided ms
  expect(uuidV7Ms(createdId)).toBe(fixedMs);
});

test("RunTree default/regular behavior uses UUIDv7 and start_time matches id; post/patch include fields", async () => {
  const fixedMs = 1_700_111_222_333;
  const client = new FakeClient();

  const rt = new RunTree({
    name: "regular-v7",
    run_type: "tool",
    start_time: fixedMs,
    client: client as any,
    tracingEnabled: true,
  });

  await rt.postRun();
  await rt.patchRun();

  expect(client.creates.length).toBe(1);
  expect(client.creates[0].run_type).toBe("tool");
  expect(client.creates[0].start_time).toBeDefined();

  expect(client.updates.length).toBe(1);
  expect(client.updates[0].run_type).toBe("tool");
  expect(client.updates[0].start_time).toBeDefined();

  // v7 id and encoded time
  expect(getUuidVersion(rt.id)).toBe(7);
  expect(uuidV7Ms(rt.id)).toBe(fixedMs);
});
