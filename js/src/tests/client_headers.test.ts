/* eslint-disable @typescript-eslint/no-explicit-any, no-process-env */
import {
  describe,
  it,
  expect,
  jest,
  beforeEach,
  afterEach,
} from "@jest/globals";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { Client } from "../client.js";

describe("caller-supplied headers", () => {
  const mockJsonResponse = () =>
    jest.fn(
      async () =>
        new Response("{}", {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
    );

  const requestHeaders = (mockFetch: jest.Mock): Headers => {
    const [, init] = mockFetch.mock.calls[0] as unknown as [
      RequestInfo | URL,
      RequestInit,
    ];
    return new Headers(init.headers);
  };

  it("forwards config.headers to the generated OpenAPI client", async () => {
    const mockFetch = mockJsonResponse();
    const client = new Client({
      apiUrl: "https://api.smith.langchain.com",
      apiKey: "test-api-key",
      headers: { "X-Corp-Trace": "abc123" },
      fetchImplementation: mockFetch as any,
    });

    await (client as any).openAPIClient.info.list();

    const headers = requestHeaders(mockFetch);
    expect(headers.get("x-corp-trace")).toBe("abc123");
    // The SDK's own auth header must survive.
    expect(headers.get("x-api-key")).toBe("test-api-key");
  });

  it("forwards fetchOptions.headers to the generated OpenAPI client", async () => {
    const mockFetch = mockJsonResponse();
    const client = new Client({
      apiKey: "test-api-key",
      fetchOptions: { headers: { "X-Corp-Trace": "abc123" } },
      fetchImplementation: mockFetch as any,
    });

    await (client as any).openAPIClient.info.list();

    expect(requestHeaders(mockFetch).get("x-corp-trace")).toBe("abc123");
  });

  it.each([
    ["config.headers", { headers: { "x-api-key": "hijacked" } }],
    [
      "fetchOptions.headers",
      { fetchOptions: { headers: { "x-api-key": "hijacked" } } },
    ],
  ])(
    "does not let %s override the auth header on the generated client",
    async (_name, config) => {
      const mockFetch = mockJsonResponse();
      const client = new Client({
        apiKey: "real-key",
        fetchImplementation: mockFetch as any,
        ...config,
      });

      await (client as any).openAPIClient.info.list();

      expect(requestHeaders(mockFetch).get("x-api-key")).toBe("real-key");
    },
  );

  it("keeps required headers when fetchOptions.headers is set on handwritten calls", async () => {
    const mockFetch = mockJsonResponse();
    const client = new Client({
      apiKey: "real-key",
      workspaceId: "11111111-1111-1111-1111-111111111111",
      fetchOptions: {
        headers: { "X-Corp-Trace": "abc123", "x-api-key": "hijacked" },
      },
      fetchImplementation: mockFetch as any,
    });

    await client.readProject({
      projectId: "22222222-2222-2222-2222-222222222222",
    });

    const headers = requestHeaders(mockFetch);
    expect(headers.get("x-corp-trace")).toBe("abc123");
    // Previously `...this.fetchOptions` replaced the whole header set.
    expect(headers.get("x-api-key")).toBe("real-key");
    expect(headers.get("x-tenant-id")).toBe(
      "11111111-1111-1111-1111-111111111111",
    );
  });

  it("rebuilds the generated client when headers are set after construction", async () => {
    const mockFetch = mockJsonResponse();
    const client = new Client({
      apiKey: "test-api-key",
      fetchImplementation: mockFetch as any,
    });

    client.headers = { "X-Corp-Trace": "set-later" };
    await (client as any).openAPIClient.info.list();

    expect(requestHeaders(mockFetch).get("x-corp-trace")).toBe("set-later");
  });

  it("picks up headers mutated through the getter, which never fires the setter", async () => {
    const mockFetch = mockJsonResponse();
    const client = new Client({
      apiKey: "test-api-key",
      headers: { "X-Corp-Trace": "initial" },
      fetchImplementation: mockFetch as any,
    });

    // `get headers` hands back the caller's own object by reference.
    client.headers["X-Corp-Trace"] = "mutated";
    client.headers["X-Added-Later"] = "added";
    await (client as any).openAPIClient.info.list();

    const headers = requestHeaders(mockFetch);
    expect(headers.get("x-corp-trace")).toBe("mutated");
    expect(headers.get("x-added-later")).toBe("added");
  });

  it("stops forwarding a caller Authorization once profile auth supplies one", async () => {
    const mockFetch = mockJsonResponse();
    const client = new Client({
      apiKey: undefined,
      headers: { Authorization: "Bearer caller-token" },
      fetchImplementation: mockFetch as any,
    });
    // A profile holding only a refresh token has no auth header yet, so the
    // caller's survives; once refreshed, the profile's must win instead.
    let profileHeader: { name: string; value: string } | undefined;
    (client as any).profileAuth = {
      currentAuthHeader: () => profileHeader,
      getAuthHeader: async () => profileHeader,
      isProfileAuthorizationHeader: (value: string) =>
        value === profileHeader?.value,
    };

    await (client as any).openAPIClient.info.list();
    expect(requestHeaders(mockFetch).get("authorization")).toBe(
      "Bearer caller-token",
    );

    profileHeader = { name: "Authorization", value: "Bearer profile-token" };
    const secondFetch = mockJsonResponse();
    (client as any).fetchImplementation = secondFetch;
    await (client as any).openAPIClient.info.list();

    // The generated client must not still be holding the stale snapshot.
    expect(requestHeaders(secondFetch).get("authorization")).toBe(
      "Bearer profile-token",
    );
  });

  it("rejects malformed caller-supplied header names", () => {
    expect(
      () =>
        new Client({
          apiKey: "test-api-key",
          fetchOptions: { headers: { "X-Bad\nInjected": "value" } },
        }),
    ).toThrow();
    expect(
      () =>
        new Client({
          apiKey: "test-api-key",
          headers: { "X-Bad\nInjected": "value" },
        }),
    ).toThrow();
    const client = new Client({ apiKey: "test-api-key" });
    expect(() => {
      client.headers = { "X-Bad\nInjected": "value" };
    }).toThrow();
  });
});

describe("caller-supplied header collisions", () => {
  it("overrides rather than appends when both channels set the same header", () => {
    const client = new Client({
      apiKey: "test-api-key",
      headers: { "X-Corp-Trace": "from-config" },
      fetchOptions: { headers: { "x-corp-trace": "from-fetch-options" } },
    });

    const merged = (client as any)._mergedHeaders;
    // A plain spread would leave both spellings and yield "a, b" once
    // `Headers` appends them.
    expect(new Headers(merged).get("x-corp-trace")).toBe("from-fetch-options");
  });

  it.each([
    ["config.headers", (h: Record<string, string>) => ({ headers: h })],
    [
      "fetchOptions.headers",
      (h: Record<string, string>) => ({ fetchOptions: { headers: h } }),
    ],
  ])(
    "resolves duplicate spellings within %s to the last value",
    (_name, build) => {
      const client = new Client({
        apiKey: "test-api-key",
        ...build({ "X-Corp-Trace": "first", "x-corp-trace": "second" }),
      });

      const merged = (client as any)._mergedHeaders;
      expect(new Headers(merged).get("x-corp-trace")).toBe("second");
    },
  );

  it.each([["x-api-key"], ["X-Api-Key"]])(
    "never lets a caller-supplied %s reach the required headers",
    (name) => {
      const client = new Client({
        apiKey: "real-key",
        headers: { [name]: "hijacked" },
      });

      const merged = (client as any)._mergedHeaders;
      expect(new Headers(merged).get("x-api-key")).toBe("real-key");
    },
  );
});

describe("caller-supplied credentials", () => {
  const originalEnv = process.env;
  let tempDir: string;

  beforeEach(() => {
    process.env = { ...originalEnv };
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "langsmith-caller-auth-"));
    // No configured credential of any kind: no env key, and a profile config
    // with no auth so the machine's real profile can't supply one.
    delete process.env.LANGSMITH_API_KEY;
    delete process.env.LANGCHAIN_API_KEY;
    delete process.env.LANGSMITH_PROFILE;
    delete process.env.LANGSMITH_WORKSPACE_ID;
    delete process.env.LANGCHAIN_WORKSPACE_ID;
    const configPath = path.join(tempDir, "config.json");
    fs.writeFileSync(configPath, `${JSON.stringify({ profiles: {} })}\n`);
    process.env.LANGSMITH_CONFIG_FILE = configPath;
  });

  afterEach(() => {
    fs.rmSync(tempDir, { recursive: true, force: true });
    process.env = originalEnv;
  });

  const mockJsonResponse = () =>
    jest.fn(
      async () =>
        new Response("{}", {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
    );

  it.each([
    ["Authorization", "Bearer caller-token"],
    ["x-api-key", "caller-key"],
  ])(
    "keeps a caller-supplied %s when no credential is configured",
    async (name, value) => {
      const mockFetch = mockJsonResponse();
      const client = new Client({
        apiUrl: "https://api.smith.langchain.com",
        headers: { [name]: value },
        fetchImplementation: mockFetch as any,
      });

      // The SDK has no credential of its own to apply, so dropping the
      // caller's would leave the request unauthenticated.
      expect(
        new Headers((client as any)._mergedHeaders).get(name.toLowerCase()),
      ).toBe(value);

      await (client as any).openAPIClient.info.list();

      const [, init] = mockFetch.mock.calls[0] as unknown as [
        RequestInfo | URL,
        RequestInit,
      ];
      expect(new Headers(init.headers).get(name.toLowerCase())).toBe(value);
    },
  );
});
