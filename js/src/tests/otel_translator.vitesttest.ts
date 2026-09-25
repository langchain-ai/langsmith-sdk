/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { LangSmithToOTELTranslator } from "../experimental/otel/translator.js";
import * as otelSingleton from "../singletons/otel.js";

// Minimal span mock that records everything set on it
function makeSpanMock() {
  const attributes: Record<string, any> = {};
  const statusHistory: { code: number; message?: string }[] = [];
  const exceptions: (Error | string)[] = [];
  let endTime: number | Date | undefined;

  return {
    setAttribute: vi.fn((key: string, value: any) => {
      attributes[key] = value;
    }),
    setStatus: vi.fn((status: { code: number; message?: string }) => {
      statusHistory.push(status);
    }),
    recordException: vi.fn((e: Error | string) => {
      exceptions.push(e);
    }),
    end: vi.fn((t?: number | Date) => {
      endTime = t;
    }),
    // Inspection helpers
    _attributes: attributes,
    _statusHistory: statusHistory,
    _exceptions: exceptions,
    get _endTime() {
      return endTime;
    },
  };
}

// A minimal OTELContext stand-in — the translator treats it as opaque
const DUMMY_CONTEXT = {} as any;

function makeTranslator(span: ReturnType<typeof makeSpanMock>) {
  vi.spyOn(otelSingleton, "getOTELTrace").mockReturnValue({
    getSpan: vi.fn().mockReturnValue(span),
  } as any);

  return new LangSmithToOTELTranslator();
}

