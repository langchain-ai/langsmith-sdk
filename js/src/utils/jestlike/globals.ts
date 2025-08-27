import { AsyncLocalStorage } from "node:async_hooks";
import { Dataset, TracerSession, Example } from "../../schemas.js";
import { Client, CreateProjectParams } from "../../client.js";
import { getEnvironmentVariable } from "../env.js";
import { isTracingEnabled } from "../../env.js";
import { RunTree } from "../../run_trees.js";
import { SimpleEvaluationResult } from "./types.js";

export const DEFAULT_TEST_CLIENT = new Client();

export type TestWrapperAsyncLocalStorageData = {
  enableTestTracking?: boolean;
  dataset?: Dataset;
  createdAt: string;
  projectConfig?: Partial<CreateProjectParams>;
  project?: TracerSession;
  setLoggedOutput?: (value: Record<string, unknown>) => void;
  onFeedbackLogged?: (feedback: SimpleEvaluationResult) => void;
  currentExample?: Partial<Example> & { syncPromise?: Promise<Example> };
  client: Client;
  suiteUuid: string;
  suiteName: string;
  testRootRunTree?: RunTree;
  setupPromise?: Promise<void>;
};

export const testWrapperAsyncLocalStorageInstance =
  new AsyncLocalStorage<TestWrapperAsyncLocalStorageData>();

export function trackingEnabled(context: TestWrapperAsyncLocalStorageData) {
  if (typeof context.enableTestTracking === "boolean") {
    return context.enableTestTracking;
  }
  if (getEnvironmentVariable("LANGSMITH_TEST_TRACKING") === "false") {
    return false;
  }
  return isTracingEnabled();
}

export const evaluatorLogFeedbackPromises = new Set();
export const syncExamplePromises = new Map();

export function _logTestFeedback(params: {
  exampleId?: string;
  feedback: SimpleEvaluationResult;
  context: TestWrapperAsyncLocalStorageData;
  runTree?: RunTree;
  client: Client;
  sourceRunId?: string;
}) {
  const { exampleId, feedback, context, runTree, client, sourceRunId } = params;
  if (trackingEnabled(context)) {
    if (exampleId === undefined) {
      throw new Error(
        "Could not log feedback to LangSmith: missing example id. Please contact us for help."
      );
    }
    if (runTree === undefined) {
      throw new Error(
        "Could not log feedback to LangSmith: missing run information. Please contact us for help."
      );
    }
    evaluatorLogFeedbackPromises.add(
      (async () => {
        await syncExamplePromises.get(exampleId);
        await client?.logEvaluationFeedback(
          feedback,
          runTree,
          sourceRunId !== undefined
            ? { __run: { run_id: sourceRunId } }
            : undefined
        );
      })()
    );
  }
  context.onFeedbackLogged?.(feedback);
}
