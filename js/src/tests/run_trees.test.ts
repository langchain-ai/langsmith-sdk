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
  expect(
    await getAssumedTreeFromCalls(callSpy.mock.calls, client)
  ).toMatchObject({
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

test("reroot functionality slices dotted order correctly", () => {
  // Create a parent run tree
  const parentId = "00000000-0000-0000-0000-000000000000";
  const parent = new RunTree({
    name: "parent",
    id: parentId,
    project_name: "main-project",
  });

  // Create child runs
  const child1Id = "11111111-1111-1111-1111-111111111111";
  const child1 = parent.createChild({ name: "child1", id: child1Id });

  const child2Id = "22222222-2222-2222-2222-222222222222";
  const child2 = child1.createChild({ name: "child2", id: child2Id });

  // Create a replica with reroot enabled
  const replicaConfig = {
    projectName: "child-project",
    reroot: true,
  };

  // Set distributed parent ID (simulating fromHeaders behavior)
  child2.distributedParentId = child1Id;
  child2.replicas = [replicaConfig];

  // Use private method to remap for project with reroot
  const remapped = (child2 as any)._remapForProject({
    projectName: "child-project",
    runtimeEnv: undefined,
    excludeChildRuns: true,
    reroot: true,
    distributedParentId: child1Id,
  });

  // Verify that the dotted order was sliced
  // Original dotted order should have parent -> child1 -> child2
  // After slicing at child1, it should only have child2
  const originalSegments = child2.dotted_order.split(".");
  const remappedSegments = remapped.dotted_order.split(".");

  // The remapped version should have fewer segments
  expect(remappedSegments.length).toBeLessThan(originalSegments.length);

  // The parent_run_id should be undefined after rerooting at the immediate parent
  if (child2.parent_run_id === child1Id) {
    expect(remapped.parent_run_id).toBeUndefined();
  }

  // The trace_id should be updated to the new root
  expect(remapped.trace_id).toBeTruthy();
});

test("reroot with fromHeaders sets distributedParentId", () => {
  const parentDottedOrder =
    "20210503T000000000000000000000000-0000-0000-0000-000000000000";
  const headers = {
    "langsmith-trace": parentDottedOrder,
  };

  const runTree = RunTree.fromHeaders(headers);

  expect(runTree).toBeDefined();
  expect(runTree!.distributedParentId).toBe(runTree!.id);
});

test("distributed tracing: _sliceParentId method", () => {
  const { client } = mockClient();

  // Create a 3-level hierarchy: grandparent -> parent -> child
  const grandparent = new RunTree({
    name: "Grandparent",
    inputs: { text: "root" },
    client: client,
  });

  const parent = grandparent.createChild({ name: "Parent" });
  const child = parent.createChild({ name: "Child" });

  const parentId = parent.id;

  // Get the child's run data
  const childDict = (child as any)._convertToCreate(child, undefined, true);

  // Verify initial state
  expect(childDict.parent_run_id).toBe(parent.id);
  expect(childDict.trace_id).toBe(grandparent.id);
  expect(childDict.dotted_order).toBeTruthy();

  // Slice at parent ID
  (child as any)._sliceParentId(parentId, childDict);

  // After slicing, parent_run_id should be undefined
  expect(childDict.parent_run_id).toBeUndefined();

  // Trace ID should now be the child's ID
  expect(childDict.trace_id).toBe(child.id);

  // Dotted order should have only 1 segment (just the child)
  const segments = childDict.dotted_order.split(".");
  expect(segments.length).toBe(1);
});

test("distributed tracing: _remapForProject with reroot", () => {
  const { client } = mockClient();

  const grandparent = new RunTree({
    name: "Grandparent",
    inputs: { text: "root" },
    client: client,
    project_name: "original_project",
  });

  const parent = grandparent.createChild({ name: "Parent" });
  const child = parent.createChild({ name: "Child" });

  const parentId = parent.id;

  // Simulate distributed parent ID being set
  child.distributedParentId = parentId;

  // Test WITH reroot enabled
  const remappedWithReroot = (child as any)._remapForProject({
    projectName: "child_project",
    runtimeEnv: undefined,
    excludeChildRuns: true,
    reroot: true, // reroot enabled
    distributedParentId: parentId,
  });

  expect(remappedWithReroot.parent_run_id).toBeUndefined();
  expect(remappedWithReroot.session_name).toBe("child_project");

  const segmentsWithReroot = remappedWithReroot.dotted_order.split(".");
  expect(segmentsWithReroot.length).toBe(1);

  // Test WITHOUT reroot (should keep parent relationship)
  const remappedWithoutReroot = (child as any)._remapForProject({
    projectName: "child_project_2",
    runtimeEnv: undefined,
    excludeChildRuns: true,
    reroot: false, // reroot disabled
    distributedParentId: parentId,
  });

  expect(remappedWithoutReroot.parent_run_id).toBeTruthy();

  // Test with no reroot parameter (should keep parent relationship)
  const remappedNoParam = (child as any)._remapForProject({
    projectName: "child_project_3",
    runtimeEnv: undefined,
    excludeChildRuns: true,
    distributedParentId: parentId,
  });

  expect(remappedNoParam.parent_run_id).toBeTruthy();
});

test("distributed tracing: fromHeaders sets distributedParentId correctly", () => {
  const { client } = mockClient();

  // Create a hierarchy: grandparent -> parent -> child
  const grandparent = new RunTree({
    name: "Grandparent",
    inputs: { text: "grandparent" },
    client: client,
    project_name: "original_project",
  });

  const parent = grandparent.createChild({ name: "Parent" });
  const child = parent.createChild({ name: "Child" });

  // Get headers from child
  const headers = child.toHeaders();

  // Create a new run tree from headers
  const fromHeadersRun = RunTree.fromHeaders(headers);

  expect(fromHeadersRun).toBeDefined();
  expect(fromHeadersRun!.distributedParentId).toBe(fromHeadersRun!.id);
  expect(fromHeadersRun!.distributedParentId).toBe(child.id);

  // Now create a new run that should use this distributed parent ID
  const newRun = new RunTree({
    name: "NewRun",
    inputs: { text: "new_run" },
    client: client,
    project_name: "child_project",
  });

  newRun.distributedParentId = fromHeadersRun!.id;

  // Remap with reroot enabled
  const remapped = (newRun as any)._remapForProject({
    projectName: "child_project",
    runtimeEnv: undefined,
    excludeChildRuns: true,
    reroot: true,
    distributedParentId: newRun.distributedParentId,
  });

  expect(remapped.parent_run_id).toBeUndefined();

  const segments = remapped.dotted_order.split(".");
  expect(segments.length).toBe(1);
  expect(remapped.trace_id).toBe(newRun.id);
});

test("_sliceParentId handles missing parent gracefully", () => {
  const { client } = mockClient();

  const parent = new RunTree({
    name: "Parent",
    inputs: { text: "parent" },
    client: client,
  });

  const child = parent.createChild({ name: "Child" });

  const childDict = (child as any)._convertToCreate(child, undefined, true);
  const originalDottedOrder = childDict.dotted_order;
  const originalParentRunId = childDict.parent_run_id;

  // Try to slice with a non-existent parent ID
  const nonExistentId = "99999999-9999-9999-9999-999999999999";
  (child as any)._sliceParentId(nonExistentId, childDict);

  // Should not modify dotted order if parent not found
  expect(childDict.dotted_order).toBe(originalDottedOrder);

  // Should not modify parent_run_id if it doesn't match
  expect(childDict.parent_run_id).toBe(originalParentRunId);
});

test("_sliceParentId handles empty dotted order segments", () => {
  const { client } = mockClient();

  const singleRun = new RunTree({
    name: "SingleRun",
    inputs: { text: "single" },
    client: client,
  });

  const runDict = (singleRun as any)._convertToCreate(
    singleRun,
    undefined,
    true
  );

  // Try to slice at the run's own ID (should result in empty segments)
  (singleRun as any)._sliceParentId(singleRun.id, runDict);

  // When all segments are removed, trace_id should be set to the run's ID
  expect(runDict.trace_id).toBe(singleRun.id);
});

test("integration: reroot with replicas makes correct API calls", async () => {
  const callSpy = jest.fn<typeof fetch>().mockResolvedValue({
    ok: true,
    text: () => Promise.resolve(""),
  } as Response);

  const client = new Client({
    autoBatchTracing: false,
    callerOptions: { maxRetries: 0 },
    timeout_ms: 30_000,
    apiKey: "test-key",
    fetchImplementation: callSpy,
  });

  // Create a 3-level hierarchy
  const grandparent = new RunTree({
    name: "Grandparent",
    inputs: { text: "root" },
    client: client,
    project_name: "main-project",
  });

  const parent = grandparent.createChild({ name: "Parent" });
  const child = parent.createChild({ name: "Child" });

  // Set up replicas - one with reroot, one without
  child.distributedParentId = parent.id;
  child.replicas = [
    {
      projectName: "child-project-rerooted",
      apiKey: "replica1-key",
      apiUrl: "https://replica1.example.com",
      reroot: true,
    },
    {
      projectName: "child-project-full-trace",
      apiKey: "replica2-key",
      apiUrl: "https://replica2.example.com",
      reroot: false,
    },
  ];

  // Post the run
  await child.postRun();

  // Verify that createRun was called twice (once per replica)
  expect(callSpy).toHaveBeenCalledTimes(2);

  // Verify the URLs called
  const calls = callSpy.mock.calls;
  expect(calls[0][0]).toBe("https://replica1.example.com/runs");
  expect(calls[1][0]).toBe("https://replica2.example.com/runs");

  // Verify that both calls include the Authorization header with different keys
  const call1Headers = (calls[0][1] as any)?.headers;
  const call2Headers = (calls[1][1] as any)?.headers;

  expect(call1Headers?.["x-api-key"]).toBe("replica1-key");
  expect(call2Headers?.["x-api-key"]).toBe("replica2-key");

  // The actual rerooting logic is already tested in unit tests
  // This integration test just verifies the API calls are made to the correct endpoints
}, 180_000);

test("child_runs array is cleared after postRun to prevent memory leak", async () => {
  const { client } = mockClient();

  const parent = new RunTree({
    name: "Parent",
    inputs: { text: "parent" },
    client: client,
  });

  const child1 = parent.createChild({ name: "Child1" });
  const child2 = parent.createChild({ name: "Child2" });

  // Before posting, parent should have references to children
  expect(parent.child_runs).toHaveLength(2);
  expect(parent.child_runs).toContain(child1);
  expect(parent.child_runs).toContain(child2);

  // Post the parent run
  await parent.postRun();

  // After posting, child_runs should be cleared to prevent memory leak
  expect(parent.child_runs).toHaveLength(0);
});

test("child_runs array is cleared after patchRun to prevent memory leak", async () => {
  const { client } = mockClient();

  const parent = new RunTree({
    name: "Parent",
    inputs: { text: "parent" },
    client: client,
  });

  parent.createChild({ name: "Child1" });
  parent.createChild({ name: "Child2" });

  // Before patching, parent should have references to children
  expect(parent.child_runs).toHaveLength(2);

  // Patch the parent run
  await parent.patchRun();

  // After patching, child_runs should be cleared to prevent memory leak
  expect(parent.child_runs).toHaveLength(0);
});

test("memory leak test with multiple iterations", async () => {
  const { client } = mockClient();

  // Simulate multiple requests creating parent-child hierarchies
  for (let i = 0; i < 10; i++) {
    const parent = new RunTree({
      name: `Parent${i}`,
      inputs: { iteration: i },
      client: client,
    });

    // Each parent creates multiple children
    parent.createChild({ name: `Child${i}-1` });
    parent.createChild({ name: `Child${i}-2` });
    parent.createChild({ name: `Child${i}-3` });

    expect(parent.child_runs).toHaveLength(3);

    // Post the run
    await parent.postRun();

    // After posting, array should be cleared
    expect(parent.child_runs).toHaveLength(0);
  }
});
