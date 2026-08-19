import { bench, describe } from "vitest";

import { Client } from "../../client.js";
import { traceable } from "../../traceable.js";
import { chatPayload } from "./payloads.js";

/**
 * `traceable` wraps user code, so its overhead is paid on every call of an
 * instrumented function. The client uses a stub fetch implementation, so the
 * measurement only covers the SDK work (context propagation, run tree creation
 * and serialization).
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

describe("traceable", () => {
  const client = benchClient();
  const inputs = chatPayload(4);

  const leaf = traceable(async (value: number) => value + 1, {
    name: "leaf",
    client,
    tracingEnabled: true,
  });

  const parent = traceable(
    async (value: number) => {
      let total = 0;
      for (let i = 0; i < 5; i += 1) {
        total += await leaf(value + i);
      }
      return total;
    },
    { name: "parent", client, tracingEnabled: true },
  );

  const withPayload = traceable(
    async (payload: Record<string, unknown>) => ({
      choices: Object.keys(payload).length,
    }),
    { name: "with_payload", client, tracingEnabled: true, run_type: "llm" },
  );

  bench("50 flat traced calls", async () => {
    for (let i = 0; i < 50; i += 1) {
      await leaf(i);
    }
  });

  bench("10 nested traced calls", async () => {
    for (let i = 0; i < 10; i += 1) {
      await parent(i);
    }
  });

  bench("20 traced calls with chat payloads", async () => {
    for (let i = 0; i < 20; i += 1) {
      await withPayload(inputs);
    }
  });
});
