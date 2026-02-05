/* eslint-disable @typescript-eslint/no-explicit-any */
import { jest, describe, it, expect } from "@jest/globals";
import { SandboxClient } from "../experimental/sandbox/client.js";
import { Sandbox } from "../experimental/sandbox/sandbox.js";
import {
  LangSmithResourceNotFoundError,
  LangSmithDataplaneNotConfiguredError,
  LangSmithQuotaExceededError,
  LangSmithValidationError,
  LangSmithResourceTimeoutError,
  LangSmithSandboxCreationError,
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
});
