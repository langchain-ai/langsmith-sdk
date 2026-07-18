/* eslint-disable @typescript-eslint/no-explicit-any */
import { jest, describe, it, expect } from "@jest/globals";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { inspect } from "node:util";
import { SandboxClient } from "../sandbox/client.js";
import { Sandbox } from "../sandbox/sandbox.js";
import { CommandHandle } from "../sandbox/command_handle.js";
import { traceable } from "../traceable.js";
import {
  awsAuth,
  gitMount,
  gcpAuth,
  gcsMount,
  mountConfig,
  opaqueSecret,
  proxyConfig,
  s3Mount,
  workspaceSecret,
} from "../sandbox/index.js";
import {
  buildWsUrl,
  buildAuthHeaders,
  WSStreamControl,
  raiseForWsError,
} from "../sandbox/ws_execute.js";
import {
  LangSmithResourceCreationError,
  LangSmithResourceNotFoundError,
  LangSmithDataplaneNotConfiguredError,
  LangSmithQuotaExceededError,
  LangSmithValidationError,
  LangSmithResourceTimeoutError,
  LangSmithSandboxCreationError,
  LangSmithSandboxOperationError,
  LangSmithCommandTimeoutError,
  LangSmithSandboxServerReloadError,
} from "../sandbox/errors.js";
import type {
  WsMessage,
  OutputChunk,
  CreateSandboxOptions,
} from "../sandbox/types.js";
import { validateTtl } from "../sandbox/helpers.js";
import { getAssumedTreeFromCalls } from "./utils/tree.js";
import { mockClient as createTraceClient } from "./utils/mock_client.js";

const assertRawMountsAreNotCreateOptions = (
  options: CreateSandboxOptions,
): void => {
  void options;
  // @ts-expect-error raw mounts are only accepted inside mountConfig
  const invalidOptions: CreateSandboxOptions = { mounts: [] };
  void invalidOptions;
};
void assertRawMountsAreNotCreateOptions;

// Helper to create typed mock functions
const createMockFetch = (response: any) =>
  jest
    .fn<(url: string, init?: RequestInit) => Promise<Response>>()
    .mockResolvedValue(response);

// Helper to create a mock SandboxClient with the required methods
const createMockClient = (overrides: Record<string, any> = {}) =>
  ({
    _fetch: createMockFetch({}),
    getApiKey: () => "test-key",
    deleteSandbox: jest.fn<() => Promise<void>>().mockResolvedValue(undefined),
    ...overrides,
  }) as unknown as SandboxClient;

describe("sandbox proxy config helpers", () => {
  it("workspaceSecret wraps names and preserves references", () => {
    expect(workspaceSecret("AWS_KEY_ID_REF")).toEqual({
      type: "workspace_secret",
      value: "{AWS_KEY_ID_REF}",
    });
    expect(workspaceSecret("{AWS_KEY_VALUE_REF}")).toEqual({
      type: "workspace_secret",
      value: "{AWS_KEY_VALUE_REF}",
    });
  });

  it.each(["", "   ", "{}", "{AWS_KEY_ID_REF"])(
    "workspaceSecret rejects invalid name %p",
    (name) => {
      expect(() => workspaceSecret(name)).toThrow();
    },
  );

  it("opaqueSecret builds a write-only secret value", () => {
    expect(opaqueSecret("AKIAFAKE")).toEqual({
      type: "opaque",
      value: "AKIAFAKE",
    });
  });

  it("awsAuth builds an AWS auth rule", () => {
    expect(
      awsAuth({
        accessKeyId: workspaceSecret("AWS_KEY_ID_REF"),
        secretAccessKey: workspaceSecret("AWS_KEY_VALUE_REF"),
      }),
    ).toEqual({
      name: "aws",
      type: "aws",
      enabled: true,
      aws: {
        access_key_id: {
          type: "workspace_secret",
          value: "{AWS_KEY_ID_REF}",
        },
        secret_access_key: {
          type: "workspace_secret",
          value: "{AWS_KEY_VALUE_REF}",
        },
      },
    });
  });

  it("gcpAuth builds a GCP auth rule with built-in Google API host matching", () => {
    expect(
      gcpAuth({
        serviceAccountJson: workspaceSecret("GCP_SERVICE_ACCOUNT_JSON"),
        scopes: ["https://www.googleapis.com/auth/devstorage.read_write"],
      }),
    ).toEqual({
      name: "gcp",
      type: "gcp",
      enabled: true,
      gcp: {
        service_account_json: {
          type: "workspace_secret",
          value: "{GCP_SERVICE_ACCOUNT_JSON}",
        },
        scopes: ["https://www.googleapis.com/auth/devstorage.read_write"],
      },
    });
  });

  it("proxyConfig composes multiple provider rules", () => {
    const awsRule = awsAuth({
      accessKeyId: workspaceSecret("AWS_KEY_ID_REF"),
      secretAccessKey: workspaceSecret("AWS_KEY_VALUE_REF"),
    });
    const gcpRule = gcpAuth({
      serviceAccountJson: workspaceSecret("GCP_SERVICE_ACCOUNT_JSON"),
      scopes: ["https://www.googleapis.com/auth/devstorage.read_write"],
    });

    expect(
      proxyConfig({
        rules: [awsRule, gcpRule],
        noProxy: ["metadata.google.internal"],
        accessControl: { allow_list: ["*.googleapis.com", "*.amazonaws.com"] },
      }),
    ).toEqual({
      rules: [awsRule, gcpRule],
      no_proxy: ["metadata.google.internal"],
      access_control: { allow_list: ["*.googleapis.com", "*.amazonaws.com"] },
    });
  });

  it("mountConfig nests mounts and provider auth", () => {
    const awsAuthRule = awsAuth({
      accessKeyId: workspaceSecret("AWS_KEY_ID_REF"),
      secretAccessKey: workspaceSecret("AWS_KEY_VALUE_REF"),
    });
    const gcpAuthRule = gcpAuth({
      serviceAccountJson: workspaceSecret("GCP_SERVICE_ACCOUNT_JSON"),
    });

    expect(
      mountConfig({
        auth: [awsAuthRule, gcpAuthRule],
        mounts: [
          s3Mount({
            id: "s3_data",
            mountPath: "/mnt/s3-data",
            bucket: "s3-bucket",
            prefix: "datasets",
            region: "us-east-1",
            readOnly: true,
          }),
          gcsMount({
            id: "gcs_data",
            mountPath: "/mnt/gcs-data",
            bucket: "gcs-bucket",
            prefix: "datasets",
          }),
        ],
      }),
    ).toEqual({
      auth: {
        aws: awsAuthRule.aws,
        gcp: {
          service_account_json: {
            type: "workspace_secret",
            value: "{GCP_SERVICE_ACCOUNT_JSON}",
          },
        },
      },
      mounts: [
        {
          id: "s3_data",
          type: "s3",
          mount_path: "/mnt/s3-data",
          read_only: true,
          s3: {
            endpoint_url: "https://s3.amazonaws.com",
            region: "us-east-1",
            bucket: "s3-bucket",
            prefix: "datasets",
            path_style: false,
          },
        },
        {
          id: "gcs_data",
          type: "gcs",
          mount_path: "/mnt/gcs-data",
          gcs: {
            bucket: "gcs-bucket",
            prefix: "datasets",
          },
        },
      ],
    });
  });

  it("gitMount serializes the backend shape", () => {
    expect(
      gitMount({
        id: "repo",
        mountPath: "/mnt/repo",
        remoteUrl: "https://github.com/langchain-ai/langsmith-sdk.git",
        ref: { type: "branch", name: "main" },
        refreshIntervalSeconds: 60,
      }),
    ).toEqual({
      id: "repo",
      type: "git",
      mount_path: "/mnt/repo",
      git: {
        remote_url: "https://github.com/langchain-ai/langsmith-sdk.git",
        ref: { type: "branch", name: "main" },
        refresh_interval_seconds: 60,
      },
    });
  });

  it("gitMount allows tag refs and omitted optional fields", () => {
    expect(
      gitMount({
        id: "repo",
        mountPath: "/mnt/repo",
        remoteUrl: "https://github.com/langchain-ai/langsmith-sdk.git",
        ref: { type: "tag", name: "v1.0.0" },
      }).git,
    ).toEqual({
      remote_url: "https://github.com/langchain-ai/langsmith-sdk.git",
      ref: { type: "tag", name: "v1.0.0" },
    });

    expect(
      gitMount({
        id: "repo",
        mountPath: "/mnt/repo",
        remoteUrl: "https://github.com/langchain-ai/langsmith-sdk.git",
      }).git,
    ).toEqual({
      remote_url: "https://github.com/langchain-ai/langsmith-sdk.git",
    });
  });

  it.each([
    "",
    "http://github.com/langchain-ai/langsmith-sdk.git",
    "https://github.com",
    "https://user:pass@github.com/langchain-ai/langsmith-sdk.git",
    "https://github.com/langchain-ai/langsmith-sdk.git?token=secret",
    "https://github.com/langchain-ai/langsmith-sdk.git#main",
    "https://github.com/langchain-ai/langsmith-sdk.git\n",
    "https://github.com/langchain-ai/langsmith-sdk.git\0",
  ])("gitMount rejects invalid remote URL %p", (remoteUrl) => {
    expect(() =>
      gitMount({
        id: "repo",
        mountPath: "/mnt/repo",
        remoteUrl,
      }),
    ).toThrow();
  });

  it.each([
    { ref: { type: "commit", name: "abc123" } },
    { ref: { type: "branch" } },
    { ref: { type: "branch", name: "" } },
    { refreshIntervalSeconds: 0 },
  ])("gitMount rejects invalid ref or refresh interval", (options) => {
    expect(() =>
      gitMount({
        id: "repo",
        mountPath: "/mnt/repo",
        remoteUrl: "https://github.com/langchain-ai/langsmith-sdk.git",
        ...(options as any),
      }),
    ).toThrow();
  });

  it("mountConfig accepts Git mounts without provider auth", () => {
    const mount = gitMount({
      id: "repo",
      mountPath: "/mnt/repo",
      remoteUrl: "https://github.com/langchain-ai/langsmith-sdk.git",
    });

    expect(mountConfig({ mounts: [mount] })).toEqual({
      auth: {},
      mounts: [mount],
    });
  });

  it("mountConfig nests mixed bucket and Git mounts", () => {
    const awsAuthRule = awsAuth({
      accessKeyId: workspaceSecret("AWS_KEY_ID_REF"),
      secretAccessKey: workspaceSecret("AWS_KEY_VALUE_REF"),
    });
    const gcpAuthRule = gcpAuth({
      serviceAccountJson: workspaceSecret("GCP_SERVICE_ACCOUNT_JSON"),
    });
    const mounts = [
      s3Mount({
        id: "s3_data",
        mountPath: "/mnt/s3-data",
        bucket: "s3-bucket",
      }),
      gcsMount({
        id: "gcs_data",
        mountPath: "/mnt/gcs-data",
        bucket: "gcs-bucket",
      }),
      gitMount({
        id: "repo",
        mountPath: "/mnt/repo",
        remoteUrl: "https://github.com/langchain-ai/langsmith-sdk.git",
      }),
    ];

    expect(mountConfig({ auth: [awsAuthRule, gcpAuthRule], mounts })).toEqual({
      auth: {
        aws: awsAuthRule.aws,
        gcp: {
          service_account_json: {
            type: "workspace_secret",
            value: "{GCP_SERVICE_ACCOUNT_JSON}",
          },
        },
      },
      mounts,
    });
  });

  it.each([
    {
      auth: [],
      mounts: [
        s3Mount({ id: "s3_data", mountPath: "/mnt/s3-data", bucket: "b" }),
      ],
      message: /aws/i,
    },
    {
      auth: [],
      mounts: [
        gcsMount({ id: "gcs_data", mountPath: "/mnt/gcs-data", bucket: "b" }),
      ],
      message: /gcp/i,
    },
    {
      auth: [
        awsAuth({
          accessKeyId: workspaceSecret("AWS_KEY_ID_REF"),
          secretAccessKey: workspaceSecret("AWS_KEY_VALUE_REF"),
        }),
        awsAuth({
          accessKeyId: workspaceSecret("AWS_KEY_ID_REF_2"),
          secretAccessKey: workspaceSecret("AWS_KEY_VALUE_REF_2"),
        }),
      ],
      mounts: [
        s3Mount({ id: "s3_data", mountPath: "/mnt/s3-data", bucket: "b" }),
      ],
      message: /duplicate/i,
    },
  ])("mountConfig validates provider auth", ({ auth, mounts, message }) => {
    expect(() => mountConfig({ auth, mounts })).toThrow(message);
  });

  it("mountConfig rejects provider credentials inside mount specs", () => {
    const mount = s3Mount({
      id: "s3_data",
      mountPath: "/mnt/s3-data",
      bucket: "s3-bucket",
    }) as any;
    mount.s3.access_key_id = workspaceSecret("AWS_KEY_ID_REF");

    expect(() =>
      mountConfig({
        auth: [
          awsAuth({
            accessKeyId: workspaceSecret("AWS_KEY_ID_REF"),
            secretAccessKey: workspaceSecret("AWS_KEY_VALUE_REF"),
          }),
        ],
        mounts: [mount],
      }),
    ).toThrow(/credentials/i);
  });

  it.each([{ scopes: [] }, { scopes: [""] }])(
    "gcpAuth rejects empty scopes",
    ({ scopes }) => {
      expect(() =>
        gcpAuth({
          serviceAccountJson: workspaceSecret("GCP_SERVICE_ACCOUNT_JSON"),
          scopes,
        }),
      ).toThrow();
    },
  );

  it("proxyConfig rejects GCP auth without scopes", () => {
    expect(() =>
      proxyConfig({
        rules: [
          gcpAuth({
            serviceAccountJson: workspaceSecret("GCP_SERVICE_ACCOUNT_JSON"),
          }),
        ],
      }),
    ).toThrow(/scopes/i);
  });
});

