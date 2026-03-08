/* eslint-disable @typescript-eslint/no-explicit-any */
import { jest, describe, it, expect } from "@jest/globals";
import { SandboxClient } from "../experimental/sandbox/client.js";
import { Sandbox } from "../experimental/sandbox/sandbox.js";
import {
  LangSmithResourceCreationError,
  LangSmithResourceNotFoundError,
  LangSmithDataplaneNotConfiguredError,
  LangSmithQuotaExceededError,
  LangSmithValidationError,
  LangSmithResourceTimeoutError,
  LangSmithSandboxCreationError,
  LangSmithSandboxNotReadyError,
} from "../experimental/sandbox/errors.js";

// Helper to create typed mock functions
const createMockFetch = (response: any) =>
  jest
    .fn<(url: string, init?: RequestInit) => Promise<Response>>()
    .mockResolvedValue(response);

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
      // Create a minimal mock client
      const mockClient = {
        _fetch: createMockFetch({}),
        deleteSandbox: jest
          .fn<() => Promise<void>>()
          .mockResolvedValue(undefined),
      } as unknown as SandboxClient;

      const sandbox = new (Sandbox as any)(
        {
          id: "sandbox-123",
          name: "test-sandbox",
          template_name: "python-sandbox",
          // No dataplane_url
        },
        mockClient,
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

      const mockClient = {
        _fetch: mockFetch,
        deleteSandbox: jest
          .fn<() => Promise<void>>()
          .mockResolvedValue(undefined),
      } as unknown as SandboxClient;

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

      const mockClient = {
        _fetch: mockFetch,
        deleteSandbox: jest
          .fn<() => Promise<void>>()
          .mockResolvedValue(undefined),
      } as unknown as SandboxClient;

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

      const mockClient = {
        _fetch: mockFetch,
        deleteSandbox: jest
          .fn<() => Promise<void>>()
          .mockResolvedValue(undefined),
      } as unknown as SandboxClient;

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

      const mockClient = {
        _fetch: mockFetch,
        deleteSandbox: jest
          .fn<() => Promise<void>>()
          .mockResolvedValue(undefined),
      } as unknown as SandboxClient;

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

      const mockClient = {
        _fetch: mockFetch,
        deleteSandbox: jest
          .fn<() => Promise<void>>()
          .mockResolvedValue(undefined),
      } as unknown as SandboxClient;

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

      const mockClient = {
        _fetch: createMockFetch({}),
        deleteSandbox: mockDeleteSandbox,
      } as unknown as SandboxClient;

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
    const mockFetch = jest.fn<typeof fetch>().mockImplementation(
      async (url: any) => {
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
      }
    );

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
    const mockClient = {
      _fetch: createMockFetch({}),
      deleteSandbox: jest
        .fn<() => Promise<void>>()
        .mockResolvedValue(undefined),
    } as unknown as SandboxClient;

    const sandbox = new (Sandbox as any)(
      {
        name: "test-sandbox",
        template_name: "python-sandbox",
        status: "provisioning",
        status_message: "Waiting for resources",
      },
      mockClient
    );

    expect(sandbox.status).toBe("provisioning");
    expect(sandbox.status_message).toBe("Waiting for resources");
  });

  it("should throw LangSmithSandboxNotReadyError when status is not ready", async () => {
    const mockClient = {
      _fetch: createMockFetch({}),
      deleteSandbox: jest
        .fn<() => Promise<void>>()
        .mockResolvedValue(undefined),
    } as unknown as SandboxClient;

    const sandbox = new (Sandbox as any)(
      {
        name: "test-sandbox",
        template_name: "python-sandbox",
        dataplane_url: "https://dp.example.com",
        status: "provisioning",
      },
      mockClient
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

    const mockClient = {
      _fetch: mockFetch,
      deleteSandbox: jest
        .fn<() => Promise<void>>()
        .mockResolvedValue(undefined),
    } as unknown as SandboxClient;

    const sandbox = new (Sandbox as any)(
      {
        name: "test-sandbox",
        template_name: "python-sandbox",
        dataplane_url: "https://dp.example.com",
        status: "ready",
      },
      mockClient
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
});
