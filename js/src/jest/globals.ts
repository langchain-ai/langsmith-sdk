import { AsyncLocalStorage } from "node:async_hooks";
import { Dataset, TracerSession, Example } from "../schemas.js";
import { Client, CreateProjectParams } from "../client.js";
import { getEnvironmentVariable } from "../utils/env.js";
import { isTracingEnabled } from "../env.js";
import { EvaluationResult } from "../evaluation/evaluator.js";
import { RunTree } from "../run_trees.js";

export type JestAsyncLocalStorageData = {
  enableTestTracking?: boolean;
  dataset?: Dataset;
  createdAt: string;
  projectConfig?: Partial<CreateProjectParams>;
  project?: TracerSession;
  setLoggedOutput?: (value: Record<string, unknown>) => void;
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
  return isTracingEnabled();
}

export const evaluatorLogFeedbackPromises = new Set();
export const syncExamplePromises = new Map();

export function _logTestFeedback(params: {
  exampleId?: string;
  feedback: EvaluationResult;
  context: JestAsyncLocalStorageData;
  runTree: RunTree;
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
}
