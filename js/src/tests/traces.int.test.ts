/**
 * Smoke integration tests for the v2 traces resource.
 *
 * Covers `Client.traces` (query, listRuns), exposed in #3162.
 */
import { Client } from "../client.js";
import { v4 as uuidv4 } from "../utils/uuid/src/index.js";
import { deleteProject, pollRunsUntilCount, waitUntil } from "./utils.js";

async function setUpProjectWithRuns(client: Client) {
  const projectName = `__test_v2_traces_${uuidv4().slice(0, 12)}`;
  if (await client.hasProject({ projectName })) {
    await deleteProject(client, projectName);
  }

  const now = new Date();
  await client.createRun({
    name: "run_1",
    inputs: { i: 1 },
    run_type: "llm",
    project_name: projectName,
    start_time: now.getTime(),
  });
  await client.createRun({
    name: "run_2",
    inputs: { i: 2 },
    run_type: "llm",
    project_name: projectName,
    start_time: now.getTime() + 1000,
  });
  await pollRunsUntilCount(client, projectName, 2, 30_000);

  const project = await client.readProject({ projectName });
  const projectId = project.id;
  const minStartTime = new Date(now.getTime() - 60 * 60 * 1000).toISOString();
  const maxStartTime = new Date(now.getTime() + 5 * 60 * 1000).toISOString();

  return { projectName, projectId, minStartTime, maxStartTime };
}

test("traces.query returns a page of traces for the project", async () => {
  const client = new Client({
    autoBatchTracing: false,
    callerOptions: { maxRetries: 6 },
  });
  const { projectName, projectId, minStartTime, maxStartTime } =
    await setUpProjectWithRuns(client);
  try {
    let itemCount = 0;
    await waitUntil(
      async () => {
        const page = await client.traces.query({
          project_id: projectId,
          page_size: 10,
          min_start_time: minStartTime,
          max_start_time: maxStartTime,
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

test("traces.listRuns returns the runs belonging to a trace", async () => {
  const client = new Client({
    autoBatchTracing: false,
    callerOptions: { maxRetries: 6 },
  });
  const { projectName, projectId, minStartTime, maxStartTime } =
    await setUpProjectWithRuns(client);
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
