import { jest } from "@jest/globals";
import type { Run as V2Run } from "../_openapi_client/resources/runs/runs.js";
import type { Client } from "../client.js";
import type { Run, TracerSession } from "../schemas.js";
import { loadTraces, v2RunToRun } from "../utils/v2_migration.js";

async function* fromArray<T>(items: T[]): AsyncGenerator<T> {
  yield* items;
}

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
        parent_run_id: undefined,
        inputs: v2Run.inputs,
        outputs: v2Run.outputs,
      }),
    );
  });

  test("loads runs from v2 when SDB querying is enabled", async () => {
    const queryV2 = jest.fn(() => fromArray([v2Run]));
    const listRuns = jest.fn();
    const client = {
      _supportsSDBQuery: async () => true,
      runs: { queryV2 },
      listRuns,
    } as unknown as Client;

    const runs = await loadTraces(client, project, { loadNested: false });

    expect(runs).toHaveLength(1);
    expect(runs[0].session_id).toBe(project.id);
    expect(queryV2).toHaveBeenCalledWith(
      expect.objectContaining({
        project_ids: [project.id],
        min_start_time: "1970-01-01T00:00:00.000Z",
        max_start_time: "1970-01-01T00:00:01.000Z",
        is_root: true,
      }),
    );
    expect(listRuns).not.toHaveBeenCalled();
  });

  test("loads and nests runs from v1 when SDB querying is disabled", async () => {
    const root: Run = {
      id: "00000000-0000-0000-0000-000000000005",
      name: "root",
      run_type: "chain",
      inputs: {},
    };
    const child: Run = {
      id: "00000000-0000-0000-0000-000000000006",
      name: "child",
      run_type: "tool",
      inputs: {},
      parent_run_id: root.id,
      dotted_order: "2",
    };
    const listRuns = jest.fn(() => fromArray([child, root]));
    const queryV2 = jest.fn();
    const client = {
      _supportsSDBQuery: async () => false,
      runs: { queryV2 },
      listRuns,
    } as unknown as Client;

    const runs = await loadTraces(client, project, { loadNested: true });

    expect(runs).toEqual([root]);
    expect(root.child_runs).toEqual([child]);
    expect(listRuns).toHaveBeenCalledWith({
      projectId: project.id,
      executionOrder: undefined,
    });
    expect(queryV2).not.toHaveBeenCalled();
  });
});
