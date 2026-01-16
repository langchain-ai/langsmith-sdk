/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable no-process-env */
/* eslint-disable @typescript-eslint/no-non-null-assertion */
/* eslint-disable prefer-const */
/* eslint-disable no-instanceof/no-instanceof */
import { jest, describe } from "@jest/globals";
import { Client } from "../client.js";
import { RunTree } from "../run_trees.js";
import { traceable } from "../traceable.js";
import { getLangSmithEnvironmentVariable } from "../utils/env.js";
import { mockClient } from "./utils/mock_client.js";

// Helper function to parse mock request body
const parseMockRequestBody = async (
  body: string | Uint8Array | ReadableStream | undefined
): Promise<{ post: any[]; patch: any[] }> => {
  if (!body) {
    return { post: [], patch: [] };
  }

  if (typeof body === "string") {
    return JSON.parse(body);
  }

  let rawMultipart: string;
  if (body instanceof ReadableStream) {
    rawMultipart = await new Response(body).text();
  } else {
    rawMultipart = new TextDecoder().decode(body);
  }

  if (rawMultipart.trim().startsWith("{")) {
    return JSON.parse(rawMultipart);
  }

  // Parse the multipart form data boundary from the raw text
  const boundary = rawMultipart.split("\r\n")[0].trim();
  // Split the multipart body into individual parts
  const parts = rawMultipart.split(boundary).slice(1, -1);

  const entries: [string, any][] = parts.map((part) => {
    const [headers, ...contentParts] = part.trim().split("\r\n\r\n");
    const content = contentParts.join("\r\n\r\n");
    // Extract the name from Content-Disposition header
    const nameMatch = headers.match(/name="([^"]+)"/);
    const name = nameMatch ? nameMatch[1] : "";
    return [name, content.trim()];
  });

  const reconstructedBody: any = {
    post: [],
    patch: [],
  };

  for (const [key, value] of entries) {
    let [method, id, type] = key.split(".");
    let parsedValue;
    try {
      parsedValue = JSON.parse(value);
    } catch (e) {
      parsedValue = value;
    }

    if (!(method in reconstructedBody)) {
      throw new Error(`${method} must be "post" or "patch"`);
    }

    if (!type) {
      reconstructedBody[method as keyof typeof reconstructedBody].push(
        parsedValue
      );
    } else {
      for (const item of reconstructedBody[method]) {
        if (item.id === id) {
          item[type] = parsedValue;
        }
      }
    }
  }

  return reconstructedBody;
};

