/**
 * Smoke integration tests for the v2 threads resource.
 *
 * Covers `Client.threads` (query, listTraces, stats), exposed in #3162.
 */
import { Client } from "../client.js";
import { v4 as uuidv4 } from "../utils/uuid/src/index.js";
import { deleteProject, pollRunsUntilCount, waitUntil } from "./utils.js";

async function setUpProjectWithThread(client: Client) {
  const projectName = `__test_v2_threads_${uuidv4().slice(0, 12)}`;
  if (await client.hasProject({ projectName })) {
    await deleteProject(client, projectName);
  }

  const threadId = `thread-${uuidv4().slice(0, 8)}`;
  const now = new Date();
  // Backend derives thread_id from extra.metadata; set session_id/conversation_id
  // to null so thread_id is used for grouping.
  const threadMeta = {
    metadata: {
      thread_id: threadId,
      session_id: null,
      conversation_id: null,
    },
  };
  await client.createRun({
    name: "run_1",
    inputs: { i: 1 },
    run_type: "llm",
    project_name: projectName,
    start_time: now.getTime(),
    extra: threadMeta,
  });
  await client.createRun({
    name: "run_2",
    inputs: { i: 2 },
    run_type: "llm",
    project_name: projectName,
    start_time: now.getTime() + 1000,
    extra: threadMeta,
  });
  await pollRunsUntilCount(client, projectName, 2, 30_000);

  const project = await client.readProject({ projectName });
  const projectId = project.id;
  const minStartTime = new Date(now.getTime() - 60 * 60 * 1000).toISOString();
  const maxStartTime = new Date(now.getTime() + 5 * 60 * 1000).toISOString();

  return { projectName, projectId, threadId, minStartTime, maxStartTime };
}

test("threads.query returns a page containing the created thread", async () => {
  const client = new Client({
    autoBatchTracing: false,
    callerOptions: { maxRetries: 6 },
  });
  const { projectName, projectId, threadId, minStartTime, maxStartTime } =
    await setUpProjectWithThread(client);
  try {
    let matched: { thread_id?: string } | undefined;
    await waitUntil(
      async () => {
        const page = await client.threads.query({
          project_id: projectId,
          page_size: 10,
          min_start_time: minStartTime,
          max_start_time: maxStartTime,
        });
        matched = page.items.find((t) => t.thread_id === threadId);
        return matched !== undefined;
      },
      90_000,
      3_000,
    );
    expect(matched?.thread_id).toBe(threadId);
  } finally {
    await deleteProject(client, projectName);
  }
});

test("threads.listTraces returns traces belonging to the thread", async () => {
  const client = new Client({
    autoBatchTracing: false,
    callerOptions: { maxRetries: 6 },
  });
  const { projectName, projectId, threadId } =
    await setUpProjectWithThread(client);
  try {
    let itemCount = 0;
    await waitUntil(
      async () => {
        const page = await client.threads.listTraces(threadId, {
          project_id: projectId,
          page_size: 10,
        });
        itemCount = page.items.length;
        return itemCount > 0;
      },
      60_000,
      3_000,
    );
    expect(itemCount).toBeGreaterThan(0);
  } finally {
    await deleteProject(client, projectName);
  }
});

test("threads.stats returns a well-formed stats response", async () => {
  const client = new Client({
    autoBatchTracing: false,
    callerOptions: { maxRetries: 6 },
  });
  const { projectName, projectId, threadId } =
    await setUpProjectWithThread(client);
  try {
    const stats = await client.threads.stats(threadId, {
      selects: ["TURNS"],
      session_id: projectId,
    });
    expect(stats).toBeDefined();
  } finally {
    await deleteProject(client, projectName);
  }
});
