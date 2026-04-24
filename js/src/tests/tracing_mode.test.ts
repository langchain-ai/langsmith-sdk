/* eslint-disable no-process-env */
import { resolveTracingMode } from "../utils/env.js";
import { Client } from "../client.js";

describe("resolveTracingMode", () => {
  const saved = { ...process.env };
  afterEach(() => {
    process.env = { ...saved };
  });

  it("defaults to langsmith", () => {
    delete process.env.LANGSMITH_TRACING_MODE;
    delete process.env.LANGCHAIN_TRACING_MODE;
    delete process.env.OTEL_ENABLED;
    delete process.env.LANGSMITH_OTEL_ENABLED;
    expect(resolveTracingMode()).toBe("langsmith");
  });

  it("returns explicit config value", () => {
    expect(resolveTracingMode("otel")).toBe("otel");
    expect(resolveTracingMode("langsmith")).toBe("langsmith");
  });

  it("reads LANGSMITH_TRACING_MODE env var", () => {
    process.env.LANGSMITH_TRACING_MODE = "otel";
    expect(resolveTracingMode()).toBe("otel");
  });

  it("falls back to legacy LANGSMITH_OTEL_ENABLED", () => {
    delete process.env.LANGSMITH_TRACING_MODE;
    process.env.LANGSMITH_OTEL_ENABLED = "true";
    expect(resolveTracingMode()).toBe("otel");
  });

  it("explicit config takes precedence over env var", () => {
    process.env.LANGSMITH_TRACING_MODE = "otel";
    expect(resolveTracingMode("langsmith")).toBe("langsmith");
  });

  it("throws on invalid env var value", () => {
    process.env.LANGSMITH_TRACING_MODE = "hybrid";
    expect(() => resolveTracingMode()).toThrow(
      "Invalid LANGSMITH_TRACING_MODE"
    );
  });
});

describe("Client.tracingMode", () => {
  it("defaults to langsmith", () => {
    const client = new Client({ apiKey: "test-key" });
    expect(client.tracingMode).toBe("langsmith");
  });

  it("respects explicit tracingMode config", () => {
    const client = new Client({ apiKey: "test-key", tracingMode: "otel" });
    expect(client.tracingMode).toBe("otel");
  });
});
