import { AsyncLocalStorage } from "node:async_hooks";
import { Dataset, TracerSession, Example } from "../schemas.js";
import { Client, CreateProjectParams } from "../client.js";
import { getEnvironmentVariable } from "../utils/env.js";

export type JestAsyncLocalStorageData = {
  enableTestTracking?: boolean;
  dataset?: Dataset;
  // examples?: (Example & { inputHash: string; outputHash: string })[];
  createdAt: string;
  projectConfig?: Partial<CreateProjectParams>;
  project?: TracerSession;
  currentExample?: Partial<Example> & { syncPromise?: Promise<Example> };
  client: Client;
  suiteUuid: string;
  suiteName: string;
};

export const jestAsyncLocalStorageInstance =
  new AsyncLocalStorage<JestAsyncLocalStorageData>();

export function trackingEnabled(context: JestAsyncLocalStorageData) {
  if (typeof context.enableTestTracking === "boolean") {
    return context.enableTestTracking;
  }
  if (getEnvironmentVariable("LANGSMITH_TEST_TRACKING") === "false") {
    return false;
  }
  return getEnvironmentVariable("LANGSMITH_TRACING_V2") === "true";
}
