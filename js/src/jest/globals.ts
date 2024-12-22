import { AsyncLocalStorage } from "node:async_hooks";
import { Dataset, TracerSession, Example } from "../schemas.js";
import { Client } from "../client.js";
import { getEnvironmentVariable } from "../utils/env.js";

export const jestAsyncLocalStorageInstance = new AsyncLocalStorage<{
  dataset?: Dataset;
  examples?: (Example & { inputHash: string; outputHash: string })[];
  createdAt: string;
  project?: TracerSession;
  currentExample?: Partial<Example>;
  client: Client;
  suiteUuid: string;
  suiteName: string;
}>();

export function trackingEnabled() {
  return getEnvironmentVariable("LANGSMITH_TEST_TRACKING") === "true";
}
