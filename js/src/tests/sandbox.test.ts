/* eslint-disable @typescript-eslint/no-explicit-any */
import { jest, describe, it, expect } from "@jest/globals";
import { SandboxClient } from "../experimental/sandbox/client.js";
import { Sandbox } from "../experimental/sandbox/sandbox.js";
import { CommandHandle } from "../experimental/sandbox/command_handle.js";
import {
  buildWsUrl,
  buildAuthHeaders,
  WSStreamControl,
  raiseForWsError,
} from "../experimental/sandbox/ws_execute.js";
import {
  LangSmithResourceCreationError,
  LangSmithResourceNotFoundError,
  LangSmithDataplaneNotConfiguredError,
  LangSmithQuotaExceededError,
  LangSmithValidationError,
  LangSmithResourceTimeoutError,
  LangSmithSandboxCreationError,
  LangSmithSandboxNotReadyError,
  LangSmithSandboxOperationError,
  LangSmithCommandTimeoutError,
  LangSmithSandboxServerReloadError,
} from "../experimental/sandbox/errors.js";
import type { WsMessage, OutputChunk } from "../experimental/sandbox/types.js";
import { validateTtl } from "../experimental/sandbox/helpers.js";

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
  } as unknown as SandboxClient);

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
});

describe("Sandbox", () => {
  describe("run", () => {
    it("should throw DataplaneNotConfiguredError when dataplane_url is missing", async () => {
      const sandbox = new (Sandbox as any)(
        {
          id: "sandbox-123",
          name: "test-sandbox",
          template_name: "python-sandbox",
          // No dataplane_url
        },
        createMockClient(),
        false
      );

      await expect(sandbox.run("echo hello")).rejects.toThrow(
        LangSmithDataplaneNotConfiguredError
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
          template_name: "python-sandbox",
          dataplane_url: "https://dataplane.example.com",
        },
        mockClient,
        false
      );

      const result = await sandbox.run('echo "Hello, World!"');

      expect(result.stdout).toBe("Hello, World!\n");
      expect(result.stderr).toBe("");
      expect(result.exit_code).toBe(0);
      expect(mockFetch).toHaveBeenCalledTimes(1);
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
          template_name: "python-sandbox",
          dataplane_url: "https://dataplane.example.com",
        },
        mockClient,
        false
      );

      await sandbox.run("echo $MY_VAR", {
        env: { MY_VAR: "test-value" },
        cwd: "/tmp",
      });

      const [, options] = mockFetch.mock.calls[0] as [string, RequestInit];
      const body = JSON.parse(options.body as string);
      expect(body.env).toEqual({ MY_VAR: "test-value" });
      expect(body.cwd).toBe("/tmp");
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
          template_name: "python-sandbox",
          dataplane_url: "https://dataplane.example.com",
        },
        mockClient,
        false
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
          template_name: "python-sandbox",
          dataplane_url: "https://dataplane.example.com",
        },
        mockClient,
        false
      );

      const content = new TextEncoder().encode("Binary content");
      await sandbox.write("/tmp/test.bin", content);

      expect(mockFetch).toHaveBeenCalledTimes(1);
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
          template_name: "python-sandbox",
          dataplane_url: "https://dataplane.example.com",
        },
        mockClient,
        false
      );

      const content = await sandbox.read("/tmp/test.txt");

      const text = new TextDecoder().decode(content);
      expect(text).toBe("File content here");
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
          template_name: "python-sandbox",
          dataplane_url: "https://dataplane.example.com",
        },
        mockClient
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
        template_name: "python-sandbox",
        dataplane_url: "https://dp.example.com",
        status: "ready",
      }),
    } as Response);

    const client = createClientWithMock(mockFetch);
    await client.createSandbox("python-sandbox");

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
        template_name: "python-sandbox",
        status: "provisioning",
      }),
    } as Response);

    const client = createClientWithMock(mockFetch);
    const sandbox = await client.createSandbox("python-sandbox", {
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
        template_name: "python-sandbox",
        status: "provisioning",
      }),
    } as Response);

    const client = createClientWithMock(mockFetch);
    await client.createSandbox("python-sandbox", { waitForReady: false });

    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    // The signal should be an AbortSignal with 30s timeout
    expect(init.signal).toBeDefined();
  });

  it("should include ttl_seconds and idle_ttl_seconds in the request body when set", async () => {
    const mockFetch = jest.fn<typeof fetch>().mockResolvedValue({
      ok: true,
      json: async () => ({
        name: "test-sb",
        template_name: "python-sandbox",
        dataplane_url: "https://dp.example.com",
        status: "ready",
        ttl_seconds: 3600,
        idle_ttl_seconds: 600,
        expires_at: "2026-03-24T15:00:00Z",
      }),
    } as Response);

    const client = createClientWithMock(mockFetch);
    const sandbox = await client.createSandbox("python-sandbox", {
      ttlSeconds: 3600,
      idleTtlSeconds: 600,
    });

    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(init.body as string);
    expect(body.ttl_seconds).toBe(3600);
    expect(body.idle_ttl_seconds).toBe(600);
    expect(sandbox.ttl_seconds).toBe(3600);
    expect(sandbox.idle_ttl_seconds).toBe(600);
    expect(sandbox.expires_at).toBe("2026-03-24T15:00:00Z");
  });

  it("should reject invalid TTL values before calling the API", async () => {
    const mockFetch = jest.fn<typeof fetch>();
    const client = createClientWithMock(mockFetch);

    await expect(
      client.createSandbox("python-sandbox", { ttlSeconds: 61 })
    ).rejects.toThrow(LangSmithValidationError);
    expect(mockFetch).not.toHaveBeenCalled();
  });
});

