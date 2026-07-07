/**
 * Smoke integration tests for the v2 threads and traces resources.
 *
 * Covers `Client.threads` (query, listTraces, stats) and `Client.traces`
 * (query, listRuns), exposed in #3162.
 */
import { Client } from "../client.js";
import { v4 as uuidv4 } from "../utils/uuid/src/index.js";
import { deleteProject, pollRunsUntilCount, waitUntil } from "./utils.js";

async function setUpProjectWithThread(client: Client) {
  const projectName = `__test_v2_threads_traces_${uuidv4().slice(0, 12)}`;
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
    await waitUntil(
      async () => {
        const page = await client.threads.query({
          project_id: projectId,
          page_size: 10,
          min_start_time: minStartTime,
          max_start_time: maxStartTime,
        });
        return page.items.some((t) => t.thread_id === threadId);
      },
      90_000,
      3_000,
    );
    const page = await client.threads.query({
      project_id: projectId,
      page_size: 10,
      min_start_time: minStartTime,
      max_start_time: maxStartTime,
    });
    expect(page.items.some((t) => t.thread_id === threadId)).toBe(true);
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
    await waitUntil(
      async () => {
        const page = await client.threads.listTraces(threadId, {
          project_id: projectId,
          page_size: 10,
        });
        return page.items.length > 0;
      },
      60_000,
      3_000,
    );
    const page = await client.threads.listTraces(threadId, {
      project_id: projectId,
      page_size: 10,
    });
    expect(page.items.length).toBeGreaterThan(0);
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
    // Stats are computed by an eventually-consistent aggregation job, so this
    // only smoke-tests that the endpoint responds rather than asserting that
    // `turns` has been populated yet.
    const stats = await client.threads.stats(threadId, {
      selects: ["TURNS"],
      session_id: projectId,
    });
    expect(stats).toBeDefined();
  } finally {
    await deleteProject(client, projectName);
  }
});

test("traces.query returns a page of traces for the project", async () => {
  const client = new Client({
    autoBatchTracing: false,
    callerOptions: { maxRetries: 6 },
  });
  const { projectName, projectId, minStartTime, maxStartTime } =
    await setUpProjectWithThread(client);
  try {
    await waitUntil(
      async () => {
        const page = await client.traces.query({
          project_id: projectId,
          page_size: 10,
          min_start_time: minStartTime,
          max_start_time: maxStartTime,
        });
        return page.items.length > 0;
      },
      60_000,
      3_000,
    );
    const page = await client.traces.query({
      project_id: projectId,
      page_size: 10,
      min_start_time: minStartTime,
      max_start_time: maxStartTime,
    });
    expect(page.items.length).toBeGreaterThan(0);
  } finally {
    await deleteProject(client, projectName);
  }
});

test("traces.listRuns returns the runs belonging to a trace", async () => {
  const client = new Client({
    autoBatchTracing: false,
    callerOptions: { maxRetries: 6 },
  });
  const { projectName, projectId, minStartTime, maxStartTime } =
    await setUpProjectWithThread(client);
  try {
    const page = await client.traces.query({
      project_id: projectId,
      page_size: 10,
      min_start_time: minStartTime,
      max_start_time: maxStartTime,
    });
    expect(page.items.length).toBeGreaterThan(0);
    const rootRun = page.items[0].root_run;
    expect(rootRun).toBeDefined();
    const traceId = rootRun!.id;
    expect(traceId).toBeDefined();

    const response = await client.traces.listRuns(traceId!, {
      project_id: projectId,
    });
    expect(response.items).toBeDefined();
    expect(response.items!.length).toBeGreaterThan(0);
  } finally {
    await deleteProject(client, projectName);
  }
});
