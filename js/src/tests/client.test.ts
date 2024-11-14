/* eslint-disable @typescript-eslint/no-explicit-any */
import { jest } from "@jest/globals";
import { v4 as uuidv4 } from "uuid";
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
import { ExampleUpsertWithAttachments } from "../schemas.js";
import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

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

    it("should return 'https://dev.smith.langchain.com' if apiUrl contains 'dev'", () => {
      const client = new Client({
        apiUrl: "https://dev.smith.langchain.com/api",
        apiKey: "test-api-key",
      });
      const result = (client as any).getHostUrl();
      expect(result).toBe("https://dev.smith.langchain.com");
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

  describe("upsertExamplesMultipart", () => {
    it("should upsert examples with attachments via multipart endpoint", async () => {
      const datasetName = `__test_upsert_examples_multipart${uuidv4().slice(0, 4)}`;
      // NEED TO FIX THIS AFTER ENDPOINT MAKES IT TO PROD
      const client = new Client({ 
        apiUrl: "https://dev.api.smith.langchain.com", 
        apiKey: "HARDCODE FOR TESTING" 
      });

      // Clean up existing dataset if it exists
      if (await client.hasDataset({ datasetName })) {
        await client.deleteDataset({ datasetName });
      }

      // Create actual dataset
      const dataset = await client.createDataset(
        datasetName, {
          description: "Test dataset for multipart example upload",
          dataType: "kv"
        }
      );
      
      const pathname = path.join(
        path.dirname(fileURLToPath(import.meta.url)),
        "test_data",
        "parrot-icon.png"
      );
      // Create test examples
      const exampleId = uuidv4();
      const example1: ExampleUpsertWithAttachments = {
        id: exampleId,
        dataset_id: dataset.id,
        inputs: { text: "hello world" },
        // check that passing no outputs works fine
        attachments: {
          test_file: ["image/png", fs.readFileSync(pathname)],
        },
      };

      const example2: ExampleUpsertWithAttachments = {
        dataset_id: dataset.id,
        inputs: { text: "foo bar" },
        outputs: { response: "baz" },
        attachments: {
          my_file: ["image/png", fs.readFileSync(pathname)],
        },
      };

      // Test creating examples
      const createdExamples = await client.upsertExamplesMultipart({
        upserts: [
        example1,
        example2,
      ]});

      expect(createdExamples.count).toBe(2);

      const createdExample1 = await client.readExample(
        createdExamples.example_ids[0]
      );
      expect(createdExample1.inputs["text"]).toBe("hello world");

      const createdExample2 = await client.readExample(
        createdExamples.example_ids[1]
      );
      expect(createdExample2.inputs["text"]).toBe("foo bar");
      expect(createdExample2.outputs?.["response"]).toBe("baz");

      // Test examples were sent to correct dataset
      const allExamplesInDataset = [];
      for await (const example of client.listExamples({
        datasetId: dataset.id,
      })) {
        allExamplesInDataset.push(example);
      }
      expect(allExamplesInDataset.length).toBe(2);

      // Test updating example
      const example1Update: ExampleUpsertWithAttachments = {
        id: exampleId,
        dataset_id: dataset.id,
        inputs: { text: "bar baz" },
        outputs: { response: "foo" },
        attachments: {
          my_file: ["image/png", fs.readFileSync(pathname)],
        },
      };

      const updatedExamples = await client.upsertExamplesMultipart({
        upserts: [
        example1Update,
      ]});
      expect(updatedExamples.count).toBe(1);
      expect(updatedExamples.example_ids[0]).toBe(exampleId);

      const updatedExample = await client.readExample(updatedExamples.example_ids[0]);
      expect(updatedExample.inputs["text"]).toBe("bar baz");
      expect(updatedExample.outputs?.["response"]).toBe("foo");

      // Test invalid example fails
      const example3: ExampleUpsertWithAttachments = {
        dataset_id: uuidv4(), // not a real dataset
        inputs: { text: "foo bar" },
        outputs: { response: "baz" },
        attachments: {
          my_file: ["image/png", fs.readFileSync(pathname)],
        },
      };

      const errorResponse = await client.upsertExamplesMultipart({ upserts: [example3] });
      expect(errorResponse).toHaveProperty("error");

      // Clean up
      await client.deleteDataset({ datasetName });
    });
  });
});