beforeEach(() => {
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Helpers to build minimal RunCreate / RunUpdate payloads
// ---------------------------------------------------------------------------
function makeRunCreate(overrides: Record<string, any> = {}) {
  return {
    id: "run-1",
    trace_id: "trace-1",
    name: "test-run",
    run_type: "llm",
    inputs: { messages: [{ role: "user", content: "hi" }], model: "gpt-4o" },
    start_time: new Date().toISOString(),
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("exportBatch — post operation", () => {
  it("sets basic span attributes from a RunCreate", () => {
    const span = makeSpanMock();
    const translator = makeTranslator(span);

    translator.exportBatch(
      [
        {
          operation: "post",
          id: "run-1",
          trace_id: "trace-1",
          run: makeRunCreate({ end_time: new Date().toISOString() }),
        },
      ],
      new Map([["run-1", DUMMY_CONTEXT]]),
    );

    expect(span.setAttribute).toHaveBeenCalledWith(
      "langsmith.span.kind",
      "llm",
    );
    expect(span.setAttribute).toHaveBeenCalledWith(
      "gen_ai.operation.name",
      "chat",
    );
    expect(span.setAttribute).toHaveBeenCalledWith(
      "langsmith.trace.name",
      "test-run",
    );
  });

  it("ends the span when end_time is present", () => {
    const span = makeSpanMock();
    const translator = makeTranslator(span);
    const endTime = new Date().toISOString();

    translator.exportBatch(
      [
        {
          operation: "post",
          id: "run-1",
          trace_id: "trace-1",
          run: makeRunCreate({ end_time: endTime }),
        },
      ],
      new Map([["run-1", DUMMY_CONTEXT]]),
    );

    expect(span.end).toHaveBeenCalledWith(new Date(endTime));
  });

  it("does NOT end the span when end_time is absent", () => {
    const span = makeSpanMock();
    const translator = makeTranslator(span);

    translator.exportBatch(
      [
        {
          operation: "post",
          id: "run-1",
          trace_id: "trace-1",
          run: makeRunCreate({ end_time: undefined }),
        },
      ],
      new Map([["run-1", DUMMY_CONTEXT]]),
    );

    expect(span.end).not.toHaveBeenCalled();
  });

  it("sets OK status when there is no error", () => {
    const span = makeSpanMock();
    const translator = makeTranslator(span);

    translator.exportBatch(
      [
        {
          operation: "post",
          id: "run-1",
          trace_id: "trace-1",
          run: makeRunCreate({ end_time: new Date().toISOString() }),
        },
      ],
      new Map([["run-1", DUMMY_CONTEXT]]),
    );

    expect(span.setStatus).toHaveBeenCalledWith({ code: 1 });
  });

  it("sets ERROR status and records exception when run has error", () => {
    const span = makeSpanMock();
    const translator = makeTranslator(span);

    translator.exportBatch(
      [
        {
          operation: "post",
          id: "run-1",
          trace_id: "trace-1",
          run: makeRunCreate({
            end_time: new Date().toISOString(),
            error: "Something went wrong",
          }),
        },
      ],
      new Map([["run-1", DUMMY_CONTEXT]]),
    );

    expect(span.setStatus).toHaveBeenCalledWith({ code: 2 });
    expect(span.recordException).toHaveBeenCalledWith(
      new Error("Something went wrong"),
    );
  });

  it("skips gracefully when context has no active span", () => {
    vi.spyOn(otelSingleton, "getOTELTrace").mockReturnValue({
      getSpan: vi.fn().mockReturnValue(undefined),
    } as any);
    const translator = new LangSmithToOTELTranslator();

    // Should not throw
    expect(() =>
      translator.exportBatch(
        [
          {
            operation: "post",
            id: "run-1",
            trace_id: "trace-1",
            run: makeRunCreate({ end_time: new Date().toISOString() }),
          },
        ],
        new Map([["run-1", DUMMY_CONTEXT]]),
      ),
    ).not.toThrow();
  });
});

describe("exportBatch — patch operation", () => {
  it("updates and ends an existing span on patch", () => {
    const span = makeSpanMock();
    const translator = makeTranslator(span);
    const endTime = new Date().toISOString();

    // First create the span (no end_time so it stays open)
    translator.exportBatch(
      [
        {
          operation: "post",
          id: "run-1",
          trace_id: "trace-1",
          run: makeRunCreate({ end_time: undefined }),
        },
      ],
      new Map([["run-1", DUMMY_CONTEXT]]),
    );

    expect(span.end).not.toHaveBeenCalled();

    // Then patch it with an end_time
    translator.exportBatch(
      [
        {
          operation: "patch",
          id: "run-1",
          trace_id: "trace-1",
          run: { end_time: endTime },
        },
      ],
      new Map(),
    );

    expect(span.end).toHaveBeenCalledWith(new Date(endTime));
  });
});

describe("usage_metadata", () => {
  it("sets langsmith.usage_metadata from extra.metadata", () => {
    const span = makeSpanMock();
    const translator = makeTranslator(span);
    const usageMetadata = {
      input_tokens: 100,
      output_tokens: 50,
      total_tokens: 150,
    };

    translator.exportBatch(
      [
        {
          operation: "post",
          id: "run-1",
          trace_id: "trace-1",
          run: makeRunCreate({
            end_time: new Date().toISOString(),
            extra: { metadata: { usage_metadata: usageMetadata } },
          }),
        },
      ],
      new Map([["run-1", DUMMY_CONTEXT]]),
    );

    expect(span._attributes["langsmith.usage_metadata"]).toBe(
      JSON.stringify(usageMetadata),
    );
  });

  it("also copies usage_metadata into langsmith.metadata.usage_metadata via the metadata loop", () => {
    const span = makeSpanMock();
    const translator = makeTranslator(span);
    const usageMetadata = {
      input_tokens: 10,
      output_tokens: 5,
      total_tokens: 15,
    };

    translator.exportBatch(
      [
        {
          operation: "post",
          id: "run-1",
          trace_id: "trace-1",
          run: makeRunCreate({
            end_time: new Date().toISOString(),
            extra: { metadata: { usage_metadata: usageMetadata } },
          }),
        },
      ],
      new Map([["run-1", DUMMY_CONTEXT]]),
    );

    expect(span._attributes["langsmith.metadata.usage_metadata"]).toBe(
      JSON.stringify(usageMetadata),
    );
  });
});

describe("metadata attributes", () => {
  it("writes arbitrary metadata keys under langsmith.metadata.*", () => {
    const span = makeSpanMock();
    const translator = makeTranslator(span);

    translator.exportBatch(
      [
        {
          operation: "post",
          id: "run-1",
          trace_id: "trace-1",
          run: makeRunCreate({
            end_time: new Date().toISOString(),
            extra: {
              metadata: {
                ls_model_name: "gpt-4o",
                custom_tag: "foo",
                complex: { nested: { value: "test" } },
              },
            },
          }),
        },
      ],
      new Map([["run-1", DUMMY_CONTEXT]]),
    );

    expect(span._attributes["langsmith.metadata.ls_model_name"]).toBe("gpt-4o");
    expect(span._attributes["langsmith.metadata.custom_tag"]).toBe("foo");
    expect(span._attributes["langsmith.metadata.complex"]).toBe(
      JSON.stringify({ nested: { value: "test" } }),
    );
  });
});

describe("token counts from outputs", () => {
  it("extracts token counts from outputs.usage_metadata", () => {
    const span = makeSpanMock();
    const translator = makeTranslator(span);

    translator.exportBatch(
      [
        {
          operation: "post",
          id: "run-1",
          trace_id: "trace-1",
          run: makeRunCreate({
            end_time: new Date().toISOString(),
            outputs: {
              usage_metadata: { input_tokens: 200, output_tokens: 80 },
            },
          }),
        },
      ],
      new Map([["run-1", DUMMY_CONTEXT]]),
    );

    expect(span._attributes["gen_ai.usage.input_tokens"]).toBe(200);
    expect(span._attributes["gen_ai.usage.output_tokens"]).toBe(80);
    expect(span._attributes["gen_ai.usage.total_tokens"]).toBe(280);
  });

  it("overrides usage from metadata if present in outputs", () => {
    const span = makeSpanMock();
    const translator = makeTranslator(span);

    translator.exportBatch(
      [
        {
          operation: "post",
          id: "run-1",
          trace_id: "trace-1",
          run: makeRunCreate({
            end_time: new Date().toISOString(),
            outputs: {
              // Explicitly set usage in outputs
              usage_metadata: {
                input_tokens: 200,
                output_tokens: 80,
                total_tokens: 280,
              },
            },
            extra: {
              metadata: {
                usage_metadata: {
                  input_tokens: 0,
                  output_tokens: 0,
                  total_tokens: 0,
                },
              },
            },
          }),
        },
      ],
      new Map([["run-1", DUMMY_CONTEXT]]),
    );

    expect(span._attributes["langsmith.usage_metadata"]).toBe(
      JSON.stringify({
        input_tokens: 200,
        output_tokens: 80,
        total_tokens: 280,
      }),
    );

    expect(span._attributes["gen_ai.usage.input_tokens"]).toBe(200);
    expect(span._attributes["gen_ai.usage.output_tokens"]).toBe(80);
    expect(span._attributes["gen_ai.usage.total_tokens"]).toBe(280);
  });
});

function attributesForRun(overrides: Record<string, any>) {
  const span = makeSpanMock();
  makeTranslator(span).exportBatch(
    [
      {
        operation: "post",
        id: "run-1",
        trace_id: "trace-1",
        run: makeRunCreate({
          end_time: new Date().toISOString(),
          ...overrides,
        }),
      },
    ],
    new Map([["run-1", DUMMY_CONTEXT]]),
  );
  return span._attributes;
}

describe("tool attributes", () => {
  it("sets tool name and call id on tool runs", () => {
    const attrs = attributesForRun({
      run_type: "tool",
      name: "Bash",
      extra: { metadata: { tool_call_id: "toolu_123" } },
    });

    expect(attrs["gen_ai.tool.name"]).toBe("Bash");
    expect(attrs["gen_ai.tool.call.id"]).toBe("toolu_123");
  });

  it("omits tool name and call id on non-tool runs", () => {
    const attrs = attributesForRun({
      name: "Bash",
      extra: { metadata: { tool_call_id: "toolu_123" } },
    });

    expect(attrs).not.toHaveProperty("gen_ai.tool.name");
    expect(attrs).not.toHaveProperty("gen_ai.tool.call.id");
  });

  it("passes tool definitions through in provider shapes", () => {
    const tools = [
      {
        type: "function",
        function: {
          name: "get_weather",
          description: "Get the weather",
          parameters: { type: "object", properties: {} },
        },
      },
      { name: "search", description: "Search", input_schema: {} },
      { type: "tool_search" },
    ];
    const attrs = attributesForRun({ extra: { invocation_params: { tools } } });

    expect(JSON.parse(attrs["gen_ai.tool.definitions"])).toEqual(tools);
  });

  it.each([
    {},
    { invocation_params: {} },
    { invocation_params: { tools: [] } },
  ])("omits tool definitions without tools (%j)", (extra) => {
    expect(attributesForRun({ extra })).not.toHaveProperty(
      "gen_ai.tool.definitions",
    );
  });
});
