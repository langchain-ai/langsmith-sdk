import type { Run as V2Run } from "../_openapi_client/resources/runs/runs.js";
import type { TracerSession } from "../schemas.js";
import { v2RunToRun } from "../utils/v2_migration.js";

const project: TracerSession = {
  id: "00000000-0000-0000-0000-000000000001",
  tenant_id: "00000000-0000-0000-0000-000000000002",
  start_time: 0,
  end_time: 1_000,
};

const v2Run: V2Run = {
  id: "00000000-0000-0000-0000-000000000003",
  name: "root",
  run_type: "CHAIN",
  start_time: "1970-01-01T00:00:00.000Z",
  trace_id: "00000000-0000-0000-0000-000000000003",
  project_id: project.id,
  parent_run_ids: [],
  reference_example_id: "00000000-0000-0000-0000-000000000004",
  inputs: { question: "test" },
  outputs: { answer: "test" },
  status: "SUCCESS",
};

describe("v2 migration utils", () => {
  test("maps generated v2 runs to legacy runs", () => {
    expect(v2RunToRun(v2Run)).toEqual(
      expect.objectContaining({
        id: v2Run.id,
        session_id: project.id,
        run_type: "chain",
        status: "success",
        parent_run_id: undefined,
        inputs: v2Run.inputs,
        outputs: v2Run.outputs,
      }),
    );
  });
});
