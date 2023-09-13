import { Client } from "../client.js";
import { RunTree, RunTreeConfig } from "../run_trees.js";
import { jest } from "@jest/globals";

async function toArray<T>(iterable: AsyncIterable<T>): Promise<T[]> {
  const result: T[] = [];
  for await (const item of iterable) {
    result.push(item);
  }
  return result;
}

test("Test persisting runs and adding feedback", async () => {
  const projectName = `__test_run_tree`;
  const langchainClient = new Client({
    apiUrl: "http://localhost:1984",
  });
  const projects = await toArray(langchainClient.listProjects());
  if (projects.map((project) => project.name).includes(projectName)) {
    await langchainClient.deleteProject({ projectName });
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

  const child_llm_run = await parent_run.createChild({
    name: "child_run",
    run_type: "llm",
    inputs: { text: "hello world" },
  });

  const child_chain_run = await parent_run.createChild({
    name: "child_chain_run",
    run_type: "chain",
    inputs: { text: "hello world" },
  });

  const grandchild_chain_run = await child_chain_run.createChild({
    name: "grandchild_chain_run",
    run_type: "chain",
    inputs: { text: "hello world" },
  });

  await grandchild_chain_run.end({ output: ["Hi"] });
  await child_chain_run.end(undefined, "AN ERROR");
  const child_tool_run = await parent_run.createChild({
    name: "child_tool_run",
    run_type: "tool",
    inputs: { text: "hello world" },
  });
  await child_tool_run.end({ output: ["Hi"] });
  await child_llm_run.end({ prompts: ["hello world"] });
  await parent_run.end({ output: ["Hi"] });
  // Capture console.warn output
  const consoleWarnSpy = jest
    .spyOn(console, "warn")
    .mockImplementation(() => {});

  // Assert that console.warn was called
  await parent_run.postRun(false);
  expect(consoleWarnSpy).toHaveBeenCalled();

  // Restore console.warn
  consoleWarnSpy.mockRestore();
  const runs = await toArray(langchainClient.listRuns({ projectName }));
  expect(runs.length).toEqual(5);
  const runMap = new Map(runs.map((run) => [run.name, run]));
  expect(runMap.get("parent_run")?.execution_order).toEqual(1);
  expect(runMap.get("child_run")?.execution_order).toEqual(2);
  expect(runMap.get("child_chain_run")?.execution_order).toEqual(2);
  expect(runMap.get("grandchild_chain_run")?.execution_order).toEqual(3);
  expect(runMap.get("child_tool_run")?.execution_order).toEqual(4);

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

  const nestedRun = await langchainClient.readRun(
    runMap.get("parent_run")?.id ?? "",
    { loadChildRuns: true }
  );
  expect(nestedRun.child_runs).not.toBeNull();
  expect(nestedRun.child_runs?.length).toEqual(3);
  const firstTwo = new Map(
    nestedRun.child_runs
      ?.slice(0, 2)
      .map((childRun) => [childRun.name, childRun])
  );
  expect(firstTwo.has("child_run")).toBeTruthy();
  expect(firstTwo.has("child_chain_run")).toBeTruthy();
  expect(nestedRun.child_runs?.[2].name).toEqual("child_tool_run");
  expect(firstTwo.get("child_chain_run")?.child_runs).not.toBeNull();
  expect(firstTwo.get("child_chain_run")?.child_runs?.length).toEqual(1);
  expect(firstTwo.get("child_chain_run")?.child_runs?.[0].name).toEqual(
    "grandchild_chain_run"
  );

  await langchainClient.createFeedback(runs[0].id, "supermetric", {
    value: {
      clarity: "good",
      fluency: "good",
      relevance: "very bad",
    },
    score: 0.5,
    feedbackSourceType: "model",
  });
  const feedback2 = await langchainClient.createFeedback(
    runs[0].id,
    "a tag",
    {}
  );
  expect(feedback2.id).not.toBeNull();
  const res = await langchainClient.updateFeedback(feedback2.id, {
    correction: { good_output: "a correction" },
  });
  expect(res.correction).toEqual({ good_output: "a correction" });
  const feedbacks = await toArray(
    langchainClient.listFeedback({ runIds: [runs[0].id] })
  );
  expect(feedbacks.length).toEqual(2);
  expect(feedbacks[0].run_id).toEqual(runs[0].id);
  const updatedFeedback = await langchainClient.readFeedback(feedback2.id);
  expect(updatedFeedback.correction).toEqual({ good_output: "a correction" });
  const feedback = await langchainClient.readFeedback(feedbacks[0].id);
  expect(feedback.id).toEqual(feedbacks[0].id);
  await langchainClient.deleteFeedback(feedback.id);
  await expect(langchainClient.readFeedback(feedback.id)).rejects.toThrow();
  const feedbackArray = await toArray(
    langchainClient.listFeedback({ runIds: [runs[0].id] })
  );
  expect(feedbackArray.length).toEqual(1);

  await langchainClient.deleteProject({ projectName });
  await expect(langchainClient.readProject({ projectName })).rejects.toThrow();
});

test("Test post and patch run", async () => {
  const projectName = `__test_run_tree`;
  const langchainClient = new Client({
    apiUrl: "http://localhost:1984",
  });
  const projects = await toArray(langchainClient.listProjects());
  if (projects.map((project) => project.name).includes(projectName)) {
    await langchainClient.deleteProject({ projectName });
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
  await parent_run.postRun();

  const child_llm_run = await parent_run.createChild({
    name: "child_run",
    run_type: "llm",
    inputs: { text: "hello world" },
  });
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

  const runs = await toArray(langchainClient.listRuns({ projectName }));
  expect(runs.length).toEqual(5);
  const runMap = new Map(runs.map((run) => [run.name, run]));
  expect(runMap.get("parent_run")?.execution_order).toEqual(1);
  expect(runMap.get("child_run")?.execution_order).toEqual(2);
  expect(runMap.get("child_chain_run")?.execution_order).toEqual(2);
  expect(runMap.get("grandchild_chain_run")?.execution_order).toEqual(3);
  expect(runMap.get("child_tool_run")?.execution_order).toEqual(4);

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
});
