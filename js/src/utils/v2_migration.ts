import type {
  Run as V2Run,
  RunSelectField,
} from "../_openapi_client/resources/runs/runs.js";
import type { Client } from "../client.js";
import type { Run, TracerSession } from "../schemas.js";

// Omitting selects from `/v2/runs/query` returns only the run ID.
export const V2_RUN_SELECTS: RunSelectField[] = [
  "ID",
  "NAME",
  "RUN_TYPE",
  "STATUS",
  "START_TIME",
  "END_TIME",
  "INPUTS",
  "OUTPUTS",
  "PARENT_RUN_IDS",
  "PROJECT_ID",
  "TRACE_ID",
  "DOTTED_ORDER",
  "REFERENCE_EXAMPLE_ID",
  "ERROR",
];

export function v2RunToRun(run: V2Run): Run {
  if (run.id == null || run.name == null || run.run_type == null) {
    throw new Error("V2 run response is missing required fields.");
  }
  return {
    id: run.id,
    name: run.name,
    run_type: run.run_type.toLowerCase(),
    start_time: run.start_time,
    end_time: run.end_time,
    trace_id: run.trace_id,
    session_id: run.project_id,
    parent_run_id: run.parent_run_ids?.at(-1),
    dotted_order: run.dotted_order,
    reference_example_id: run.reference_example_id,
    inputs: run.inputs ?? {},
    outputs: run.outputs,
    error: run.error ?? undefined,
    status: run.status?.toLowerCase(),
  };
}

export async function loadTracesV2(
  client: Client,
  project: TracerSession,
  options: { isRoot?: boolean },
): Promise<Run[]> {
  const runs: Run[] = [];
  const pager = client.runs.queryV2({
    project_ids: [project.id],
    min_start_time: new Date(project.start_time).toISOString(),
    max_start_time: new Date(project.end_time ?? Date.now()).toISOString(),
    is_root: options.isRoot,
    selects: V2_RUN_SELECTS,
  });
  for await (const run of pager) {
    runs.push(v2RunToRun(run));
  }
  return runs;
}
