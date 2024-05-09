/* eslint-disable import/no-extraneous-dependencies */
import { CallbackManager } from "@langchain/core/callbacks/manager";
import { LangChainTracer } from "@langchain/core/tracers/tracer_langchain";
import { RunTree } from "./run_trees.js";
import { Run } from "./schemas.js";

// TODO: move this to langchain/smith
export async function getLangchainCallbacks(runTree: RunTree) {
  // TODO: CallbackManager.configure() is only async due to LangChainTracer
  // creationg being async, which is unnecessary.

  const callbacks = await CallbackManager.configure();
  let langChainTracer = callbacks?.handlers.find(
    (handler): handler is LangChainTracer =>
      handler?.name === "langchain_tracer"
  );

  if (!langChainTracer && runTree.tracingEnabled) {
    langChainTracer = new LangChainTracer();
    callbacks?.addHandler(langChainTracer);
  }

  const runMap = new Map<string, Run>();

  const queue = [runTree];
  const visited = new Set<string>();

  while (queue.length > 0) {
    const current = queue.shift();
    if (!current || visited.has(current.id)) continue;
    visited.add(current.id);

    runMap.set(current.id, current);
    if (current.child_runs) {
      queue.push(...current.child_runs);
    }

    if (current.parent_run) {
      queue.push(current.parent_run);
    }
  }

  if (callbacks != null) {
    Object.assign(callbacks, { _parentRunId: runTree.id });
  }

  if (langChainTracer != null) {
    Object.assign(langChainTracer, { runMap, client: runTree.client });
  }

  return callbacks;
}
