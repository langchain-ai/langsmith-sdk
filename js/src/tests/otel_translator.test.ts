import { describe, expect, it } from "@jest/globals";
import { LangSmithToOTELTranslator } from "../experimental/otel/translator.js";
import * as constants from "../experimental/otel/constants.js";

type Attributes = Record<string, unknown>;

function makeSpan() {
  const attrs: Attributes = {};
  return {
    attributes: attrs,
    setAttribute(key: string, value: unknown) {
      attrs[key] = value;
    },
    setStatus() {},
    recordException() {},
    end() {},
  };
}

function makeRunCreate(extra: Record<string, unknown> = {}) {
  return {
    id: "test-id",
    name: "test",
    run_type: "llm",
    inputs: {},
    start_time: Date.now(),
    extra,
    tags: [],
  };
}

describe("LangSmithToOTELTranslator - gen_ai.system from ls_provider", () => {
  it("uses ls_provider=anthropic over model-name heuristics", () => {
    const translator = new LangSmithToOTELTranslator();
    const span = makeSpan();
    const runCreate = makeRunCreate({
      metadata: {
        ls_provider: "anthropic",
        ls_model_name: "claude-haiku-4-5",
      },
    });

    // Access the private method via exportBatch by providing a mock OTel context
    // We exercise it indirectly by checking the exported span attributes via
    // a spy on span.setAttribute.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (translator as any).setSpanAttributes(span, runCreate, {
      operation: "post",
      id: "test-id",
      trace_id: "trace-id",
      run: runCreate,
    });

    expect(span.attributes[constants.GEN_AI_SYSTEM]).toBe("anthropic");
  });

  it("uses ls_provider=openai to set gen_ai.system=openai", () => {
    const translator = new LangSmithToOTELTranslator();
    const span = makeSpan();
    const runCreate = makeRunCreate({
      metadata: {
        ls_provider: "openai",
        ls_model_name: "gpt-4.1",
      },
    });

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (translator as any).setSpanAttributes(span, runCreate, {
      operation: "post",
      id: "test-id",
      trace_id: "trace-id",
      run: runCreate,
    });

    expect(span.attributes[constants.GEN_AI_SYSTEM]).toBe("openai");
  });

  it("falls back to model-name heuristics when ls_provider is absent", () => {
    const translator = new LangSmithToOTELTranslator();
    const span = makeSpan();
    const runCreate = makeRunCreate({
      metadata: {
        ls_model_name: "claude-3-5-sonnet-20241022",
      },
    });

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (translator as any).setSpanAttributes(span, runCreate, {
      operation: "post",
      id: "test-id",
      trace_id: "trace-id",
      run: runCreate,
    });

    expect(span.attributes[constants.GEN_AI_SYSTEM]).toBe("anthropic");
  });

  it("falls back to langchain when ls_provider is absent and model name is unrecognized", () => {
    const translator = new LangSmithToOTELTranslator();
    const span = makeSpan();
    const runCreate = makeRunCreate({
      metadata: {
        ls_model_name: "some-custom-model",
      },
    });

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (translator as any).setSpanAttributes(span, runCreate, {
      operation: "post",
      id: "test-id",
      trace_id: "trace-id",
      run: runCreate,
    });

    expect(span.attributes[constants.GEN_AI_SYSTEM]).toBe("langchain");
  });

  it("uses ls_provider=anthropic even when model name alias does not contain 'claude'", () => {
    const translator = new LangSmithToOTELTranslator();
    const span = makeSpan();
    const runCreate = makeRunCreate({
      metadata: {
        ls_provider: "anthropic",
        ls_model_name: "haiku-4-5",
      },
    });

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (translator as any).setSpanAttributes(span, runCreate, {
      operation: "post",
      id: "test-id",
      trace_id: "trace-id",
      run: runCreate,
    });

    expect(span.attributes[constants.GEN_AI_SYSTEM]).toBe("anthropic");
  });
});
