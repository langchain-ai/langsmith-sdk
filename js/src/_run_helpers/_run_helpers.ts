import { AsyncLocalStorage } from "async_hooks";
import { RunTree } from "../run_trees.js";
import { Client } from "../index.js";

interface TracingState {
  parentRunTree?: RunTree;
  projectName?: string;
  tags?: string[];
  metadata?: Record<string, unknown>;
}

const asyncLocalStorage = new AsyncLocalStorage<TracingState>();

export function getCurrentRun() {
  const store = asyncLocalStorage.getStore();
  if (!store) {
    throw new Error("No tracing context found");
  }
  return store.parentRunTree;
}

export function traceable<T, R>(
  props: {
    name?: string;
    runType: string;
    metadata?: Record<string, unknown>;
    tags?: string[];
    client?: Client;
  } = {
    runType: "chain",
  }
) {
  const { name, runType, metadata, tags, client } = props;
  return function (
    target: (...args: T[]) => Promise<R>
  ): (...args: T[]) => Promise<R> {
    return async function (this: unknown, ...args: T[]): Promise<R> {
      const store = asyncLocalStorage.getStore() || {};
      const parentRunTree = store.parentRunTree || null;
      const resolvedName = name ?? target.name;
      const runTree = parentRunTree
        ? await parentRunTree.createChild({
            name: resolvedName,
            run_type: runType,
            extra: { metadata, tags },
            client,
          })
        : new RunTree({
            name: resolvedName,
            run_type: runType,
            extra: { metadata, tags },
            client,
          });
      asyncLocalStorage.enterWith({ parentRunTree: runTree });
      await runTree.postRun();
      try {
        const result = await target.apply(this, args);
        if (
          typeof result === "object" &&
          typeof (result as Promise<unknown>)?.then === "function"
        ) {
          await result;
        }
        await runTree.end(result, undefined, Date.now());

        return result;
      } catch (error) {
        let errorString = "";
        if (
          typeof error === "object" &&
          error !== null &&
          (error as Error)?.message
        ) {
          errorString =
            (error as Error).message +
            ((error as Error).stack ? `\n\n${(error as Error).stack}` : "");
        } else {
          errorString = error?.toString() ?? "";
        }
        await runTree.end(undefined, errorString, Date.now());
        throw error;
      } finally {
        asyncLocalStorage.exit(() => {});
        await runTree.patchRun();
      }
    };
  };
}
