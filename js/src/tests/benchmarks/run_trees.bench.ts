import { bench, describe } from "vitest";

import { Client } from "../../client.js";
import { convertToDottedOrderFormat, RunTree } from "../../run_trees.js";
import { chatPayload } from "./payloads.js";

/**
 * `RunTree` is the object every tracing integration builds. These benchmarks
 * cover construction, child creation and header propagation. No request ever
 * leaves the process: the client is built on a stub fetch implementation.
 */
function benchClient(): Client {
  return new Client({
    apiKey: "fake-api-key",
    apiUrl: "https://api.smith.langchain.com",
    autoBatchTracing: false,
    fetchImplementation: async () =>
      new Response("", {
        status: 202,
        headers: { "content-type": "text/plain" },
      }),
  });
}

describe("RunTree", () => {
  const client = benchClient();
  const inputs = chatPayload(4);
  const outputs = {
    choices: [{ message: { role: "assistant", content: "ok" } }],
  };

  bench("create 200 run trees", () => {
    for (let i = 0; i < 200; i += 1) {
      new RunTree({ name: `run_${i}`, client, tracingEnabled: true });
    }
  });

  bench("create a tree with 50 children", async () => {
    const parent = new RunTree({
      name: "chain",
      run_type: "chain",
      inputs,
      client,
      tracingEnabled: true,
      extra: { metadata: { ls_model_name: "gpt-4o-mini" } },
    });
    for (let i = 0; i < 50; i += 1) {
      const child = parent.createChild({
        name: `llm_${i}`,
        run_type: "llm",
        inputs,
      });
      await child.end(outputs);
    }
    await parent.end(outputs);
  });

  bench("serialize a run tree to a run create payload", async () => {
    const parent = new RunTree({
      name: "chain",
      run_type: "chain",
      inputs,
      client,
      tracingEnabled: true,
    });
    for (let i = 0; i < 20; i += 1) {
      const child = parent.createChild({
        name: `llm_${i}`,
        run_type: "llm",
        inputs,
      });
      await child.end(outputs);
    }
    await parent.end(outputs);
    parent.toJSON();
  });

  bench("propagate tracing headers", () => {
    const parent = new RunTree({
      name: "parent",
      client,
      tracingEnabled: true,
    });
    const child = parent.createChild({ name: "child", run_type: "llm" });
    for (let i = 0; i < 200; i += 1) {
      child.toHeaders();
    }
  });

  bench("convertToDottedOrderFormat", () => {
    const now = Date.now();
    for (let i = 0; i < 500; i += 1) {
      convertToDottedOrderFormat(now + i, `${i}`);
    }
  });
});
