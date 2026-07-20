/**
 * Smoke integration tests for the v2 public.runs resource.
 *
 * Covers `Client.public.runs` (retrieve, query) against a live backend. Public
 * shared-run reads are authenticated by the share token in the path; the
 * client's API key is used only to mint that token via runs.share.create.
 */
import { Client } from "../client.js";
import { v4 as uuidv4 } from "../utils/uuid/src/index.js";
import { deleteProject, pollRunsUntilCount, waitUntil } from "./utils.js";

// Public run fields to request; START_TIME is needed as the retrieve coordinate.
const SELECTS: Array<"ID" | "NAME" | "RUN_TYPE" | "STATUS" | "START_TIME"> = [
  "ID",
  "NAME",
  "RUN_TYPE",
  "STATUS",
  "START_TIME",
];

async function setUpSharedRun(client: Client) {
  const projectName = `__test_v2_public_runs_${uuidv4().slice(0, 12)}`;
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
  const traceId = run.trace_id ?? runId;

  let shareToken: string | undefined;
  // share.create resolves the trace root from SmithDB, which may lag indexing.
  await waitUntil(
    async () => {
      const resp = await client.runs.share.create(runId, {
        session_id: project.id,
        trace_id: traceId,
      });
      shareToken = resp.share_token;
      return !!shareToken;
    },
    90_000,
    3_000,
  );
  if (!shareToken) throw new Error("share.create did not return a share_token");

  return { projectName, runId, projectId: project.id, shareToken };
}

test("public.runs.query returns the shared trace's runs by share token", async () => {
  const client = new Client({
    autoBatchTracing: false,
    callerOptions: { maxRetries: 6 },
  });
  const { projectName, runId, shareToken } = await setUpSharedRun(client);
  try {
    let found = false;
    await waitUntil(
      async () => {
        const page = await client.public.runs.query(shareToken, {
          selects: SELECTS,
        });
        found = (page.items ?? []).some((i) => i.id === runId);
        return found;
      },
      90_000,
      3_000,
    );
    expect(found).toBe(true);
  } finally {
    await deleteProject(client, projectName);
  }
});

test("public.runs.retrieve returns a single run by share token, id, start_time", async () => {
  const client = new Client({
    autoBatchTracing: false,
    callerOptions: { maxRetries: 6 },
  });
  const { projectName, runId, shareToken } = await setUpSharedRun(client);
  try {
    let retrievedId: string | undefined;
    await waitUntil(
      async () => {
        // Derive the exact start_time coordinate from the public read path
        // itself, so it matches what the backend stored (retrieve is a point
        // lookup).
        const page = await client.public.runs.query(shareToken, {
          selects: SELECTS,
        });
        const item = (page.items ?? []).find((i) => i.id === runId);
        if (!item?.start_time) return false;
        const run = await client.public.runs.retrieve(runId, {
          share_token: shareToken,
          selects: SELECTS,
          start_time: item.start_time,
        });
        retrievedId = run.id;
        return retrievedId === runId;
      },
      90_000,
      3_000,
    );
    expect(retrievedId).toBe(runId);
  } finally {
    await deleteProject(client, projectName);
  }
});