describe("SandboxClient", () => {
  describe("constructor", () => {
    it("should trim trailing slash from endpoint", () => {
      const client = new SandboxClient({
        apiEndpoint: "https://custom.api.com/sandboxes/",
        apiKey: "test-key",
      });
      expect((client as any)._baseUrl).toBe("https://custom.api.com/sandboxes");
    });

    it("should use custom endpoint when provided", () => {
      const client = new SandboxClient({
        apiEndpoint: "https://custom.api.com/sandboxes",
        apiKey: "test-key",
      });
      expect((client as any)._baseUrl).toBe("https://custom.api.com/sandboxes");
    });
  });

  describe("toString", () => {
    it("should not expose sensitive information like API keys", () => {
      const client = new SandboxClient({
        apiEndpoint: "https://custom.api.com/sandboxes",
        apiKey: "super-secret-sandbox-api-key-12345",
      });

      const str = client.toString();
      expect(str).not.toContain("super-secret-sandbox-api-key-12345");
      expect(str).toContain("https://custom.api.com/sandboxes");
      expect(str).toBe(
        '[LangSmithSandboxClient apiEndpoint="https://custom.api.com/sandboxes"]',
      );
    });

    it("should be called when converting to string", () => {
      const client = new SandboxClient({
        apiEndpoint: "https://custom.api.com/sandboxes",
        apiKey: "secret-key",
      });

      const str = String(client);
      expect(str).not.toContain("secret-key");
      expect(str).toContain("https://custom.api.com/sandboxes");
    });

    it("should be called by Node.js inspect", () => {
      const client = new SandboxClient({
        apiEndpoint: "https://custom.api.com/sandboxes",
        apiKey: "secret-key",
      });

      const inspectResult = inspect(client);
      expect(inspectResult).not.toContain("secret-key");
      expect(inspectResult).toContain("https://custom.api.com/sandboxes");
      expect(inspectResult).toBe(
        '[LangSmithSandboxClient apiEndpoint="https://custom.api.com/sandboxes"]',
      );
    });

    it("should expose the Node.js custom inspect hook", () => {
      const client = new SandboxClient({
        apiEndpoint: "https://custom.api.com/sandboxes",
        apiKey: "secret-key",
      });

      const inspectSymbol = Symbol.for("nodejs.util.inspect.custom");
      const inspectFn = (client as any)[inspectSymbol];
      expect(typeof inspectFn).toBe("function");
      expect(inspectFn.call(client)).toBe(
        '[LangSmithSandboxClient apiEndpoint="https://custom.api.com/sandboxes"]',
      );
    });
  });
});

