import { jest, expect, it } from "@jest/globals";
import { env } from "node:process";
import { SandboxClient } from "../sandbox/client.js";

const cases = [
  "https://ls.example.com",
  "https://eu.api.smith.langchain.com",
  "https://ls.example.com/prefix",
].flatMap((host) =>
  ["", "/", "/api", "/api/", "/api/v1", "/api/v1/"].flatMap((suffix) =>
    [false, true].map((explicit) => ({ host, suffix, explicit })),
  ),
);

it.each(cases)(
  "normalizes sandbox requests: %p",
  async ({ host, suffix, explicit }) => {
    const previous = env.LANGSMITH_ENDPOINT;
    const originalFetch = globalThis.fetch;
    const fetch = jest.fn<typeof globalThis.fetch>().mockImplementation(
      async () =>
        new Response(JSON.stringify({ sandboxes: [], registries: [] }), {
          headers: { "Content-Type": "application/json" },
        }),
    );
    globalThis.fetch = fetch;
    env.LANGSMITH_ENDPOINT = host + suffix;
    try {
      const client = new SandboxClient({
        apiKey: "test",
        ...(explicit ? { apiEndpoint: `${host}/api/v2/sandboxes/` } : {}),
      });
      await client.listSandboxes();
      await client.registries.list();
      expect(fetch.mock.calls.map(([url]) => String(url))).toEqual([
        `${host}/api/v2/sandboxes/boxes`,
        `${host}/api/v2/sandboxes/registries`,
      ]);
    } finally {
      globalThis.fetch = originalFetch;
      if (previous === undefined) delete env.LANGSMITH_ENDPOINT;
      else env.LANGSMITH_ENDPOINT = previous;
    }
  },
);
