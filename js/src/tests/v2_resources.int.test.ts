/**
 * Integration tests for v2 OpenAPI client resources exposed on the JS Client:
 * client.runs
 */

import { Client } from "../client.js";
import { v4 as uuidv4 } from "../utils/uuid/src/index.js";
import { deleteProject } from "./utils.js";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function projectName(suffix: string): string {
  return `__test_v2_resources_${suffix}_${uuidv4().replace(/-/g, "")}`;
}

/**
 * Tries to get a project's UUID, retrying until found.
 * Returns null if the API key lacks projects:read permission (403).
 */
async function getProjectId(
  client: Client,
  proj: string,
  maxRetries = 30,
  sleepMs = 2000,
): Promise<string | null> {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const project = await client.readProject({ projectName: proj });
      return String(project.id);
    } catch (e: any) {
      const msg = String(e?.message ?? e);
      if (msg.includes("403") || msg.includes("projects:read")) {
        return null;
      }
    }
    await new Promise((r) => setTimeout(r, sleepMs));
  }
  throw new Error(`Project "${proj}" not found after ${maxRetries} retries`);
}

/**
 * Creates a root run via the legacy client.
 * Returns { traceId, projectId, startTime }.
 * projectId is null when the API key lacks projects:read permission.
 */
async function postTrace(
  client: Client,
  proj: string,
): Promise<{ traceId: string; projectId: string | null; startTime: Date }> {
  const traceId = uuidv4();
  const startTime = new Date();
  await client.createRun({
    id: traceId,
    name: "root_run",
    run_type: "chain",
    inputs: { input: "hello" },
    outputs: { result: "ok" },
    start_time: startTime.getTime(),
    end_time: new Date().getTime(),
    project_name: proj,
  });
  const projectId = await getProjectId(client, proj);
  return { traceId, projectId, startTime };
}

// ---------------------------------------------------------------------------
// runs resource
// ---------------------------------------------------------------------------

describe("client.runs v2 resource", () => {
  let client: Client;

  beforeAll(() => {
    client = new Client();
  });

  test("queryV2 (alias: query)", async () => {
    const proj = projectName("runs_query");
    const { traceId, projectId } = await postTrace(client, proj);
    if (!projectId) {
      console.warn(
        "SKIPPED: requires projects:read permission (service key limitation)",
      );
      await deleteProject(client, proj);
      return;
    }
    const runs: unknown[] = [];
    for await (const run of client.runs.query({
      project_ids: [projectId],
      selects: ["ID", "NAME", "RUN_TYPE", "TRACE_ID"],
    })) {
      runs.push(run);
    }
    expect(runs.length).toBeGreaterThanOrEqual(1);
    const traceIds = runs.map((r: any) => r.trace_id);
    expect(traceIds).toContain(traceId);
    await deleteProject(client, proj);
  });

  test("retrieveV2 (alias: retrieve)", async () => {
    const proj = projectName("runs_retrieve");
    const { traceId, projectId, startTime } = await postTrace(client, proj);
    if (!projectId) {
      console.warn(
        "SKIPPED: requires projects:read permission (service key limitation)",
      );
      await deleteProject(client, proj);
      return;
    }
    let run: any;
    for (let i = 0; i < 30; i++) {
      try {
        run = await client.runs.retrieve(traceId, {
          project_id: projectId,
          start_time: startTime.toISOString(),
        });
        if (run?.id === traceId) break;
      } catch {
        // not indexed yet
      }
      await new Promise((r) => setTimeout(r, 2000));
    }
    expect(run?.id).toBe(traceId);
    await deleteProject(client, proj);
  });

});

