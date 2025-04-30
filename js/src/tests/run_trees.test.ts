/* eslint-disable no-process-env, @typescript-eslint/no-explicit-any */

import { jest } from "@jest/globals";
import { Client } from "../client.js";
import { RunTree } from "../run_trees.js";

const _DATE = 1620000000000;
Date.now = jest.fn(() => _DATE);

test("Should work with manually set API key", async () => {
  const key = process.env.LANGCHAIN_API_KEY;
  delete process.env.LANGCHAIN_API_KEY;
  try {
    const langchainClient = new Client({
      autoBatchTracing: true,
      callerOptions: { maxRetries: 0 },
      timeout_ms: 30_000,
      apiKey: key,
    });
    const callSpy = jest
      .spyOn((langchainClient as any).batchIngestCaller, "call")
      .mockResolvedValue({
        ok: true,
        text: () => "",
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

test("distributed", () => {
  const parent = new RunTree({
    name: "parent_1",
    id: "00000000-0000-0000-0000-00000000000",
    start_time: Date.parse("2021-05-03T00:00:00.000Z"),
    project_name: "test_project",
  });

  const serialized = parent.toHeaders();
  expect(serialized.baggage).toContain("test_project");

  const child2 = RunTree.fromHeaders(serialized)?.createChild({
    name: "child_2",
    id: "00000000-0000-0000-0000-00000000001",
    start_time: Date.parse("2021-05-03T00:00:01.000Z"),
  });

  expect(JSON.parse(JSON.stringify(child2))).toMatchObject({
    name: "child_2",
    run_type: "chain",
    session_name: "test_project",
    dotted_order:
      "20210503T000000000001Z00000000-0000-0000-0000-00000000000.20210503T000001000002Z00000000-0000-0000-0000-00000000001",
  });
});

test("shared client between run trees", () => {
  const runTree1 = new RunTree({ name: "tree_1" });
  const runTree2 = new RunTree({ name: "tree_2" });

  expect(runTree1.client).toBeDefined();
  expect(runTree2.client).toBeDefined();
  expect(runTree1.client).toBe(runTree2.client);
});