describe("validateTtl", () => {
  it("accepts undefined, 0, and positive multiples of 60", () => {
    expect(() => validateTtl(undefined, "ttlSeconds")).not.toThrow();
    expect(() => validateTtl(0, "ttlSeconds")).not.toThrow();
    expect(() => validateTtl(60, "ttlSeconds")).not.toThrow();
    expect(() => validateTtl(3600, "idleTtlSeconds")).not.toThrow();
  });

  it("rejects negative values and non-multiples of 60", () => {
    expect(() => validateTtl(-1, "ttlSeconds")).toThrow(
      LangSmithValidationError
    );
    expect(() => validateTtl(30, "ttlSeconds")).toThrow(
      LangSmithValidationError
    );
    expect(() => validateTtl(61, "idleTtlSeconds")).toThrow(
      LangSmithValidationError
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

  it("should PATCH ttl fields when provided in options", async () => {
    const mockFetch = jest.fn<typeof fetch>().mockResolvedValue({
      ok: true,
      json: async () => ({
        name: "sb-1",
        template_name: "python-sandbox",
        status: "ready",
        ttl_seconds: 0,
        idle_ttl_seconds: 1800,
      }),
    } as Response);

    const client = createClientWithMock(mockFetch);
    await client.updateSandbox("sb-1", {
      ttlSeconds: 0,
      idleTtlSeconds: 1800,
    });

    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe("PATCH");
    const body = JSON.parse(init.body as string);
    expect(body.ttl_seconds).toBe(0);
    expect(body.idle_ttl_seconds).toBe(1800);
    expect(body.name).toBeUndefined();
  });

  it("should still support rename via string second argument", async () => {
    const mockFetch = jest.fn<typeof fetch>().mockResolvedValue({
      ok: true,
      json: async () => ({
        name: "sb-renamed",
        template_name: "python-sandbox",
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
        template_name: "python-sandbox",
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
      LangSmithResourceNotFoundError
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
            template_name: "python-sandbox",
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
      client.waitForSandbox("test-sb", { pollInterval: 0.01 })
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
      client.waitForSandbox("test-sb", { timeout: 0.05, pollInterval: 0.01 })
    ).rejects.toThrow(LangSmithResourceTimeoutError);
  });
});

describe("Sandbox - status fields and not-ready guard", () => {
  it("should populate status and status_message from SandboxData", () => {
    const sandbox = new (Sandbox as any)(
      {
        name: "test-sandbox",
        template_name: "python-sandbox",
        status: "provisioning",
        status_message: "Waiting for resources",
      },
      createMockClient()
    );

    expect(sandbox.status).toBe("provisioning");
    expect(sandbox.status_message).toBe("Waiting for resources");
  });

  it("should throw LangSmithSandboxNotReadyError when status is not ready", async () => {
    const sandbox = new (Sandbox as any)(
      {
        name: "test-sandbox",
        template_name: "python-sandbox",
        dataplane_url: "https://dp.example.com",
        status: "provisioning",
      },
      createMockClient()
    );

    await expect(sandbox.run("echo hello")).rejects.toThrow(
      LangSmithSandboxNotReadyError
    );
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
        template_name: "python-sandbox",
        dataplane_url: "https://dp.example.com",
        status: "ready",
      },
      createMockClient({ _fetch: mockFetch })
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
      "pending"
    );
    expect(error.resourceType).toBe("sandbox");
    expect(error.lastStatus).toBe("pending");
    expect(error.toString()).toContain("pending");
  });

  it("LangSmithQuotaExceededError should have quotaType", () => {
    const error = new LangSmithQuotaExceededError(
      "Quota exceeded",
      "sandbox_count"
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
      details
    );
    expect(error.field).toBe("cpu");
    expect(error.details).toEqual(details);
  });

  it("LangSmithSandboxCreationError should have errorType and custom toString", () => {
    const error = new LangSmithSandboxCreationError(
      "Creation failed",
      "ImagePull"
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
      "ImagePull"
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
      "wss://dataplane.example.com/execute/ws"
    );
  });

  it("should convert http to ws", () => {
    expect(buildWsUrl("http://localhost:8080")).toBe(
      "ws://localhost:8080/execute/ws"
    );
  });

  it("should handle URLs with paths", () => {
    expect(buildWsUrl("https://dataplane.example.com/some/path")).toBe(
      "wss://dataplane.example.com/some/path/execute/ws"
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
      LangSmithSandboxOperationError
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
    messages: WsMessage[]
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
        LangSmithSandboxOperationError
      );
    });

    it("should throw if first message is not 'started'", async () => {
      const stream = createMockStream([
        { type: "stdout", data: "hello\n", offset: 0 },
      ]);

      const handle = new CommandHandle(stream, null, createMockSandbox());
      await expect(handle._ensureStarted()).rejects.toThrow(
        "Expected 'started' message"
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

    it("should throw if stream ends without exit message", async () => {
      const stream = createMockStream([
        { type: "started", command_id: "cmd-123", pid: 42 },
        { type: "stdout", data: "hello\n", offset: 0 },
      ]);

      const handle = new CommandHandle(stream, null, createMockSandbox());
      await handle._ensureStarted();

      await expect(handle.result).rejects.toThrow(
        "Command stream ended without exit message"
      );
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
