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

function makeV2Run(overrides: Partial<V2Run> = {}): V2Run {
  return { ...v2Run, ...overrides };
}

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

  // ---------------------------------------------------------------------------
  // run_type / status normalisation
  // ---------------------------------------------------------------------------

  test("lowercases run_type LLM", () => {
    expect(v2RunToRun(makeV2Run({ run_type: "LLM" })).run_type).toBe("llm");
  });

  test("lowercases status ERROR", () => {
    expect(v2RunToRun(makeV2Run({ status: "ERROR" })).status).toBe("error");
  });

  // ---------------------------------------------------------------------------
  // parent_run_id — last element of parent_run_ids
  // ---------------------------------------------------------------------------

  test("sets parent_run_id to the last element of parent_run_ids", () => {
    const grandparent = "00000000-0000-0000-0000-000000000010";
    const parent = "00000000-0000-0000-0000-000000000011";
    const result = v2RunToRun(
      makeV2Run({ parent_run_ids: [grandparent, parent] }),
    );
    expect(result.parent_run_id).toBe(parent);
  });

  test("parent_run_id is undefined for root runs", () => {
    const result = v2RunToRun(makeV2Run({ parent_run_ids: [] }));
    expect(result.parent_run_id).toBeUndefined();
  });

  // ---------------------------------------------------------------------------
  // tags / extra — passed through as-is
  // ---------------------------------------------------------------------------

  test("passes tags through", () => {
    const result = v2RunToRun(makeV2Run({ tags: ["prod", "v2"] }));
    expect(result.tags).toEqual(["prod", "v2"]);
  });

  test("tags is undefined when absent", () => {
    const result = v2RunToRun(makeV2Run({ tags: undefined }));
    expect(result.tags).toBeUndefined();
  });

  test("passes extra through", () => {
    const extra = { metadata: { env: "prod" } };
    const result = v2RunToRun(makeV2Run({ extra }));
    expect(result.extra).toEqual(extra);
  });

  // ---------------------------------------------------------------------------
  // events — typed cast, no serialization in JS
  // ---------------------------------------------------------------------------

  test("passes events through as-is", () => {
    const events = [{ name: "start", time: "2024-01-01T00:00:00Z" }];
    const result = v2RunToRun(makeV2Run({ events: events as V2Run["events"] }));
    expect(result.events).toEqual(events);
  });

  // ---------------------------------------------------------------------------
  // feedback_stats — converted to plain object via Object.fromEntries
  // ---------------------------------------------------------------------------

  test("converts feedback_stats to plain object", () => {
    const feedback_stats = {
      quality: { avg: 0.9, n: 10, mode: null, is_all_model: false },
    } as unknown as V2Run["feedback_stats"];
    const result = v2RunToRun(makeV2Run({ feedback_stats }));
    expect(result.feedback_stats).toBeDefined();
    expect(result.feedback_stats!["quality"]).toMatchObject({ avg: 0.9 });
  });

  test("feedback_stats is undefined when absent", () => {
    const result = v2RunToRun(makeV2Run({ feedback_stats: undefined }));
    expect(result.feedback_stats).toBeUndefined();
  });

  // ---------------------------------------------------------------------------
  // first_token_time — ISO string → ms timestamp
  // ---------------------------------------------------------------------------

  test("converts first_token_time ISO string to ms number", () => {
    const iso = "2024-06-01T12:00:00.000Z";
    const result = v2RunToRun(makeV2Run({ first_token_time: iso }));
    expect(result.first_token_time).toBe(new Date(iso).getTime());
    expect(typeof result.first_token_time).toBe("number");
  });

  test("first_token_time is undefined when absent", () => {
    const result = v2RunToRun(makeV2Run({ first_token_time: undefined }));
    expect(result.first_token_time).toBeUndefined();
  });

  // ---------------------------------------------------------------------------
  // app_path — passed through as-is
  // ---------------------------------------------------------------------------

  test("passes app_path through", () => {
    const app_path = "/o/my-org/projects/p/abc/r/run-id";
    const result = v2RunToRun(makeV2Run({ app_path }));
    expect(result.app_path).toBe(app_path);
  });

  // ---------------------------------------------------------------------------
  // token counts — passed through as-is
  // ---------------------------------------------------------------------------

  test("passes prompt_tokens through", () => {
    const result = v2RunToRun(makeV2Run({ prompt_tokens: 42 }));
    expect(result.prompt_tokens).toBe(42);
  });

  test("passes completion_tokens through", () => {
    const result = v2RunToRun(makeV2Run({ completion_tokens: 18 }));
    expect(result.completion_tokens).toBe(18);
  });

  test("passes total_tokens through", () => {
    const result = v2RunToRun(makeV2Run({ total_tokens: 60 }));
    expect(result.total_tokens).toBe(60);
  });

  test("token counts are undefined when absent", () => {
    const result = v2RunToRun(
      makeV2Run({
        prompt_tokens: undefined,
        completion_tokens: undefined,
        total_tokens: undefined,
      }),
    );
    expect(result.prompt_tokens).toBeUndefined();
    expect(result.completion_tokens).toBeUndefined();
    expect(result.total_tokens).toBeUndefined();
  });
});
