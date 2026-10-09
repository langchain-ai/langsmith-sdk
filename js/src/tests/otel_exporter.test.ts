/* eslint-disable no-process-env */
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  jest,
  test,
} from "@jest/globals";
import { createServer, type IncomingHttpHeaders } from "node:http";
import type { AddressInfo } from "node:net";
import { AgentAddress } from "../address.js";
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

describe("agent addressing", () => {
  beforeEach(() => {
    for (const name of [
      "LANGSMITH_PROJECT",
      "LANGCHAIN_PROJECT",
      "LANGCHAIN_SESSION",
      "LANGSMITH_AGENT_ID",
      "LANGSMITH_AGENT_ENVIRONMENT",
    ]) {
      delete process.env[name];
    }
  });

  async function exportedHeaders(
    config?: ConstructorParameters<typeof LangSmithOTLPTraceExporter>[0],
  ): Promise<IncomingHttpHeaders> {
    let headers: IncomingHttpHeaders = {};
    const server = createServer((request, response) => {
      headers = request.headers;
      request.resume();
      response.writeHead(200, { "Content-Type": "application/x-protobuf" });
      response.end();
    });
    await new Promise<void>((resolve) =>
      server.listen(0, "127.0.0.1", resolve),
    );
    process.env.LANGSMITH_ENDPOINT = `http://127.0.0.1:${
      (server.address() as AddressInfo).port
    }`;
    const exporter = new LangSmithOTLPTraceExporter(config);
    try {
      await new Promise((resolve) => exporter.export([], resolve));
      return headers;
    } finally {
      await exporter.shutdown();
      await new Promise<void>((resolve, reject) => {
        server.close((error) => (error ? reject(error) : resolve()));
      });
    }
  }

  test("sends the configured agent environment as headers", async () => {
    const headers = await exportedHeaders({
      address: new AgentAddress("support-agent", "Staging"),
    });

    expect(headers["langsmith-agent-id"]).toBe("support-agent");
    expect(headers["langsmith-agent-environment"]).toBe("staging");
  });

  test("takes the env agent when nothing is named", async () => {
    process.env.LANGSMITH_AGENT_ID = "support-agent";
    process.env.LANGSMITH_AGENT_ENVIRONMENT = "production";

    const headers = await exportedHeaders();

    expect(headers["langsmith-agent-id"]).toBe("support-agent");
    expect(headers["langsmith-agent-environment"]).toBe("production");
  });

  test("keeps explicit headers beside the agent headers", async () => {
    const headers = await exportedHeaders({
      address: new AgentAddress("support-agent", "staging"),
      headers: { "x-api-key": "explicit-key" },
    });

    expect(headers["x-api-key"]).toBe("explicit-key");
    expect(headers["langsmith-agent-id"]).toBe("support-agent");
  });

  test("an explicit project beats the env agent", async () => {
    process.env.LANGSMITH_AGENT_ID = "support-agent";
    process.env.LANGSMITH_AGENT_ENVIRONMENT = "production";

    const headers = await exportedHeaders({ projectName: "mine" });

    expect(headers["langsmith-agent-id"]).toBeUndefined();
    expect(headers["langsmith-agent-environment"]).toBeUndefined();
  });

  test("sends no agent headers for a project", async () => {
    process.env.LANGSMITH_PROJECT = "from-env";

    const headers = await exportedHeaders();

    expect(headers["langsmith-agent-id"]).toBeUndefined();
  });

  test("rejects a project and an address", () => {
    expect(
      () =>
        new LangSmithOTLPTraceExporter({
          projectName: "mine",
          address: new AgentAddress("support-agent", "staging"),
        }),
    ).toThrow(/project .* or to an address/);
  });

  test("rejects an env that names a project and an agent", () => {
    process.env.LANGSMITH_PROJECT = "from-env";
    process.env.LANGSMITH_AGENT_ID = "support-agent";
    process.env.LANGSMITH_AGENT_ENVIRONMENT = "production";

    expect(() => new LangSmithOTLPTraceExporter()).toThrow(
      /project .* or to an address/,
    );
  });
});
