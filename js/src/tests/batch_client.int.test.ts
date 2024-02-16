import { Client } from "../client.js";
import { RunTree, convertToDottedOrderFormat } from "../run_trees.js";
import { v4 as uuidv4 } from "uuid";

async function deleteProject(langchainClient: Client, projectName: string) {
  try {
    await langchainClient.readProject({ projectName });
    await langchainClient.deleteProject({ projectName });
  } catch (e) {
    // Pass
  }
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

async function waitUntilRunFound(
  client: Client,
  runId: string,
  checkOutputs = false
) {
  return waitUntil(
    async () => {
      try {
        const run = await client.readRun(runId);
        if (checkOutputs) {
          return (
            run.outputs !== null &&
            run.outputs !== undefined &&
            Object.keys(run.outputs).length !== 0
          );
        }
        return true;
      } catch (e) {
        return false;
      }
    },
    30_000,
    5_000
  );
}

test.concurrent(
  "Test persist update run",
  async () => {
    const langchainClient = new Client({
      autoBatchTracing: true,
      callerOptions: { maxRetries: 2 },
      timeout_ms: 30_000,
    });
    const projectName = "__test_persist_update_run_batch_1";
    await deleteProject(langchainClient, projectName);

    const runId = uuidv4();
    const dottedOrder = convertToDottedOrderFormat(
      new Date().getTime() / 1000,
      runId
    );
    await langchainClient.createRun({
      id: runId,
      project_name: projectName,
      name: "test_run",
      run_type: "llm",
      inputs: { text: "hello world" },
      trace_id: runId,
      dotted_order: dottedOrder,
    });

    await langchainClient.updateRun(runId, {
      outputs: { output: ["Hi"] },
      dotted_order: dottedOrder,
      trace_id: runId,
    });
    await waitUntilRunFound(langchainClient, runId, true);
    const storedRun = await langchainClient.readRun(runId);
    expect(storedRun.id).toEqual(runId);
    await langchainClient.deleteProject({ projectName });
  },
  180_000
);

test.concurrent(
  "Test persist update runs above the batch size limit",
  async () => {
    const langchainClient = new Client({
      autoBatchTracing: true,
      callerOptions: { maxRetries: 2 },
      pendingAutoBatchedRunLimit: 2,
      timeout_ms: 30_000,
    });
    const projectName = "__test_persist_update_run_batch_above_bs_limit";
    await deleteProject(langchainClient, projectName);

    const createRun = async () => {
      const runId = uuidv4();
      const dottedOrder = convertToDottedOrderFormat(
        new Date().getTime() / 1000,
        runId
      );
      await langchainClient.createRun({
        id: runId,
        project_name: projectName,
        name: "test_run",
        run_type: "llm",
        inputs: { text: "hello world" },
        trace_id: runId,
        dotted_order: dottedOrder,
      });

      await langchainClient.updateRun(runId, {
        outputs: { output: ["Hi"] },
        dotted_order: dottedOrder,
        trace_id: runId,
        end_time: Math.floor(new Date().getTime() / 1000),
      });
      await waitUntilRunFound(langchainClient, runId, true);
      const storedRun = await langchainClient.readRun(runId);
      expect(storedRun.id).toEqual(runId);
    };

    await Promise.all([createRun(), createRun(), createRun()]);

    await langchainClient.deleteProject({ projectName });
  },
  180_000
);

test.concurrent(
  "Test persist update run with delay",
  async () => {
    const langchainClient = new Client({
      autoBatchTracing: true,
      callerOptions: { maxRetries: 2 },
      timeout_ms: 30_000,
    });
    const projectName = "__test_persist_update_run_batch_with_delay";
    await deleteProject(langchainClient, projectName);

    const runId = uuidv4();
    const dottedOrder = convertToDottedOrderFormat(
      new Date().getTime() / 1000,
      runId
    );
    await langchainClient.createRun({
      id: runId,
      project_name: projectName,
      name: "test_run",
      run_type: "llm",
      inputs: { text: "hello world" },
      trace_id: runId,
      dotted_order: dottedOrder,
    });

    await new Promise((resolve) => setTimeout(resolve, 1000));
    await langchainClient.updateRun(runId, {
      outputs: { output: ["Hi"] },
      dotted_order: dottedOrder,
      trace_id: runId,
      end_time: Math.floor(new Date().getTime() / 1000),
    });
    await waitUntilRunFound(langchainClient, runId, true);
    const storedRun = await langchainClient.readRun(runId);
    expect(storedRun.id).toEqual(runId);
    await langchainClient.deleteProject({ projectName });
  },
  180_000
);

test.concurrent(
  "Test persist update run tree",
  async () => {
    const langchainClient = new Client({
      autoBatchTracing: true,
      callerOptions: { maxRetries: 2 },
      timeout_ms: 30_000,
    });
    const projectName = "__test_persist_update_run_tree";
    await deleteProject(langchainClient, projectName);
    const runId = uuidv4();
    const runTree = new RunTree({
      name: "Test Run Tree",
      id: runId,
      inputs: { input: "foo1" },
      client: langchainClient,
      project_name: projectName,
    });
    await runTree.postRun();
    await runTree.end({ output: "foo2" });
    await runTree.patchRun();
    await waitUntilRunFound(langchainClient, runId, true);
    const storedRun = await langchainClient.readRun(runId);
    expect(storedRun.id).toEqual(runId);
    expect(storedRun.dotted_order).toEqual(runTree.dotted_order);
    expect(storedRun.trace_id).toEqual(runTree.trace_id);
    expect(storedRun.inputs).toEqual({ input: "foo1" });
    expect(storedRun.outputs).toEqual({ output: "foo2" });
    await langchainClient.deleteProject({ projectName });
  },
  180_000
);
