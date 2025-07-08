/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable no-process-env */
import { jest } from "@jest/globals";
import { Client } from "../client.js";
import {
  getEnvironmentVariables,
  getLangChainEnvVars,
  getLangChainEnvVarsMetadata,
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

      const envVars = getEnvironmentVariables();
      const langchainEnvVars = getLangChainEnvVars();
      const langchainMetadataEnvVars = getLangChainEnvVarsMetadata();

      expect(envVars).toMatchObject({
        LANGCHAIN_REVISION_ID: "test_revision_id",
        LANGCHAIN_API_KEY: "fake_api_key",
        LANGCHAIN_OTHER_KEY: "test_other_key",
        LANGCHAIN_ENDPOINT: "https://example.com",
        SOME_RANDOM_THING: "random",
        LANGCHAIN_OTHER_NON_SENSITIVE_METADATA: "test_some_metadata",
      });
      expect(langchainEnvVars).toMatchObject({
        LANGCHAIN_REVISION_ID: "test_revision_id",
        LANGCHAIN_API_KEY: "fa********ey",
        LANGCHAIN_OTHER_KEY: "te**********ey",
        LANGCHAIN_ENDPOINT: "https://example.com",
        LANGCHAIN_OTHER_NON_SENSITIVE_METADATA: "test_some_metadata",
      });
      expect(langchainEnvVars).not.toHaveProperty("SOME_RANDOM_THING");
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

  describe("validate multiple urls", () => {
    const ORIGINAL_ENV = { ...process.env };

    afterEach(() => {
      // Restore original env to avoid side-effects between tests
      process.env = { ...ORIGINAL_ENV };
    });

    it("should throw when LANGSMITH_RUNS_ENDPOINTS set alongside LANGCHAIN/LANGSMITH_ENDPOINT", () => {
      // eslint-disable-next-line no-process-env
      process.env.LANGCHAIN_ENDPOINT =
        "https://api.smith.langchain-endpoint.com";
      // eslint-disable-next-line no-process-env
      process.env.LANGSMITH_ENDPOINT =
        "https://api.smith.langsmith-endpoint.com";
      // eslint-disable-next-line no-process-env
      process.env.LANGSMITH_RUNS_ENDPOINTS =
        '{"https://api.smith.langsmith-endpoint_1.com": "123"}';
      expect(() => new Client()).toThrow(
        "You cannot provide both LANGSMITH_ENDPOINT / LANGCHAIN_ENDPOINT"
      );
    });

    it("should parse LANGSMITH_RUNS_ENDPOINTS JSON mapping and set defaults correctly", () => {
      const data = [
        { url: "https://api.smith.langsmith-endpoint_1.com", apiKey: "123" },
        { url: "https://api.smith.langsmith-endpoint_2.com", apiKey: "456" },
        { url: "https://api.smith.langsmith-endpoint_3.com", apiKey: "789" },
      ] as { url: string; apiKey?: string }[];
      // Ensure conflicting env vars are removed
      // eslint-disable-next-line no-process-env
      delete process.env.LANGCHAIN_ENDPOINT;
      // eslint-disable-next-line no-process-env
      delete process.env.LANGSMITH_ENDPOINT;
      // eslint-disable-next-line no-process-env
      process.env.LANGSMITH_RUNS_ENDPOINTS = JSON.stringify(data);

      const client = new Client({ autoBatchTracing: false });
      const internal = client as unknown as {
        _destinations: { url: string; apiKey?: string }[];
        apiUrl: string;
        apiKey?: string;
      };

      expect(internal._destinations).toEqual(data);
      expect(internal.apiUrl).toBe(data[0].url);
      expect(internal.apiKey).toBe(data[0].apiKey);
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
});
