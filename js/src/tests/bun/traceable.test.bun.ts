// @ts-expect-error Bun types are not imported due to conflicts with Node types
import { test, expect } from "bun:test";
import { traceable } from "../../traceable.js";
import { Client } from "../../client.js";
import { waitUntilRunFound } from "../utils.js";
import { v7 as uuidv7 } from "uuid";

test("Simple Bun tracing integration test", async () => {
  const client = new Client();
  const runId = uuidv7();

  await traceable(
    async (input: { text: string }) => {
      return { out: input.text };
    },
    {
      name: "bun_tracing_test",
      client,
      id: runId,
    }
  )({ text: "Hello world" });

  // Wait for the run to be found in the backend
  await waitUntilRunFound(client, runId, true, 90_000);

  const storedRun = await client.readRun(runId);
  expect(storedRun.id).toEqual(runId);
  expect(storedRun.name).toEqual("bun_tracing_test");
  expect(storedRun.inputs).toEqual({ text: "Hello world" });
  expect(storedRun.outputs).toEqual({ out: "Hello world" });
}, 90_000);
