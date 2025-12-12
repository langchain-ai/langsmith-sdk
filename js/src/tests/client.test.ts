/* eslint-disable @typescript-eslint/no-explicit-any */
import { jest } from "@jest/globals";
import { Client, mergeRuntimeEnvIntoRun } from "../client.js";
import {
  getLangSmithEnvironmentVariables,
  getLangSmithEnvVarsMetadata,
} from "../utils/env.js";
import {
  isVersionGreaterOrEqual,
  parsePromptIdentifier,
} from "../utils/prompts.js";

describe("Client", () => {
  describe("createLLMExample", () => {
    it("should create an example with the given input and generation", async () => {
      const client = new Client({ apiKey: "test-api-key" });
      const createExampleSpy = jest
        .spyOn(client, "createExample")
        .mockResolvedValue({
          id: "test-example-id",
          dataset_id: "test-dataset-id",
          inputs: {},
          outputs: { text: "Bonjour, monde!" },
          created_at: "2022-01-01T00:00:00.000Z",
          modified_at: "2022-01-01T00:00:00.000Z",
          runs: [],
        });

      const input = "Hello, world!";
      const generation = "Bonjour, monde!";
      const options = { datasetName: "test-dataset" };

      await client.createLLMExample(input, generation, options);
      expect(createExampleSpy).toHaveBeenCalledWith(
        { input },
        { output: generation },
        options
      );
    });
  });

  describe("createChatExample", () => {
    it("should convert LangChainBaseMessage objects to examples", async () => {
      const client = new Client({ apiKey: "test-api-key" });
      const createExampleSpy = jest
        .spyOn(client, "createExample")
        .mockResolvedValue({
          id: "test-example-id",
          dataset_id: "test-dataset-id",
          inputs: {},
          outputs: { text: "Bonjour", sender: "bot" },
          created_at: "2022-01-01T00:00:00.000Z",
          modified_at: "2022-01-01T00:00:00.000Z",
          runs: [],
        });

      const input = [
        { text: "Hello", sender: "user" },
        { text: "Hi there", sender: "bot" },
      ];
      const generations = {
        type: "langchain",
        data: { text: "Bonjour", sender: "bot" },
      };
      const options = { datasetName: "test-dataset" };

      await client.createChatExample(input, generations, options);

      expect(createExampleSpy).toHaveBeenCalledWith(
        {
          input: [
            { text: "Hello", sender: "user" },
            { text: "Hi there", sender: "bot" },
          ],
        },
        {
          output: {
            data: { text: "Bonjour", sender: "bot" },
            type: "langchain",
          },
        },
        options
      );
    });
  });

  it("should trim trailing slash on a passed apiUrl", () => {
    const client = new Client({ apiUrl: "https://example.com/" });
    const result = (client as any).apiUrl;
    expect(result).toBe("https://example.com");
  });

  describe("getHostUrl", () => {
    it("should return the webUrl if it exists", () => {
      const client = new Client({
        webUrl: "http://example.com",
        apiKey: "test-api-key",
      });
      const result = (client as any).getHostUrl();
      expect(result).toBe("http://example.com");
    });

    it("should return 'http://localhost:3000' if apiUrl is localhost", () => {
      const client = new Client({ apiUrl: "http://localhost/api" });
      const result = (client as any).getHostUrl();
      expect(result).toBe("http://localhost:3000");
    });

    it("should return the webUrl without '/api' if apiUrl contains '/api'", () => {
      const client = new Client({
        webUrl: "https://example.com",
        apiKey: "test-api-key",
      });
      const result = (client as any).getHostUrl();
      expect(result).toBe("https://example.com");
    });

    it("should trim trailing slash on a passed webUrl", () => {
      const client = new Client({ webUrl: "https://example.com/" });
      const result = (client as any).getHostUrl();
      expect(result).toBe("https://example.com");
    });

    it("should trim /api/v1 from the apiUrl", () => {
      const client = new Client({
        apiUrl: "https://my-other-domain.com/api/v1",
      });
      const result = (client as any).getHostUrl();
      expect(result).toBe("https://my-other-domain.com");
    });

    it("should return 'https://dev.smith.langchain.com' if apiUrl contains 'dev'", () => {
      const client = new Client({
        apiUrl: "https://dev.smith.langchain.com/api",
        apiKey: "test-api-key",
      });
      const result = (client as any).getHostUrl();
      expect(result).toBe("https://dev.smith.langchain.com");
    });

    it("should return 'https://beta.smith.langchain.com' if apiUrl contains 'beta'", () => {
      const client = new Client({
        apiUrl: "https://beta.smith.langchain.com/api",
        apiKey: "test-api-key",
      });
      const result = (client as any).getHostUrl();
      expect(result).toBe("https://beta.smith.langchain.com");
    });

    it("should return 'https://eu.smith.langchain.com' if apiUrl contains 'eu'", () => {
      const client = new Client({
        apiUrl: "https://eu.smith.langchain.com/api",
        apiKey: "test-api-key",
      });
      const result = (client as any).getHostUrl();
      expect(result).toBe("https://eu.smith.langchain.com");
    });

    it("should return 'https://smith.langchain.com' for any other apiUrl", () => {
      const client = new Client({
        apiUrl: "https://smith.langchain.com/api",
        apiKey: "test-api-key",
      });
      const result = (client as any).getHostUrl();
      expect(result).toBe("https://smith.langchain.com");
    });
  });

  describe("env functions", () => {
    it("should return the env variables correctly", async () => {
      // eslint-disable-next-line no-process-env
      process.env.LANGCHAIN_REVISION_ID = "test_revision_id";
      // eslint-disable-next-line no-process-env
      process.env.LANGCHAIN_API_KEY = "fake_api_key";
      // eslint-disable-next-line no-process-env
      process.env.LANGCHAIN_OTHER_KEY = "test_other_key";
      // eslint-disable-next-line no-process-env
      process.env.LANGCHAIN_OTHER_NON_SENSITIVE_METADATA = "test_some_metadata";
      // eslint-disable-next-line no-process-env
      process.env.LANGCHAIN_ENDPOINT = "https://example.com";
      // eslint-disable-next-line no-process-env
      process.env.SOME_RANDOM_THING = "random";

      const envVars = getLangSmithEnvironmentVariables();
      const langchainMetadataEnvVars = getLangSmithEnvVarsMetadata();

      expect(envVars).toMatchObject({
        LANGCHAIN_REVISION_ID: "test_revision_id",
        LANGCHAIN_API_KEY: "fa********ey",
        LANGCHAIN_OTHER_KEY: "te**********ey",
        LANGCHAIN_ENDPOINT: "https://example.com",
        LANGCHAIN_OTHER_NON_SENSITIVE_METADATA: "test_some_metadata",
      });
      expect(envVars).not.toHaveProperty("SOME_RANDOM_THING");

      delete langchainMetadataEnvVars.LANGSMITH_TRACING;
      expect(langchainMetadataEnvVars).toEqual({
        revision_id: "test_revision_id",
        LANGCHAIN_OTHER_NON_SENSITIVE_METADATA: "test_some_metadata",
      });
    });
  });

  describe("isVersionGreaterOrEqual", () => {
    it("should return true if the version is greater or equal", () => {
      // Test versions equal to 0.5.23
      expect(isVersionGreaterOrEqual("0.5.23", "0.5.23")).toBe(true);

      // Test versions greater than 0.5.23
      expect(isVersionGreaterOrEqual("0.5.24", "0.5.23"));
      expect(isVersionGreaterOrEqual("0.6.0", "0.5.23"));
      expect(isVersionGreaterOrEqual("1.0.0", "0.5.23"));

      // Test versions less than 0.5.23
      expect(isVersionGreaterOrEqual("0.5.22", "0.5.23")).toBe(false);
      expect(isVersionGreaterOrEqual("0.5.0", "0.5.23")).toBe(false);
      expect(isVersionGreaterOrEqual("0.4.99", "0.5.23")).toBe(false);
    });
  });

  describe("parsePromptIdentifier", () => {
    it("should parse valid identifiers correctly", () => {
      expect(parsePromptIdentifier("name")).toEqual(["-", "name", "latest"]);
      expect(parsePromptIdentifier("owner/name")).toEqual([
        "owner",
        "name",
        "latest",
      ]);
      expect(parsePromptIdentifier("owner/name:commit")).toEqual([
        "owner",
        "name",
        "commit",
      ]);
      expect(parsePromptIdentifier("name:commit")).toEqual([
        "-",
        "name",
        "commit",
      ]);
    });

    it("should throw an error for invalid identifiers", () => {
      const invalidIdentifiers = [
        "",
        "/",
        ":",
        "owner/",
        "/name",
        "owner//name",
        "owner/name/",
        "owner/name/extra",
        ":commit",
      ];

      invalidIdentifiers.forEach((identifier) => {
        expect(() => parsePromptIdentifier(identifier)).toThrowError(
          `Invalid identifier format: ${identifier}`
        );
      });
    });
  });

  describe("_filterForSampling patch logic", () => {
    it("should filter patch runs based on trace_id instead of run.id", () => {
      const client = new Client({
        apiKey: "test-api-key",
        tracingSamplingRate: 0.5,
      });

      // Mock the _shouldSample method to control sampling decisions
      let counter = 0;
      jest.spyOn(client as any, "_shouldSample").mockImplementation(() => {
        counter += 1;
        return counter % 2 === 0; // Accept even-numbered calls (2nd, 4th, etc.)
      });

      // Create two traces
      const traceId1 = "trace-1";
      const traceId2 = "trace-2";
      const childRunId1 = "child-1";
      const childRunId2 = "child-2";

      // Create root runs (these will be sampled)
      const rootRuns = [
        {
          id: traceId1,
          trace_id: traceId1,
          name: "root_run_1",
          run_type: "llm" as const,
          inputs: { text: "hello" },
        },
        {
          id: traceId2,
          trace_id: traceId2,
          name: "root_run_2",
          run_type: "llm" as const,
          inputs: { text: "world" },
        },
      ];

      // Test POST filtering (initial sampling)
      const postFiltered = (client as any)._filterForSampling(rootRuns, false);

      // Based on our mock, first call returns false, second returns true
      // So only root_run_2 should be sampled
      expect(postFiltered).toHaveLength(1);
      expect(postFiltered[0].id).toBe(traceId2);

      // Verify that traceId1 is in filtered set, traceId2 is not
      expect((client as any).filteredPostUuids.has(traceId1)).toBe(true);
      expect((client as any).filteredPostUuids.has(traceId2)).toBe(false);

      // Test PATCH filtering - child runs should follow their trace's sampling decision
      const patchRuns = [
        {
          id: childRunId1,
          trace_id: traceId1,
          name: "child_run_1",
          run_type: "tool" as const,
          inputs: { text: "child hello" },
          outputs: { result: "child result 1" },
        },
        {
          id: childRunId2,
          trace_id: traceId2,
          name: "child_run_2",
          run_type: "tool" as const,
          inputs: { text: "child world" },
          outputs: { result: "child result 2" },
        },
      ];

      const patchFiltered = (client as any)._filterForSampling(patchRuns, true);

      // Only child_run_2 should be included (its trace was sampled)
      // child_run_1 should be filtered out (its trace was not sampled)
      expect(patchFiltered).toHaveLength(1);
      expect(patchFiltered[0].id).toBe(childRunId2);
      expect(patchFiltered[0].trace_id).toBe(traceId2);
    });

    it("should remove trace_id from filtered set when processing root run patches", () => {
      const client = new Client({
        apiKey: "test-api-key",
        tracingSamplingRate: 0.5,
      });

      // Mock the _shouldSample method to reject first trace, accept second
      let counter = 0;
      jest.spyOn(client as any, "_shouldSample").mockImplementation(() => {
        counter += 1;
        return counter % 2 === 0;
      });

      const traceId1 = "trace-1";
      const traceId2 = "trace-2";

      // Create root runs and sample them
      const rootRuns = [
        {
          id: traceId1,
          trace_id: traceId1,
          name: "root_run_1",
          run_type: "llm" as const,
          inputs: { text: "hello" },
        },
        {
          id: traceId2,
          trace_id: traceId2,
          name: "root_run_2",
          run_type: "llm" as const,
          inputs: { text: "world" },
        },
      ];

      (client as any)._filterForSampling(rootRuns, false);

      // Verify initial state
      expect((client as any).filteredPostUuids.has(traceId1)).toBe(true);
      expect((client as any).filteredPostUuids.has(traceId2)).toBe(false);

      // Test PATCH filtering for root runs (updates to the root runs themselves)
      const rootPatchRuns = [
        {
          id: traceId1,
          trace_id: traceId1,
          name: "root_run_1",
          run_type: "llm" as const,
          inputs: { text: "hello" },
          outputs: { result: "root result 1" },
        },
        {
          id: traceId2,
          trace_id: traceId2,
          name: "root_run_2",
          run_type: "llm" as const,
          inputs: { text: "world" },
          outputs: { result: "root result 2" },
        },
      ];

      const rootPatchFiltered = (client as any)._filterForSampling(
        rootPatchRuns,
        true
      );

      // Only root_run_2 should be included, and traceId1 should be removed from filtered set
      // since we're updating the root run that was originally filtered
      expect(rootPatchFiltered).toHaveLength(1);
      expect(rootPatchFiltered[0].id).toBe(traceId2);

      // traceId1 should be removed from filtered set since we processed its root run
      expect((client as any).filteredPostUuids.has(traceId1)).toBe(false);
      expect((client as any).filteredPostUuids.has(traceId2)).toBe(false);
    });

    it("should handle mixed traces with patch sampling", () => {
      const client = new Client({
        apiKey: "test-api-key",
        tracingSamplingRate: 0.5,
      });

      // Mock sampling to accept every other trace
      let counter = 0;
      jest.spyOn(client as any, "_shouldSample").mockImplementation(() => {
        counter += 1;
        return counter % 2 === 1; // Accept odd-numbered calls (1st, 3rd, etc.)
      });

      // Create multiple traces
      const traceIds = ["trace-0", "trace-1", "trace-2", "trace-3"];
      const childRunIds = ["child-0", "child-1", "child-2", "child-3"];

      // Create root runs
      const rootRuns = traceIds.map((traceId, i) => ({
        id: traceId,
        trace_id: traceId,
        name: `root_run_${i}`,
        run_type: "llm" as const,
        inputs: { text: `hello ${i}` },
      }));

      // Sample the root runs
      const postFiltered = (client as any)._filterForSampling(rootRuns, false);

      // Based on our mock: 1st and 3rd calls return true (indices 0, 2)
      expect(postFiltered).toHaveLength(2);
      const sampledTraceIds = new Set(postFiltered.map((run: any) => run.id));
      expect(sampledTraceIds.has(traceIds[0])).toBe(true);
      expect(sampledTraceIds.has(traceIds[2])).toBe(true);

      // Create child runs for all traces
      const childRuns = traceIds.map((traceId, i) => ({
        id: childRunIds[i],
        trace_id: traceId,
        name: `child_run_${i}`,
        run_type: "tool" as const,
        inputs: { text: `child ${i}` },
        outputs: { result: `child result ${i}` },
      }));

      // Test patch filtering for child runs
      const patchFiltered = (client as any)._filterForSampling(childRuns, true);

      // Only children of sampled traces should be included
      expect(patchFiltered).toHaveLength(2);
      const patchTraceIds = new Set(
        patchFiltered.map((run: any) => run.trace_id)
      );
      expect(patchTraceIds.has(traceIds[0])).toBe(true);
      expect(patchTraceIds.has(traceIds[2])).toBe(true);
      expect(patchTraceIds.has(traceIds[1])).toBe(false);
      expect(patchTraceIds.has(traceIds[3])).toBe(false);
    });
  });

  describe("Workspace Support", () => {
    // eslint-disable-next-line no-process-env
    const originalEnv = process.env;

    beforeEach(() => {
      jest.resetModules();
      // eslint-disable-next-line no-process-env
      process.env = { ...originalEnv };
    });

    afterEach(() => {
      // eslint-disable-next-line no-process-env
      process.env = originalEnv;
    });

    it("should read workspaceId from environment variable", () => {
      // eslint-disable-next-line no-process-env
      process.env.LANGSMITH_WORKSPACE_ID = "env-workspace-id";
      const client = new Client();
      expect((client as any).workspaceId).toBe("env-workspace-id");
    });

    it("should prioritize config over environment variable", () => {
      // eslint-disable-next-line no-process-env
      process.env.LANGSMITH_WORKSPACE_ID = "env-workspace-id";
      const client = new Client({ workspaceId: "config-workspace-id" });
      expect((client as any).workspaceId).toBe("config-workspace-id");
    });

    describe("E2E Workspace Tests", () => {
      it("should include workspace ID in headers when making API calls", async () => {
        // set env vars
        // eslint-disable-next-line no-process-env
        process.env.LANGSMITH_API_KEY = "test-api-key";
        // eslint-disable-next-line no-process-env
        process.env.LANGSMITH_WORKSPACE_ID = "test-workspace-id";

        // Create mock fetch function
        const mockFetch = jest.fn().mockImplementation(async () => ({
          ok: true,
          status: 200,
          statusText: "OK",
          json: async () => ({ id: "run-123", name: "test-run" }),
          text: async () => '{"id":"run-123","name":"test-run"}',
        }));

        const client = new Client({
          fetchImplementation: mockFetch as any,
        });

        // API call
        await client.createRun({
          name: "test-run",
          run_type: "llm",
          inputs: { text: "hello" },
        });

        // Verify the call was made with correct headers
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining("/runs"),
          expect.objectContaining({
            method: "POST",
            headers: expect.objectContaining({
              "x-tenant-id": "test-workspace-id",
              "x-api-key": "test-api-key",
            }),
          })
        );

        // eslint-disable-next-line no-process-env
        delete process.env.LANGSMITH_API_KEY;
        // eslint-disable-next-line no-process-env
        delete process.env.LANGSMITH_WORKSPACE_ID;
      });

      it("should handle org-scoped key error and throw workspace validation error", async () => {
        // Create mock fetch function that returns 403 with org-scoped error
        const mockFetch = jest.fn().mockImplementation(async () => ({
          ok: false,
          status: 403,
          statusText: "Forbidden",
          json: async () => ({ error: "org_scoped_key_requires_workspace" }),
          text: async () => '{"error":"org_scoped_key_requires_workspace"}',
        }));

        const client = new Client({
          apiKey: "org-scoped-key",
          fetchImplementation: mockFetch as any,
        });

        // call API without workspace - should fail with workspace validation error
        await expect(
          client.createRun({
            name: "test-run",
            run_type: "llm",
            inputs: { text: "hello" },
          })
        ).rejects.toThrow("[403]: Forbidden");

        expect(mockFetch).toHaveBeenCalled();
      });

      it("should handle other 403 errors without throwing workspace validation error", async () => {
        // Create mock fetch function that returns 403 with different error
        const mockFetch = jest.fn().mockImplementation(async () => ({
          ok: false,
          status: 403,
          statusText: "Forbidden",
          json: async () => ({ error: "insufficient_permissions" }),
          text: async () => '{"error":"insufficient_permissions"}',
        }));

        const client = new Client({
          apiKey: "test-key",
          fetchImplementation: mockFetch as any,
        });

        // call API - should fail with regular error
        await expect(
          client.createRun({
            name: "test-run",
            run_type: "llm",
            inputs: { text: "hello" },
          })
        ).rejects.toThrow("Failed to create run");

        expect(mockFetch).toHaveBeenCalled();
      });

      it("should work correctly when workspace is provided in options", async () => {
        // Create mock fetch function
        const mockFetch = jest.fn().mockImplementation(async () => ({
          ok: true,
          status: 200,
          statusText: "OK",
          json: async () => ({ id: "run-123", name: "test-run" }),
          text: async () => '{"id":"run-123","name":"test-run"}',
        }));

        const client = new Client({
          apiKey: "org-scoped-key",
          fetchImplementation: mockFetch as any,
        });

        // call with workspace ID in options should succeed
        await client.createRun(
          {
            name: "test-run",
            run_type: "llm",
            inputs: { text: "hello" },
          },
          { workspaceId: "test-workspace-id" }
        );

        // check call was made with correct headers
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining("/runs"),
          expect.objectContaining({
            method: "POST",
            headers: expect.objectContaining({
              "x-tenant-id": "test-workspace-id",
            }),
          })
        );
      });

      it("should handle multiple API calls with different workspace configurations", async () => {
        // Create mock fetch function
        const mockFetch = jest.fn().mockImplementation(async () => ({
          ok: true,
          status: 200,
          statusText: "OK",
          json: async () => ({ id: "run-123", name: "test-run" }),
          text: async () => '{"id":"run-123","name":"test-run"}',
        }));

        const client = new Client({
          apiKey: "test-api-key",
          workspaceId: "default-workspace-id",
          fetchImplementation: mockFetch as any,
        });

        // first call uses default workspace
        await client.createRun({
          name: "test-run",
          run_type: "llm",
          inputs: { text: "hello" },
        });

        // second call overrides workspace
        await client.updateRun(
          "550e8400-e29b-41d4-a716-446655440000",
          {
            outputs: { result: "updated" },
          },
          { workspaceId: "override-workspace-id" }
        );

        expect(mockFetch).toHaveBeenCalledTimes(2);

        const firstCall = mockFetch.mock.calls[0];
        const secondCall = mockFetch.mock.calls[1];

        expect((firstCall[1] as any).headers["x-tenant-id"]).toBe(
          "default-workspace-id"
        );
        expect((secondCall[1] as any).headers["x-tenant-id"]).toBe(
          "override-workspace-id"
        );
      });
    });
  });

  describe("listRuns", () => {
    it("should warn when child_run_ids is in select parameter", async () => {
      const consoleWarnSpy = jest
        .spyOn(console, "warn")
        .mockImplementation(() => {});

      // Create mock fetch function
      const mockFetch = jest.fn().mockImplementation(async () => ({
        ok: true,
        status: 200,
        statusText: "OK",
        json: async () => ({ runs: [] }),
      }));

      const client = new Client({
        apiKey: "org-scoped-key",
        fetchImplementation: mockFetch as any,
      });

      // Test that warning is issued when child_run_ids is in select
      const runs = [];
      for await (const run of client.listRuns({
        projectId: "00000000-0000-0000-0000-000000000000",
        select: ["id", "name", "child_run_ids"],
      })) {
        runs.push(run);
      }

      expect(consoleWarnSpy).toHaveBeenCalledWith(
        expect.stringMatching(
          "Deprecated: 'child_run_ids' in the listRuns select parameter is deprecated and will be removed in a future version."
        )
      );
      consoleWarnSpy.mockClear();

      // Test that no warning is issued when child_run_ids is not in select
      for await (const run of client.listRuns({
        projectId: "00000000-0000-0000-0000-000000000000",
        select: ["id", "name"],
      })) {
        runs.push(run);
      }

      expect(consoleWarnSpy).not.toHaveBeenCalled();
      consoleWarnSpy.mockRestore();
    });
  });

  describe("omitTracedRuntimeInfo", () => {
    it("should omit runtime info when flag is true", () => {
      const run: any = {
        id: "test-run-id",
        name: "test-run",
        run_type: "llm" as const,
        inputs: { text: "hello" },
      };

      const result = mergeRuntimeEnvIntoRun(run, undefined, true);

      expect(result.extra).toBeUndefined();
    });

    it("should include runtime info when flag is false", () => {
      const run: any = {
        id: "test-run-id",
        name: "test-run",
        run_type: "llm" as const,
        inputs: { text: "hello" },
      };

      const result = mergeRuntimeEnvIntoRun(run, undefined, false);

      expect(result.extra).toBeDefined();
      expect(result.extra.runtime).toBeDefined();
      expect(result.extra.metadata).toBeDefined();
    });
  });
});