describe("LANGSMITH_RUNS_ENDPOINTS Replica Testing", () => {
  let originalEnv: NodeJS.ProcessEnv;

  beforeEach(() => {
    // Save original environment
    originalEnv = { ...process.env };

    // Clear relevant environment variables
    delete process.env.LANGSMITH_ENDPOINT;
    delete process.env.LANGCHAIN_ENDPOINT;
    delete process.env.LANGSMITH_RUNS_ENDPOINTS;
    delete process.env.LANGSMITH_API_KEY;
    delete process.env.LANGCHAIN_API_KEY;
  });

  afterEach(() => {
    // Restore original environment
    process.env = originalEnv;
    jest.clearAllMocks();
  });

  describe("Environment Variable Reading", () => {
    it("should parse LANGSMITH_RUNS_ENDPOINTS JSON correctly", () => {
      const endpointsConfig = {
        "https://api.smith.langchain.com": "primary-key-123",
        "https://replica1.example.com": "replica1-key-456",
        "https://replica2.example.com": "replica2-key-789",
      };

      process.env.LANGSMITH_RUNS_ENDPOINTS = JSON.stringify(endpointsConfig);

      const envVar = getLangSmithEnvironmentVariable("RUNS_ENDPOINTS");
      expect(envVar).toBe(JSON.stringify(endpointsConfig));

      const parsed = JSON.parse(envVar!);
      expect(parsed).toEqual(endpointsConfig);
    });

    it("should handle malformed JSON gracefully", () => {
      process.env.LANGSMITH_RUNS_ENDPOINTS = "invalid-json";

      const envVar = getLangSmithEnvironmentVariable("RUNS_ENDPOINTS");
      expect(envVar).toBe("invalid-json");

      expect(() => JSON.parse(envVar!)).toThrow();
    });

    it("should prioritize LANGSMITH_RUNS_ENDPOINTS over LANGCHAIN_ variant", () => {
      process.env.LANGCHAIN_RUNS_ENDPOINTS = JSON.stringify({
        "https://old.example.com": "old-key",
      });
      process.env.LANGSMITH_RUNS_ENDPOINTS = JSON.stringify({
        "https://new.example.com": "new-key",
      });

      const envVar = getLangSmithEnvironmentVariable("RUNS_ENDPOINTS");
      expect(JSON.parse(envVar!)).toEqual({
        "https://new.example.com": "new-key",
      });
    });

    it("should parse LANGSMITH_RUNS_ENDPOINTS with new array format", () => {
      const endpointsConfig = [
        { api_url: "https://api.smith.langchain.com", api_key: "key1" },
        { api_url: "https://api.smith.langchain.com", api_key: "key2" },
        { api_url: "https://replica.example.com", api_key: "replica-key" },
      ];

      process.env.LANGSMITH_RUNS_ENDPOINTS = JSON.stringify(endpointsConfig);

      const envVar = getLangSmithEnvironmentVariable("RUNS_ENDPOINTS");
      expect(envVar).toBe(JSON.stringify(endpointsConfig));

      const parsed = JSON.parse(envVar!);
      expect(parsed).toEqual(endpointsConfig);
    });

    it("should parse LANGSMITH_RUNS_ENDPOINTS with object format", () => {
      const endpointsConfig = {
        "https://api.smith.langchain.com": "key1",
        "https://replica.example.com": "single-key",
        "https://another.example.com": "key3",
      };

      process.env.LANGSMITH_RUNS_ENDPOINTS = JSON.stringify(endpointsConfig);

      const envVar = getLangSmithEnvironmentVariable("RUNS_ENDPOINTS");
      expect(envVar).toBe(JSON.stringify(endpointsConfig));

      const parsed = JSON.parse(envVar!);
      expect(parsed).toEqual(endpointsConfig);
    });
  });

  describe("Client Replica Configuration", () => {
    it("should configure client with replica endpoints from environment", async () => {
      const endpointsConfig = {
        "https://api.smith.langchain.com": "primary-key",
        "https://replica1.example.com": "replica1-key",
        "https://replica2.example.com": "replica2-key",
      };

      process.env.LANGSMITH_RUNS_ENDPOINTS = JSON.stringify(endpointsConfig);

      const client = new Client({ autoBatchTracing: false });

      // Mock the main caller for createRun
      const callSpy = jest
        .spyOn((client as any).caller, "call")
        .mockResolvedValue({ ok: true, text: () => "" });

      // Create a run that should be sent to all replicas
      const runCreate = {
        id: "test-run-id",
        name: "test-run",
        inputs: { input: "test" },
        run_type: "chain" as const,
        start_time: Date.now(),
      };

      await client.createRun(runCreate);

      // Verify calls were made (the exact number depends on internal batching logic)
      expect(callSpy).toHaveBeenCalled();
    });

    it("should handle different API keys for different replicas", async () => {
      const endpointsConfig = {
        "https://primary.example.com": "primary-secret-key",
        "https://backup.example.com": "backup-secret-key",
      };

      process.env.LANGSMITH_RUNS_ENDPOINTS = JSON.stringify(endpointsConfig);

      const client = new Client({ autoBatchTracing: false });

      const callSpy = jest
        .spyOn((client as any).caller, "call")
        .mockResolvedValue({ ok: true, text: () => "" });

      const runCreate = {
        id: "test-run-id",
        name: "test-run",
        inputs: { input: "test" },
        run_type: "chain" as const,
        start_time: Date.now(),
      };

      await client.createRun(runCreate);

      expect(callSpy).toHaveBeenCalled();
    });
  });

  describe("RunTree Replicas", () => {
    it("should send traces to multiple replicas via RunTree", async () => {
      const endpointsConfig = {
        "https://primary.example.com": "primary-key",
        "https://secondary.example.com": "secondary-key",
      };

      process.env.LANGSMITH_RUNS_ENDPOINTS = JSON.stringify(endpointsConfig);

      const client = new Client({ autoBatchTracing: false });

      // Mock HTTP calls
      const callSpy = jest
        .spyOn((client as any).caller, "call")
        .mockResolvedValue({ ok: true, text: () => "" });

      const runTree = new RunTree({
        name: "test-run",
        inputs: { input: "test" },
        client,
        project_name: "test-project",
      });

      await runTree.postRun();

      // Verify calls were made for primary endpoint
      expect(callSpy).toHaveBeenCalled();
    });

    it("should handle replica-specific project names", async () => {
      const client = new Client({ autoBatchTracing: false });

      const callSpy = jest
        .spyOn((client as any).caller, "call")
        .mockResolvedValue({ ok: true, text: () => "" });

      const runTree = new RunTree({
        name: "test-run",
        inputs: { input: "test" },
        client,
        project_name: "primary-project",
        replicas: [
          {
            apiUrl: "https://replica1.example.com",
            apiKey: "replica1-key",
            projectName: "replica1-project",
          },
          {
            apiUrl: "https://replica2.example.com",
            apiKey: "replica2-key",
            projectName: "replica2-project",
          },
        ],
      });

      await runTree.postRun();

      // Should make calls for primary + replicas (at least 1 call)
      expect(callSpy).toHaveBeenCalled();
    });

    it("should handle new array format with multiple endpoints", async () => {
      const endpointsConfig = [
        {
          api_url: "https://workspace1.example.com",
          api_key: "workspace1-key",
        },
        {
          api_url: "https://workspace2.example.com",
          api_key: "workspace2-key",
        },
        {
          api_url: "https://workspace1.example.com",
          api_key: "workspace1-alt-key",
        },
      ];

      process.env.LANGSMITH_RUNS_ENDPOINTS = JSON.stringify(endpointsConfig);

      const client = new Client({ autoBatchTracing: false });

      const callSpy = jest
        .spyOn((client as any).caller, "call")
        .mockResolvedValue({ ok: true, text: () => "" });

      const runTree = new RunTree({
        name: "test-run",
        inputs: { input: "test" },
        client,
        project_name: "test-project",
      });

      await runTree.postRun();

      // Should make calls for all replicas
      expect(callSpy).toHaveBeenCalled();
    });

    it("should handle object format", async () => {
      const endpointsConfig = {
        "https://workspace1.example.com": "workspace1-key",
        "https://workspace2.example.com": "workspace2-key",
        "https://single.example.com": "single-key",
      };

      process.env.LANGSMITH_RUNS_ENDPOINTS = JSON.stringify(endpointsConfig);

      const client = new Client({ autoBatchTracing: false });

      const callSpy = jest
        .spyOn((client as any).caller, "call")
        .mockResolvedValue({ ok: true, text: () => "" });

      const runTree = new RunTree({
        name: "test-run",
        inputs: { input: "test" },
        client,
        project_name: "test-project",
      });

      await runTree.postRun();

      // Should make calls for all replicas (3 total)
      expect(callSpy).toHaveBeenCalled();
    });
  });

  describe("Traceable with Replicas", () => {
    it("should send traces to replicas when using traceable functions", async () => {
      const endpointsConfig = {
        "https://primary.example.com": "primary-key",
        "https://replica.example.com": "replica-key",
      };

      process.env.LANGSMITH_RUNS_ENDPOINTS = JSON.stringify(endpointsConfig);

      const client = new Client({ autoBatchTracing: false });

      const callSpy = jest
        .spyOn((client as any).caller, "call")
        .mockResolvedValue({ ok: true, text: () => "" });

      const tracedFunction = traceable(
        async (input: string) => {
          return { output: `processed: ${input}` };
        },
        {
          client,
          name: "test-traceable",
          tracingEnabled: true,
        }
      );

      const result = await tracedFunction("test input");

      expect(result).toEqual({ output: "processed: test input" });

      // Verify traces were sent
      expect(callSpy).toHaveBeenCalled();
    });
  });

  describe("Batch Processing with Replicas", () => {
    it("should send batched runs to multiple endpoints", async () => {
      const endpointsConfig = {
        "https://primary.example.com": "primary-key",
        "https://replica.example.com": "replica-key",
      };

      process.env.LANGSMITH_RUNS_ENDPOINTS = JSON.stringify(endpointsConfig);

      const mockFetch = jest.fn<typeof fetch>().mockResolvedValue({
        ok: true,
        status: 200,
        text: () => Promise.resolve(""),
        json: () => Promise.resolve({}),
      } as Response);

      const client = new Client({
        autoBatchTracing: true,
        fetchImplementation: mockFetch,
      });

      const batchCallSpy = mockFetch;

      jest.spyOn(client as any, "_getServerInfo").mockResolvedValue({
        version: "test",
        batch_ingest_config: { use_multipart_endpoint: false },
      });

      // Create multiple runs using traceable to avoid authorization issues
      const traceableFn = traceable(
        async (input: string) => ({ output: input }),
        { client, name: "batch-test", tracingEnabled: true }
      );

      // Execute multiple traceable functions
      const promises = Array.from({ length: 3 }, (_, i) =>
        traceableFn(`test-${i}`)
      );

      await Promise.all(promises);
      await client.awaitPendingTraceBatches();

      // Should have exactly two requests (one per replica endpoint)
      expect(batchCallSpy).toHaveBeenCalledTimes(2);

      // Parse the batch payloads to verify separate batches per replica
      const calls = batchCallSpy.mock.calls;
      const parsedBodies = await Promise.all(
        calls.map(async (call) => {
          const requestParam = call[1] as any; // fetch calls have [url, init] format
          return parseMockRequestBody(requestParam?.body);
        })
      );

      // Should have exactly 2 batches (one per replica)
      expect(parsedBodies).toHaveLength(2);

      // Both batches should have identical structure and content
      parsedBodies.forEach((body) => {
        expect(body.post).toHaveLength(3); // 3 traceable function calls
        expect(body.patch).toHaveLength(0); // Updates should be combined into post

        // Verify each posted run has the expected structure
        body.post.forEach((run: any, index: number) => {
          expect(run).toMatchObject({
            name: "batch-test",
            inputs: { input: `test-${index}` },
            outputs: { output: `test-${index}` },
            run_type: "chain",
          });
        });
      });

      // Verify both batches contain identical runs
      expect(parsedBodies[0].post).toEqual(parsedBodies[1].post);
      expect(parsedBodies[0].patch).toEqual(parsedBodies[1].patch);
    });

    it("should handle multipart batch endpoint with replicas", async () => {
      const endpointsConfig = {
        "https://primary.example.com": "primary-key",
        "https://replica.example.com": "replica-key",
      };

      process.env.LANGSMITH_RUNS_ENDPOINTS = JSON.stringify(endpointsConfig);

      const multipartCallSpy = jest.fn<typeof fetch>().mockResolvedValue({
        ok: true,
        text: () => Promise.resolve(""),
      } as Response);

      const client = new Client({
        autoBatchTracing: true,
        fetchImplementation: multipartCallSpy,
      });

      jest.spyOn(client as any, "_getServerInfo").mockResolvedValue({
        version: "test",
        batch_ingest_config: { use_multipart_endpoint: true },
      });

      const traceableFn = traceable(
        async (input: string) => ({ output: input }),
        { client, name: "multipart-test", tracingEnabled: true }
      );

      // Execute multiple traceable functions to ensure batching
      const promises = Array.from({ length: 2 }, (_, i) =>
        traceableFn(`multipart-test-${i}`)
      );

      await Promise.all(promises);
      await client.awaitPendingTraceBatches();

      // Should have exactly two requests (one per replica endpoint)
      expect(multipartCallSpy).toHaveBeenCalledTimes(2);

      // Parse the multipart batch payloads to verify separate batches per replica
      const calls = multipartCallSpy.mock.calls;
      const parsedBodies = await Promise.all(
        calls.map(async (call) => {
          const requestParam = call[1] as any;
          return parseMockRequestBody(requestParam?.body);
        })
      );

      // Should have exactly 2 batches (one per replica)
      expect(parsedBodies).toHaveLength(2);

      // Both batches should have identical structure and content
      parsedBodies.forEach((body) => {
        expect(body.post).toHaveLength(2); // 2 traceable function calls
        expect(body.patch).toHaveLength(0); // Updates should be combined into post

        // Verify each posted run has the expected structure
        body.post.forEach((run: any, index: number) => {
          expect(run).toMatchObject({
            name: "multipart-test",
            inputs: { input: `multipart-test-${index}` },
            outputs: { output: `multipart-test-${index}` },
            run_type: "chain",
          });
        });
      });

      // Verify both batches contain identical runs
      expect(parsedBodies[0].post).toEqual(parsedBodies[1].post);
      expect(parsedBodies[0].patch).toEqual(parsedBodies[1].patch);
    });
  });

  describe("Error Handling", () => {
    it("should handle replica endpoint failures gracefully", async () => {
      const endpointsConfig = {
        "https://primary.example.com": "primary-key",
        "https://failing-replica.example.com": "replica-key",
      };

      process.env.LANGSMITH_RUNS_ENDPOINTS = JSON.stringify(endpointsConfig);

      const client = new Client({ autoBatchTracing: false });

      // Mock primary to succeed, replica to fail
      const callSpy = jest
        .spyOn((client as any).caller, "call")
        .mockImplementation((...args: unknown[]) => {
          const url = args[0] as string;
          if (url.includes("failing-replica")) {
            return Promise.reject(new Error("Network error"));
          }
          return Promise.resolve({ ok: true, text: () => "" });
        });

      const consoleSpy = jest
        .spyOn(console, "error")
        .mockImplementation(() => {});

      const runTree = new RunTree({
        name: "test-run",
        inputs: { input: "test" },
        client,
        project_name: "test-project",
        replicas: [
          {
            apiUrl: "https://failing-replica.example.com",
            apiKey: "replica-key",
            projectName: "replica-project",
          },
        ],
      });

      // Should not throw, but should log errors
      await expect(runTree.postRun()).resolves.not.toThrow();

      expect(callSpy).toHaveBeenCalled();
      expect(consoleSpy).toHaveBeenCalled();

      consoleSpy.mockRestore();
    });

    it("should validate endpoint URLs", () => {
      const invalidEndpointsConfig = {
        "not-a-valid-url": "some-key",
        "https://valid.example.com": "valid-key",
      };

      process.env.LANGSMITH_RUNS_ENDPOINTS = JSON.stringify(
        invalidEndpointsConfig
      );

      // Creating client should not throw, but invalid URLs might be handled during requests
      expect(() => new Client({ autoBatchTracing: false })).not.toThrow();
    });

    it("should handle invalid value types in LANGSMITH_RUNS_ENDPOINTS", async () => {
      const invalidEndpointsConfig = {
        "https://valid-string.example.com": "valid-key",
        "https://invalid-number.example.com": 123,
        "https://invalid-object.example.com": { key: "value" },
        "https://invalid-null.example.com": null,
      };

      process.env.LANGSMITH_RUNS_ENDPOINTS = JSON.stringify(
        invalidEndpointsConfig
      );

      // Spy on console.warn to check warning messages
      const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});

      const client = new Client({ autoBatchTracing: false });

      // Mock HTTP calls to prevent actual requests
      jest
        .spyOn((client as any).caller, "call")
        .mockResolvedValue({ ok: true, text: () => "" });

      // Create a RunTree to trigger replica parsing
      const runTree = new RunTree({
        name: "test-run",
        inputs: { input: "test" },
        client,
        project_name: "test-project",
      });

      await runTree.postRun();

      // Should warn about invalid value types
      expect(warnSpy).toHaveBeenCalledWith(
        expect.stringContaining(
          "Invalid value type in LANGSMITH_RUNS_ENDPOINTS"
        )
      );

      warnSpy.mockRestore();
    });

    it("should handle invalid items in new array format", async () => {
      const invalidEndpointsConfig = [
        { api_url: "https://valid.example.com", api_key: "valid-key" },
        "invalid-string-item",
        { api_url: "https://missing-key.example.com" }, // missing api_key
        { api_key: "missing-url-key" }, // missing api_url
        { api_url: 123, api_key: "invalid-url-type" }, // invalid api_url type
        { api_url: "https://invalid-key-type.example.com", api_key: 456 }, // invalid api_key type
      ];

      process.env.LANGSMITH_RUNS_ENDPOINTS = JSON.stringify(
        invalidEndpointsConfig
      );

      // Spy on console.warn to check warning messages
      const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});

      const client = new Client({ autoBatchTracing: false });

      jest
        .spyOn((client as any).caller, "call")
        .mockResolvedValue({ ok: true, text: () => "" });

      // Create a RunTree to trigger replica parsing
      const runTree = new RunTree({
        name: "test-run",
        inputs: { input: "test" },
        client,
        project_name: "test-project",
      });

      await runTree.postRun();

      // Should warn about various invalid types
      expect(warnSpy).toHaveBeenCalledWith(
        expect.stringContaining("Invalid item type in LANGSMITH_RUNS_ENDPOINTS")
      );
      expect(warnSpy).toHaveBeenCalledWith(
        expect.stringContaining(
          "Invalid api_url type in LANGSMITH_RUNS_ENDPOINTS"
        )
      );
      expect(warnSpy).toHaveBeenCalledWith(
        expect.stringContaining(
          "Invalid api_key type in LANGSMITH_RUNS_ENDPOINTS"
        )
      );

      warnSpy.mockRestore();
    });
  });

  describe("Performance and Concurrency", () => {
    it("should handle concurrent requests to multiple replicas", async () => {
      const endpointsConfig = {
        "https://primary.example.com": "primary-key",
        "https://replica1.example.com": "replica1-key",
        "https://replica2.example.com": "replica2-key",
        "https://replica3.example.com": "replica3-key",
      };

      process.env.LANGSMITH_RUNS_ENDPOINTS = JSON.stringify(endpointsConfig);

      const client = new Client({ autoBatchTracing: true });

      const callSpy = jest
        .spyOn((client as any).batchIngestCaller, "callWithOptions")
        .mockResolvedValue({ ok: true, text: () => "" });

      jest.spyOn(client as any, "_getServerInfo").mockResolvedValue({
        version: "test",
        batch_ingest_config: { use_multipart_endpoint: false },
      });

      // Create many concurrent traceable functions
      const traceableFn = traceable(
        async (input: string) => ({ output: input }),
        { client, name: "concurrent-test", tracingEnabled: true }
      );

      const concurrentRuns = Array.from({ length: 20 }, (_, i) =>
        traceableFn(`concurrent-${i}`)
      );

      await Promise.all(concurrentRuns);
      await client.awaitPendingTraceBatches();

      expect(callSpy).toHaveBeenCalled();
    });
  });

  describe("Replica Behavior with Main Project", () => {
    it("replica targeting same project as default should include children", async () => {
      const { client, callSpy } = mockClient();
      const mainProject = "main-project";

      // Grandchild has no replicas
      const grandchild = traceable(
        async () => {
          return "grandchild";
        },
        {
          name: "grandchild",
          client,
          project_name: mainProject,
          tracingEnabled: true,
        }
      );

      // Child has replicas: one for main project, one for replica project with reroot
      const child = traceable(
        async () => {
          const grandchildRes = await grandchild();
          return "child: " + grandchildRes;
        },
        {
          replicas: [
            {
              projectName: mainProject, // Same as default
            },
            {
              projectName: "replica-project",
              reroot: true,
            },
          ],
          name: "child",
          client,
          project_name: mainProject,
          tracingEnabled: true,
        }
      );

      // Parent has no replicas
      const parent = traceable(
        async () => {
          const childRes = await child();
          return "parent: " + childRes;
        },
        {
          name: "parent",
          client,
          project_name: mainProject,
          tracingEnabled: true,
        }
      );

      await parent();

      // Wait for async operations
      await new Promise((resolve) => setTimeout(resolve, 100));

      // Get all POST calls
      const allPostCalls = callSpy.mock.calls.filter(
        (call) =>
          (call[0] as string).includes("/runs") &&
          (call[1] as any)?.method === "POST"
      );

      // Parse runs from calls
      const runs = allPostCalls.map((call) => {
        const body = (call[1] as any)?.body;
        let bodyStr: string;
        if (typeof body === "string") {
          bodyStr = body;
        } else if (Buffer.isBuffer(body)) {
          bodyStr = body.toString("utf-8");
        } else if (ArrayBuffer.isView(body)) {
          bodyStr = new TextDecoder().decode(body);
        } else {
          bodyStr = JSON.stringify(body);
        }
        return JSON.parse(bodyStr);
      });

      // Count runs by project
      const mainProjectRuns = runs.filter(
        (r) => r.session_name === mainProject
      );
      const replicaProjectRuns = runs.filter(
        (r) => r.session_name === "replica-project"
      );

      // Expected:
      // - Parent: 1 in main (no replicas, uses default)
      // - Child: 2 (main via default + replica-project via replica with new ID, skips main replica)
      // - Grandchild: 2 (inherits child's replicas, main via default + replica-project via replica with new ID)
      // Total: 5 runs (3 in main, 2 in replica-project)

      expect(runs.length).toBe(5);
      expect(mainProjectRuns.length).toBe(3); // parent, child, grandchild
      expect(replicaProjectRuns.length).toBe(2); // child (rerooted), grandchild (remapped IDs)

      // Verify each run type appears in main project
      const mainNames = mainProjectRuns.map((r) => r.name).sort();
      expect(mainNames).toEqual(["child", "grandchild", "parent"]);

      // Verify child and grandchild appear in replica project
      const replicaNames = replicaProjectRuns.map((r) => r.name).sort();
      expect(replicaNames).toEqual(["child", "grandchild"]);
    });
  });
});
