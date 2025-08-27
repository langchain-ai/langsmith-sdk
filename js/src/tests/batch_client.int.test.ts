import { v4 as uuidv4 } from "uuid";
import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import nodeFetch from "node-fetch";

import { Client } from "../client.js";
import { RunTree, convertToDottedOrderFormat } from "../run_trees.js";
import {
  deleteProject,
  waitUntilProjectFound,
  waitUntilRunFound,
} from "./utils.js";
import { traceable } from "../traceable.js";
import {
  _globalFetchImplementationIsNodeFetch,
  overrideFetchImplementation,
} from "../singletons/fetch.js";

test("Test persist update run", async () => {
  const langchainClient = new Client({
    autoBatchTracing: true,
    callerOptions: { maxRetries: 2 },
    timeout_ms: 30_000,
  });
  const projectName =
    "__test_persist_update_run_batch_1" + uuidv4().substring(0, 4);
  await deleteProject(langchainClient, projectName);

  const runId = uuidv4();
  const { dottedOrder } = convertToDottedOrderFormat(
    new Date().getTime(),
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

  await Promise.all([
    waitUntilRunFound(langchainClient, runId, true),
    waitUntilProjectFound(langchainClient, projectName),
  ]);

  const storedRun = await langchainClient.readRun(runId);
  expect(storedRun.id).toEqual(runId);
  await langchainClient.deleteProject({ projectName });
}, 180_000);

test("Test persist update runs above the batch size limit", async () => {
  const langchainClient = new Client({
    autoBatchTracing: true,
    callerOptions: { maxRetries: 6 },
    batchSizeBytesLimit: 1,
    timeout_ms: 30_000,
  });
  const projectName =
    "__test_persist_update_run_batch_above_bs_limit" + uuidv4().substring(0, 4);
  await deleteProject(langchainClient, projectName);

  const createRun = async () => {
    const runId = uuidv4();
    const { dottedOrder } = convertToDottedOrderFormat(
      new Date().getTime(),
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
    await Promise.all([
      waitUntilRunFound(langchainClient, runId, true),
      waitUntilProjectFound(langchainClient, projectName),
    ]);

    const storedRun = await langchainClient.readRun(runId);
    expect(storedRun.id).toEqual(runId);
  };

  await Promise.all([createRun(), createRun(), createRun()]);

  await langchainClient.deleteProject({ projectName });
}, 180_000);

test("Test persist update run with delay", async () => {
  const langchainClient = new Client({
    autoBatchTracing: true,
    callerOptions: { maxRetries: 6 },
    timeout_ms: 30_000,
  });
  const projectName =
    "__test_persist_update_run_batch_with_delay" + uuidv4().substring(0, 4);
  await deleteProject(langchainClient, projectName);

  const runId = uuidv4();
  const { dottedOrder } = convertToDottedOrderFormat(
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
  await Promise.all([
    waitUntilRunFound(langchainClient, runId, true),
    waitUntilProjectFound(langchainClient, projectName),
  ]);
  const storedRun = await langchainClient.readRun(runId);
  expect(storedRun.id).toEqual(runId);
  await langchainClient.deleteProject({ projectName });
}, 180_000);

test("Test persist update run tree", async () => {
  const langchainClient = new Client({
    autoBatchTracing: true,
    callerOptions: { maxRetries: 6 },
    timeout_ms: 30_000,
  });
  const projectName =
    "__test_persist_update_run_tree" + uuidv4().substring(0, 4);
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
  await Promise.all([
    waitUntilRunFound(langchainClient, runId, true),
    waitUntilProjectFound(langchainClient, projectName),
  ]);
  const storedRun = await langchainClient.readRun(runId);
  expect(storedRun.id).toEqual(runId);
  expect(storedRun.dotted_order).toEqual(runTree.dotted_order);
  expect(storedRun.trace_id).toEqual(runTree.trace_id);
  expect(storedRun.inputs).toEqual({ input: "foo1" });
  expect(storedRun.outputs).toEqual({ output: "foo2" });
  await langchainClient.deleteProject({ projectName });
}, 180_000);

test("Test persist run with attachment", async () => {
  const langchainClient = new Client({
    autoBatchTracing: true,
    callerOptions: { maxRetries: 6 },
    timeout_ms: 30_000,
  });
  const projectName = "__test_create_attachment" + uuidv4().substring(0, 4);
  await deleteProject(langchainClient, projectName);

  const runId = uuidv4();
  const { dottedOrder } = convertToDottedOrderFormat(
    new Date().getTime() / 1000,
    runId
  );
  const pathname = path.join(
    path.dirname(fileURLToPath(import.meta.url)),
    "test_data",
    "parrot-icon.png"
  );
  await langchainClient.createRun({
    id: runId,
    project_name: projectName,
    name: "test_run",
    run_type: "llm",
    inputs: { text: "hello world" },
    trace_id: runId,
    dotted_order: dottedOrder,
    attachments: {
      testimage: ["image/png", fs.readFileSync(pathname)],
    },
  });

  await langchainClient.updateRun(runId, {
    outputs: { output: ["Hi"] },
    dotted_order: dottedOrder,
    trace_id: runId,
    end_time: Math.floor(new Date().getTime() / 1000),
  });

  await Promise.all([
    waitUntilRunFound(langchainClient, runId, true),
    waitUntilProjectFound(langchainClient, projectName),
  ]);

  const storedRun = await langchainClient.readRun(runId);
  expect(storedRun.id).toEqual(runId);
  await langchainClient.deleteProject({ projectName });
}, 180_000);

test.skip("very large runs", async () => {
  const langchainClient = new Client({
    autoBatchTracing: true,
    callerOptions: { maxRetries: 6 },
    timeout_ms: 120_000,
  });

  const projectName = "__test_large_runs" + uuidv4().substring(0, 4);
  await deleteProject(langchainClient, projectName);

  console.time("largeRunTimer");

  const promises = [];
  for (let i = 0; i < 10; i++) {
    promises.push(
      traceable(
        async () => {
          return "x".repeat(9000000);
        },
        {
          project_name: projectName,
          client: langchainClient,
          tracingEnabled: true,
        }
      )()
    );
  }

  await Promise.all(promises);

  console.timeLog("largeRunTimer");

  await langchainClient.awaitPendingTraceBatches();

  console.timeLog("largeRunTimer");

  await Promise.all([waitUntilProjectFound(langchainClient, projectName)]);

  await langchainClient.deleteProject({ projectName });
}, 180_000);

test("multipart should work with overridden node-fetch", async () => {
  overrideFetchImplementation(nodeFetch);

  const langchainClient = new Client({
    autoBatchTracing: true,
    callerOptions: { maxRetries: 6 },
    timeout_ms: 120_000,
  });

  const projectName = "__test_node_fetch" + uuidv4().substring(0, 4);
  await deleteProject(langchainClient, projectName);

  await traceable(
    async () => {
      return "testing with node fetch";
    },
    {
      project_name: projectName,
      client: langchainClient,
      tracingEnabled: true,
    }
  )();

  await langchainClient.awaitPendingTraceBatches();

  await Promise.all([waitUntilProjectFound(langchainClient, projectName)]);

  await langchainClient.deleteProject({ projectName });
});
