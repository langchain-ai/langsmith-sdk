/* eslint-disable no-process-env */
import { afterEach, beforeEach, expect, jest, test } from "@jest/globals";
import { createServer } from "node:http";
import type { AddressInfo } from "node:net";
import { LangSmithOTLPTraceExporter } from "../experimental/otel/exporter.js";
import { _resetWarnedMessages } from "../utils/warn.js";

beforeEach(() => {
  _resetWarnedMessages();
  jest.spyOn(console, "warn").mockImplementation(() => {});
  jest.replaceProperty(process, "env", { ...process.env });
  delete process.env.OTEL_EXPORTER_OTLP_ENDPOINT;
  delete process.env.OTEL_EXPORTER_OTLP_TRACES_ENDPOINT;
  delete process.env.OTEL_EXPORTER_OTLP_HEADERS;
  process.env.LANGSMITH_TRACING = "true";
  process.env.LANGSMITH_API_KEY = "test-key";
});

afterEach(() => {
  jest.restoreAllMocks();
});

test.each([
  { name: "LangSmith default", expectedPath: "/otel/v1/traces" },
  { name: "base endpoint", basePath: "", expectedPath: "/v1/traces" },
  {
    name: "base endpoint with trailing slash",
    basePath: "/otel/",
    expectedPath: "/otel/v1/traces",
  },
  {
    name: "legacy full traces URL",
    basePath: "/otel/v1/traces",
    expectedPath: "/otel/v1/traces",
  },
  {
    name: "legacy custom traces URL",
    basePath: "/custom/traces",
    expectedPath: "/custom/traces",
  },
  {
    name: "base endpoint without traces path segment",
    basePath: "/not-traces",
    expectedPath: "/not-traces/v1/traces",
  },
  {
    name: "trace-specific endpoint",
    tracesPath: "/custom/traces",
    expectedPath: "/custom/traces",
  },
  {
    name: "trace-specific endpoint overrides base",
    basePath: "/ignored/traces",
    tracesPath: "/otel/v1/traces",
    expectedPath: "/otel/v1/traces",
  },
  {
    name: "explicit URL overrides environment",
    basePath: "/ignored/traces",
    tracesPath: "/also-ignored",
    configPath: "/explicit/traces",
    expectedPath: "/explicit/traces",
  },
])("exports to the resolved URL: $name", async (options) => {
  let requestPath: string | undefined;
  let requestMethod: string | undefined;
  const server = createServer((request, response) => {
    requestPath = request.url;
    requestMethod = request.method;
    request.resume();
    response.writeHead(200, { "Content-Type": "application/x-protobuf" });
    response.end();
  });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const baseUrl = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
  process.env.LANGSMITH_ENDPOINT = `${baseUrl}/`;
  if (options.basePath !== undefined) {
    process.env.OTEL_EXPORTER_OTLP_ENDPOINT = `${baseUrl}${options.basePath}`;
  }
  if (options.tracesPath !== undefined) {
    process.env.OTEL_EXPORTER_OTLP_TRACES_ENDPOINT = `${baseUrl}${options.tracesPath}`;
  }
  const envBefore = { ...process.env };
  const exporter = new LangSmithOTLPTraceExporter(
    options.configPath === undefined
      ? undefined
      : { url: `${baseUrl}${options.configPath}` },
  );
  try {
    const result = await new Promise<{ code: number }>((resolve) => {
      exporter.export([], resolve);
    });
    expect(result.code).toBe(0);
    expect(requestMethod).toBe("POST");
    expect(requestPath).toBe(options.expectedPath);
    expect(process.env).toEqual(envBefore);
    const shouldWarn =
      options.configPath === undefined &&
      options.tracesPath === undefined &&
      options.basePath?.endsWith("/traces");
    const secondExporter = new LangSmithOTLPTraceExporter(
      options.configPath === undefined
        ? undefined
        : { url: `${baseUrl}${options.configPath}` },
    );
    await secondExporter.shutdown();
    expect(console.warn).toHaveBeenCalledTimes(shouldWarn ? 1 : 0);
    if (shouldWarn) {
      expect(console.warn).toHaveBeenCalledWith(
        expect.stringContaining("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"),
      );
      expect(console.warn).toHaveBeenCalledWith(
        expect.stringContaining("preserved unchanged"),
      );
      expect(console.warn).toHaveBeenCalledWith(
        expect.stringContaining("removed in the v1 release"),
      );
    }
  } finally {
    await exporter.shutdown();
    await new Promise<void>((resolve, reject) => {
      server.close((error) => (error ? reject(error) : resolve()));
    });
  }
});
