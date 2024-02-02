import { Client } from "../client.js";
import {
  RunTree,
  RunTreeConfig,
  convertToDottedOrderFormat,
} from "../run_trees.js";

async function toArray<T>(iterable: AsyncIterable<T>): Promise<T[]> {
  const result: T[] = [];
  for await (const item of iterable) {
    result.push(item);
  }
  return result;
}

async function waitUntil(
  condition: () => Promise<boolean>,
  timeout: number,
  interval: number
): Promise<void> {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    if (await condition()) {
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, interval));
  }
  throw new Error("Timeout");
}

test.concurrent(
  "Test post and patch run",
  async () => {
    const projectName = `__test_run_tree`;
    const langchainClient = new Client({});
    try {
      await langchainClient.readProject({ projectName });
      await langchainClient.deleteProject({ projectName });
    } catch (e) {
      // Pass
    }
    const parentRunConfig: RunTreeConfig = {
      name: "parent_run",
      run_type: "chain",
      inputs: { text: "hello world" },
      project_name: projectName,
      serialized: {},
      client: langchainClient,
    };

    const parent_run = new RunTree(parentRunConfig);
    expect(parent_run.trace_id).toEqual(parent_run.id);
    expect(parent_run.dotted_order).toEqual(
      convertToDottedOrderFormat(parent_run.start_time, parent_run.id)
    );
    await parent_run.postRun();

    const child_llm_run = await parent_run.createChild({
      name: "child_run",
      run_type: "llm",
      inputs: { text: "hello world" },
    });
    expect(child_llm_run.dotted_order).toEqual(
      parent_run.dotted_order +
        "." +
        convertToDottedOrderFormat(child_llm_run.start_time, child_llm_run.id)
    );
    expect(child_llm_run.trace_id).toEqual(parent_run.trace_id);
    await child_llm_run.postRun();

    const child_chain_run = await parent_run.createChild({
      name: "child_chain_run",
      run_type: "chain",
      inputs: { text: "hello world" },
    });
    await child_chain_run.postRun();

    const grandchild_chain_run = await child_chain_run.createChild({
      name: "grandchild_chain_run",
      run_type: "chain",
      inputs: { text: "hello world" },
    });
    await grandchild_chain_run.postRun();
    await grandchild_chain_run.end({ output: ["Hi"] });
    await grandchild_chain_run.patchRun();
    await child_chain_run.end(undefined, "AN ERROR");
    await child_chain_run.patchRun();
    const child_tool_run = await parent_run.createChild({
      name: "child_tool_run",
      run_type: "tool",
      inputs: { text: "hello world" },
    });
    await child_tool_run.postRun();
    await child_tool_run.end({ output: ["Hi"] });
    await child_tool_run.patchRun();
    await child_llm_run.end({ prompts: ["hello world"] });
    await child_llm_run.patchRun();
    await parent_run.end({ output: ["Hi"] });
    await parent_run.patchRun();

    await waitUntil(
      async () => {
        try {
          const runs = await toArray(langchainClient.listRuns({ projectName }));
          return runs.length === 5;
        } catch (e) {
          return false;
        }
      },
      30_000, // Wait up to 30 seconds
      3000 // every 3 second
    );
    const runs = await toArray(langchainClient.listRuns({ projectName }));
    expect(runs.length).toEqual(5);
    const runMap = new Map(runs.map((run) => [run.name, run]));
    expect(runMap.get("child_run")?.parent_run_id).toEqual(
      runMap.get("parent_run")?.id
    );
    expect(runMap.get("child_chain_run")?.parent_run_id).toEqual(
      runMap.get("parent_run")?.id
    );
    expect(runMap.get("grandchild_chain_run")?.parent_run_id).toEqual(
      runMap.get("child_chain_run")?.id
    );
    expect(runMap.get("child_tool_run")?.parent_run_id).toEqual(
      runMap.get("parent_run")?.id
    );
    expect(runMap.get("parent_run")?.parent_run_id).toBeNull();
    await langchainClient.deleteProject({ projectName });
  },
  120_000
);