describe("Sandbox", () => {
  describe("run", () => {
    it("should throw DataplaneNotConfiguredError when dataplane_url is missing", async () => {
      const sandbox = new (Sandbox as any)(
        {
          id: "sandbox-123",
          name: "test-sandbox",
          // No dataplane_url
        },
        createMockClient(),
        false,
      );

      await expect(sandbox.run("echo hello")).rejects.toThrow(
        LangSmithDataplaneNotConfiguredError,
      );
    });

    it("should execute a command and return result", async () => {
      const mockFetch = createMockFetch({
        ok: true,
        json: async () => ({
          stdout: "Hello, World!\n",
          stderr: "",
          exit_code: 0,
        }),
      });

      const mockClient = createMockClient({ _fetch: mockFetch });

      const sandbox = new (Sandbox as any)(
        {
          id: "sandbox-123",
          name: "test-sandbox",
          dataplane_url: "https://dataplane.example.com",
        },
        mockClient,
        false,
      );

      const result = await sandbox.run('echo "Hello, World!"');

      expect(result.stdout).toBe("Hello, World!\n");
      expect(result.stderr).toBe("");
      expect(result.exit_code).toBe(0);
      expect(mockFetch).toHaveBeenCalledTimes(1);

      const [, options] = mockFetch.mock.calls[0] as [string, RequestInit];
      const body = JSON.parse(options.body as string);
      expect(body).not.toHaveProperty("env");
    });

    it("should pass environment variables and cwd to command", async () => {
      const mockFetch = createMockFetch({
        ok: true,
        json: async () => ({
          stdout: "test-value\n",
          stderr: "",
          exit_code: 0,
        }),
      });

      const mockClient = createMockClient({ _fetch: mockFetch });

      const sandbox = new (Sandbox as any)(
        {
          id: "sandbox-123",
          name: "test-sandbox",
          dataplane_url: "https://dataplane.example.com",
        },
        mockClient,
        false,
      );

      await sandbox.run("echo $MY_VAR", {
        env: { MY_VAR: "test-value" },
        cwd: "/tmp",
      });

      const [, options] = mockFetch.mock.calls[0] as [string, RequestInit];
      const body = JSON.parse(options.body as string);
      expect(body.env).toEqual({
        MY_VAR: "test-value",
      });
      expect(body.cwd).toBe("/tmp");
    });

    it("should trace run with sandbox metadata", async () => {
      const mockFetch = createMockFetch({
        ok: true,
        json: async () => ({
          stdout: "Hello, World!\n",
          stderr: "",
          exit_code: 0,
        }),
      });
      const mockClient = createMockClient({ _fetch: mockFetch });
      const sandbox = new (Sandbox as any)(
        {
          id: "sandbox-123",
          name: "test-sandbox",
          dataplane_url: "https://dataplane.example.com",
        },
        mockClient,
        false,
      );
      const { client: traceClient, callSpy } = createTraceClient();
      const agent = traceable(
        async () =>
          sandbox.run("echo $SECRET", {
            env: { SECRET: "redacted" },
            cwd: "/tmp",
          }),
        {
          name: "agent",
          client: traceClient,
          tracingEnabled: true,
          metadata: { sandbox_id: "outer", sandbox_name: "outer" },
        },
      );

      await agent();

      const tree = await getAssumedTreeFromCalls(
        callSpy.mock.calls,
        traceClient,
      );
      const sandboxRun = Object.values(tree.data).find(
        (run) => run.name === "Sandbox.run",
      );
      expect(sandboxRun).toBeDefined();
      expect(sandboxRun?.run_type).toBe("tool");
      expect(sandboxRun?.extra?.metadata).toMatchObject({
        sandbox_id: "sandbox-123",
        sandbox_name: "test-sandbox",
      });
      expect(sandboxRun?.inputs).toMatchObject({
        command: "echo $SECRET",
        cwd: "/tmp",
      });
      expect(JSON.stringify(sandboxRun?.inputs)).not.toContain("redacted");
      expect(sandboxRun?.outputs).toMatchObject({
        stdout: "Hello, World!\n",
        stderr: "",
        exit_code: 0,
      });
    });
  });

  describe("reconnect", () => {
    it("should trace reconnect with sandbox metadata", async () => {
      const mockClient = createMockClient();
      const sandbox = new (Sandbox as any)(
        {
          id: "sandbox-123",
          name: "test-sandbox",
          dataplane_url: "https://dataplane.example.com",
        },
        mockClient,
        false,
      );
      (sandbox as any)._reconnectUntraced = jest.fn(async () => ({
        commandId: "cmd-123",
        pid: 456,
      }));
      const { client: traceClient, callSpy } = createTraceClient();
      const agent = traceable(
        async () =>
          sandbox.reconnect("cmd-123", {
            stdoutOffset: 7,
            stderrOffset: 11,
          }),
        {
          name: "agent",
          client: traceClient,
          tracingEnabled: true,
          metadata: { sandbox_id: "outer", sandbox_name: "outer" },
        },
      );

      await agent();

      const tree = await getAssumedTreeFromCalls(
        callSpy.mock.calls,
        traceClient,
      );
      const sandboxReconnect = Object.values(tree.data).find(
        (run) => run.name === "Sandbox.reconnect",
      );
      expect(sandboxReconnect).toBeDefined();
      expect(sandboxReconnect?.run_type).toBe("tool");
      expect(sandboxReconnect?.extra?.metadata).toMatchObject({
        sandbox_id: "sandbox-123",
        sandbox_name: "test-sandbox",
      });
      expect(sandboxReconnect?.inputs).toEqual({
        command_id: "cmd-123",
        stdout_offset: 7,
        stderr_offset: 11,
      });
      expect(sandboxReconnect?.outputs).toMatchObject({
        command_id: "cmd-123",
        pid: 456,
      });
    });
  });

  describe("write", () => {
    it("should write string content to a file", async () => {
      const mockFetch = createMockFetch({
        ok: true,
        json: async () => ({}),
      });

      const mockClient = createMockClient({ _fetch: mockFetch });

      const sandbox = new (Sandbox as any)(
        {
          id: "sandbox-123",
          name: "test-sandbox",
          dataplane_url: "https://dataplane.example.com",
        },
        mockClient,
        false,
      );

      await sandbox.write("/tmp/test.txt", "Hello, World!");

      expect(mockFetch).toHaveBeenCalledTimes(1);
      const [url] = mockFetch.mock.calls[0] as [string, RequestInit];
      expect(url).toContain("/upload?path=%2Ftmp%2Ftest.txt");
    });

    it("should write Uint8Array content", async () => {
      const mockFetch = createMockFetch({
        ok: true,
        json: async () => ({}),
      });

      const mockClient = createMockClient({ _fetch: mockFetch });

      const sandbox = new (Sandbox as any)(
        {
          id: "sandbox-123",
          name: "test-sandbox",
          dataplane_url: "https://dataplane.example.com",
        },
        mockClient,
        false,
      );

      const content = new TextEncoder().encode("Binary content");
      await sandbox.write("/tmp/test.bin", content);

      expect(mockFetch).toHaveBeenCalledTimes(1);
    });

    it("should trace write with sandbox metadata without file contents", async () => {
      const mockFetch = createMockFetch({
        ok: true,
        json: async () => ({}),
      });
      const mockClient = createMockClient({ _fetch: mockFetch });
      const sandbox = new (Sandbox as any)(
        {
          id: "sandbox-123",
          name: "test-sandbox",
          dataplane_url: "https://dataplane.example.com",
        },
        mockClient,
        false,
      );
      const { client: traceClient, callSpy } = createTraceClient();
      const agent = traceable(
        async () => sandbox.write("/tmp/test.txt", "secret", 12),
        {
          name: "agent",
          client: traceClient,
          tracingEnabled: true,
          metadata: { sandbox_id: "outer", sandbox_name: "outer" },
        },
      );

      await agent();

      const tree = await getAssumedTreeFromCalls(
        callSpy.mock.calls,
        traceClient,
      );
      const sandboxWrite = Object.values(tree.data).find(
        (run) => run.name === "Sandbox.write",
      );
      expect(sandboxWrite).toBeDefined();
      expect(sandboxWrite?.run_type).toBe("tool");
      expect(sandboxWrite?.extra?.metadata).toMatchObject({
        sandbox_id: "sandbox-123",
        sandbox_name: "test-sandbox",
      });
      expect(sandboxWrite?.inputs).toEqual({
        path: "/tmp/test.txt",
        timeout: 12,
        content_bytes: 6,
      });
      expect(JSON.stringify(sandboxWrite?.inputs)).not.toContain("secret");
      expect(sandboxWrite?.outputs).toMatchObject({
        path: "/tmp/test.txt",
        bytes: 6,
      });
    });
  });

  describe("read", () => {
    it("should read content from a file", async () => {
      const testContent = "File content here";
      const mockFetch = createMockFetch({
        ok: true,
        arrayBuffer: async () => new TextEncoder().encode(testContent).buffer,
      });

      const mockClient = createMockClient({ _fetch: mockFetch });

      const sandbox = new (Sandbox as any)(
        {
          id: "sandbox-123",
          name: "test-sandbox",
          dataplane_url: "https://dataplane.example.com",
        },
        mockClient,
        false,
      );

      const content = await sandbox.read("/tmp/test.txt");

      const text = new TextDecoder().decode(content);
      expect(text).toBe("File content here");
    });

    it("should trace read with sandbox metadata without file contents in inputs", async () => {
      const testContent = "secret";
      const mockFetch = createMockFetch({
        ok: true,
        arrayBuffer: async () => new TextEncoder().encode(testContent).buffer,
      });
      const mockClient = createMockClient({ _fetch: mockFetch });
      const sandbox = new (Sandbox as any)(
        {
          id: "sandbox-123",
          name: "test-sandbox",
          dataplane_url: "https://dataplane.example.com",
        },
        mockClient,
        false,
      );
      const { client: traceClient, callSpy } = createTraceClient();
      const agent = traceable(async () => sandbox.read("/tmp/test.txt", 12), {
        name: "agent",
        client: traceClient,
        tracingEnabled: true,
        metadata: { sandbox_id: "outer", sandbox_name: "outer" },
      });

      const content = await agent();

      expect(new TextDecoder().decode(content)).toBe("secret");
      const tree = await getAssumedTreeFromCalls(
        callSpy.mock.calls,
        traceClient,
      );
      const sandboxRead = Object.values(tree.data).find(
        (run) => run.name === "Sandbox.read",
      );
      expect(sandboxRead).toBeDefined();
      expect(sandboxRead?.run_type).toBe("tool");
      expect(sandboxRead?.extra?.metadata).toMatchObject({
        sandbox_id: "sandbox-123",
        sandbox_name: "test-sandbox",
      });
      expect(sandboxRead?.inputs).toEqual({
        path: "/tmp/test.txt",
        timeout: 12,
      });
      expect(JSON.stringify(sandboxRead?.inputs)).not.toContain("secret");
      expect(sandboxRead?.outputs).toMatchObject({
        path: "/tmp/test.txt",
        bytes: 6,
      });
    });
  });

  describe("delete", () => {
    it("should call deleteSandbox on the client", async () => {
      const mockDeleteSandbox = jest
        .fn<(name: string) => Promise<void>>()
        .mockResolvedValue(undefined);

      const mockClient = createMockClient({
        deleteSandbox: mockDeleteSandbox,
      });

      const sandbox = new (Sandbox as any)(
        {
          id: "sandbox-123",
          name: "test-sandbox",
          dataplane_url: "https://dataplane.example.com",
        },
        mockClient,
      );

      await sandbox.delete();

      expect(mockDeleteSandbox).toHaveBeenCalledWith("test-sandbox");
    });
  });
});

