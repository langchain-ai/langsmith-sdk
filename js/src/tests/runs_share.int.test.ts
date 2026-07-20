/**
 * Smoke integration tests for the v2 runs.share resource.
 *
 * Covers `Client.runs.share` (create, delete) against a live backend.
 */
import { Client } from "../client.js";
import { v4 as uuidv4 } from "../utils/uuid/src/index.js";
import { deleteProject, pollRunsUntilCount, waitUntil } from "./utils.js";

async function setUpProjectWithRun(client: Client) {
  const projectName = `__test_v2_runs_share_${uuidv4().slice(0, 12)}`;
  if (await client.hasProject({ projectName })) {
    await deleteProject(client, projectName);
  }

  const runId = uuidv4();
  const now = new Date();
  await client.createRun({
    id: runId,
    name: "run_1",
    inputs: { i: 1 },
    run_type: "llm",
    project_name: projectName,
    start_time: now.getTime(),
  });
  await pollRunsUntilCount(client, projectName, 1, 30_000);

  const run = await client.readRun(runId);
  const project = await client.readProject({ projectName });
  return {
    projectName,
    runId,
    traceId: run.trace_id ?? runId,
    projectId: project.id,
  };
}

test("runs.share.create mints a share token for a run's trace root", async () => {
  const client = new Client({
    autoBatchTracing: false,
    callerOptions: { maxRetries: 6 },
  });
  const { projectName, runId, traceId, projectId } =
    await setUpProjectWithRun(client);
  try {
    let shareToken: string | undefined;
    // share.create resolves the trace root from SmithDB, which may lag indexing.
    await waitUntil(
      async () => {
        const resp = await client.runs.share.create(runId, {
          session_id: projectId,
          trace_id: traceId,
        });
        shareToken = resp.share_token;
        return !!shareToken;
      },
      90_000,
      3_000,
    );
    expect(shareToken).toBeDefined();
    expect(typeof shareToken).toBe("string");
  } finally {
    await deleteProject(client, projectName);
  }
});

test("runs.share.delete removes the share token and is idempotent", async () => {
  const client = new Client({
    autoBatchTracing: false,
    callerOptions: { maxRetries: 6 },
  });
  const { projectName, runId, traceId, projectId } =
    await setUpProjectWithRun(client);
  try {
    await waitUntil(
      async () => {
        const resp = await client.runs.share.create(runId, {
          session_id: projectId,
          trace_id: traceId,
        });
        return !!resp.share_token;
      },
      90_000,
      3_000,
    );

    // Delete resolves (204) and is idempotent: a second delete also succeeds.
    // Success is "does not reject".
    await client.runs.share.delete(traceId, { session_id: projectId });
    await client.runs.share.delete(traceId, { session_id: projectId });
  } finally {
    await deleteProject(client, projectName);
  }
});
