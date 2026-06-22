/**
 * Integration tests for v2 OpenAPI client resources exposed on the JS Client:
 * client.runs, client.threads, client.traces
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
 * Generates a dotted_order string matching the format expected by the backend:
 * `YYYYMMDDTHHmmssffffffZ{run_uuid}`
 * Python equivalent: `_create_current_dotted_order(start_time, run_id)`
 */
function makeDottedOrder(date: Date, runId: string): string {
  const pad = (n: number, len: number) => String(n).padStart(len, "0");
  const Y = date.getUTCFullYear();
  const M = pad(date.getUTCMonth() + 1, 2);
  const D = pad(date.getUTCDate(), 2);
  const h = pad(date.getUTCHours(), 2);
  const m = pad(date.getUTCMinutes(), 2);
  const s = pad(date.getUTCSeconds(), 2);
  const us = pad(date.getUTCMilliseconds() * 1000, 6);
  return `${Y}${M}${D}T${h}${m}${s}${us}Z${runId}`;
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

/**
 * Creates a run tagged with thread_id metadata.
 * projectId is null when the API key lacks projects:read permission.
 */
async function postThreadTrace(
  client: Client,
  proj: string,
  threadId: string,
): Promise<{ traceId: string; projectId: string | null; startTime: Date }> {
  const traceId = uuidv4();
  const startTime = new Date();
  await client.createRun({
    id: traceId,
    name: "thread_root",
    run_type: "chain",
    inputs: { q: "test" },
    outputs: { a: "answer" },
    start_time: startTime.getTime(),
    end_time: new Date().getTime(),
    project_name: proj,
    extra: { metadata: { thread_id: threadId } },
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

  test("create", async () => {
    const proj = projectName("runs_create");
    const runId = uuidv4();
    const now = new Date().toISOString();
    const resp = await client.runs.create({
      id: runId,
      name: "test_run_create",
      run_type: "chain",
      inputs: { x: 1 },
      start_time: now,
      session_name: proj,
    });
    expect(resp).toBeDefined();
    await deleteProject(client, proj);
  });

  test("update", async () => {
    const proj = projectName("runs_update");
    const runId = uuidv4();
    const now = new Date().toISOString();
    await client.runs.create({
      id: runId,
      name: "update_run",
      run_type: "chain",
      inputs: { x: 1 },
      start_time: now,
      session_name: proj,
    });
    const resp = await client.runs.update(runId, {
      outputs: { y: 2 },
      end_time: new Date().toISOString(),
    });
    expect(resp).toBeDefined();
    await deleteProject(client, proj);
  });

  test("ingestBatch", async () => {
    const proj = projectName("runs_batch");
    const runId1 = uuidv4();
    const runId2 = uuidv4();
    const now = new Date();
    const resp = await client.runs.ingestBatch({
      post: [
        {
          id: runId1,
          trace_id: runId1,
          dotted_order: makeDottedOrder(now, runId1),
          name: "batch_run_1",
          run_type: "chain",
          inputs: { n: 1 },
          start_time: now.toISOString(),
          session_name: proj,
        },
        {
          id: runId2,
          trace_id: runId2,
          dotted_order: makeDottedOrder(now, runId2),
          name: "batch_run_2",
          run_type: "llm",
          inputs: { n: 2 },
          start_time: now.toISOString(),
          session_name: proj,
        },
      ],
    });
    expect(resp).toBeDefined();
    await deleteProject(client, proj);
  });

  test("queryV2 (alias: query)", async () => {
    const proj = projectName("runs_query");
    const { traceId, projectId } = await postTrace(client, proj);
    if (!projectId) {
      console.warn("SKIPPED: requires projects:read permission (service key limitation)");
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
    const runId = uuidv4();
    const now = new Date();
    const nowIso = now.toISOString();
    await client.runs.create({
      id: runId,
      name: "retrieve_run",
      run_type: "chain",
      inputs: { x: 1 },
      start_time: nowIso,
      session_name: proj,
    });
    const projectId = await getProjectId(client, proj);
    if (!projectId) {
      console.warn("SKIPPED: requires projects:read permission (service key limitation)");
      await deleteProject(client, proj);
      return;
    }
    let run: any;
    for (let i = 0; i < 30; i++) {
      try {
        run = await client.runs.retrieve(runId, {
          project_id: projectId,
          start_time: nowIso,
        });
        if (run?.id === runId) break;
      } catch {
        // not indexed yet
      }
      await new Promise((r) => setTimeout(r, 2000));
    }
    expect(run?.id).toBe(runId);
    await deleteProject(client, proj);
  });

  test("stats", async () => {
    const proj = projectName("runs_stats");
    const { projectId } = await postTrace(client, proj);
    if (!projectId) {
      console.warn("SKIPPED: requires projects:read permission (service key limitation)");
      await deleteProject(client, proj);
      return;
    }
    const stats = await client.runs.stats({ session: [projectId] });
    expect(stats).toBeDefined();
    await deleteProject(client, proj);
  });

  test("update2", async () => {
    const proj = projectName("runs_update2");
    const runId = uuidv4();
    const now = new Date().toISOString();
    await client.runs.create({
      id: runId,
      name: "update2_run",
      run_type: "chain",
      inputs: { x: 1 },
      start_time: now,
      session_name: proj,
    });
    // PATCH endpoint requires at least an empty JSON body
    const resp = await client.runs.update2(runId, { body: {} });
    expect(resp).toBeDefined();
    await deleteProject(client, proj);
  });
});

// ---------------------------------------------------------------------------
// threads resource
// ---------------------------------------------------------------------------

describe("client.threads v2 resource", () => {
  let client: Client;

  beforeAll(() => {
    client = new Client();
  });

  test("query", async () => {
    const proj = projectName("threads_query");
    const { projectId } = await postTrace(client, proj);
    if (!projectId) {
      console.warn("SKIPPED: requires projects:read permission (service key limitation)");
      await deleteProject(client, proj);
      return;
    }
    const threads: unknown[] = [];
    for await (const thread of client.threads.query({ project_id: projectId })) {
      threads.push(thread);
    }
    expect(Array.isArray(threads)).toBe(true);
    await deleteProject(client, proj);
  });

  test("traces.list", async () => {
    const proj = projectName("threads_traces");
    const threadId = uuidv4();
    const { projectId } = await postThreadTrace(client, proj, threadId);
    if (!projectId) {
      console.warn("SKIPPED: requires projects:read permission (service key limitation)");
      await deleteProject(client, proj);
      return;
    }
    const traces: unknown[] = [];
    for await (const trace of client.threads.traces.list(threadId, {
      project_id: projectId,
    })) {
      traces.push(trace);
    }
    expect(Array.isArray(traces)).toBe(true);
    await deleteProject(client, proj);
  });
});

// ---------------------------------------------------------------------------
// traces resource
// ---------------------------------------------------------------------------

describe("client.traces v2 resource", () => {
  let client: Client;

  beforeAll(() => {
    client = new Client();
  });

  test("runs.list", async () => {
    const proj = projectName("traces_runs");
    const { traceId, projectId, startTime } = await postTrace(client, proj);
    if (!projectId) {
      console.warn("SKIPPED: requires projects:read permission (service key limitation)");
      await deleteProject(client, proj);
      return;
    }
    const result = await client.traces.runs.list(traceId, {
      project_id: projectId,
      min_start_time: startTime.toISOString(),
      max_start_time: new Date().toISOString(),
      selects: ["ID", "NAME", "RUN_TYPE"],
    });
    expect(result).toBeDefined();
    await deleteProject(client, proj);
  });
});