describe("SandboxClient - createSandbox", () => {
  // Helper to create a SandboxClient with a mocked fetch
  const createClientWithMock = (mockFetch: any) => {
    const client = new SandboxClient({
      apiEndpoint: "https://api.example.com/v2/sandboxes",
      apiKey: "test-key",
    });
    (client as any)._caller = { call: (fn: any) => fn() };
    (client as any)._fetchImpl = mockFetch;
    return client;
  };

  it("should send wait_for_ready: true and include timeout by default", async () => {
    const mockFetch = jest.fn<typeof fetch>().mockResolvedValue({
      ok: true,
      json: async () => ({
        name: "test-sb",
        dataplane_url: "https://dp.example.com",
        status: "ready",
      }),
    } as Response);

    const client = createClientWithMock(mockFetch);
    await client.createSandbox("snap-123");

    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(init.body as string);
    expect(body.wait_for_ready).toBe(true);
    expect(body.timeout).toBe(30);
  });

  it("should send wait_for_ready: false and omit timeout when waitForReady is false", async () => {
    const mockFetch = jest.fn<typeof fetch>().mockResolvedValue({
      ok: true,
      json: async () => ({
        name: "test-sb",
        status: "provisioning",
      }),
    } as Response);

    const client = createClientWithMock(mockFetch);
    const sandbox = await client.createSandbox("snap-123", {
      waitForReady: false,
    });

    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(init.body as string);
    expect(body.wait_for_ready).toBe(false);
    expect(body.timeout).toBeUndefined();
    expect(sandbox.status).toBe("provisioning");
  });

  it("should use 30s HTTP timeout when waitForReady is false", async () => {
    const mockFetch = jest.fn<typeof fetch>().mockResolvedValue({
      ok: true,
      json: async () => ({
        name: "test-sb",
        status: "provisioning",
      }),
    } as Response);

    const client = createClientWithMock(mockFetch);
    await client.createSandbox("snap-123", { waitForReady: false });

    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    // The signal should be an AbortSignal with 30s timeout
    expect(init.signal).toBeDefined();
  });

  it("should include idle_ttl_seconds and delete_after_stop_seconds in the request body when set", async () => {
    const mockFetch = jest.fn<typeof fetch>().mockResolvedValue({
      ok: true,
      json: async () => ({
        name: "test-sb",
        dataplane_url: "https://dp.example.com",
        status: "ready",
        idle_ttl_seconds: 600,
        delete_after_stop_seconds: 86400,
        stopped_at: null,
      }),
    } as Response);

    const client = createClientWithMock(mockFetch);
    const sandbox = await client.createSandbox("snap-123", {
      idleTtlSeconds: 600,
      deleteAfterStopSeconds: 86400,
    });

    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(init.body as string);
    expect(body.idle_ttl_seconds).toBe(600);
    expect(body.delete_after_stop_seconds).toBe(86400);
    expect(sandbox.idle_ttl_seconds).toBe(600);
    expect(sandbox.delete_after_stop_seconds).toBe(86400);
    expect(sandbox.stopped_at).toBeUndefined();
  });

  it("should reject invalid retention values before calling the API", async () => {
    const mockFetch = jest.fn<typeof fetch>();
    const client = createClientWithMock(mockFetch);

    await expect(
      client.createSandbox("snap-123", { idleTtlSeconds: 61 }),
    ).rejects.toThrow(LangSmithValidationError);
    await expect(
      client.createSandbox("snap-123", { deleteAfterStopSeconds: 61 }),
    ).rejects.toThrow(LangSmithValidationError);
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("should forward proxyConfig in the request body under proxy_config", async () => {
    const mockFetch = jest.fn<typeof fetch>().mockResolvedValue({
      ok: true,
      json: async () => ({
        name: "test-sb",
        status: "ready",
      }),
    } as Response);

    const client = createClientWithMock(mockFetch);
    const proxyConfig = {
      access_control: {
        allow_list: ["github.com", "*.example.com"],
      },
    };
    await client.createSandbox("snap-123", { proxyConfig });

    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(init.body as string);
    expect(body.proxy_config).toEqual(proxyConfig);
  });

  it("should forward composed proxy config in the request body", async () => {
    const mockFetch = jest.fn<typeof fetch>().mockResolvedValue({
      ok: true,
      json: async () => ({
        name: "test-sb",
        status: "ready",
      }),
    } as Response);

    const client = createClientWithMock(mockFetch);
    const config = proxyConfig({
      rules: [
        awsAuth({
          accessKeyId: workspaceSecret("AWS_KEY_ID_REF"),
          secretAccessKey: workspaceSecret("AWS_KEY_VALUE_REF"),
        }),
      ],
    });
    await client.createSandbox("snap-123", { proxyConfig: config });

    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(init.body as string);
    expect(body.proxy_config).toEqual(config);
  });

  it("should forward mountConfig in the request body under mount_config", async () => {
    const mockFetch = jest.fn<typeof fetch>().mockResolvedValue({
      ok: true,
      json: async () => ({
        name: "test-sb",
        status: "ready",
      }),
    } as Response);

    const client = createClientWithMock(mockFetch);
    const config = mountConfig({
      auth: [
        awsAuth({
          accessKeyId: workspaceSecret("AWS_KEY_ID_REF"),
          secretAccessKey: workspaceSecret("AWS_KEY_VALUE_REF"),
        }),
      ],
      mounts: [
        s3Mount({
          id: "s3_data",
          mountPath: "/mnt/s3-data",
          bucket: "s3-bucket",
        }),
      ],
    });
    await client.createSandbox("snap-123", { mountConfig: config });

    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(init.body as string);
    expect(body.mount_config).toEqual(config);
    expect(body.mounts).toBeUndefined();
    expect(body.proxy_config).toBeUndefined();
  });

  it("should preserve mountConfig and proxyConfig separately", async () => {
    const mockFetch = jest.fn<typeof fetch>().mockResolvedValue({
      ok: true,
      json: async () => ({
        name: "test-sb",
        status: "ready",
      }),
    } as Response);

    const client = createClientWithMock(mockFetch);
    const awsAuthBlock = awsAuth({
      accessKeyId: workspaceSecret("AWS_KEY_ID_REF"),
      secretAccessKey: workspaceSecret("AWS_KEY_VALUE_REF"),
    });
    const extraRule = {
      name: "github",
      type: "headers",
      enabled: true,
      match_hosts: ["github.com"],
      headers: { authorization: "Bearer {GITHUB_TOKEN}" },
    };
    const config = mountConfig({
      auth: [awsAuthBlock],
      mounts: [
        s3Mount({
          id: "s3_data",
          mountPath: "/mnt/s3-data",
          bucket: "s3-bucket",
        }),
      ],
    });
    const extraProxyConfig = proxyConfig({
      rules: [extraRule],
      noProxy: ["metadata.google.internal"],
      accessControl: { allow_list: ["github.com", "*.amazonaws.com"] },
    });

    await client.createSandbox("snap-123", {
      mountConfig: config,
      proxyConfig: extraProxyConfig,
    });

    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(init.body as string);
    expect(body.mount_config).toEqual(config);
    expect(body.mounts).toBeUndefined();
    expect(body.proxy_config).toEqual({
      rules: [extraRule],
      no_proxy: ["metadata.google.internal"],
      access_control: { allow_list: ["github.com", "*.amazonaws.com"] },
    });
  });

  it.each([
    {
      provider: "aws",
      mountAuth: () =>
        awsAuth({
          accessKeyId: workspaceSecret("AWS_KEY_ID_REF"),
          secretAccessKey: workspaceSecret("AWS_KEY_VALUE_REF"),
        }),
      mounts: () => [
        s3Mount({
          id: "s3_data",
          mountPath: "/mnt/s3-data",
          bucket: "s3-bucket",
        }),
      ],
      explicitAuth: () =>
        awsAuth({
          accessKeyId: workspaceSecret("AWS_KEY_ID_REF_2"),
          secretAccessKey: workspaceSecret("AWS_KEY_VALUE_REF_2"),
          name: "aws-extra",
        }),
      message:
        "aws auth cannot be provided in both mountConfig and proxyConfig",
    },
    {
      provider: "gcp",
      mountAuth: () =>
        gcpAuth({
          serviceAccountJson: workspaceSecret("GCP_SERVICE_ACCOUNT_JSON"),
        }),
      mounts: () => [
        gcsMount({
          id: "gcs_data",
          mountPath: "/mnt/gcs-data",
          bucket: "gcs-bucket",
        }),
      ],
      explicitAuth: () =>
        gcpAuth({
          serviceAccountJson: workspaceSecret("GCP_SERVICE_ACCOUNT_JSON_2"),
          scopes: ["https://www.googleapis.com/auth/devstorage.read_write"],
          name: "gcp-extra",
        }),
      message:
        "gcp auth cannot be provided in both mountConfig and proxyConfig",
    },
  ])(
    "should reject duplicate $provider auth across mountConfig and proxyConfig",
    async ({ mountAuth, mounts, explicitAuth, message }) => {
      const mockFetch = jest.fn<typeof fetch>().mockResolvedValue({
        ok: true,
        json: async () => ({
          name: "test-sb",
          status: "ready",
        }),
      } as Response);
      const client = createClientWithMock(mockFetch);
      const config = mountConfig({
        auth: [mountAuth()],
        mounts: mounts(),
      });
      const extraProxyConfig = proxyConfig({
        rules: [explicitAuth()],
      });

      await expect(
        client.createSandbox("snap-123", {
          mountConfig: config,
          proxyConfig: extraProxyConfig,
        }),
      ).rejects.toThrow(message);
      expect(mockFetch).not.toHaveBeenCalled();
    },
  );

  it("should omit proxy_config from the request body when not provided", async () => {
    const mockFetch = jest.fn<typeof fetch>().mockResolvedValue({
      ok: true,
      json: async () => ({
        name: "test-sb",
        status: "ready",
      }),
    } as Response);

    const client = createClientWithMock(mockFetch);
    await client.createSandbox("snap-123");

    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(init.body as string);
    expect(body.proxy_config).toBeUndefined();
  });
});

describe("validateTtl", () => {
  it("accepts undefined, 0, and positive multiples of 60", () => {
    expect(() => validateTtl(undefined, "idleTtlSeconds")).not.toThrow();
    expect(() => validateTtl(0, "idleTtlSeconds")).not.toThrow();
    expect(() => validateTtl(60, "idleTtlSeconds")).not.toThrow();
    expect(() => validateTtl(3600, "deleteAfterStopSeconds")).not.toThrow();
  });

  it("rejects negative values and non-multiples of 60", () => {
    expect(() => validateTtl(-1, "idleTtlSeconds")).toThrow(
      LangSmithValidationError,
    );
    expect(() => validateTtl(30, "idleTtlSeconds")).toThrow(
      LangSmithValidationError,
    );
    expect(() => validateTtl(61, "deleteAfterStopSeconds")).toThrow(
      LangSmithValidationError,
    );
  });
});

describe("SandboxClient - updateSandbox", () => {
  const createClientWithMock = (mockFetch: any) => {
    const client = new SandboxClient({
      apiEndpoint: "https://api.example.com/v2/sandboxes",
      apiKey: "test-key",
    });
    (client as any)._caller = { call: (fn: any) => fn() };
    (client as any)._fetchImpl = mockFetch;
    return client;
  };

  it("should PATCH retention fields when provided in options", async () => {
    const mockFetch = jest.fn<typeof fetch>().mockResolvedValue({
      ok: true,
      json: async () => ({
        name: "sb-1",
        status: "ready",
        idle_ttl_seconds: 1800,
        delete_after_stop_seconds: 0,
      }),
    } as Response);

    const client = createClientWithMock(mockFetch);
    await client.updateSandbox("sb-1", {
      idleTtlSeconds: 1800,
      deleteAfterStopSeconds: 0,
    });

    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe("PATCH");
    const body = JSON.parse(init.body as string);
    expect(body.idle_ttl_seconds).toBe(1800);
    expect(body.delete_after_stop_seconds).toBe(0);
    expect(body.name).toBeUndefined();
  });

  it("should still support rename via string second argument", async () => {
    const mockFetch = jest.fn<typeof fetch>().mockResolvedValue({
      ok: true,
      json: async () => ({
        name: "sb-renamed",
        status: "ready",
      }),
    } as Response);

    const client = createClientWithMock(mockFetch);
    await client.updateSandbox("sb-1", "sb-renamed");

    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(init.body as string);
    expect(body.name).toBe("sb-renamed");
  });

  it("should GET sandbox when update options object is empty", async () => {
    const mockFetch = jest.fn<typeof fetch>().mockResolvedValue({
      ok: true,
      json: async () => ({
        name: "sb-1",
        status: "ready",
      }),
    } as Response);

    const client = createClientWithMock(mockFetch);
    const sb = await client.updateSandbox("sb-1", {});

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/boxes/sb-1");
    expect(init.method).toBeUndefined();
    expect(sb.name).toBe("sb-1");
  });
});

describe("SandboxClient - getSandboxStatus", () => {
  const createClientWithMock = (mockFetch: any) => {
    const client = new SandboxClient({
      apiEndpoint: "https://api.example.com/v2/sandboxes",
      apiKey: "test-key",
    });
    (client as any)._caller = { call: (fn: any) => fn() };
    (client as any)._fetchImpl = mockFetch;
    return client;
  };

  it("should return ResourceStatus", async () => {
    const mockFetch = jest.fn<typeof fetch>().mockResolvedValue({
      ok: true,
      json: async () => ({
        status: "ready",
      }),
    } as Response);

    const client = createClientWithMock(mockFetch);
    const result = await client.getSandboxStatus("test-sb");

    expect(result.status).toBe("ready");
    const [url] = mockFetch.mock.calls[0] as [string];
    expect(url).toContain("/boxes/test-sb/status");
  });

  it("should throw LangSmithResourceNotFoundError on 404", async () => {
    const mockFetch = jest.fn<typeof fetch>().mockResolvedValue({
      ok: false,
      status: 404,
    } as Response);

    const client = createClientWithMock(mockFetch);
    await expect(client.getSandboxStatus("nonexistent")).rejects.toThrow(
      LangSmithResourceNotFoundError,
    );
  });
});

describe("SandboxClient - waitForSandbox", () => {
  const createClientWithMock = (mockFetch: any) => {
    const client = new SandboxClient({
      apiEndpoint: "https://api.example.com/v2/sandboxes",
      apiKey: "test-key",
    });
    (client as any)._caller = { call: (fn: any) => fn() };
    (client as any)._fetchImpl = mockFetch;
    return client;
  };

  it("should poll until ready and return sandbox", async () => {
    let callCount = 0;
    const mockFetch = jest
      .fn<typeof fetch>()
      .mockImplementation(async (url: any) => {
        const urlStr = typeof url === "string" ? url : url.toString();
        if (urlStr.includes("/status")) {
          callCount++;
          return {
            ok: true,
            json: async () => ({
              status: callCount < 3 ? "provisioning" : "ready",
            }),
          } as Response;
        }
        // getSandbox call
        return {
          ok: true,
          json: async () => ({
            name: "test-sb",
            dataplane_url: "https://dp.example.com",
            status: "ready",
          }),
        } as Response;
      });

    const client = createClientWithMock(mockFetch);
    const sandbox = await client.waitForSandbox("test-sb", {
      pollInterval: 0.01,
    });

    expect(sandbox.status).toBe("ready");
    expect(sandbox.dataplane_url).toBe("https://dp.example.com");
    expect(callCount).toBe(3);
  });

  it("should throw LangSmithResourceCreationError on failed status", async () => {
    const mockFetch = jest.fn<typeof fetch>().mockResolvedValue({
      ok: true,
      json: async () => ({
        status: "failed",
        status_message: "Image pull failed",
      }),
    } as Response);

    const client = createClientWithMock(mockFetch);
    await expect(
      client.waitForSandbox("test-sb", { pollInterval: 0.01 }),
    ).rejects.toThrow(LangSmithResourceCreationError);
  });

  it("should throw LangSmithResourceTimeoutError on timeout", async () => {
    const mockFetch = jest.fn<typeof fetch>().mockResolvedValue({
      ok: true,
      json: async () => ({
        status: "provisioning",
      }),
    } as Response);

    const client = createClientWithMock(mockFetch);
    await expect(
      client.waitForSandbox("test-sb", { timeout: 0.05, pollInterval: 0.01 }),
    ).rejects.toThrow(LangSmithResourceTimeoutError);
  });
});

describe("Sandbox - status fields and not-ready guard", () => {
  it("should populate status and status_message from SandboxData", () => {
    const sandbox = new (Sandbox as any)(
      {
        name: "test-sandbox",
        status: "provisioning",
        status_message: "Waiting for resources",
      },
      createMockClient(),
    );

    expect(sandbox.status).toBe("provisioning");
    expect(sandbox.status_message).toBe("Waiting for resources");
  });

  it("does not gate dataplane ops on status (stopped runs; platform resumes)", async () => {
    const mockFetch = createMockFetch({
      ok: true,
      json: async () => ({ stdout: "ok\n", stderr: "", exit_code: 0 }),
    });
    const sandbox = new (Sandbox as any)(
      {
        name: "test-sandbox",
        dataplane_url: "https://dp.example.com",
        status: "stopped",
      },
      createMockClient({ _fetch: mockFetch }),
    );

    const result = await sandbox.run("echo ok");
    expect(result.stdout).toBe("ok\n");
  });

  it("should allow operations when status is ready", async () => {
    const mockFetch = createMockFetch({
      ok: true,
      json: async () => ({
        stdout: "hello\n",
        stderr: "",
        exit_code: 0,
      }),
    });

    const sandbox = new (Sandbox as any)(
      {
        name: "test-sandbox",
        dataplane_url: "https://dp.example.com",
        status: "ready",
      },
      createMockClient({ _fetch: mockFetch }),
    );

    const result = await sandbox.run("echo hello");
    expect(result.stdout).toBe("hello\n");
  });
});

describe("Error classes", () => {
  it("LangSmithResourceNotFoundError should have resourceType", () => {
    const error = new LangSmithResourceNotFoundError("Not found", "sandbox");
    expect(error.resourceType).toBe("sandbox");
    expect(error.message).toBe("Not found");
    expect(error.name).toBe("LangSmithResourceNotFoundError");
  });

  it("LangSmithResourceTimeoutError should have resourceType and lastStatus", () => {
    const error = new LangSmithResourceTimeoutError(
      "Timeout",
      "sandbox",
      "pending",
    );
    expect(error.resourceType).toBe("sandbox");
    expect(error.lastStatus).toBe("pending");
    expect(error.toString()).toContain("pending");
  });

  it("LangSmithQuotaExceededError should have quotaType", () => {
    const error = new LangSmithQuotaExceededError(
      "Quota exceeded",
      "sandbox_count",
    );
    expect(error.quotaType).toBe("sandbox_count");
  });

  it("LangSmithValidationError should have field and details", () => {
    const details = [
      { loc: ["body", "cpu"], msg: "Invalid", type: "value_error" },
    ];
    const error = new LangSmithValidationError(
      "Validation failed",
      "cpu",
      details,
    );
    expect(error.field).toBe("cpu");
    expect(error.details).toEqual(details);
  });

  it("LangSmithSandboxCreationError should have errorType and custom toString", () => {
    const error = new LangSmithSandboxCreationError(
      "Creation failed",
      "ImagePull",
    );
    expect(error.errorType).toBe("ImagePull");
    expect(error.toString()).toContain("ImagePull");
  });

  it("LangSmithDataplaneNotConfiguredError should be a LangSmithSandboxError", () => {
    const error = new LangSmithDataplaneNotConfiguredError("No dataplane");
    expect(error.name).toBe("LangSmithDataplaneNotConfiguredError");
  });

  it("LangSmithResourceCreationError should have resourceType and errorType", () => {
    const error = new LangSmithResourceCreationError(
      "Provisioning failed",
      "sandbox",
      "ImagePull",
    );
    expect(error.name).toBe("LangSmithResourceCreationError");
    expect(error.resourceType).toBe("sandbox");
    expect(error.errorType).toBe("ImagePull");
    expect(error.toString()).toContain("ImagePull");
  });

  it("LangSmithCommandTimeoutError should extend SandboxOperationError", () => {
    const error = new LangSmithCommandTimeoutError("Command timed out", 60);
    expect(error.name).toBe("LangSmithCommandTimeoutError");
    expect(error.timeout).toBe(60);
    expect(error.operation).toBe("command");
    expect(error.errorType).toBe("CommandTimeout");
    expect(error).toBeInstanceOf(LangSmithSandboxOperationError);
  });

  it("LangSmithSandboxServerReloadError should extend SandboxConnectionError", () => {
    const error = new LangSmithSandboxServerReloadError("Server reloading");
    expect(error.name).toBe("LangSmithSandboxServerReloadError");
    expect(error.message).toBe("Server reloading");
  });
});

// =============================================================================
// WebSocket Execute Tests
// =============================================================================

describe("buildWsUrl", () => {
  it("should convert https to wss and append /execute/ws", () => {
    expect(buildWsUrl("https://dataplane.example.com")).toBe(
      "wss://dataplane.example.com/execute/ws",
    );
  });

  it("should convert http to ws", () => {
    expect(buildWsUrl("http://localhost:8080")).toBe(
      "ws://localhost:8080/execute/ws",
    );
  });

  it("should handle URLs with paths", () => {
    expect(buildWsUrl("https://dataplane.example.com/some/path")).toBe(
      "wss://dataplane.example.com/some/path/execute/ws",
    );
  });
});

describe("buildAuthHeaders", () => {
  it("should return X-Api-Key header when key is provided", () => {
    expect(buildAuthHeaders("test-key")).toEqual({ "X-Api-Key": "test-key" });
  });

  it("should return empty headers when no key", () => {
    expect(buildAuthHeaders(undefined)).toEqual({});
  });
});

describe("WSStreamControl", () => {
  it("should track killed state", () => {
    const control = new WSStreamControl();
    expect(control.killed).toBe(false);
    control.sendKill();
    expect(control.killed).toBe(true);
  });

  it("should not throw when sending on unbound control", () => {
    const control = new WSStreamControl();
    // Should not throw
    control.sendKill();
    control.sendInput("hello");
  });
});

describe("raiseForWsError", () => {
  it("should throw LangSmithCommandTimeoutError for CommandTimeout", () => {
    const msg: WsMessage = {
      type: "error",
      error_type: "CommandTimeout",
      error: "Command timed out after 60s",
    };
    expect(() => raiseForWsError(msg)).toThrow(LangSmithCommandTimeoutError);
  });

  it("should throw SandboxOperationError for CommandNotFound", () => {
    const msg: WsMessage = {
      type: "error",
      error_type: "CommandNotFound",
      error: "Not found",
    };
    expect(() => raiseForWsError(msg, "cmd-123")).toThrow(
      LangSmithSandboxOperationError,
    );
    try {
      raiseForWsError(msg, "cmd-123");
    } catch (e: any) {
      expect(e.message).toContain("cmd-123");
      expect(e.operation).toBe("reconnect");
    }
  });

  it("should throw SandboxOperationError for SessionExpired", () => {
    const msg: WsMessage = {
      type: "error",
      error_type: "SessionExpired",
      error: "Expired",
    };
    expect(() => raiseForWsError(msg)).toThrow(LangSmithSandboxOperationError);
  });

  it("should throw SandboxOperationError for unknown error types", () => {
    const msg: WsMessage = {
      type: "error",
      error_type: "UnknownError",
      error: "Something went wrong",
    };
    expect(() => raiseForWsError(msg)).toThrow(LangSmithSandboxOperationError);
  });
});

// =============================================================================
// CommandHandle Tests
// =============================================================================

describe("CommandHandle", () => {
  // Helper to create an async iterator from an array of WsMessages
  function createMockStream(
    messages: WsMessage[],
  ): AsyncIterableIterator<WsMessage> {
    let index = 0;
    return {
      next: async () => {
        if (index < messages.length) {
          return { value: messages[index++], done: false };
        }
        return { value: undefined as any, done: true };
      },
      [Symbol.asyncIterator]() {
        return this;
      },
    };
  }

  function createMockSandbox(): Sandbox {
    return {
      _client: { getApiKey: () => "test-key" },
      dataplane_url: "https://dp.example.com",
      name: "test-sandbox",
      reconnect: jest.fn<any>(),
    } as unknown as Sandbox;
  }

  describe("construction and _ensureStarted", () => {
    it("should read 'started' message and populate commandId/pid", async () => {
      const stream = createMockStream([
        { type: "started", command_id: "cmd-123", pid: 42 },
        { type: "stdout", data: "hello\n", offset: 0 },
        { type: "exit", exit_code: 0 },
      ]);

      const handle = new CommandHandle(stream, null, createMockSandbox());
      await handle._ensureStarted();

      expect(handle.commandId).toBe("cmd-123");
      expect(handle.pid).toBe(42);
    });

    it("should throw if stream ends before started message", async () => {
      const stream = createMockStream([]);

      const handle = new CommandHandle(stream, null, createMockSandbox());
      await expect(handle._ensureStarted()).rejects.toThrow(
        LangSmithSandboxOperationError,
      );
    });

    it("should throw if first message is not 'started'", async () => {
      const stream = createMockStream([
        { type: "stdout", data: "hello\n", offset: 0 },
      ]);

      const handle = new CommandHandle(stream, null, createMockSandbox());
      await expect(handle._ensureStarted()).rejects.toThrow(
        "Expected 'started' message",
      );
    });

    it("should skip _ensureStarted for reconnections (commandId set)", async () => {
      const stream = createMockStream([
        { type: "stdout", data: "hello\n", offset: 0 },
        { type: "exit", exit_code: 0 },
      ]);

      const handle = new CommandHandle(stream, null, createMockSandbox(), {
        commandId: "cmd-123",
      });
      // Should already be started
      expect(handle.commandId).toBe("cmd-123");
    });
  });

  describe("iteration", () => {
    it("should yield OutputChunk objects", async () => {
      const stream = createMockStream([
        { type: "started", command_id: "cmd-123", pid: 42 },
        { type: "stdout", data: "hello ", offset: 0 },
        { type: "stderr", data: "warn\n", offset: 0 },
        { type: "stdout", data: "world\n", offset: 6 },
        { type: "exit", exit_code: 0 },
      ]);

      const handle = new CommandHandle(stream, null, createMockSandbox());
      await handle._ensureStarted();

      const chunks: OutputChunk[] = [];
      for await (const chunk of handle) {
        chunks.push(chunk);
      }

      expect(chunks).toHaveLength(3);
      expect(chunks[0]).toEqual({
        stream: "stdout",
        data: "hello ",
        offset: 0,
      });
      expect(chunks[1]).toEqual({
        stream: "stderr",
        data: "warn\n",
        offset: 0,
      });
      expect(chunks[2]).toEqual({
        stream: "stdout",
        data: "world\n",
        offset: 6,
      });
    });

    it("should track offsets", async () => {
      const stream = createMockStream([
        { type: "started", command_id: "cmd-123", pid: 42 },
        { type: "stdout", data: "hello", offset: 0 },
        { type: "stderr", data: "err", offset: 0 },
        { type: "exit", exit_code: 0 },
      ]);

      const handle = new CommandHandle(stream, null, createMockSandbox());
      await handle._ensureStarted();

      for await (const _chunk of handle) {
        // drain
      }

      expect(handle.lastStdoutOffset).toBe(5);
      expect(handle.lastStderrOffset).toBe(3);
    });
  });

  describe("result", () => {
    it("should drain stream and return ExecutionResult", async () => {
      const stream = createMockStream([
        { type: "started", command_id: "cmd-123", pid: 42 },
        { type: "stdout", data: "hello ", offset: 0 },
        { type: "stdout", data: "world\n", offset: 6 },
        { type: "stderr", data: "warning\n", offset: 0 },
        { type: "exit", exit_code: 0 },
      ]);

      const handle = new CommandHandle(stream, null, createMockSandbox());
      await handle._ensureStarted();

      const result = await handle.result;

      expect(result.stdout).toBe("hello world\n");
      expect(result.stderr).toBe("warning\n");
      expect(result.exit_code).toBe(0);
    });

    it("should reconnect if stream ends without exit message", async () => {
      const stream = createMockStream([
        { type: "started", command_id: "cmd-123", pid: 42 },
        { type: "stdout", data: "hello\n", offset: 0 },
      ]);

      const sandbox = createMockSandbox();
      const reconnectHandle = {
        _stream: createMockStream([{ type: "exit", exit_code: 0 }]),
        _control: null,
      };
      (sandbox.reconnect as any).mockResolvedValue(reconnectHandle);

      const handle = new CommandHandle(stream, null, sandbox);
      await handle._ensureStarted();
      const backoffBase = CommandHandle.BACKOFF_BASE;
      CommandHandle.BACKOFF_BASE = 0;
      try {
        const result = await handle.result;

        expect(result.stdout).toBe("hello\n");
        expect(result.exit_code).toBe(0);
        expect(sandbox.reconnect).toHaveBeenCalledWith("cmd-123", {
          stdoutOffset: 6,
          stderrOffset: 0,
        });
      } finally {
        CommandHandle.BACKOFF_BASE = backoffBase;
      }
    });
  });

  describe("output callbacks", () => {
    it("should invoke onStdout/onStderr for every chunk", async () => {
      const stream = createMockStream([
        { type: "started", command_id: "cmd-123", pid: 42 },
        { type: "stdout", data: "out1", offset: 0 },
        { type: "stderr", data: "err1", offset: 0 },
        { type: "stdout", data: "out2", offset: 4 },
        { type: "exit", exit_code: 0 },
      ]);

      const stdoutData: string[] = [];
      const stderrData: string[] = [];
      const handle = new CommandHandle(stream, null, createMockSandbox(), {
        onStdout: (d) => stdoutData.push(d),
        onStderr: (d) => stderrData.push(d),
      });

      const result = await handle.result;

      expect(result.exit_code).toBe(0);
      expect(stdoutData).toEqual(["out1", "out2"]);
      expect(stderrData).toEqual(["err1"]);
    });

    it("should keep invoking callbacks for chunks received after a reconnect", async () => {
      // Mid-stream disconnect: the first connection delivers part of the
      // output and dies without an exit message; the reconnected stream
      // delivers the tail. Callbacks must see ALL chunks (this is the bug
      // that silently truncated tails for sandbox.run({ onStdout })).
      const stream = createMockStream([
        { type: "started", command_id: "cmd-123", pid: 42 },
        { type: "stdout", data: "before-disconnect ", offset: 0 },
      ]);

      const sandbox = createMockSandbox();
      const reconnectHandle = {
        _stream: createMockStream([
          { type: "stdout", data: "after-reconnect", offset: 18 },
          { type: "exit", exit_code: 0 },
        ]),
        _control: null,
      };
      (sandbox.reconnect as any).mockResolvedValue(reconnectHandle);

      const stdoutData: string[] = [];
      const handle = new CommandHandle(stream, null, sandbox, {
        onStdout: (d) => stdoutData.push(d),
      });

      const backoffBase = CommandHandle.BACKOFF_BASE;
      CommandHandle.BACKOFF_BASE = 0;
      try {
        const result = await handle.result;

        expect(result.exit_code).toBe(0);
        expect(stdoutData).toEqual(["before-disconnect ", "after-reconnect"]);
        expect(result.stdout).toBe("before-disconnect after-reconnect");
      } finally {
        CommandHandle.BACKOFF_BASE = backoffBase;
      }
    });
  });

  describe("kill", () => {
    it("should call sendKill on control", () => {
      const control = new WSStreamControl();
      const stream = createMockStream([]);
      const handle = new CommandHandle(stream, control, createMockSandbox(), {
        commandId: "cmd-123",
      });

      handle.kill();

      expect(control.killed).toBe(true);
    });
  });

  describe("sendInput", () => {
    it("should not throw when control is null", () => {
      const stream = createMockStream([]);
      const handle = new CommandHandle(stream, null, createMockSandbox(), {
        commandId: "cmd-123",
      });

      // Should not throw
      handle.sendInput("test input");
    });
  });
});

describe("SandboxClient - createSandbox (snapshotId)", () => {
  const createClientWithMock = (mockFetch: any) => {
    const client = new SandboxClient({
      apiEndpoint: "https://api.example.com/v2/sandboxes",
      apiKey: "test-key",
    });
    (client as any)._caller = { call: (fn: any) => fn() };
    (client as any)._fetchImpl = mockFetch;
    return client;
  };

  it("should send snapshot_id in the request body", async () => {
    const mockFetch = jest.fn<typeof fetch>().mockResolvedValue({
      ok: true,
      json: async () => ({
        name: "test-sb",
        snapshot_id: "snap-1",
        dataplane_url: "https://dp.example.com",
        status: "ready",
      }),
    } as Response);

    const client = createClientWithMock(mockFetch);
    const sandbox = await client.createSandbox("snap-1");

    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(init.body as string);
    expect(body.snapshot_id).toBe("snap-1");
    expect(body.template_name).toBeUndefined();
    expect(sandbox.snapshot_id).toBe("snap-1");
  });

  it("should include vcpus, mem_bytes, fs_capacity_bytes when provided", async () => {
    const mockFetch = jest.fn<typeof fetch>().mockResolvedValue({
      ok: true,
      json: async () => ({
        name: "test-sb",
        snapshot_id: "snap-1",
        status: "ready",
        vcpus: 4,
        mem_bytes: 1073741824,
        fs_capacity_bytes: 4294967296,
      }),
    } as Response);

    const client = createClientWithMock(mockFetch);
    const sandbox = await client.createSandbox("snap-1", {
      vCpus: 4,
      memBytes: 1073741824,
      fsCapacityBytes: 4294967296,
    });

    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(init.body as string);
    expect(body.vcpus).toBe(4);
    expect(body.mem_bytes).toBe(1073741824);
    expect(body.fs_capacity_bytes).toBe(4294967296);
    expect(sandbox.vCpus).toBe(4);
    expect(sandbox.mem_bytes).toBe(1073741824);
  });

  it("should send snapshot_name (and no snapshot_id) when resolved by name", async () => {
    const mockFetch = jest.fn<typeof fetch>().mockResolvedValue({
      ok: true,
      json: async () => ({
        name: "test-sb",
        snapshot_id: "snap-1",
        dataplane_url: "https://dp.example.com",
        status: "ready",
      }),
    } as Response);

    const client = createClientWithMock(mockFetch);
    const sandbox = await client.createSandbox({
      snapshotName: "my-snap",
    });

    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(init.body as string);
    expect(body.snapshot_name).toBe("my-snap");
    expect(body.snapshot_id).toBeUndefined();
    expect(body.template_name).toBeUndefined();
    expect(sandbox.snapshot_id).toBe("snap-1");
  });

  it("should omit snapshot_id when no snapshot is provided", async () => {
    const mockFetch = jest.fn<typeof fetch>().mockResolvedValue({
      ok: true,
      json: async () => ({
        name: "test-sb",
        dataplane_url: "https://dp.example.com",
        status: "ready",
      }),
    } as Response);
    const client = createClientWithMock(mockFetch);

    await client.createSandbox({ name: "test-sb" });

    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(init.body as string);
    expect(body.snapshot_id).toBeUndefined();
    expect(body.snapshot_name).toBeUndefined();
  });

  it("should throw when both snapshotId and snapshotName are provided", async () => {
    const mockFetch = jest.fn<typeof fetch>();
    const client = createClientWithMock(mockFetch);

    await expect(
      client.createSandbox("snap-1", { snapshotName: "my-snap" }),
    ).rejects.toThrow(LangSmithValidationError);
    await expect(
      client.createSandbox("snap-1", { snapshotName: "my-snap" }),
    ).rejects.toThrow(
      /At most one of snapshotId or options\.snapshotName may be set/,
    );
    expect(mockFetch).not.toHaveBeenCalled();
  });
});

describe("SandboxClient - snapshot operations", () => {
  const createClientWithMock = (mockFetch: any) => {
    const client = new SandboxClient({
      apiEndpoint: "https://api.example.com/v2/sandboxes",
      apiKey: "test-key",
    });
    (client as any)._caller = { call: (fn: any) => fn() };
    (client as any)._fetchImpl = mockFetch;
    return client;
  };

  it("createSnapshot should POST and poll until ready", async () => {
    const mockFetch = jest
      .fn<typeof fetch>()
      // POST /snapshots -> building
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: "snap-1",
          name: "my-env",
          status: "building",
          fs_capacity_bytes: 4294967296,
        }),
      } as Response)
      // GET /snapshots/snap-1 -> ready
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: "snap-1",
          name: "my-env",
          status: "ready",
          fs_capacity_bytes: 4294967296,
        }),
      } as Response);

    const client = createClientWithMock(mockFetch);
    const snapshot = await client.createSnapshot(
      "my-env",
      "python:3.12-slim",
      4294967296,
      { registryId: "reg-1" },
    );

    expect(snapshot.id).toBe("snap-1");
    expect(snapshot.status).toBe("ready");
    expect(mockFetch).toHaveBeenCalledTimes(2);
    expect(
      JSON.parse((mockFetch.mock.calls[0][1] as RequestInit).body as string),
    ).toEqual({
      name: "my-env",
      docker_image: "python:3.12-slim",
      fs_capacity_bytes: 4294967296,
      registry_id: "reg-1",
    });
  });

  it("createSnapshotFromDockerfile should sync, build, and capture", async () => {
    const context = await mkdtemp(join(tmpdir(), "langsmith-docker-context-"));
    const client = createClientWithMock(jest.fn<typeof fetch>());
    const writes: [string, string | Uint8Array][] = [];
    const commands: string[] = [];
    const fakeSandbox = {
      name: "builder",
      write: jest
        .fn<(path: string, content: string | Uint8Array) => Promise<void>>()
        .mockImplementation(async (path, content) => {
          writes.push([path, content]);
        }),
      run: jest
        .fn<
          (
            command: string,
          ) => Promise<{ stdout: string; stderr: string; exit_code: number }>
        >()
        .mockImplementation(async (command) => {
          commands.push(command);
          return { stdout: "", stderr: "", exit_code: 0 };
        }),
      delete: jest.fn<() => Promise<void>>().mockResolvedValue(undefined),
    };
    const mockSnapshot = {
      id: "snap-1",
      name: "snap",
      status: "ready",
      fs_capacity_bytes: 4294967296,
    };
    const createSandboxSpy = jest
      .spyOn(client, "createSandbox")
      .mockResolvedValue(fakeSandbox as any);
    const captureSnapshotSpy = jest
      .spyOn(client, "captureSnapshot")
      .mockResolvedValue(mockSnapshot);

    try {
      await writeFile(join(context, "Dockerfile"), "FROM scratch\n");

      const snapshot = await client.createSnapshotFromDockerfile(
        "snap",
        "Dockerfile",
        4294967296,
        { context },
      );

      expect(snapshot).toEqual(mockSnapshot);
      expect(createSandboxSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          name: expect.stringMatching(/^snapshot-builder-/),
          fsCapacityBytes: 4294967296,
        }),
      );
      // Build scratch must live on the capacity-backed root filesystem, not
      // the RAM-backed /tmp tmpfs that fsCapacityBytes does not size.
      const tarPath = writes[0][0];
      expect(tarPath).toMatch(
        /^\/var\/lib\/langsmith-build\/[^/]+\/context\.tar$/,
      );
      expect(writes[0][1]).toEqual(expect.any(Uint8Array));
      expect(commands[0]).toContain("tar -xf");
      expect(commands[0]).toContain(tarPath);
      expect(commands[0]).not.toContain("/tmp");
      expect(commands[1]).not.toContain("/tmp");
      expect(commands[1]).toContain("--frontend");
      expect(commands[1]).toContain("dockerfile.v0");
      expect(commands[1]).toContain("docker info >/dev/null 2>&1");
      expect(commands[1]).toContain("| docker load");
      expect(captureSnapshotSpy).toHaveBeenCalledWith(
        "builder",
        "snap",
        expect.objectContaining({
          dockerImage: expect.stringMatching(/^langsmith-snapshot-build:/),
          fsCapacityBytes: 4294967296,
        }),
      );
      expect(fakeSandbox.delete).toHaveBeenCalledTimes(1);
    } finally {
      await rm(context, { recursive: true, force: true });
    }
  });

  it("createSnapshotFromDockerfile should forward vCpus/memBytes to the builder", async () => {
    const context = await mkdtemp(join(tmpdir(), "langsmith-docker-context-"));
    const client = createClientWithMock(jest.fn<typeof fetch>());
    const fakeSandbox = {
      name: "builder",
      write: jest
        .fn<(path: string, content: string | Uint8Array) => Promise<void>>()
        .mockResolvedValue(undefined),
      run: jest
        .fn<
          (
            command: string,
          ) => Promise<{ stdout: string; stderr: string; exit_code: number }>
        >()
        .mockResolvedValue({ stdout: "", stderr: "", exit_code: 0 }),
      delete: jest.fn<() => Promise<void>>().mockResolvedValue(undefined),
    };
    const createSandboxSpy = jest
      .spyOn(client, "createSandbox")
      .mockResolvedValue(fakeSandbox as any);
    jest.spyOn(client, "captureSnapshot").mockResolvedValue({
      id: "snap-1",
      name: "snap",
      status: "ready",
      fs_capacity_bytes: 4294967296,
    });

    try {
      await writeFile(join(context, "Dockerfile"), "FROM scratch\n");

      await client.createSnapshotFromDockerfile(
        "snap",
        "Dockerfile",
        4294967296,
        {
          context,
          vCpus: 2,
          memBytes: 8589934592,
        },
      );

      expect(createSandboxSpy).toHaveBeenCalledWith(
        expect.objectContaining({ vCpus: 2, memBytes: 8589934592 }),
      );
    } finally {
      await rm(context, { recursive: true, force: true });
    }
  });

  it("captureSnapshot should POST to /boxes/{name}/snapshot", async () => {
    const mockFetch = jest
      .fn<typeof fetch>()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: "snap-2",
          name: "captured",
          status: "building",
          fs_capacity_bytes: 4294967296,
          source_sandbox_id: "my-vm",
        }),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: "snap-2",
          name: "captured",
          status: "ready",
          fs_capacity_bytes: 4294967296,
        }),
      } as Response);

    const client = createClientWithMock(mockFetch);
    const snapshot = await client.captureSnapshot("my-vm", "captured");

    expect(snapshot.id).toBe("snap-2");
    expect(snapshot.status).toBe("ready");
    const [url] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/boxes/my-vm/snapshot");
  });

  it("getSnapshot should return snapshot data", async () => {
    const mockFetch = jest.fn<typeof fetch>().mockResolvedValue({
      ok: true,
      json: async () => ({
        id: "snap-1",
        name: "my-env",
        status: "ready",
        fs_capacity_bytes: 4294967296,
      }),
    } as Response);

    const client = createClientWithMock(mockFetch);
    const snapshot = await client.getSnapshot("snap-1");

    expect(snapshot.id).toBe("snap-1");
    expect(snapshot.name).toBe("my-env");
  });

  it("getSnapshot should throw ResourceNotFoundError on 404", async () => {
    const mockFetch = jest.fn<typeof fetch>().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ detail: "not found" }),
      text: async () => "not found",
    } as Response);

    const client = createClientWithMock(mockFetch);
    await expect(client.getSnapshot("nonexistent")).rejects.toThrow(
      LangSmithResourceNotFoundError,
    );
  });

  it("listSnapshots should return array", async () => {
    const mockFetch = jest.fn<typeof fetch>().mockResolvedValue({
      ok: true,
      json: async () => ({
        snapshots: [
          {
            id: "snap-1",
            name: "env-1",
            status: "ready",
            fs_capacity_bytes: 4294967296,
          },
          {
            id: "snap-2",
            name: "env-2",
            status: "building",
            fs_capacity_bytes: 8589934592,
          },
        ],
        offset: 0,
      }),
    } as Response);

    const client = createClientWithMock(mockFetch);
    const snapshots = await client.listSnapshots();

    expect(snapshots).toHaveLength(2);
    expect(snapshots[0].name).toBe("env-1");
    expect(snapshots[1].status).toBe("building");

    const [url] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(new URL(url).search).toBe("");
  });

  it("listSnapshots should forward nameContains, limit, and offset as query params", async () => {
    const mockFetch = jest.fn<typeof fetch>().mockResolvedValue({
      ok: true,
      json: async () => ({
        snapshots: [
          {
            id: "snap-1",
            name: "env-1",
            status: "ready",
          },
        ],
        offset: 5,
      }),
    } as Response);

    const client = createClientWithMock(mockFetch);
    const snapshots = await client.listSnapshots({
      nameContains: "env",
      limit: 10,
      offset: 5,
    });

    expect(snapshots).toHaveLength(1);
    expect(snapshots[0].name).toBe("env-1");

    const [url] = mockFetch.mock.calls[0] as [string, RequestInit];
    const parsed = new URL(url);
    expect(parsed.pathname.endsWith("/snapshots")).toBe(true);
    expect(parsed.searchParams.get("name_contains")).toBe("env");
    expect(parsed.searchParams.get("limit")).toBe("10");
    expect(parsed.searchParams.get("offset")).toBe("5");
  });

  it("deleteSnapshot should send DELETE request", async () => {
    const mockFetch = jest.fn<typeof fetch>().mockResolvedValue({
      ok: true,
    } as Response);

    const client = createClientWithMock(mockFetch);
    await client.deleteSnapshot("snap-1");

    const [url, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/snapshots/snap-1");
    expect(init.method).toBe("DELETE");
  });

  it("waitForSnapshot should return immediately if already ready", async () => {
    const mockFetch = jest.fn<typeof fetch>().mockResolvedValue({
      ok: true,
      json: async () => ({
        id: "snap-1",
        name: "env",
        status: "ready",
        fs_capacity_bytes: 4294967296,
      }),
    } as Response);

    const client = createClientWithMock(mockFetch);
    const snapshot = await client.waitForSnapshot("snap-1");
    expect(snapshot.status).toBe("ready");
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it("waitForSnapshot should throw on failed status", async () => {
    const mockFetch = jest.fn<typeof fetch>().mockResolvedValue({
      ok: true,
      json: async () => ({
        id: "snap-1",
        name: "env",
        status: "failed",
        status_message: "Docker pull failed",
        fs_capacity_bytes: 4294967296,
      }),
    } as Response);

    const client = createClientWithMock(mockFetch);
    await expect(client.waitForSnapshot("snap-1")).rejects.toThrow(
      LangSmithResourceCreationError,
    );
  });
});

describe("SandboxClient - start/stop", () => {
  const createClientWithMock = (mockFetch: any) => {
    const client = new SandboxClient({
      apiEndpoint: "https://api.example.com/v2/sandboxes",
      apiKey: "test-key",
    });
    (client as any)._caller = { call: (fn: any) => fn() };
    (client as any)._fetchImpl = mockFetch;
    return client;
  };

  it("startSandbox should POST to /start and poll until ready", async () => {
    const mockFetch = jest
      .fn<typeof fetch>()
      // POST /boxes/my-vm/start -> 202
      .mockResolvedValueOnce({ ok: true } as Response)
      // GET /boxes/my-vm/status -> ready
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ status: "ready" }),
      } as Response)
      // GET /boxes/my-vm -> full sandbox
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          name: "my-vm",
          status: "ready",
          dataplane_url: "https://dp.example.com/my-vm",
        }),
      } as Response);

    const client = createClientWithMock(mockFetch);
    const sandbox = await client.startSandbox("my-vm");

    expect(sandbox.name).toBe("my-vm");
    expect(sandbox.status).toBe("ready");
    const [url] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/boxes/my-vm/start");
  });

  it("startSandbox should throw ResourceNotFoundError on 404", async () => {
    const mockFetch = jest.fn<typeof fetch>().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ detail: "not found" }),
      text: async () => "not found",
    } as Response);

    const client = createClientWithMock(mockFetch);
    await expect(client.startSandbox("nonexistent")).rejects.toThrow(
      LangSmithResourceNotFoundError,
    );
  });

  it("stopSandbox should POST to /stop", async () => {
    const mockFetch = jest
      .fn<typeof fetch>()
      .mockResolvedValue({ ok: true } as Response);

    const client = createClientWithMock(mockFetch);
    await client.stopSandbox("my-vm");

    const [url] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/boxes/my-vm/stop");
  });

  it("stopSandbox should throw ResourceNotFoundError on 404", async () => {
    const mockFetch = jest.fn<typeof fetch>().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ detail: "not found" }),
      text: async () => "not found",
    } as Response);

    const client = createClientWithMock(mockFetch);
    await expect(client.stopSandbox("nonexistent")).rejects.toThrow(
      LangSmithResourceNotFoundError,
    );
  });
});

