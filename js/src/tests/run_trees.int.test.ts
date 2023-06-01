import * as uuid from "uuid";
import { LangChainPlusClient } from "../client.js";
import { RunTree, RunTreeConfig } from "../run_trees.js";

test("Test persisting runs and adding feedback", async () => {
  const session_name = `__test_run_tree + ${uuid.v4()}`;
  const langchainClient = new LangChainPlusClient({
    apiUrl: "http://localhost:1984",
  });
  const sessions = await langchainClient.listSessions();
  if (sessions.map((session) => session.name).includes(session_name)) {
    await langchainClient.deleteSession({ session_name });
  }

  const parentRunConfig: RunTreeConfig = {
    name: "parent_run",
    run_type: "chain",
    inputs: { text: "hello world" },
    session_name: session_name,
    serialized: {},
    apiUrl: "http://localhost:1984",
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
  await parent_run.postRun(false);

  const runs = await langchainClient.listRuns({ session_name });
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

  await langchainClient.createFeedback(runs[0].id, "supermetric", {
    value: {
      clarity: "good",
      fluency: "good",
      relevance: "very bad",
    },
    score: 0.5,
    feedbackSourceType: "MODEL",
  });
  await langchainClient.createFeedback(runs[0].id, "a tag", {});
  const feedbacks = Array.from(
    await langchainClient.listFeedback({ run_ids: [runs[0].id] })
  );
  expect(feedbacks.length).toEqual(2);
  expect(feedbacks[0].run_id).toEqual(runs[0].id);
  const feedback = await langchainClient.readFeedback(feedbacks[0].id);
  expect(feedback.id).toEqual(feedbacks[0].id);
  await langchainClient.deleteFeedback(feedback.id);
  try {
    await langchainClient.readFeedback(feedback.id);
  } catch (error) {
    // expect(error).toBeInstanceOf(LangChainPlusError);
  }
  expect(
    Array.from(await langchainClient.listFeedback({ run_ids: [runs[0].id] }))
      .length
  ).toEqual(1);

  await langchainClient.deleteSession({ session_name });
  try {
    await langchainClient.readSession({ session_name });
  } catch (error) {
    // expect(error).toBeInstanceOf(LangChainPlusError);
  }
});

test("Test post and patch run", async () => {
  const session_name = `__test_run_tree + ${uuid.v4()}`;
  const langchainClient = new LangChainPlusClient({
    apiUrl: "http://localhost:1984",
  });
  const sessions = await langchainClient.listSessions();
  if (sessions.map((session) => session.name).includes(session_name)) {
    await langchainClient.deleteSession({ session_name });
  }

  const parentRunConfig: RunTreeConfig = {
    name: "parent_run",
    run_type: "chain",
    inputs: { text: "hello world" },
    session_name: session_name,
    serialized: {},
    apiUrl: "http://localhost:1984",
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

  const runs = await langchainClient.listRuns({ session_name });
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
});
