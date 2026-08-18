import codspeedPlugin from "@codspeed/vitest-plugin";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [codspeedPlugin()],
  test: {
    benchmark: {
      include: ["src/**/*.bench.ts"],
    },
    // Benchmarks must never reach the network: every client is built on a stub
    // fetch implementation, and tracing is disabled globally.
    env: {
      LANGSMITH_TRACING: "false",
      LANGSMITH_API_KEY: "fake-api-key",
      LANGSMITH_ENDPOINT: "https://api.smith.langchain.com",
    },
  },
});
