/* eslint-disable @typescript-eslint/no-explicit-any, no-process-env */
import { jest } from "@jest/globals";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { inspect } from "node:util";
import {
  Client,
  mergeRuntimeEnvIntoRun,
  _checkBackendVersion,
} from "../client.js";
import {
  getLangSmithEnvironmentVariables,
  getLangSmithEnvVarsMetadata,
} from "../utils/env.js";
import { parseHubIdentifier } from "../utils/prompts.js";

describe("Client", () => {
  describe("createFeedback", () => {
    it("can opt out of extending trace retention", async () => {
      const mockFetch = jest.fn<typeof fetch>().mockResolvedValue(
        new Response("{}", {
          status: 200,
          statusText: "OK",
          headers: { "content-type": "application/json" },
        }),
      );
      const client = new Client({
        apiUrl: "http://localhost:1984",
        apiKey: "test-api-key",
        fetchImplementation: mockFetch,
      });

      await client.createFeedback(
        "550e8400-e29b-41d4-a716-446655440000",
        "Foo",
        {
          score: 1,
          extendTraceRetention: false,
        },
      );

      const [, init] = mockFetch.mock.calls[0];
      expect(JSON.parse(init?.body as string)).toEqual(
        expect.objectContaining({
          extend_trace_retention: false,
        }),
      );
    });

    it("applies run ID sampling before sending feedback", async () => {
      const mockFetch = jest.fn<typeof fetch>().mockResolvedValue(
        new Response("{}", {
          status: 200,
          statusText: "OK",
          headers: { "content-type": "application/json" },
        }),
      );
      const client = new Client({
        apiUrl: "http://localhost:1984",
        apiKey: "test-api-key",
        fetchImplementation: mockFetch,
        tracingSamplingRate: 0.5,
      });

      const sampledFeedback = await client.createFeedback(
        "00000000-0000-0000-0000-000000000001",
        "Foo",
        { score: 1 },
      );
      const filteredFeedback = await client.createFeedback(
        "00000000-0000-0000-0000-000000000002",
        "Foo",
        { score: 0 },
      );

      expect(sampledFeedback.run_id).toBe(
        "00000000-0000-0000-0000-000000000001",
      );
      expect(filteredFeedback.run_id).toBe(
        "00000000-0000-0000-0000-000000000002",
      );
      expect(mockFetch).toHaveBeenCalledTimes(1);
      const [, init] = mockFetch.mock.calls[0];
      expect(JSON.parse(init?.body as string)).toEqual(
        expect.objectContaining({
          run_id: "00000000-0000-0000-0000-000000000001",
        }),
      );
    });
  });

  describe("evaluators", () => {
    it("creates an evaluator through the platform endpoint", async () => {
      const mockFetch = jest
        .fn<typeof fetch>()
        .mockResolvedValueOnce(
          // first call: _checkStainlessVersion triggers GET /info
          new Response(JSON.stringify({ version: "0.16.14" }), {
            status: 200,
            statusText: "OK",
            headers: { "content-type": "application/json" },
          }),
        )
        .mockResolvedValueOnce(
          // second call: the actual evaluator create
          new Response(
            JSON.stringify({
              evaluator: {
                id: "eval-1",
                name: "SDK smoke test code evaluator",
                type: "code",
              },
            }),
            {
              status: 200,
              statusText: "OK",
              headers: { "content-type": "application/json" },
            },
          ),
        );
      const client = new Client({
        apiUrl: "http://localhost:8080",
        apiKey: "test-api-key",
        workspaceId: "test-workspace-id",
        fetchImplementation: mockFetch,
      });

      const response = await client.evaluators.create({
        name: "SDK smoke test code evaluator",
        type: "code",
        code_evaluator: {
          code: "def perform_eval(run, example):\n    return {'score': 1}",
          language: "python",
        },
      });

      expect(response.evaluator?.id).toBe("eval-1");
      const [url, init] = mockFetch.mock.calls[1]; // call[0] is the /info prefetch
      const headers = new Headers(init?.headers);
      expect(url).toBe("http://localhost:8080/v1/platform/evaluators");
      expect(init).toEqual(
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            name: "SDK smoke test code evaluator",
            type: "code",
            code_evaluator: {
              code: "def perform_eval(run, example):\n    return {'score': 1}",
              language: "python",
            },
          }),
        }),
      );
      expect(headers.get("content-type")).toBe("application/json");
      expect(headers.get("x-api-key")).toBe("test-api-key");
      expect(headers.get("x-tenant-id")).toBe("test-workspace-id");
    });
  });

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
        options,
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
        options,
      );
    });
  });

  it("should trim trailing slash on a passed apiUrl", () => {
    const client = new Client({ apiUrl: "https://example.com/" });
    const result = (client as any).apiUrl;
    expect(result).toBe("https://example.com");
  });

  describe("profile config", () => {
    const originalEnv = process.env;
    let tempDir: string;

    const writeProfileConfig = (config: unknown) => {
      const configPath = path.join(tempDir, "config.json");
      fs.writeFileSync(configPath, `${JSON.stringify(config, null, 2)}\n`);
      process.env.LANGSMITH_CONFIG_FILE = configPath;
      return configPath;
    };

    beforeEach(() => {
      process.env = { ...originalEnv };
      tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "langsmith-profile-"));
      delete process.env.LANGSMITH_API_KEY;
      delete process.env.LANGCHAIN_API_KEY;
      delete process.env.LANGSMITH_ENDPOINT;
      delete process.env.LANGCHAIN_ENDPOINT;
      delete process.env.LANGSMITH_WORKSPACE_ID;
      delete process.env.LANGCHAIN_WORKSPACE_ID;
      delete process.env.LANGSMITH_PROFILE;
    });

    afterEach(() => {
      fs.rmSync(tempDir, { recursive: true, force: true });
      process.env = originalEnv;
    });

    it("loads api URL, API key header, and workspace from the active profile", () => {
      writeProfileConfig({
        current_profile: "prod",
        profiles: {
          prod: {
            api_key: "profile-key",
            api_url: "https://profile.example.com",
            workspace_id: "workspace-id",
          },
        },
      });

      const client = new Client();

      expect((client as any).apiUrl).toBe("https://profile.example.com");
      expect((client as any).apiKey).toBeUndefined();
      expect((client as any).workspaceId).toBe("workspace-id");
      expect((client as any)._mergedHeaders["x-api-key"]).toBe("profile-key");
      expect((client as any)._mergedHeaders["x-tenant-id"]).toBe(
        "workspace-id",
      );
    });

    it("uses profile OAuth access tokens before profile API keys", () => {
      writeProfileConfig({
        profiles: {
          default: {
            api_key: "profile-key",
            oauth: {
              access_token: "profile-access-token",
            },
          },
        },
      });

      const client = new Client();

      expect((client as any).apiKey).toBeUndefined();
      expect((client as any)._mergedHeaders.Authorization).toBe(
        "Bearer profile-access-token",
      );
      expect((client as any)._mergedHeaders["x-api-key"]).toBeUndefined();
    });

    it("suppresses profile auth when environment auth is set", () => {
      writeProfileConfig({
        profiles: {
          default: {
            api_key: "profile-key",
            api_url: "https://profile.example.com",
            workspace_id: "workspace-id",
            oauth: {
              access_token: "profile-access-token",
            },
          },
        },
      });
      process.env.LANGSMITH_API_KEY = "env-key";

      const client = new Client();

      expect((client as any).apiUrl).toBe("https://profile.example.com");
      expect((client as any).workspaceId).toBe("workspace-id");
      expect((client as any)._mergedHeaders["x-api-key"]).toBe("env-key");
      expect((client as any)._mergedHeaders.Authorization).toBeUndefined();
    });

    it("suppresses profile auth when constructor auth is set", async () => {
      writeProfileConfig({
        profiles: {
          default: {
            api_key: "profile-key",
            api_url: "https://profile.example.com",
            oauth: {
              access_token: "old-access-token",
              refresh_token: "old-refresh-token",
              expires_at: new Date(Date.now() - 60_000).toISOString(),
            },
          },
        },
      });
      const mockFetch = jest.fn(
        async () => new Response("{}", { status: 200 }),
      );
      const client = new Client({
        apiKey: "constructor-key",
        fetchImplementation: mockFetch as any,
      });

      await (client as any)._fetch("https://profile.example.com/info", {
        headers: (client as any)._mergedHeaders,
      });

      expect((client as any).apiUrl).toBe("https://profile.example.com");
      expect((client as any)._mergedHeaders["x-api-key"]).toBe(
        "constructor-key",
      );
      expect((client as any)._mergedHeaders.Authorization).toBeUndefined();
      expect(mockFetch).toHaveBeenCalledTimes(1);
      const [[requestUrl]] = mockFetch.mock.calls as unknown as [
        [RequestInfo | URL, RequestInit | undefined],
      ];
      expect(String(requestUrl)).toBe("https://profile.example.com/info");
    });

    it("refreshes expired profile OAuth tokens before requests", async () => {
      const configPath = writeProfileConfig({
        profiles: {
          default: {
            api_url: "https://profile.example.com",
            oauth: {
              access_token: "old-access-token",
              refresh_token: "old-refresh-token",
              expires_at: new Date(Date.now() - 60_000).toISOString(),
            },
          },
        },
      });
      const mockFetch = jest.fn(
        async (input: RequestInfo | URL, init?: RequestInit) => {
          if (String(input) === "https://profile.example.com/oauth/token") {
            expect(init?.method).toBe("POST");
            expect(String(init?.body)).toContain("grant_type=refresh_token");
            expect(String(init?.body)).toContain("client_id=langsmith-cli");
            expect(String(init?.body)).toContain(
              "refresh_token=old-refresh-token",
            );
            return new Response(
              JSON.stringify({
                access_token: "new-access-token",
                refresh_token: "new-refresh-token",
                expires_in: 300,
              }),
              { status: 200 },
            );
          }
          return new Response("{}", { status: 200 });
        },
      );
      const client = new Client({ fetchImplementation: mockFetch as any });

      await (client as any)._fetch("https://profile.example.com/info", {
        headers: (client as any)._mergedHeaders,
      });

      expect(mockFetch).toHaveBeenCalledTimes(2);
      const requestInit = mockFetch.mock.calls[1][1] as RequestInit;
      expect(requestInit.headers).toMatchObject({
        Authorization: "Bearer new-access-token",
      });
      const updated = JSON.parse(fs.readFileSync(configPath, "utf8"));
      expect(updated.profiles.default.oauth.access_token).toBe(
        "new-access-token",
      );
      expect(updated.profiles.default.oauth.refresh_token).toBe(
        "new-refresh-token",
      );
      expect(updated.profiles.default.oauth).not.toHaveProperty("token_type");
      expect(updated.profiles.default).not.toHaveProperty("bearer_token");
    });

    it("preserves explicit Authorization headers during profile refresh", async () => {
      writeProfileConfig({
        profiles: {
          default: {
            api_url: "https://profile.example.com",
            oauth: {
              access_token: "old-access-token",
              refresh_token: "old-refresh-token",
              expires_at: new Date(Date.now() - 60_000).toISOString(),
            },
          },
        },
      });
      const mockFetch = jest.fn(
        async () => new Response("{}", { status: 200 }),
      );
      const client = new Client({ fetchImplementation: mockFetch as any });

      await (client as any)._fetch("https://profile.example.com/info", {
        headers: {
          Authorization: "Bearer explicit-token",
        },
      });

      expect(mockFetch).toHaveBeenCalledTimes(1);
      const [[requestUrl, requestInit]] = mockFetch.mock.calls as unknown as [
        [RequestInfo | URL, RequestInit | undefined],
      ];
      expect(String(requestUrl)).toBe("https://profile.example.com/info");
      expect(requestInit?.headers).toMatchObject({
        Authorization: "Bearer explicit-token",
      });
    });

    it("refreshes profile OAuth tokens against profile api_url", async () => {
      writeProfileConfig({
        profiles: {
          default: {
            api_url: "https://profile.example.com",
            oauth: {
              access_token: "old-access-token",
              refresh_token: "old-refresh-token",
              expires_at: new Date(Date.now() - 60_000).toISOString(),
            },
          },
        },
      });
      const mockFetch = jest.fn(
        async (input: RequestInfo | URL, init?: RequestInit) => {
          if (String(input) === "https://profile.example.com/oauth/token") {
            expect(init?.method).toBe("POST");
            return new Response(
              JSON.stringify({
                access_token: "new-access-token",
                refresh_token: "new-refresh-token",
                expires_in: 300,
              }),
              { status: 200 },
            );
          }
          if (String(input) === "https://override.example.com/oauth/token") {
            return new Response("wrong refresh URL", { status: 418 });
          }
          return new Response("{}", { status: 200 });
        },
      );
      const client = new Client({
        apiUrl: "https://override.example.com",
        fetchImplementation: mockFetch as any,
      });

      await (client as any)._fetch("https://override.example.com/info", {
        headers: (client as any)._mergedHeaders,
      });

      expect(mockFetch.mock.calls.map(([input]) => String(input))).toEqual([
        "https://profile.example.com/oauth/token",
        "https://override.example.com/info",
      ]);
    });
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

    it("should return 'https://apac.smith.langchain.com' if apiUrl contains 'apac'", () => {
      const client = new Client({
        apiUrl: "https://apac.api.smith.langchain.com/v1",
        apiKey: "test-api-key",
      });
      const result = (client as any).getHostUrl();
      expect(result).toBe("https://apac.smith.langchain.com");
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

  describe("parseHubIdentifier", () => {
    it("should parse valid identifiers correctly", () => {
      expect(parseHubIdentifier("name")).toEqual(["-", "name", "latest"]);
      expect(parseHubIdentifier("owner/name")).toEqual([
        "owner",
        "name",
        "latest",
      ]);
      expect(parseHubIdentifier("owner/name:commit")).toEqual([
        "owner",
        "name",
        "commit",
      ]);
      expect(parseHubIdentifier("name:commit")).toEqual([
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
        expect(() => parseHubIdentifier(identifier)).toThrowError(
          /Invalid prompt identifier format/,
        );
      });
    });
  });

  describe("pullPromptCommit", () => {
    it("requires dangerouslyPullPublicPrompt for public prompt identifiers", async () => {
      const client = new Client({ apiKey: "test-api-key" });
      const fetchSpy = jest.spyOn(client as any, "_fetchPromptFromApi");

      await expect(
        client.pullPromptCommit("someuser/someprompt"),
      ).rejects.toThrow(/dangerouslyPullPublicPrompt: true/);
      expect(fetchSpy).not.toHaveBeenCalled();
    });

    it("allows public prompt identifiers with dangerouslyPullPublicPrompt", async () => {
      const client = new Client({ apiKey: "test-api-key" });
      const promptCommit = {
        owner: "someuser",
        repo: "someprompt",
        commit_hash: "abc123",
        manifest: {},
        examples: [],
      };
      jest
        .spyOn(client as any, "_fetchPromptFromApi")
        .mockResolvedValue(promptCommit);

      await expect(
        client.pullPromptCommit("someuser/someprompt", {
          dangerouslyPullPublicPrompt: true,
        }),
      ).resolves.toEqual(promptCommit);
    });
  });

  describe("listCommits", () => {
    it("should handle private prompts without explicit owner", async () => {
      const client = new Client({ apiKey: "test-api-key" });

      // Mock the _getPaginated method to capture the URL being called
      let capturedUrl: string | undefined;
      jest
        .spyOn(client as any, "_getPaginated")
        .mockImplementation(async function* (...args: any[]) {
          capturedUrl = args[0];
          yield [];
        });

      // Call listCommits with just the prompt name (no owner)
      const commits = [];
      for await (const commit of client.listCommits("my-prompt")) {
        commits.push(commit);
      }

      // Verify that the URL uses "-" as the owner for private prompts
      expect(capturedUrl).toBe("/commits/-/my-prompt/");
    });

    it("should handle prompts with explicit owner", async () => {
      const client = new Client({ apiKey: "test-api-key" });

      let capturedUrl: string | undefined;
      jest
        .spyOn(client as any, "_getPaginated")
        .mockImplementation(async function* (...args: any[]) {
          capturedUrl = args[0];
          yield [];
        });

      // Call listCommits with owner/name format
      const commits = [];
      for await (const commit of client.listCommits("owner/my-prompt")) {
        commits.push(commit);
      }

      // Verify that the URL uses the provided owner
      expect(capturedUrl).toBe("/commits/owner/my-prompt/");
    });

    it("should handle prompts with commit specifier", async () => {
      const client = new Client({ apiKey: "test-api-key" });

      let capturedUrl: string | undefined;
      jest
        .spyOn(client as any, "_getPaginated")
        .mockImplementation(async function* (...args: any[]) {
          capturedUrl = args[0];
          yield [];
        });

      // Call listCommits with prompt:commit format (commit part should be ignored for listCommits)
      const commits = [];
      for await (const commit of client.listCommits("my-prompt:abc123")) {
        commits.push(commit);
      }

      // The commit identifier is parsed but not used in the URL (listCommits lists all commits)
      expect(capturedUrl).toBe("/commits/-/my-prompt/");
    });
  });

  describe("createCommit", () => {
    it("should include description in request body when provided", async () => {
      const client = new Client({ apiKey: "test-api-key" });

      jest.spyOn(client as any, "promptExists").mockResolvedValue(true);
      jest
        .spyOn(client as any, "_getLatestCommitHash")
        .mockResolvedValue("parent123");
      jest.spyOn(client as any, "_fetch").mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ commit_hash: "new123", id: "1" }),
        text: async () => "",
        headers: new Headers(),
      });
      jest
        .spyOn(client as any, "_getPromptUrl")
        .mockReturnValue("https://smith.langchain.com/prompts/test");

      // Capture the fetch call body
      const fetchSpy = jest.spyOn(client as any, "_fetch");

      await client.createCommit(
        "owner/my-prompt",
        { id: "test" },
        {
          description: "initial prompt version",
        },
      );

      const fetchCall = fetchSpy.mock.calls[0];
      const capturedBody = (fetchCall[1] as Record<string, unknown>)
        ?.body as string;
      const parsed = JSON.parse(capturedBody);
      expect(parsed.description).toBe("initial prompt version");
    });

    it("should omit description from request body when not provided", async () => {
      const client = new Client({ apiKey: "test-api-key" });

      jest.spyOn(client as any, "promptExists").mockResolvedValue(true);
      jest
        .spyOn(client as any, "_getLatestCommitHash")
        .mockResolvedValue("parent123");
      jest.spyOn(client as any, "_fetch").mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ commit_hash: "new123", id: "1" }),
        text: async () => "",
        headers: new Headers(),
      });
      jest
        .spyOn(client as any, "_getPromptUrl")
        .mockReturnValue("https://smith.langchain.com/prompts/test");

      const fetchSpy = jest.spyOn(client as any, "_fetch");

      await client.createCommit("owner/my-prompt", { id: "test" });

      const fetchCall = fetchSpy.mock.calls[0];
      const capturedBody = (fetchCall[1] as Record<string, unknown>)
        ?.body as string;
      const parsed = JSON.parse(capturedBody);
      expect(parsed.description).toBeUndefined();
    });

    it("should create commit tags when provided", async () => {
      const client = new Client({ apiKey: "test-api-key" });

      jest.spyOn(client as any, "promptExists").mockResolvedValue(true);
      jest
        .spyOn(client as any, "_getLatestCommitHash")
        .mockResolvedValue("parent123");
      jest.spyOn(client as any, "_fetch").mockImplementation(async (url) => ({
        ok: true,
        status: 200,
        json: async () =>
          String(url).includes("/commits/")
            ? { commit: { commit_hash: "new123", id: "commit-id" } }
            : {},
        text: async () => "",
        headers: new Headers(),
      }));
      jest
        .spyOn(client as any, "_getPromptUrl")
        .mockReturnValue("https://smith.langchain.com/prompts/test");

      const fetchSpy = jest.spyOn(client as any, "_fetch");

      await client.createCommit(
        "owner/my-prompt",
        { id: "test" },
        {
          tags: ["production", "v1"],
        },
      );

      const tagCalls = fetchSpy.mock.calls.filter(([url]) =>
        String(url).endsWith("/repos/owner/my-prompt/tags"),
      );
      expect(tagCalls).toHaveLength(2);
      expect(
        tagCalls.map(([, init]) =>
          JSON.parse((init as RequestInit).body as string),
        ),
      ).toEqual(
        expect.arrayContaining([
          { tag_name: "production", commit_id: "commit-id" },
          { tag_name: "v1", commit_id: "commit-id" },
        ]),
      );
    });
  });

  describe("pushPrompt", () => {
    it("should forward commit tags without updating prompt metadata", async () => {
      const client = new Client({ apiKey: "test-api-key" });

      jest.spyOn(client, "promptExists").mockResolvedValue(true);
      const updatePromptSpy = jest.spyOn(client, "updatePrompt");
      const createCommitSpy = jest
        .spyOn(client, "createCommit")
        .mockResolvedValue("https://smith.langchain.com/prompts/test");

      await client.pushPrompt("owner/my-prompt", {
        object: { id: "test" },
        commitTags: ["production"],
      });

      expect(updatePromptSpy).not.toHaveBeenCalled();
      expect(createCommitSpy).toHaveBeenCalledWith(
        "owner/my-prompt",
        { id: "test" },
        {
          parentCommitHash: undefined,
          tags: ["production"],
          description: undefined,
        },
      );
    });
  });

  describe("_filterForSampling run ID logic", () => {
    const sampledRunId = "00000000-0000-0000-0000-000000000001";
    const filteredRunId = "00000000-0000-0000-0000-000000000002";

    const run = (id: string, traceId = id) => ({
      id,
      trace_id: traceId,
      name: `run-${id}`,
      run_type: "llm" as const,
      inputs: { text: id },
    });

    it("should filter creates and patches by stable run ID", () => {
      const client = new Client({
        apiKey: "test-api-key",
        tracingSamplingRate: 0.5,
      });

      const sampledCreate = run(sampledRunId);
      const filteredCreate = run(filteredRunId);
      const sampledUpdate = {
        ...sampledCreate,
        outputs: { result: "sampled" },
      };
      const filteredUpdate = {
        ...filteredCreate,
        outputs: { result: "filtered" },
      };

      expect(
        (client as any)._filterForSampling([sampledCreate, filteredCreate]),
      ).toEqual([sampledCreate]);
      expect(
        (client as any)._filterForSampling(
          [sampledUpdate, filteredUpdate],
          true,
        ),
      ).toEqual([sampledUpdate]);
      expect((client as any)._shouldSample(sampledRunId)).toBe(true);
      expect((client as any)._shouldSample(filteredRunId)).toBe(false);
    });

    it("should use run ID rather than trace ID", () => {
      const client = new Client({
        apiKey: "test-api-key",
        tracingSamplingRate: 0.5,
      });

      const sampledChild = run(sampledRunId, filteredRunId);
      const filteredChild = run(filteredRunId, sampledRunId);

      expect(
        (client as any)._filterForSampling([sampledChild, filteredChild]),
      ).toEqual([sampledChild]);
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
          }),
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
          }),
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
          }),
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
          { workspaceId: "test-workspace-id" },
        );

        // check call was made with correct headers
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining("/runs"),
          expect.objectContaining({
            method: "POST",
            headers: expect.objectContaining({
              "x-tenant-id": "test-workspace-id",
            }),
          }),
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
          { workspaceId: "override-workspace-id" },
        );

        expect(mockFetch).toHaveBeenCalledTimes(2);

        const firstCall = mockFetch.mock.calls[0];
        const secondCall = mockFetch.mock.calls[1];

        expect((firstCall[1] as any).headers["x-tenant-id"]).toBe(
          "default-workspace-id",
        );
        expect((secondCall[1] as any).headers["x-tenant-id"]).toBe(
          "override-workspace-id",
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
          "Deprecated: 'child_run_ids' in the listRuns select parameter is deprecated and will be removed in a future version.",
        ),
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

  describe("listRuns normalizes naive timestamps", () => {
    it("should append Z to naive timestamps returned by the API", async () => {
      const client = new Client({ apiKey: "test-api-key" });

      const naiveRun = {
        id: "run-1",
        name: "test-run",
        run_type: "chain",
        inputs: {},
        start_time: "2026-03-12T19:38:10.269893",
        end_time: "2026-03-12T19:38:11.000000",
        session_id: "proj-1",
        trace_id: "run-1",
        dotted_order: "20260312T193810269893Zrun-1",
      };

      const mockResponse = {
        runs: [naiveRun],
        cursors: {},
      };

      jest.spyOn(client as any, "_fetch").mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => mockResponse,
        text: async () => JSON.stringify(mockResponse),
      });

      const runs: any[] = [];
      for await (const run of client.listRuns({ projectId: "proj-1" })) {
        runs.push(run);
      }

      expect(runs).toHaveLength(1);
      expect(runs[0].start_time).toBe("2026-03-12T19:38:10.269893Z");
      expect(runs[0].end_time).toBe("2026-03-12T19:38:11.000000Z");
    });

    it("should not double-append Z to already-aware timestamps", async () => {
      const client = new Client({ apiKey: "test-api-key" });

      const awareRun = {
        id: "run-2",
        name: "test-run",
        run_type: "chain",
        inputs: {},
        start_time: "2026-03-12T19:38:10.269893Z",
        end_time: "2026-03-12T19:38:11.000000+00:00",
        session_id: "proj-1",
        trace_id: "run-2",
        dotted_order: "20260312T193810269893Zrun-2",
      };

      const mockResponse = {
        runs: [awareRun],
        cursors: {},
      };

      jest.spyOn(client as any, "_fetch").mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => mockResponse,
        text: async () => JSON.stringify(mockResponse),
      });

      const runs: any[] = [];
      for await (const run of client.listRuns({ projectId: "proj-1" })) {
        runs.push(run);
      }

      expect(runs).toHaveLength(1);
      expect(runs[0].start_time).toBe("2026-03-12T19:38:10.269893Z");
      expect(runs[0].end_time).toBe("2026-03-12T19:38:11.000000+00:00");
    });
  });

  describe("custom headers", () => {
    it("should include custom headers in requests", () => {
      const client = new Client({
        apiKey: "test-api-key",
        headers: {
          "X-Custom-Header": "custom-value",
          "X-Another-Header": "another-value",
        },
      });

      const mergedHeaders = (client as any)._mergedHeaders;
      expect(mergedHeaders["X-Custom-Header"]).toBe("custom-value");
      expect(mergedHeaders["X-Another-Header"]).toBe("another-value");
      // Default headers should still be present
      expect(mergedHeaders["User-Agent"]).toBeDefined();
      expect(mergedHeaders["x-api-key"]).toBe("test-api-key");
    });

    it("should not allow custom headers to override required headers", () => {
      const client = new Client({
        apiKey: "correct-api-key",
        headers: {
          "x-api-key": "wrong-key",
          "X-Custom-Header": "custom-value",
        },
      });

      const mergedHeaders = (client as any)._mergedHeaders;
      // API key from config should take precedence
      expect(mergedHeaders["x-api-key"]).toBe("correct-api-key");
      // Custom header should still be present
      expect(mergedHeaders["X-Custom-Header"]).toBe("custom-value");
    });

    it("should allow dynamic update of custom headers", () => {
      const client = new Client({
        apiKey: "test-api-key",
        headers: {
          "X-Initial-Header": "initial-value",
        },
      });

      let mergedHeaders = (client as any)._mergedHeaders;
      expect(mergedHeaders["X-Initial-Header"]).toBe("initial-value");
      expect(mergedHeaders["X-New-Header"]).toBeUndefined();

      // Update custom headers
      client.headers = {
        "X-New-Header": "new-value",
        "X-Another-Header": "another-value",
      };

      mergedHeaders = (client as any)._mergedHeaders;
      expect(mergedHeaders["X-Initial-Header"]).toBeUndefined();
      expect(mergedHeaders["X-New-Header"]).toBe("new-value");
      expect(mergedHeaders["X-Another-Header"]).toBe("another-value");
    });

    it("should return custom headers via getter", () => {
      const customHeaders = { "X-Custom-Header": "custom-value" };
      const client = new Client({
        apiKey: "test-api-key",
        headers: customHeaders,
      });

      expect(client.headers).toEqual(customHeaders);
    });

    it("should work without custom headers", () => {
      const client = new Client({ apiKey: "test-api-key" });

      const mergedHeaders = (client as any)._mergedHeaders;
      expect(mergedHeaders["User-Agent"]).toBeDefined();
      expect(mergedHeaders["x-api-key"]).toBe("test-api-key");
    });
  });

  describe("_filterNewTokenEvents", () => {
    it("should strip kwargs from new_token events", () => {
      const client = new Client({ apiKey: "test-api-key" });
      const events = [
        {
          name: "new_token",
          kwargs: { token: "sensitive streaming data" },
          time: "2024-01-01T00:00:00Z",
        },
        {
          name: "other_event",
          kwargs: { data: "keep this" },
          time: "2024-01-01T00:00:01Z",
        },
      ];

      const filtered = (client as any)._filterNewTokenEvents(events);

      expect(filtered[0].name).toBe("new_token");
      expect(filtered[0].time).toBe("2024-01-01T00:00:00Z");
      expect(filtered[0].kwargs).toBeUndefined();
      expect(filtered[1].kwargs).toEqual({ data: "keep this" });
    });

    it("should handle empty events array", () => {
      const client = new Client({ apiKey: "test-api-key" });
      const filtered = (client as any)._filterNewTokenEvents([]);
      expect(filtered).toEqual([]);
    });

    it("should handle undefined events", () => {
      const client = new Client({ apiKey: "test-api-key" });
      const filtered = (client as any)._filterNewTokenEvents(undefined);
      expect(filtered).toBeUndefined();
    });

    it("should handle events without kwargs", () => {
      const client = new Client({ apiKey: "test-api-key" });
      const events = [
        { name: "new_token", time: "2024-01-01T00:00:00Z" },
        { name: "other_event", time: "2024-01-01T00:00:01Z" },
      ];

      const filtered = (client as any)._filterNewTokenEvents(events);

      expect(filtered[0]).toEqual({
        name: "new_token",
        time: "2024-01-01T00:00:00Z",
      });
      expect(filtered[1]).toEqual({
        name: "other_event",
        time: "2024-01-01T00:00:01Z",
      });
    });

    it("should preserve other event properties", () => {
      const client = new Client({ apiKey: "test-api-key" });
      const events = [
        {
          name: "new_token",
          kwargs: { token: "data" },
          time: "2024-01-01T00:00:00Z",
          message: "token received",
          custom_field: "custom_value",
        },
      ];

      const filtered = (client as any)._filterNewTokenEvents(events);

      expect(filtered[0].name).toBe("new_token");
      expect(filtered[0].time).toBe("2024-01-01T00:00:00Z");
      expect(filtered[0].message).toBe("token received");
      expect(filtered[0].custom_field).toBe("custom_value");
      expect(filtered[0].kwargs).toBeUndefined();
    });

    it("should filter multiple new_token events", () => {
      const client = new Client({ apiKey: "test-api-key" });
      const events = [
        { name: "new_token", kwargs: { token: "chunk1" }, time: "t1" },
        { name: "new_token", kwargs: { token: "chunk2" }, time: "t2" },
        { name: "new_token", kwargs: { token: "chunk3" }, time: "t3" },
      ];

      const filtered = (client as any)._filterNewTokenEvents(events);

      expect(filtered).toHaveLength(3);
      filtered.forEach((event: any) => {
        expect(event.kwargs).toBeUndefined();
        expect(event.name).toBe("new_token");
      });
    });
  });

  describe("toString", () => {
    it("should not expose sensitive information like API keys", () => {
      const client = new Client({
        apiUrl: "https://api.smith.langchain.com",
        apiKey: "super-secret-api-key-12345",
      });

      const str = client.toString();
      // Ensure API key is NOT in the string representation
      expect(str).not.toContain("super-secret-api-key-12345");
      // Ensure the string shows the API URL
      expect(str).toContain("https://api.smith.langchain.com");
      // Ensure it's properly formatted
      expect(str).toBe(
        '[LangSmithClient apiUrl="https://api.smith.langchain.com"]',
      );
    });

    it("should be called when converting to string", () => {
      const client = new Client({
        apiUrl: "https://api.smith.langchain.com",
        apiKey: "secret-key",
      });

      const str = String(client);
      expect(str).not.toContain("secret-key");
      expect(str).toContain("https://api.smith.langchain.com");
    });

    it("should be called by Node.js inspect", () => {
      const client = new Client({
        apiUrl: "https://api.smith.langchain.com",
        apiKey: "secret-key",
      });

      const inspectResult = inspect(client);
      expect(inspectResult).not.toContain("secret-key");
      expect(inspectResult).toContain("https://api.smith.langchain.com");
      expect(inspectResult).toBe(
        '[LangSmithClient apiUrl="https://api.smith.langchain.com"]',
      );
    });

    it("should expose the Node.js custom inspect hook", () => {
      const client = new Client({
        apiUrl: "https://api.smith.langchain.com",
        apiKey: "secret-key",
      });

      const inspectSymbol = Symbol.for("nodejs.util.inspect.custom");
      const inspectFn = (client as any)[inspectSymbol];
      expect(typeof inspectFn).toBe("function");
      expect(inspectFn.call(client)).toBe(
        '[LangSmithClient apiUrl="https://api.smith.langchain.com"]',
      );
    });
  });
});

describe("_checkBackendVersion", () => {
  let warnSpy: ReturnType<typeof jest.spyOn>;

  beforeEach(() => {
    warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});
  });

  afterEach(() => {
    warnSpy.mockRestore();
  });

  it.each([
    ["0.4.9", true],
    ["0.4.99", true],
    ["0.5.0", false],
    ["0.5.1", false],
    ["1.0.0", false],
    ["0.5.4rc1", false],
    ["0.4.4rc1", true],
    ["not-a-version", true],
  ])("version %s -> warns: %s", (version, expectWarn) => {
    _checkBackendVersion(version as string, "0.5.0");
    if (expectWarn) {
      expect(warnSpy).toHaveBeenCalledTimes(1);
    } else {
      expect(warnSpy).not.toHaveBeenCalled();
    }
  });
});