describe("Sandbox - start/stop/captureSnapshot", () => {
  it("start should update status and dataplane_url", async () => {
    const mockClient = createMockClient({
      startSandbox: jest
        .fn<(name: string, opts?: any) => Promise<any>>()
        .mockResolvedValue({
          name: "my-vm",
          status: "ready",
          dataplane_url: "https://dp.example.com/my-vm",
        }),
    });

    const sandbox = new (Sandbox as any)(
      { name: "my-vm", status: "stopped", snapshot_id: "snap-1" },
      mockClient,
    );

    await sandbox.start();

    expect(sandbox.status).toBe("ready");
    expect(sandbox.dataplane_url).toBe("https://dp.example.com/my-vm");
  });

  it("stop should set status to stopped and clear dataplane_url", async () => {
    const mockClient = createMockClient({
      stopSandbox: jest
        .fn<(name: string) => Promise<void>>()
        .mockResolvedValue(undefined),
    });

    const sandbox = new (Sandbox as any)(
      {
        name: "my-vm",
        status: "ready",
        dataplane_url: "https://dp.example.com/my-vm",
      },
      mockClient,
    );

    await sandbox.stop();

    expect(sandbox.status).toBe("stopped");
    expect(sandbox.dataplane_url).toBeUndefined();
  });

  it("captureSnapshot should delegate to client", async () => {
    const mockSnapshot = {
      id: "snap-1",
      name: "captured",
      status: "ready",
      fs_capacity_bytes: 4294967296,
    };
    const mockClient = createMockClient({
      captureSnapshot: jest
        .fn<(sandboxName: string, name: string, opts?: any) => Promise<any>>()
        .mockResolvedValue(mockSnapshot),
    });

    const sandbox = new (Sandbox as any)(
      { name: "my-vm", status: "ready" },
      mockClient,
    );

    const snapshot = await sandbox.captureSnapshot("captured");

    expect(snapshot).toEqual(mockSnapshot);
    expect(mockClient.captureSnapshot).toHaveBeenCalledWith(
      "my-vm",
      "captured",
      {},
    );
  });
});

describe("SandboxClient registries", () => {
  it("exposes a cached registries accessor backed by the generated client", () => {
    const client = new SandboxClient({
      apiEndpoint: "https://api.smith.langchain.com/v2/sandboxes",
      apiKey: "k",
    });
    const first = client.registries;
    expect(first).toBeDefined();
    // Lazily built once and reused.
    expect(client.registries).toBe(first);
  });
});
