/* eslint-disable no-process-env, @typescript-eslint/no-explicit-any */

import { jest } from "@jest/globals";
import { Client } from "../client.js";
import { RunTree } from "../run_trees.js";
import { getCurrentRunTree, withRunTree } from "../singletons/traceable.js";
import { traceable } from "../traceable.js";
import { mockClient } from "./utils/mock_client.js";
import { getAssumedTreeFromCalls } from "./utils/tree.js";

const _DATE = 1620000000000;
Date.now = jest.fn(() => _DATE);

test("Should work with manually set API key", async () => {
  const key = process.env.LANGCHAIN_API_KEY;
  delete process.env.LANGCHAIN_API_KEY;
  try {
    const callSpy = jest.fn<typeof fetch>().mockResolvedValue({
      ok: true,
      text: () => Promise.resolve(""),
    } as Response);
    const langchainClient = new Client({
      autoBatchTracing: true,
      callerOptions: { maxRetries: 0 },
      timeout_ms: 30_000,
      apiKey: key,
      fetchImplementation: callSpy,
    });
    const projectName = "__test_persist_update_run_tree";
    const runTree = new RunTree({
      name: "Test Run Tree",
      inputs: { input: "foo1" },
      client: langchainClient,
      project_name: projectName,
    });
    await runTree.postRun();
    await new Promise((resolve) => setTimeout(resolve, 1500));
    expect(callSpy).toHaveBeenCalled();
  } finally {
    process.env.LANGCHAIN_API_KEY = key;
  }
}, 180_000);

test("nested", () => {
  const id = "00000000-0000-0000-0000-00000000000";
  const date = "20210503T00000000000";

  const parent = new RunTree({ name: "parent_1", id: `${id}0` });
  const child1 = parent.createChild({ name: "child_1", id: `${id}1` });
  const child2 = parent.createChild({ name: "child_2", id: `${id}2` });
  const grandchild1 = child1.createChild({
    name: "grandchild_1",
    id: `${id}3`,
  });
  const grandchild2 = child1.createChild({
    name: "grandchild_2",
    id: `${id}4`,
  });
  const child3 = parent.createChild({ name: "child_3", id: `${id}5` });

  expect(parent.dotted_order).toBe(`${date}1Z${id}0`);
  expect(child1.dotted_order).toBe(`${date}1Z${id}0.${date}2Z${id}1`);
  expect(child2.dotted_order).toBe(`${date}1Z${id}0.${date}3Z${id}2`);
  expect(grandchild1.dotted_order).toBe(
    `${date}1Z${id}0.${date}2Z${id}1.${date}3Z${id}3`
  );
  expect(grandchild2.dotted_order).toBe(
    `${date}1Z${id}0.${date}2Z${id}1.${date}4Z${id}4`
  );
  expect(child3.dotted_order).toBe(`${date}1Z${id}0.${date}5Z${id}5`);
});

test("serializing run tree", () => {
  const parent = new RunTree({ name: "parent_1" });
  parent.createChild({ name: "child_1" }).createChild({ name: "child_2" });
  parent.createChild({ name: "child_3" });

  expect(JSON.parse(JSON.stringify(parent))).toMatchObject({
    name: "parent_1",
    run_type: "chain",
    child_runs: [
      {
        name: "child_1",
        run_type: "chain",
        child_runs: [{ name: "child_2", run_type: "chain", child_runs: [] }],
      },
      {
        name: "child_3",
        run_type: "chain",
        child_runs: [],
      },
    ],
  });
});

test("distributed", async () => {
  process.env.LANGCHAIN_TRACING = "true";
  const { client, callSpy } = mockClient();
  const parent = new RunTree({
    name: "parent_1",
    id: "00000000-0000-0000-0000-00000000000",
    start_time: Date.parse("2021-05-03T00:00:00.000Z"),
    project_name: "test_project",
    client,
  });

  await parent.postRun();

  const serialized = parent.toHeaders();
  expect(serialized.baggage).toContain("test_project");

  const child2 = RunTree.fromHeaders(serialized, {
    client,
  })?.createChild({
    name: "child_2",
    id: "00000000-0000-0000-0000-00000000001",
    start_time: Date.parse("2021-05-03T00:00:01.000Z"),
  });

  await child2?.postRun();

  expect(JSON.parse(JSON.stringify(child2))).toMatchObject({
    name: "child_2",
    run_type: "chain",
    session_name: "test_project",
    dotted_order:
      "20210503T000000000001Z00000000-0000-0000-0000-00000000000.20210503T000001000002Z00000000-0000-0000-0000-00000000001",
  });

  const result = await withRunTree(child2!, () => {
    return traceable(
      () => {
        const currentRunTree = getCurrentRunTree();
        expect(currentRunTree.id).toBe("00000000-0000-0000-0000-00000000002");
        expect(currentRunTree.dotted_order).toBe(
          "20210503T000000000001Z00000000-0000-0000-0000-00000000000.20210503T000001000002Z00000000-0000-0000-0000-00000000001.20210503T000002000003Z00000000-0000-0000-0000-00000000002"
        );
        return "child2";
      },
      {
        name: "grandchild_traceable",
        client,
        id: "00000000-0000-0000-0000-00000000002",
        start_time: Date.parse("2021-05-03T00:00:02.000Z"),
      }
    )();
  });

  expect(result).toBe("child2");
  await child2?.end();
  await child2?.patchRun();
  await parent.end();
  await parent.patchRun();
  await client.awaitPendingTraceBatches();
  expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
    nodes: ["parent_1:0", "child_2:1", "grandchild_traceable:2"],
  });
});

test("shared client between run trees", () => {
  const runTree1 = new RunTree({ name: "tree_1" });
  const runTree2 = new RunTree({ name: "tree_2" });

  expect(runTree1.client).toBeDefined();
  expect(runTree2.client).toBeDefined();
  expect(runTree1.client).toBe(runTree2.client);
});
