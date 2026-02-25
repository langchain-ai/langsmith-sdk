/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable no-process-env */
/* eslint-disable import/no-extraneous-dependencies */
import { MockLanguageModelV3 } from "ai/test";
import * as ai from "ai";
import { simulateReadableStream, APICallError } from "ai";
import { z } from "zod";
import { describe, it, beforeEach, expect } from "vitest";
import {
  createLangSmithProviderOptions,
  wrapAISDK,
} from "../../../experimental/vercel/index.js";
import { traceable } from "../../../traceable.js";

// Track HTTP requests made by the real traceable function
const mockHttpRequests: any[] = [];

// Mock LangSmith Client that captures HTTP calls
class MockLangSmithClient {
  async createRun(runCreate: any) {
    mockHttpRequests.push({
      method: "POST",
      endpoint: "/runs",
      body: runCreate,
      type: "createRun",
      timestamp: Date.now(),
    });
    return { id: `mock-run-${Date.now()}` };
  }

  async updateRun(runId: string, runUpdate: any) {
    mockHttpRequests.push({
      method: "PATCH",
      endpoint: `/runs/${runId}`,
      body: runUpdate,
      type: "updateRun",
      timestamp: Date.now(),
    });
    return { id: runId };
  }
}

const standardMockedModel = new MockLanguageModelV3({
  modelId: "object-test-model",
  doGenerate: async () => ({
    content: [
      {
        type: "text" as const,
        text: '{"name": "John", "age": 30}',
      },
    ],
    finishReason: { unified: "stop" as const, raw: "stop" },
    usage: {
      promptTokens: 10,
      completionTokens: 8,
      inputTokens: {
        total: 10,
        noCache: 10,
        cacheRead: 0,
        cacheWrite: 0,
      },
      outputTokens: { total: 8, text: 8, reasoning: 0 },
      totalTokens: 18,
    },
    warnings: [],
  }),
  doStream: async () => ({
    stream: simulateReadableStream({
      chunks: [
        { type: "text-start", id: "text-1" },
        {
          type: "text-delta",
          id: "text-1",
          delta: '{"name": "John", "age": 30}',
        },
        { type: "text-end", id: "text-1" },
        {
          type: "finish",
          finishReason: { unified: "stop" as const, raw: "stop" },
          usage: {
            inputTokens: {
              total: 10,
              noCache: 10,
              cacheRead: 0,
              cacheWrite: 0,
            },
            outputTokens: { total: 5, text: 5, reasoning: 0 },
            totalTokens: 15,
          },
        },
      ],
    }),
  }),
});

describe("wrapAISDK", () => {
  let mockClient: MockLangSmithClient;

  beforeEach(() => {
    // Reset HTTP requests and create fresh mock client
    process.env.LANGSMITH_TRACING = "true";
    mockHttpRequests.length = 0;
    mockClient = new MockLangSmithClient();
  });

  describe("tracing integration", () => {
    it("should create traceable function calls", async () => {
      const wrappedMethods = wrapAISDK(
        {
          wrapLanguageModel: ai.wrapLanguageModel,
          generateText: ai.generateText,
          streamText: ai.streamText,
          generateObject: ai.generateObject,
          streamObject: ai.streamObject,
        },
        { client: mockClient as any }
      );
      const mockLangModel = new MockLanguageModelV3({
        modelId: "trace-test-model",
        doGenerate: async () => ({
          content: [{ type: "text" as const, text: "Test response" }],
          finishReason: { unified: "stop" as const, raw: "stop" },
          usage: {
            promptTokens: 5,
            completionTokens: 3,
            inputTokens: {
              total: 5,
              noCache: 5,
              cacheRead: 0,
              cacheWrite: 0,
            },
            outputTokens: { total: 3, text: 3, reasoning: 0 },
            totalTokens: 8,
          },
          warnings: [],
        }),
      });

      await wrappedMethods.generateText({
        model: mockLangModel,
        prompt: "Test prompt",
      });

      await new Promise((resolve) => setTimeout(resolve, 1));

      // Verify HTTP requests were made to LangSmith in correct order
      expect(mockHttpRequests.length).toBe(4); // 2 createRun + 2 updateRun

      // Verify sequence: createRun, createRun, updateRun, updateRun
      expect(mockHttpRequests[0].type).toBe("createRun");
      expect(mockHttpRequests[1].type).toBe("createRun");
      expect(mockHttpRequests[2].type).toBe("updateRun");
      expect(mockHttpRequests[3].type).toBe("updateRun");

      // The first createRun should be the high-level generateText call
      const generateTextRun = mockHttpRequests[0];
      expect(generateTextRun.body.extra.metadata).toHaveProperty(
        "ai_sdk_method",
        "ai.generateText"
      );
      expect(generateTextRun.body.extra.metadata).toHaveProperty(
        "ls_integration",
        "vercel-ai-sdk"
      );
      expect(generateTextRun.body.extra.metadata).toHaveProperty(
        "ls_integration_version"
      );

      // The second createRun should be the low-level doGenerate call
      const doGenerateRun = mockHttpRequests[1];
      expect(doGenerateRun.body.extra.metadata).toHaveProperty(
        "ai_sdk_method",
        "ai.doGenerate"
      );
    });

    it("should apply custom metadata in tracing config", async () => {
      const wrappedWithMetadata = wrapAISDK(
        {
          wrapLanguageModel: ai.wrapLanguageModel,
          generateText: ai.generateText,
          streamText: ai.streamText,
          generateObject: ai.generateObject,
          streamObject: ai.streamObject,
        },
        {
          name: "custom-tracer",
          metadata: {
            customField: "test-value",
            version: "2.0",
          },
          client: mockClient as any,
        }
      );

      const mockLangModel = new MockLanguageModelV3({
        modelId: "metadata-test-model",
        doGenerate: async () => ({
          content: [{ type: "text" as const, text: "Metadata test" }],
          finishReason: { unified: "stop" as const, raw: "stop" },
          usage: {
            promptTokens: 5,
            completionTokens: 3,
            inputTokens: {
              total: 5,
              noCache: 5,
              cacheRead: 0,
              cacheWrite: 0,
            },
            outputTokens: { total: 3, text: 3, reasoning: 0 },
            totalTokens: 8,
          },
          warnings: [],
        }),
      });

      await wrappedWithMetadata.generateText({
        model: mockLangModel,
        prompt: "Test with metadata",
      });

      await new Promise((resolve) => setTimeout(resolve, 1));

      // Verify custom metadata was applied in HTTP requests
      expect(mockHttpRequests.length).toBe(4); // 2 createRun + 2 updateRun

      // Verify sequence: createRun, createRun, updateRun, updateRun
      expect(mockHttpRequests[0].type).toBe("createRun");
      expect(mockHttpRequests[1].type).toBe("createRun");
      expect(mockHttpRequests[2].type).toBe("updateRun");
      expect(mockHttpRequests[3].type).toBe("updateRun");

      // The first createRun should have the AI SDK metadata with custom fields
      const generateTextRun = mockHttpRequests[0];
      const updateTextRun = mockHttpRequests[3];
      expect(generateTextRun.body.extra.metadata).toMatchObject({
        customField: "test-value",
        version: "2.0",
        ai_sdk_method: "ai.generateText",
      });
      expect(updateTextRun.body.outputs).not.toHaveProperty(
        "response_metadata"
      );
    });

    it("should allow configuring traceResponseMetadata", async () => {
      const wrappedWithMetadata = wrapAISDK(
        {
          wrapLanguageModel: ai.wrapLanguageModel,
          generateText: ai.generateText,
          streamText: ai.streamText,
          generateObject: ai.generateObject,
          streamObject: ai.streamObject,
        },
        {
          name: "custom-tracer",
          traceResponseMetadata: true,
          client: mockClient as any,
        }
      );

      const mockLangModel = new MockLanguageModelV3({
        modelId: "metadata-test-model",
        doGenerate: async () => ({
          content: [{ type: "text" as const, text: "Metadata test" }],
          finishReason: { unified: "stop" as const, raw: "stop" },
          usage: {
            promptTokens: 5,
            completionTokens: 3,
            inputTokens: {
              total: 5,
              noCache: 5,
              cacheRead: 0,
              cacheWrite: 0,
            },
            outputTokens: { total: 3, text: 3, reasoning: 0 },
            totalTokens: 8,
          },
          warnings: [],
        }),
      });

      await wrappedWithMetadata.generateText({
        model: mockLangModel,
        prompt: "Test with traced steps",
      });

      await new Promise((resolve) => setTimeout(resolve, 1));

      expect(mockHttpRequests.length).toBe(4); // 2 createRun + 2 updateRun

      // Verify sequence: createRun, createRun, updateRun, updateRun
      expect(mockHttpRequests).toMatchObject([
        { type: "createRun" },
        { type: "createRun" },
        { type: "updateRun" },
        { type: "updateRun" },
      ]);
      expect(mockHttpRequests[1].type).toBe("createRun");
      expect(mockHttpRequests[2].type).toBe("updateRun");
      expect(mockHttpRequests[3].type).toBe("updateRun");

      const updateTextRun = mockHttpRequests[3];
      expect(updateTextRun.body.outputs.response_metadata).toHaveProperty(
        "steps"
      );
    });

    it("should send error information to LangSmith on model failures", async () => {
      // Create wrapped methods with mock client for this test
      const wrappedMethodsWithMock = wrapAISDK(
        {
          wrapLanguageModel: ai.wrapLanguageModel,
          generateText: ai.generateText,
          streamText: ai.streamText,
          generateObject: ai.generateObject,
          streamObject: ai.streamObject,
        },
        { client: mockClient as any }
      );

      const mockLangModel = new MockLanguageModelV3({
        modelId: "error-test-model",
        doGenerate: async () => {
          throw new Error("TOTALLY EXPECTED MOCK DOGENERATE ERROR");
        },
      });

      try {
        await wrappedMethodsWithMock.generateText({
          model: mockLangModel,
          prompt: "This should fail",
        });
        expect(true).toBe(false); // Should not reach here
      } catch (error: any) {
        expect(error.message).toContain(
          "TOTALLY EXPECTED MOCK DOGENERATE ERROR"
        );
      }

      // Add a small delay to allow async operations to complete
      await new Promise((resolve) => setTimeout(resolve, 100));

      // Verify error was captured and sent to LangSmith
      expect(mockHttpRequests.length).toBeGreaterThan(0);

      const createRunCall = mockHttpRequests.find(
        (req) => req.type === "createRun"
      );
      expect(createRunCall).toBeDefined();
      expect(createRunCall.body.inputs).toHaveProperty(
        "prompt",
        "This should fail"
      );

      const updateRunCall = mockHttpRequests.find(
        (req) => req.type === "updateRun" && req.body.error
      );
      expect(updateRunCall).toBeDefined();
      expect(updateRunCall.body.error).toContain(
        "TOTALLY EXPECTED MOCK DOGENERATE ERROR"
      );
    });

    it("should handle streamText with proper aggregation", async () => {
      const wrappedMethods = wrapAISDK(
        {
          wrapLanguageModel: ai.wrapLanguageModel,
          generateText: ai.generateText,
          streamText: ai.streamText,
          generateObject: ai.generateObject,
          streamObject: ai.streamObject,
        },
        { client: mockClient as any }
      );

      const mockLangModel = new MockLanguageModelV3({
        modelId: "stream-test-model",
        doStream: async () => ({
          response: {},
          request: {},
          stream: simulateReadableStream({
            chunks: [
              { type: "text-start", id: "text-1" },
              { type: "text-delta", id: "text-1", delta: "Hello" },
              { type: "text-delta", id: "text-1", delta: " " },
              { type: "text-delta", id: "text-1", delta: "world" },
              { type: "text-end", id: "text-1" },
              {
                type: "finish",
                finishReason: { unified: "stop" as const, raw: "stop" },
                usage: {
                  inputTokens: {
                    total: 5,
                    noCache: 5,
                    cacheRead: 0,
                    cacheWrite: 0,
                  },
                  outputTokens: { total: 2, text: 2, reasoning: 0 },
                  totalTokens: 7,
                },
              },
            ],
          }),
        }),
      });

      const result = wrappedMethods.streamText({
        model: mockLangModel,
        prompt: "Say hello",
      });

      // Consume the stream to trigger aggregation
      let fullText = "";
      for await (const textPart of result.textStream) {
        fullText += textPart;
      }

      expect(fullText).toBe("Hello world");

      // Verify HTTP requests were made for streamText
      expect(mockHttpRequests.length).toBe(4); // 2 createRun + 2 updateRun

      const generateTextPostRun = mockHttpRequests.find(
        (req) =>
          req.type === "createRun" &&
          req.body.extra.metadata.ai_sdk_method === "ai.streamText"
      );
      expect(generateTextPostRun).toBeDefined();
      const generateTextPatchRun = mockHttpRequests.find(
        (req) =>
          req.type === "updateRun" &&
          req.body.extra.metadata.ai_sdk_method === "ai.streamText"
      );
      expect(generateTextPatchRun).toBeDefined();
      expect(generateTextPatchRun.body.outputs.content).toMatchObject([
        {
          type: "text",
          text: "Hello world",
        },
      ]);

      // Verify that by default (traceRawHttp not set), request/response are excluded
      const doStreamUpdateRun = mockHttpRequests.find(
        (req) =>
          req.type === "updateRun" &&
          req.body.extra?.metadata?.ai_sdk_method === "ai.doStream"
      );
      expect(doStreamUpdateRun).toBeDefined();
      expect(doStreamUpdateRun.body.outputs.request).toBeUndefined();
      expect(doStreamUpdateRun.body.outputs.response).toBeUndefined();
    });

    it("should delay a parent traceable's end time until the child traceable ends", async () => {
      const wrappedMethods = wrapAISDK(
        {
          wrapLanguageModel: ai.wrapLanguageModel,
          generateText: ai.generateText,
          streamText: ai.streamText,
          generateObject: ai.generateObject,
          streamObject: ai.streamObject,
        },
        { client: mockClient as any }
      );

      const mockLangModel = new MockLanguageModelV3({
        modelId: "stream-test-model",
        doStream: async () => ({
          stream: simulateReadableStream({
            chunks: [
              { type: "text-start", id: "text-1" },
              { type: "text-delta", id: "text-1", delta: "Hello" },
              { type: "text-delta", id: "text-1", delta: " " },
              { type: "text-delta", id: "text-1", delta: "world" },
              { type: "text-end", id: "text-1" },
              {
                type: "finish",
                finishReason: { unified: "stop" as const, raw: "stop" },
                usage: {
                  inputTokens: {
                    total: 5,
                    noCache: 5,
                    cacheRead: 0,
                    cacheWrite: 0,
                  },
                  outputTokens: { total: 2, text: 2, reasoning: 0 },
                  totalTokens: 7,
                },
              },
            ],
            chunkDelayInMs: 100,
          }),
        }),
      });

      const start = new Date();
      const result = await traceable(
        async () => {
          return wrappedMethods.streamText({
            model: mockLangModel,
            prompt: "Say hello",
          });
        },
        {
          client: mockClient as any,
          name: "parent-traceable",
        }
      )();

      // Should return quickly
      expect(new Date().getTime() - start.getTime()).toBeLessThan(50);

      // Consume the stream to trigger aggregation
      let fullText = "";
      for await (const textPart of result.textStream) {
        fullText += textPart;
      }

      expect(new Date().getTime() - start.getTime()).toBeGreaterThanOrEqual(
        500
      );

      expect(fullText).toBe("Hello world");

      // Verify HTTP requests were made for streamText
      expect(mockHttpRequests.length).toBe(6); // 3 createRun + 3 updateRun

      const parentCreateRun = mockHttpRequests.find(
        (req) =>
          req.type === "createRun" && req.body.name === "parent-traceable"
      );
      expect(parentCreateRun).toBeDefined();
      const parentUpdateRun = mockHttpRequests.find(
        (req) => req.type === "updateRun" && !req.body.parent_run_id
      );
      expect(parentUpdateRun).toBeDefined();
      const generateTextPostRun = mockHttpRequests.find(
        (req) =>
          req.type === "createRun" &&
          req.body.extra.metadata.ai_sdk_method === "ai.streamText"
      );
      expect(generateTextPostRun).toBeDefined();
      const generateTextPatchRun = mockHttpRequests.find(
        (req) =>
          req.type === "updateRun" &&
          req.body.extra.metadata.ai_sdk_method === "ai.streamText"
      );
      expect(generateTextPatchRun).toBeDefined();
      expect(generateTextPatchRun.body.outputs.content).toMatchObject([
        {
          type: "text",
          text: "Hello world",
        },
      ]);
      const generateLLMPatchRun = mockHttpRequests.find(
        (req) =>
          req.type === "updateRun" &&
          req.body.extra.metadata.ai_sdk_method === "ai.doStream"
      );
      expect(generateLLMPatchRun).toBeDefined();
      expect(parentUpdateRun.body.end_time).toBeGreaterThanOrEqual(
        generateTextPatchRun.body.end_time
      );
      expect(parentUpdateRun.body.end_time).toBeGreaterThanOrEqual(
        generateLLMPatchRun.body.end_time
      );
    });

    it("should handle streamText errors properly", async () => {
      const wrappedMethods = wrapAISDK(
        {
          wrapLanguageModel: ai.wrapLanguageModel,
          generateText: ai.generateText,
          streamText: ai.streamText,
          generateObject: ai.generateObject,
          streamObject: ai.streamObject,
        },
        { client: mockClient as any }
      );

      // Test error at doStream level
      const mockLangModel = new MockLanguageModelV3({
        modelId: "stream-error-model",
        doStream: async () => {
          throw new Error("TOTALLY EXPECTED MOCK DOSTREAM ERROR");
        },
      });

      const result = wrappedMethods.streamText({
        model: mockLangModel,
        prompt: "This should fail",
      });

      // Stream should be empty or error out when consumed due to doStream failure
      for await (const textPart of result.textStream) {
        console.log("Unexpected text part:", textPart);
      }

      // Add delay for async operations
      await new Promise((resolve) => setTimeout(resolve, 100));

      // Verify error was captured in LangSmith traces
      const updateRunCall = mockHttpRequests.find(
        (req) => req.type === "updateRun" && req.body.error
      );

      expect(updateRunCall).toBeDefined();
      expect(updateRunCall.body.error).toContain(
        "TOTALLY EXPECTED MOCK DOSTREAM ERROR"
      );
    });

    it("should respect traceRawHttp for streamText", async () => {
      const wrappedWithRawHttp = wrapAISDK(
        {
          wrapLanguageModel: ai.wrapLanguageModel,
          generateText: ai.generateText,
          streamText: ai.streamText,
          generateObject: ai.generateObject,
          streamObject: ai.streamObject,
        },
        {
          name: "raw-http-tracer",
          traceRawHttp: true,
          client: mockClient as any,
        }
      );

      const mockLangModel = new MockLanguageModelV3({
        modelId: "raw-http-test-model",
        doStream: async () => ({
          response: {},
          request: {},
          stream: simulateReadableStream({
            chunks: [
              { type: "text-start", id: "text-1" },
              { type: "text-delta", id: "text-1", delta: "Hello world" },
              { type: "text-end", id: "text-1" },
              {
                type: "finish",
                finishReason: { unified: "stop" as const, raw: "stop" },
                usage: {
                  inputTokens: {
                    total: 5,
                    noCache: 5,
                    cacheRead: 0,
                    cacheWrite: 0,
                  },
                  outputTokens: { total: 2, text: 2, reasoning: 0 },
                  totalTokens: 7,
                },
              },
            ],
          }),
        }),
      });

      const result = wrappedWithRawHttp.streamText({
        model: mockLangModel,
        prompt: "Say hello",
        providerOptions: {
          langsmith: createLangSmithProviderOptions({}),
        },
      });

      // Consume the stream
      let fullText = "";
      for await (const textPart of result.textStream) {
        fullText += textPart;
      }

      expect(fullText).toBe("Hello world");

      await new Promise((resolve) => setTimeout(resolve, 10));

      // Find the doStream child run update
      const doStreamUpdateRun = mockHttpRequests.find(
        (req) =>
          req.type === "updateRun" &&
          req.body.extra?.metadata?.ai_sdk_method === "ai.doStream"
      );

      expect(doStreamUpdateRun).toBeDefined();
      // When traceRawHttp is true, request and response should be in the outputs
      expect(doStreamUpdateRun.body.outputs.request).toBeDefined();
      expect(doStreamUpdateRun.body.outputs.response).toBeDefined();
    });

    it("should handle generateObject with proper output processing", async () => {
      const wrappedMethods = wrapAISDK(
        {
          wrapLanguageModel: ai.wrapLanguageModel,
          generateText: ai.generateText,
          streamText: ai.streamText,
          generateObject: ai.generateObject,
          streamObject: ai.streamObject,
        },
        { client: mockClient as any }
      );

      const mockLangModel = new MockLanguageModelV3({
        modelId: "object-test-model",
        doGenerate: async () => ({
          content: [
            {
              type: "text" as const,
              text: '{"name": "John", "age": 30}',
            },
          ],
          finishReason: { unified: "stop" as const, raw: "stop" },
          usage: {
            promptTokens: 10,
            completionTokens: 8,
            inputTokens: {
              total: 10,
              noCache: 10,
              cacheRead: 0,
              cacheWrite: 0,
            },
            outputTokens: { total: 8, text: 8, reasoning: 0 },
            totalTokens: 18,
          },
          warnings: [],
        }),
      });

      const result = await wrappedMethods.generateObject({
        model: mockLangModel,
        prompt: "Generate a person object",
        schema: z.object({
          name: z.string(),
          age: z.number(),
        }),
      });

      expect(result.object).toEqual({ name: "John", age: 30 });

      await new Promise((resolve) => setTimeout(resolve, 1));

      // Verify HTTP requests were made for generateObject
      expect(mockHttpRequests.length).toBe(4); // 2 createRun + 2 updateRun

      const generateObjectRun = mockHttpRequests.find(
        (req) =>
          req.type === "createRun" &&
          req.body.extra.metadata.ai_sdk_method === "ai.generateObject"
      );
      expect(generateObjectRun).toBeDefined();
    });

    it.each(["generateText", "streamText"])(
      "should handle %s with an object output schema",
      async (method) => {
        const wrappedMethods = wrapAISDK(
          {
            wrapLanguageModel: ai.wrapLanguageModel,
            generateText: ai.generateText,
            streamText: ai.streamText,
            generateObject: ai.generateObject,
            streamObject: ai.streamObject,
          },
          { client: mockClient as any }
        );

        const output = ai.Output.object({
          schema: z.object({
            name: z.string(),
            age: z.number(),
          }),
        });

        const result = await (wrappedMethods as any)[method]({
          model: standardMockedModel,
          prompt: "Generate a person object",
          output,
        });

        const directOutput =
          method === "generateText" ? result.output : await result.output;
        expect(directOutput).toEqual({ name: "John", age: 30 });

        await new Promise((resolve) => setTimeout(resolve, 1));

        // Verify HTTP requests were made for generateObject
        expect(mockHttpRequests.length).toBe(4); // 2 createRun + 2 updateRun

        const createRun = mockHttpRequests.find(
          (req) =>
            req.type === "createRun" &&
            req.body.extra.metadata.ai_sdk_method === `ai.${method}`
        );
        const updateRun = mockHttpRequests.find(
          (req) =>
            req.type === "updateRun" &&
            req.body.extra.metadata.ai_sdk_method === `ai.${method}`
        );
        expect(createRun).toBeDefined();
        expect(updateRun.body.outputs).toEqual({
          name: "John",
          age: 30,
        });
        expect(createRun.body.inputs.output).toEqual(
          await output.responseFormat
        );
      }
    );

    it.each(["generateText", "streamText"])(
      "should handle %s with text output",
      async (method) => {
        const wrappedMethods = wrapAISDK(
          {
            wrapLanguageModel: ai.wrapLanguageModel,
            generateText: ai.generateText,
            streamText: ai.streamText,
            generateObject: ai.generateObject,
            streamObject: ai.streamObject,
          },
          { client: mockClient as any }
        );

        const output = ai.Output.text();

        const result = await (wrappedMethods as any)[method]({
          model: standardMockedModel,
          prompt: "Generate a person object",
          output,
        });

        const directOutput =
          method === "generateText" ? result.output : await result.output;
        expect(directOutput).toEqual('{"name": "John", "age": 30}');

        await new Promise((resolve) => setTimeout(resolve, 1));

        // Verify HTTP requests were made for generateObject
        expect(mockHttpRequests.length).toBe(4); // 2 createRun + 2 updateRun

        const createRun = mockHttpRequests.find(
          (req) =>
            req.type === "createRun" &&
            req.body.extra.metadata.ai_sdk_method === `ai.${method}`
        );
        const updateRun = mockHttpRequests.find(
          (req) =>
            req.type === "updateRun" &&
            req.body.extra.metadata.ai_sdk_method === `ai.${method}`
        );
        expect(createRun).toBeDefined();
        expect(typeof updateRun.body.outputs).toEqual("object");
        expect(createRun.body.inputs.output).toEqual(
          await output.responseFormat
        );
      }
    );

    it.each(["generateText", "streamText"])(
      "should handle %s with array output",
      async (method) => {
        const wrappedMethods = wrapAISDK(
          {
            wrapLanguageModel: ai.wrapLanguageModel,
            generateText: ai.generateText,
            streamText: ai.streamText,
            generateObject: ai.generateObject,
            streamObject: ai.streamObject,
          },
          { client: mockClient as any }
        );

        const output = ai.Output.array({
          element: z.string(),
        });

        const standardMockedModel = new MockLanguageModelV3({
          modelId: "object-test-model",
          doGenerate: async () => ({
            content: [
              {
                type: "text" as const,
                text: '{"elements": ["foo"]}',
              },
            ],
            finishReason: { unified: "stop" as const, raw: "stop" },
            usage: {
              promptTokens: 10,
              completionTokens: 8,
              inputTokens: {
                total: 10,
                noCache: 10,
                cacheRead: 0,
                cacheWrite: 0,
              },
              outputTokens: { total: 8, text: 8, reasoning: 0 },
              totalTokens: 18,
            },
            warnings: [],
          }),
          doStream: async () => ({
            stream: simulateReadableStream({
              chunks: [
                { type: "text-start", id: "text-1" },
                {
                  type: "text-delta",
                  id: "text-1",
                  delta: '{"elements": ["foo"]}',
                },
                { type: "text-end", id: "text-1" },
                {
                  type: "finish",
                  finishReason: { unified: "stop" as const, raw: "stop" },
                  usage: {
                    inputTokens: {
                      total: 10,
                      noCache: 10,
                      cacheRead: 0,
                      cacheWrite: 0,
                    },
                    outputTokens: { total: 5, text: 5, reasoning: 0 },
                    totalTokens: 15,
                  },
                },
              ],
            }),
          }),
        });

        const result = await (wrappedMethods as any)[method]({
          model: standardMockedModel,
          prompt: "Generate a person object",
          output,
        });

        const directOutput =
          method === "generateText" ? result.output : await result.output;
        expect(directOutput).toEqual(["foo"]);

        await new Promise((resolve) => setTimeout(resolve, 1));

        // Verify HTTP requests were made for generateObject
        expect(mockHttpRequests.length).toBe(4); // 2 createRun + 2 updateRun

        const createRun = mockHttpRequests.find(
          (req) =>
            req.type === "createRun" &&
            req.body.extra.metadata.ai_sdk_method === `ai.${method}`
        );

        const patchRun = mockHttpRequests.find(
          (req) =>
            req.type === "updateRun" &&
            req.body.extra.metadata.ai_sdk_method === `ai.${method}`
        );
        expect(createRun).toBeDefined();
        expect(typeof patchRun.body.outputs).toEqual("object");
        // Should be wrapped
        expect(Array.isArray(patchRun.body.outputs)).toEqual(false);
        expect(createRun.body.inputs.output).toEqual(
          await output.responseFormat
        );
      }
    );

    it("should handle generateObject errors", async () => {
      const wrappedMethods = wrapAISDK(
        {
          wrapLanguageModel: ai.wrapLanguageModel,
          generateText: ai.generateText,
          streamText: ai.streamText,
          generateObject: ai.generateObject,
          streamObject: ai.streamObject,
        },
        { client: mockClient as any }
      );

      const mockLangModel = new MockLanguageModelV3({
        modelId: "object-error-model",
        doGenerate: async () => {
          throw new Error("TOTALLY EXPECTED MOCK DOGENERATE ERROR");
        },
      });

      try {
        await wrappedMethods.generateObject({
          model: mockLangModel,
          prompt: "This should fail",
          schema: z.object({
            name: z.string(),
          }),
        });
        expect(true).toBe(false); // Should not reach here
      } catch (error: any) {
        expect(error.message).toContain(
          "TOTALLY EXPECTED MOCK DOGENERATE ERROR"
        );
      }

      // Add delay for async operations
      await new Promise((resolve) => setTimeout(resolve, 100));

      // Verify error was captured in LangSmith
      const updateRunCall = mockHttpRequests.find(
        (req) => req.type === "updateRun" && req.body.error
      );
      expect(updateRunCall).toBeDefined();
      expect(updateRunCall.body.error).toContain(
        "TOTALLY EXPECTED MOCK DOGENERATE ERROR"
      );
    });

    it("should handle generateObject with explicit generics", async () => {
      const wrappedMethods = wrapAISDK(
        {
          wrapLanguageModel: ai.wrapLanguageModel,
          generateText: ai.generateText,
          streamText: ai.streamText,
          generateObject: ai.generateObject,
          streamObject: ai.streamObject,
        },
        { client: mockClient as any }
      );

      const mockLangModel = new MockLanguageModelV3({
        modelId: "object-generics-test-model",
        doGenerate: async () => ({
          content: [
            {
              type: "text" as const,
              text: '{"key": "test-value"}',
            },
          ],
          finishReason: { unified: "stop" as const, raw: "stop" },
          usage: {
            promptTokens: 10,
            completionTokens: 8,
            inputTokens: {
              total: 10,
              noCache: 10,
              cacheRead: 0,
              cacheWrite: 0,
            },
            outputTokens: { total: 8, text: 8, reasoning: 0 },
            totalTokens: 18,
          },
          warnings: [],
        }),
      });

      const result = await wrappedMethods.generateObject<
        z.ZodObject<{ key: z.ZodString; keybar: z.ZodString }>,
        "object",
        { key: string; keybar: string }
      >({
        model: mockLangModel,
        prompt: "Generate an object with a key",
        // @ts-expect-error - bad schema for test
        schema: z.object({
          key: z.string(),
        }),
      });

      void result.object.key;
      void result.object.keybar;
      // @ts-expect-error - test nonpresent keys throw type error
      void result.object.keybaz;

      expect(result.object).toEqual({ key: "test-value" });
    });

    it("should create LangSmith traces for streamObject operations", async () => {
      const wrappedMethods = wrapAISDK(
        {
          wrapLanguageModel: ai.wrapLanguageModel,
          generateText: ai.generateText,
          streamText: ai.streamText,
          generateObject: ai.generateObject,
          streamObject: ai.streamObject,
        },
        { client: mockClient as any }
      );

      const mockLangModel = new MockLanguageModelV3({
        modelId: "stream-object-trace-test",
        doStream: async () => ({
          stream: simulateReadableStream({
            chunks: [
              { type: "text-start", id: "text-1" },
              { type: "text-delta", id: "text-1", delta: '{ "name": "John" }' },
              { type: "text-end", id: "text-1" },
              {
                type: "finish",
                finishReason: { unified: "stop" as const, raw: "stop" },
                usage: {
                  inputTokens: {
                    total: 10,
                    noCache: 10,
                    cacheRead: 0,
                    cacheWrite: 0,
                  },
                  outputTokens: { total: 5, text: 5, reasoning: 0 },
                  totalTokens: 15,
                },
              },
            ],
          }),
        }),
      });

      const { partialObjectStream } = wrappedMethods.streamObject({
        model: mockLangModel,
        prompt: "Generate an object",
        schema: z.object({
          name: z.string(),
        }),
      });

      const chunks: unknown[] = [];
      for await (const partialObject of partialObjectStream) {
        chunks.push(partialObject);
      }
      expect(chunks.length).toEqual(1);
      expect(chunks.at(-1)).toMatchObject({
        name: "John",
      });

      await new Promise((resolve) => setTimeout(resolve, 100));

      expect(mockHttpRequests.length).toEqual(4);

      const streamObjectRun = mockHttpRequests.find(
        (req) =>
          req.type === "createRun" &&
          req.body.extra.metadata.ai_sdk_method === "ai.streamObject"
      );
      expect(streamObjectRun).toBeDefined();
      const streamObjectPatchRun = mockHttpRequests.find(
        (req) =>
          req.type === "updateRun" &&
          req.body.extra.metadata.ai_sdk_method === "ai.streamObject"
      );
      expect(streamObjectPatchRun).toBeDefined();
      expect(streamObjectPatchRun.body.outputs).toMatchObject({
        name: "John",
      });
    });

    it("should handle streamObject errors properly", async () => {
      const wrappedMethods = wrapAISDK(
        {
          wrapLanguageModel: ai.wrapLanguageModel,
          generateText: ai.generateText,
          streamText: ai.streamText,
          generateObject: ai.generateObject,
          streamObject: ai.streamObject,
        },
        { client: mockClient as any }
      );

      // Test error at doStream level for streamObject
      const mockLangModel = new MockLanguageModelV3({
        modelId: "stream-object-error-model",
        doStream: async () => {
          throw new Error("TOTALLY EXPECTED MOCK STREAMOBJECT DOSTREAM ERROR");
        },
      });

      const result = wrappedMethods.streamObject({
        model: mockLangModel,
        prompt: "This should fail",
        schema: z.object({
          name: z.string(),
        }),
      });

      // Stream should be empty or error out when consumed due to doStream failure
      for await (const partialObject of result.partialObjectStream) {
        console.log("Unexpected partial object:", partialObject);
      }

      // Add delay for async operations
      await new Promise((resolve) => setTimeout(resolve, 100));

      // Verify error was captured in LangSmith traces
      const updateRunCall = mockHttpRequests.find(
        (req) => req.type === "updateRun" && req.body.error
      );

      expect(updateRunCall).toBeDefined();
      expect(updateRunCall.body.error).toContain(
        "TOTALLY EXPECTED MOCK STREAMOBJECT DOSTREAM ERROR"
      );
    });

    it("should handle rate limit retries in streaming", async () => {
      const wrappedMethods = wrapAISDK(
        {
          wrapLanguageModel: ai.wrapLanguageModel,
          generateText: ai.generateText,
          streamText: ai.streamText,
          generateObject: ai.generateObject,
          streamObject: ai.streamObject,
        },
        { client: mockClient as any }
      );

      let callCount = 0;
      const mockLangModel = new MockLanguageModelV3({
        modelId: "rate-limit-test-model",
        doStream: async () => {
          callCount++;
          if (callCount <= 2) {
            // First two calls hit rate limit
            const delaySeconds = 1;
            throw new APICallError({
              message: "Rate limit reached for requests",
              url: "https://api.openai.com/v1/chat/completions",
              requestBodyValues: {},
              statusCode: 429,
              isRetryable: true,
              data: {
                error: {
                  message: "Rate limit reached for requests",
                  type: "requests",
                  param: null,
                  code: "rate_limit_exceeded",
                },
              },
              responseHeaders: {
                "retry-after": delaySeconds.toString(),
                "x-request-id": "req_abcdef123456",
              },
            });
          }

          // Third call succeeds
          return {
            stream: simulateReadableStream({
              chunks: [
                { type: "text-start", id: "text-1" },
                {
                  type: "text-delta",
                  id: "text-1",
                  delta: "Success after retry",
                },
                { type: "text-end", id: "text-1" },
                {
                  type: "finish",
                  finishReason: { unified: "stop" as const, raw: "stop" },
                  usage: {
                    inputTokens: {
                      total: 5,
                      noCache: 5,
                      cacheRead: 0,
                      cacheWrite: 0,
                    },
                    outputTokens: { total: 3, text: 3, reasoning: 0 },
                    totalTokens: 8,
                  },
                },
              ],
            }),
          };
        },
      });

      const result = wrappedMethods.streamText({
        model: mockLangModel,
        prompt: "Test rate limit retry",
      });

      // Consume the stream to verify it eventually succeeds
      let fullText = "";
      for await (const textPart of result.textStream) {
        fullText += textPart;
      }

      expect(fullText).toBe("Success after retry");
      expect(callCount).toBe(3); // Should have retried twice

      // Add delay for async operations
      await new Promise((resolve) => setTimeout(resolve, 100));

      // Verify HTTP request patterns for streaming retries
      expect(mockHttpRequests.length).toBeGreaterThan(0);

      const createRunCalls = mockHttpRequests.filter(
        (req) => req.type === "createRun"
      );
      const updateRunCalls = mockHttpRequests.filter(
        (req) => req.type === "updateRun"
      );

      // With 3 doStream attempts (2 failures + 1 success), we should see:
      // 4 createRun calls: 1 parent + 3 child doStream attempts
      // 4 updateRun calls: 1 parent success + 2 child failures + 1 child success
      expect(createRunCalls.length).toBe(4);
      expect(updateRunCalls.length).toBe(4);

      // Verify the success/error pattern: 1 parent success + 2 child errors + 1 child success
      const successUpdateCalls = mockHttpRequests.filter(
        (req) => req.type === "updateRun" && !req.body.error && req.body.outputs
      );
      const errorUpdateCalls = mockHttpRequests.filter(
        (req) => req.type === "updateRun" && req.body.error
      );

      expect(successUpdateCalls.length).toBe(2); // 1 parent streamText + 1 child doStream success
      expect(errorUpdateCalls.length).toBe(2); // 2 child doStream failures
    });

    it("should handle rate limit retries in generateText", async () => {
      const wrappedMethods = wrapAISDK(
        {
          wrapLanguageModel: ai.wrapLanguageModel,
          generateText: ai.generateText,
          streamText: ai.streamText,
          generateObject: ai.generateObject,
          streamObject: ai.streamObject,
        },
        { client: mockClient as any }
      );

      let callCount = 0;
      const mockLangModel = new MockLanguageModelV3({
        modelId: "generatetext-rate-limit-test-model",
        doGenerate: async () => {
          callCount++;
          if (callCount <= 2) {
            // First two calls hit rate limit
            const delaySeconds = 1;
            throw new APICallError({
              message: "Rate limit reached for requests",
              url: "https://api.openai.com/v1/chat/completions",
              requestBodyValues: {},
              statusCode: 429,
              isRetryable: true,
              data: {
                error: {
                  message: "Rate limit reached for requests",
                  type: "requests",
                  param: null,
                  code: "rate_limit_exceeded",
                },
              },
              responseHeaders: {
                "retry-after": delaySeconds.toString(),
                "x-request-id": "req_generatetext123",
              },
            });
          }

          // Third call succeeds
          return {
            content: [{ type: "text" as const, text: "Generated after retry" }],
            finishReason: { unified: "stop" as const, raw: "stop" },
            usage: {
              promptTokens: 10,
              completionTokens: 5,
              inputTokens: {
                total: 10,
                noCache: 10,
                cacheRead: 0,
                cacheWrite: 0,
              },
              outputTokens: { total: 5, text: 5, reasoning: 0 },
              totalTokens: 15,
            },
            warnings: [],
          };
        },
      });

      const result = await wrappedMethods.generateText({
        model: mockLangModel,
        prompt: "Test generateText rate limit retry",
      });

      expect(result.text).toBe("Generated after retry");
      expect(callCount).toBe(3); // Should have retried twice

      // Add delay for async operations
      await new Promise((resolve) => setTimeout(resolve, 100));

      // Verify HTTP request patterns for retries
      expect(mockHttpRequests.length).toBeGreaterThan(0);

      const createRunCalls = mockHttpRequests.filter(
        (req) => req.type === "createRun"
      );
      const updateRunCalls = mockHttpRequests.filter(
        (req) => req.type === "updateRun"
      );

      // With 3 doGenerate attempts (2 failures + 1 success), we should see:
      // 4 createRun calls: 1 parent + 3 child doGenerate attempts
      // 4 updateRun calls: 2 child failures + 1 child success + 1 parent success
      expect(createRunCalls.length).toBe(4);
      expect(updateRunCalls.length).toBe(4);

      // Verify the success/error pattern: 1 parent success + 2 child errors + 1 child success
      const successUpdateCalls = mockHttpRequests.filter(
        (req) => req.type === "updateRun" && !req.body.error && req.body.outputs
      );
      const errorUpdateCalls = mockHttpRequests.filter(
        (req) => req.type === "updateRun" && req.body.error
      );

      expect(successUpdateCalls.length).toBe(2); // 1 parent generateText + 1 child doGenerate success
      expect(errorUpdateCalls.length).toBe(2); // 2 child doGenerate failures

      // Find the parent generateText success (has content array)
      const parentSuccessCall = successUpdateCalls.find(
        (req) => req.body.outputs.content?.[0]?.text
      );
      expect(parentSuccessCall).toBeDefined();
      expect(parentSuccessCall.body.outputs.content[0].text).toBe(
        "Generated after retry"
      );

      // Verify the final successful call has usage metadata
      expect(
        parentSuccessCall.body.extra?.metadata?.usage_metadata
      ).toBeDefined();
      expect(
        parentSuccessCall.body.extra.metadata.usage_metadata.total_tokens
      ).toBe(15);
    });

    it("should handle stream cancellation with abortController", async () => {
      const wrappedMethods = wrapAISDK(
        {
          wrapLanguageModel: ai.wrapLanguageModel,
          generateText: ai.generateText,
          streamText: ai.streamText,
          generateObject: ai.generateObject,
          streamObject: ai.streamObject,
        },
        { client: mockClient as any }
      );

      const abortController = new AbortController();

      const mockLangModel = new MockLanguageModelV3({
        modelId: "abort-test-model",
        doStream: async () => ({
          stream: simulateReadableStream({
            chunks: [
              { type: "text-start", id: "text-1" },
              { type: "text-delta", id: "text-1", delta: "Lorem" },
              { type: "text-delta", id: "text-1", delta: " ipsum" },
              { type: "text-delta", id: "text-1", delta: " dolor" },
              { type: "text-delta", id: "text-1", delta: " sit" },
              { type: "text-delta", id: "text-1", delta: " amet" },
              { type: "text-delta", id: "text-1", delta: " consectetur" },
              { type: "text-delta", id: "text-1", delta: " adipiscing" },
              { type: "text-delta", id: "text-1", delta: " elit" },
              { type: "text-end", id: "text-1" },
              {
                type: "finish",
                finishReason: { unified: "stop" as const, raw: "stop" },
                usage: {
                  inputTokens: {
                    total: 5,
                    noCache: 5,
                    cacheRead: 0,
                    cacheWrite: 0,
                  },
                  outputTokens: { total: 8, text: 8, reasoning: 0 },
                  totalTokens: 13,
                },
              },
            ],
          }),
        }),
      });

      const result = wrappedMethods.streamText({
        model: mockLangModel,
        prompt: "Tell me a lorem ipsum poem",
        abortSignal: abortController.signal,
      });

      // Consume stream and abort after a few chunks
      let chunkCount = 0;
      let fullText = "";

      for await (const textPart of result.textStream) {
        fullText += textPart;
        chunkCount++;

        if (chunkCount > 5) {
          abortController.abort();
          break;
        }
      }

      expect(chunkCount).toBeGreaterThan(5);
      expect(fullText).toBeTruthy();

      // Add delay for async operations
      await new Promise((resolve) => setTimeout(resolve, 100));

      // Verify HTTP requests were made even with cancellation
      expect(mockHttpRequests.length).toBeGreaterThan(0);

      const createRunCall = mockHttpRequests.find(
        (req) =>
          req.type === "createRun" &&
          req.body.extra.metadata.ai_sdk_method === "ai.streamText"
      );
      expect(createRunCall).toBeDefined();
      expect(createRunCall.body.inputs).toHaveProperty(
        "prompt",
        "Tell me a lorem ipsum poem"
      );
    });
  });

  describe("config resolution", () => {
    it("should merge base and runtime configs correctly", async () => {
      const baseConfig = {
        name: "base-tracer",
        metadata: { baseField: "base-value", shared: "base" },
        tags: ["base-tag"],
        badClient: "bad",
      };

      const runtimeConfig = createLangSmithProviderOptions({
        name: "runtime-tracer",
        metadata: { runtimeField: "runtime-value", shared: "runtime" },
        tags: ["runtime-tag"],
        client: mockClient as any,
      });

      const wrappedMethods = wrapAISDK(
        {
          wrapLanguageModel: ai.wrapLanguageModel,
          generateText: ai.generateText,
          streamText: ai.streamText,
          generateObject: ai.generateObject,
          streamObject: ai.streamObject,
        },
        baseConfig
      );

      const mockLangModel = new MockLanguageModelV3({
        modelId: "config-merge-test",
        doGenerate: async () => ({
          content: [{ type: "text" as const, text: "Config test" }],
          finishReason: { unified: "stop" as const, raw: "stop" },
          usage: {
            promptTokens: 5,
            completionTokens: 3,
            inputTokens: {
              total: 5,
              noCache: 5,
              cacheRead: 0,
              cacheWrite: 0,
            },
            outputTokens: { total: 3, text: 3, reasoning: 0 },
            totalTokens: 8,
          },
          warnings: [],
        }),
      });

      await wrappedMethods.generateText({
        model: mockLangModel,
        prompt: "Test config merging",
        providerOptions: {
          langsmith: runtimeConfig,
        },
      });

      // Verify merged config was used in trace
      const createRunCall = mockHttpRequests.find(
        (req) =>
          req.type === "createRun" &&
          req.body.extra.metadata.ai_sdk_method === "ai.generateText"
      );

      expect(createRunCall).toBeDefined();
      expect(createRunCall.body.name).toBe("runtime-tracer"); // Runtime overrides base
      expect(createRunCall.body.extra.metadata).toMatchObject({
        baseField: "base-value",
        runtimeField: "runtime-value",
        shared: "runtime", // Runtime wins for conflicts
        ai_sdk_method: "ai.generateText",
      });
      expect(createRunCall.body.tags).toEqual(["runtime-tag"]); // Runtime overrides base
    });

    it("should handle process inputs and output options", async () => {
      const wrappedMethods = wrapAISDK(
        {
          wrapLanguageModel: ai.wrapLanguageModel,
          generateText: ai.generateText,
          streamText: ai.streamText,
          generateObject: ai.generateObject,
          streamObject: ai.streamObject,
        },
        { client: mockClient as any }
      );

      const mockLangModel = new MockLanguageModelV3({
        modelId: "config-provider-test",
        doGenerate: async () => ({
          content: [{ type: "text" as const, text: "Config test" }],
          finishReason: { unified: "stop" as const, raw: "stop" },
          usage: {
            promptTokens: 5,
            completionTokens: 3,
            inputTokens: {
              total: 5,
              noCache: 5,
              cacheRead: 0,
              cacheWrite: 0,
            },
            outputTokens: { total: 3, text: 3, reasoning: 0 },
            totalTokens: 8,
          },
          warnings: [],
        }),
      });

      const lsConfig = createLangSmithProviderOptions<typeof ai.generateText>({
        processInputs: (inputs) => {
          const { messages, prompt, ...rest } = inputs;
          return {
            ...rest,
            messages: messages?.map((message) => ({
              ...message,
              content: "REDACTED",
            })),
            prompt: "REDACTED",
          };
        },
        processOutputs: (outputs) => {
          // @ts-expect-error - outputs is wrapped one level deep
          outputs.content;
          const originalTracedMessage = { ...outputs.outputs };
          return {
            ...originalTracedMessage,
            content: "REDACTED",
          };
        },
        processChildLLMRunInputs: (inputs) => {
          const { prompt } = inputs;
          return {
            messages: prompt.map((message) => ({
              ...message,
              content: "REDACTED CHILD INPUTS",
            })),
          };
        },
        processChildLLMRunOutputs: (outputs) => {
          // @ts-expect-error - no wrapping for child outputs
          outputs.outputs;
          return {
            ...outputs,
            content: "REDACTED CHILD OUTPUTS",
            role: "assistant",
          };
        },
      });

      await wrappedMethods.generateText({
        model: mockLangModel,
        messages: [
          {
            role: "user",
            content: "hello there!",
          },
        ],
        providerOptions: {
          langsmith: lsConfig,
        },
      });

      await new Promise((resolve) => setTimeout(resolve, 1));

      expect(mockHttpRequests).toHaveLength(4);
      // Verify merged config was used in trace
      const createRunCall = mockHttpRequests.find(
        (req) =>
          req.type === "createRun" &&
          req.body.extra.metadata.ai_sdk_method === "ai.generateText"
      );

      expect(createRunCall).toBeDefined();
      expect(createRunCall.body.inputs).toMatchObject({
        prompt: "REDACTED",
        messages: [
          {
            content: "REDACTED",
          },
        ],
      });
      const createUpdateCall = mockHttpRequests.find(
        (req) =>
          req.type === "updateRun" &&
          req.body.extra.metadata.ai_sdk_method === "ai.generateText"
      );
      expect(createUpdateCall.body.outputs).toMatchObject({
        content: "REDACTED",
      });
      const createLLMRunCall = mockHttpRequests.find(
        (req) =>
          req.type === "createRun" &&
          req.body.extra.metadata.ai_sdk_method === "ai.doGenerate"
      );
      expect(createLLMRunCall.body.inputs).toMatchObject({
        messages: [
          {
            role: "user",
            content: "REDACTED CHILD INPUTS",
          },
        ],
      });
      const updateLLMRunCall = mockHttpRequests.find(
        (req) =>
          req.type === "updateRun" &&
          req.body.extra.metadata.ai_sdk_method === "ai.doGenerate"
      );
      expect(updateLLMRunCall.body.outputs).toMatchObject({
        content: "REDACTED CHILD OUTPUTS",
      });
    });
  });

  describe("model display name handling", () => {
    it("should handle model with config provider", async () => {
      const wrappedMethods = wrapAISDK(
        {
          wrapLanguageModel: ai.wrapLanguageModel,
          generateText: ai.generateText,
          streamText: ai.streamText,
          generateObject: ai.generateObject,
          streamObject: ai.streamObject,
        },
        { client: mockClient as any }
      );
      const modelWithConfig = new MockLanguageModelV3({
        modelId: "custom-model",
        doGenerate: async () => ({
          content: [{ type: "text" as const, text: "Config test" }],
          finishReason: { unified: "stop" as const, raw: "stop" },
          usage: {
            promptTokens: 5,
            completionTokens: 3,
            inputTokens: {
              total: 5,
              noCache: 5,
              cacheRead: 0,
              cacheWrite: 0,
            },
            outputTokens: { total: 3, text: 3, reasoning: 0 },
            totalTokens: 8,
          },
          warnings: [],
        }),
      });

      // Add config property to simulate provider info
      (modelWithConfig as any).config = { provider: "custom-provider" };

      await wrappedMethods.generateText({
        model: modelWithConfig,
        prompt: "Test config",
      });

      await new Promise((resolve) => setTimeout(resolve, 1));

      // Verify the trace was created with proper model name
      expect(mockHttpRequests.length).toBe(4); // 2 createRun + 2 updateRun

      // Verify sequence and that first run uses the custom provider name
      expect(mockHttpRequests[0].type).toBe("createRun");
      expect(mockHttpRequests[0].body.name).toBe("custom-provider");
    });
  });

  describe("experimental_output handling", () => {
    it("should preserve experimental_output as structured object in outputs", async () => {
      const wrappedMethods = wrapAISDK(
        {
          wrapLanguageModel: ai.wrapLanguageModel,
          generateText: ai.generateText,
          streamText: ai.streamText,
          generateObject: ai.generateObject,
          streamObject: ai.streamObject,
        },
        { client: mockClient as any }
      );

      const mockLangModel = new MockLanguageModelV3({
        modelId: "experimental-output-test",
        doGenerate: async () => ({
          content: [
            {
              type: "text" as const,
              text: '{"city":"Prague","temperature":15,"unit":"celsius","conditions":"sunny"}',
            },
          ],
          finishReason: { unified: "stop" as const, raw: "stop" },
          usage: {
            promptTokens: 10,
            completionTokens: 20,
            inputTokens: {
              total: 10,
              noCache: 10,
              cacheRead: 10,
              cacheWrite: 10,
            },
            outputTokens: { total: 20, text: 20, reasoning: 0 },
            totalTokens: 30,
          },
          warnings: [],
        }),
      });

      await wrappedMethods.generateText({
        model: mockLangModel,
        prompt: "What's the weather?",
        experimental_output: ai.Output.object({
          schema: z.object({
            city: z.string(),
            temperature: z.number(),
            unit: z.enum(["celsius", "fahrenheit"]),
            conditions: z.string(),
          }),
        }),
      });

      await new Promise((resolve) => setTimeout(resolve, 1));

      // Find the updateRun call for generateText (parent run)
      const updateGenerateTextCall = mockHttpRequests.find(
        (req) =>
          req.type === "updateRun" &&
          req.body.extra?.metadata?.ai_sdk_method === "ai.generateText"
      );

      expect(updateGenerateTextCall).toBeDefined();

      // Verify outputs contain the structured object at top level (like generateObject)
      expect(updateGenerateTextCall.body.outputs).toMatchObject({
        city: "Prague",
        temperature: 15,
        unit: "celsius",
        conditions: "sunny",
      });

      // Verify it's NOT stringified
      const outputsStr = JSON.stringify(updateGenerateTextCall.body.outputs);
      expect(outputsStr).not.toContain("[object Object]");
      expect(outputsStr).not.toContain('\\"city\\"'); // Should not be double-escaped
    });

    it("should preserve experimental_output as structured object in streamText", async () => {
      const wrappedMethods = wrapAISDK(
        {
          wrapLanguageModel: ai.wrapLanguageModel,
          generateText: ai.generateText,
          streamText: ai.streamText,
          generateObject: ai.generateObject,
          streamObject: ai.streamObject,
        },
        { client: mockClient as any }
      );

      const mockLangModel = new MockLanguageModelV3({
        modelId: "stream-experimental-output-test",
        doStream: async () => ({
          stream: simulateReadableStream({
            chunks: [
              { type: "text-start", id: "text-1" },
              {
                type: "text-delta",
                id: "text-1",
                delta:
                  '{"city":"Berlin","temperature":10,"unit":"celsius","conditions":"cloudy"}',
              },
              { type: "text-end", id: "text-1" },
              {
                type: "finish" as const,
                finishReason: { unified: "stop", raw: "stop" },
                usage: {
                  inputTokens: {
                    total: 10,
                    noCache: 10,
                    cacheRead: 10,
                    cacheWrite: 10,
                  },
                  outputTokens: { total: 20, text: 20, reasoning: 0 },
                  totalTokens: 30,
                },
              },
            ],
          }),
        }),
      });

      const result = wrappedMethods.streamText({
        model: mockLangModel,
        prompt: "What's the weather?",
        experimental_output: ai.Output.object({
          schema: z.object({
            city: z.string(),
            temperature: z.number(),
            unit: z.enum(["celsius", "fahrenheit"]),
            conditions: z.string(),
          }),
        }),
      });

      await result.consumeStream();

      await new Promise((resolve) => setTimeout(resolve, 100));

      // Find the updateRun call for streamText (parent run)
      const updateStreamTextCall = mockHttpRequests.find(
        (req) =>
          req.type === "updateRun" &&
          req.body.extra?.metadata?.ai_sdk_method === "ai.streamText"
      );

      expect(updateStreamTextCall).toBeDefined();

      // Verify outputs contain the structured object at top level (parsed from JSON text)
      expect(updateStreamTextCall.body.outputs).toMatchObject({
        city: "Berlin",
        temperature: 10,
        unit: "celsius",
        conditions: "cloudy",
      });

      // Verify it's NOT stringified
      const outputsStr = JSON.stringify(updateStreamTextCall.body.outputs);
      expect(outputsStr).not.toContain("[object Object]");
      expect(outputsStr).not.toContain('\\"city\\"'); // Should not be double-escaped
    });
  });

  describe("AI SDK 6 token tracking", () => {
    it("should track reasoning tokens in AI SDK 6", async () => {
      const wrappedMethods = wrapAISDK(
        {
          wrapLanguageModel: ai.wrapLanguageModel,
          generateText: ai.generateText,
          streamText: ai.streamText,
          generateObject: ai.generateObject,
          streamObject: ai.streamObject,
        },
        { client: mockClient as any }
      );

      const mockLangModel = new MockLanguageModelV3({
        modelId: "reasoning-test-model",
        doGenerate: async () => ({
          content: [{ type: "text" as const, text: "Test response" }],
          finishReason: { unified: "stop" as const, raw: "stop" },
          usage: {
            inputTokens: {
              total: 10,
              noCache: 10,
              cacheRead: 0,
              cacheWrite: 0,
            },
            outputTokens: { total: 25, text: 15, reasoning: 10 },
            totalTokens: 35,
          },
          warnings: [],
        }),
      });

      await wrappedMethods.generateText({
        model: mockLangModel,
        prompt: "Test prompt",
      });

      await new Promise((resolve) => setTimeout(resolve, 10));

      // Find the LLM run (child run)
      const llmRunUpdate = mockHttpRequests.find(
        (req) =>
          req.type === "updateRun" &&
          req.body.extra?.metadata?.ai_sdk_method === "ai.doGenerate"
      );

      expect(llmRunUpdate).toBeDefined();
      expect(llmRunUpdate.body.extra.metadata.usage_metadata).toMatchObject({
        input_tokens: 10,
        output_tokens: 25,
        total_tokens: 35,
      });

      // Verify reasoning tokens are tracked
      expect(
        llmRunUpdate.body.extra.metadata.usage_metadata.output_token_details
          .reasoning
      ).toBe(10);
    });

    it("should track cache tokens in AI SDK 6", async () => {
      const wrappedMethods = wrapAISDK(
        {
          wrapLanguageModel: ai.wrapLanguageModel,
          generateText: ai.generateText,
          streamText: ai.streamText,
          generateObject: ai.generateObject,
          streamObject: ai.streamObject,
        },
        { client: mockClient as any }
      );

      const mockLangModel = new MockLanguageModelV3({
        modelId: "cache-test-model",
        doGenerate: async () => ({
          content: [{ type: "text" as const, text: "Test response" }],
          finishReason: { unified: "stop" as const, raw: "stop" },
          usage: {
            inputTokens: {
              total: 100,
              noCache: 50,
              cacheRead: 30,
              cacheWrite: 20,
            },
            outputTokens: { total: 10, text: 10, reasoning: 0 },
            totalTokens: 110,
          },
          warnings: [],
        }),
      });

      await wrappedMethods.generateText({
        model: mockLangModel,
        prompt: "Test prompt",
      });

      await new Promise((resolve) => setTimeout(resolve, 10));

      // Find the LLM run
      const llmRunUpdate = mockHttpRequests.find(
        (req) =>
          req.type === "updateRun" &&
          req.body.extra?.metadata?.ai_sdk_method === "ai.doGenerate"
      );

      expect(llmRunUpdate).toBeDefined();
      expect(llmRunUpdate.body.extra.metadata.usage_metadata).toMatchObject({
        input_tokens: 100,
        output_tokens: 10,
        total_tokens: 110,
      });

      // Verify cache tokens are tracked
      const inputTokenDetails =
        llmRunUpdate.body.extra.metadata.usage_metadata.input_token_details;
      expect(inputTokenDetails.cache_read).toBe(30);
      expect(inputTokenDetails.cache_creation).toBe(20);
    });

    it("should track OpenAI flex service tier tokens", async () => {
      const wrappedMethods = wrapAISDK(
        {
          wrapLanguageModel: ai.wrapLanguageModel,
          generateText: ai.generateText,
          streamText: ai.streamText,
          generateObject: ai.generateObject,
          streamObject: ai.streamObject,
        },
        { client: mockClient as any }
      );

      const mockLangModel = new MockLanguageModelV3({
        modelId: "flex-test-model",
        doGenerate: async () => ({
          content: [{ type: "text" as const, text: "Test response" }],
          finishReason: { unified: "stop" as const, raw: "stop" },
          usage: {
            inputTokens: {
              total: 100,
              noCache: 80,
              cacheRead: 20,
              cacheWrite: 0,
            },
            outputTokens: { total: 30, text: 25, reasoning: 5 },
            totalTokens: 130,
          },
          providerMetadata: {
            openai: {
              serviceTier: "flex",
            },
          },
          warnings: [],
        }),
      });

      await wrappedMethods.generateText({
        model: mockLangModel,
        prompt: "Test prompt",
      });

      await new Promise((resolve) => setTimeout(resolve, 10));

      // Find the LLM run
      const llmRunUpdate = mockHttpRequests.find(
        (req) =>
          req.type === "updateRun" &&
          req.body.extra?.metadata?.ai_sdk_method === "ai.doGenerate"
      );

      expect(llmRunUpdate).toBeDefined();
      expect(llmRunUpdate.body.extra.metadata.usage_metadata).toMatchObject({
        input_tokens: 100,
        output_tokens: 30,
        total_tokens: 130,
      });

      // Verify service tier tokens are tracked with proper prefixes
      const inputTokenDetails =
        llmRunUpdate.body.extra.metadata.usage_metadata.input_token_details;
      const outputTokenDetails =
        llmRunUpdate.body.extra.metadata.usage_metadata.output_token_details;

      // Input: flex tier tokens (total - cached)
      expect(inputTokenDetails.flex).toBe(80); // 100 - 20
      expect(inputTokenDetails.flex_cache_read).toBe(20);

      // Output: flex tier tokens (total - reasoning) and reasoning tokens
      expect(outputTokenDetails.flex).toBe(25); // 30 - 5
      expect(outputTokenDetails.flex_reasoning).toBe(5);
    });

    it("should track OpenAI priority service tier tokens", async () => {
      const wrappedMethods = wrapAISDK(
        {
          wrapLanguageModel: ai.wrapLanguageModel,
          generateText: ai.generateText,
          streamText: ai.streamText,
          generateObject: ai.generateObject,
          streamObject: ai.streamObject,
        },
        { client: mockClient as any }
      );

      const mockLangModel = new MockLanguageModelV3({
        modelId: "priority-test-model",
        doGenerate: async () => ({
          content: [{ type: "text" as const, text: "Test response" }],
          finishReason: { unified: "stop" as const, raw: "stop" },
          usage: {
            inputTokens: {
              total: 50,
              noCache: 50,
              cacheRead: 0,
              cacheWrite: 0,
            },
            outputTokens: { total: 40, text: 30, reasoning: 10 },
            totalTokens: 90,
          },
          providerMetadata: {
            openai: {
              serviceTier: "priority",
            },
          },
          warnings: [],
        }),
      });

      await wrappedMethods.generateText({
        model: mockLangModel,
        prompt: "Test prompt",
      });

      await new Promise((resolve) => setTimeout(resolve, 10));

      // Find the LLM run
      const llmRunUpdate = mockHttpRequests.find(
        (req) =>
          req.type === "updateRun" &&
          req.body.extra?.metadata?.ai_sdk_method === "ai.doGenerate"
      );

      expect(llmRunUpdate).toBeDefined();

      // Verify service tier tokens are tracked with priority prefix
      const inputTokenDetails =
        llmRunUpdate.body.extra.metadata.usage_metadata.input_token_details;
      const outputTokenDetails =
        llmRunUpdate.body.extra.metadata.usage_metadata.output_token_details;

      expect(inputTokenDetails.priority).toBe(50);
      expect(outputTokenDetails.priority).toBe(30); // 40 - 10
      expect(outputTokenDetails.priority_reasoning).toBe(10);
    });

    it("should handle streaming with cache and reasoning tokens", async () => {
      const wrappedMethods = wrapAISDK(
        {
          wrapLanguageModel: ai.wrapLanguageModel,
          generateText: ai.generateText,
          streamText: ai.streamText,
          generateObject: ai.generateObject,
          streamObject: ai.streamObject,
        },
        { client: mockClient as any }
      );

      const mockLangModel = new MockLanguageModelV3({
        modelId: "stream-cache-reasoning-test",
        doStream: async () => ({
          stream: simulateReadableStream({
            chunks: [
              { type: "text-start", id: "text-1" },
              { type: "text-delta", id: "text-1", delta: "Hello" },
              { type: "text-delta", id: "text-1", delta: " world" },
              { type: "text-end", id: "text-1" },
              {
                type: "finish" as const,
                finishReason: { unified: "stop", raw: "stop" },
                usage: {
                  inputTokens: {
                    total: 200,
                    noCache: 100,
                    cacheRead: 80,
                    cacheWrite: 20,
                  },
                  outputTokens: { total: 50, text: 40, reasoning: 10 },
                  totalTokens: 250,
                },
                providerMetadata: {
                  openai: {
                    serviceTier: "flex",
                  },
                },
              },
            ],
          }),
        }),
      });

      const result = wrappedMethods.streamText({
        model: mockLangModel,
        prompt: "Test prompt",
      });

      await result.consumeStream();
      await new Promise((resolve) => setTimeout(resolve, 10));

      // Find the LLM run
      const llmRunUpdate = mockHttpRequests.find(
        (req) =>
          req.type === "updateRun" &&
          req.body.extra?.metadata?.ai_sdk_method === "ai.doStream"
      );

      expect(llmRunUpdate).toBeDefined();
      expect(llmRunUpdate.body.extra.metadata.usage_metadata).toMatchObject({
        input_tokens: 200,
        output_tokens: 50,
        total_tokens: 250,
      });

      // Verify all token details are tracked
      const inputTokenDetails =
        llmRunUpdate.body.extra.metadata.usage_metadata.input_token_details;
      const outputTokenDetails =
        llmRunUpdate.body.extra.metadata.usage_metadata.output_token_details;

      expect(inputTokenDetails.flex_cache_read).toBe(80);
      expect(inputTokenDetails.cache_creation).toBe(20);
      expect(inputTokenDetails.flex).toBe(120); // 200 - 80

      expect(outputTokenDetails.flex_reasoning).toBe(10);
      expect(outputTokenDetails.flex).toBe(40); // 50 - 10
    });
  });

  describe("ToolLoopAgent tracing", () => {
    it("should wrap ToolLoopAgent class correctly", async () => {
      const wrappedMethods = wrapAISDK(
        {
          wrapLanguageModel: ai.wrapLanguageModel,
          generateText: ai.generateText,
          streamText: ai.streamText,
          generateObject: ai.generateObject,
          streamObject: ai.streamObject,
          ToolLoopAgent: ai.ToolLoopAgent,
        },
        { client: mockClient as any }
      );

      // Verify ToolLoopAgent was wrapped
      expect(wrappedMethods.ToolLoopAgent).toBeDefined();
      expect(wrappedMethods.ToolLoopAgent).not.toBe(ai.ToolLoopAgent);
    });

    it("should trace ToolLoopAgent.generate() without tools", async () => {
      const wrappedMethods = wrapAISDK(
        {
          wrapLanguageModel: ai.wrapLanguageModel,
          generateText: ai.generateText,
          streamText: ai.streamText,
          generateObject: ai.generateObject,
          streamObject: ai.streamObject,
          ToolLoopAgent: ai.ToolLoopAgent,
        },
        { client: mockClient as any }
      );

      const mockLangModel = new MockLanguageModelV3({
        modelId: "no-tools-test",
        doGenerate: async () => ({
          content: [
            {
              type: "text" as const,
              text: "Direct response without tools",
            },
          ],
          finishReason: { unified: "stop" as const, raw: "stop" },
          usage: {
            promptTokens: 20,
            completionTokens: 8,
            inputTokens: {
              total: 20,
              noCache: 20,
              cacheRead: 0,
              cacheWrite: 0,
            },
            outputTokens: { total: 8, text: 8, reasoning: 0 },
            totalTokens: 28,
          },
          warnings: [],
        }),
      });

      const agent = new wrappedMethods.ToolLoopAgent({
        model: mockLangModel,
        tools: {},
      });

      const result = await agent.generate({
        prompt: "Just answer directly",
      });

      expect(result.text).toBe("Direct response without tools");

      await new Promise((resolve) => setTimeout(resolve, 100));

      // Should have agent run and LLM run, but no tool runs
      const agentRun = mockHttpRequests.find(
        (req) =>
          req.type === "createRun" &&
          req.body.extra.metadata.ai_sdk_method === "ai.ToolLoopAgent.generate"
      );
      expect(agentRun).toBeDefined();
      expect(agentRun.body.name).toBe("ToolLoopAgent");
      expect(agentRun.body.inputs).toHaveProperty(
        "prompt",
        "Just answer directly"
      );

      const llmRun = mockHttpRequests.find(
        (req) =>
          req.type === "createRun" &&
          req.body.extra.metadata.ai_sdk_method === "ai.doGenerate"
      );
      expect(llmRun).toBeDefined();

      const toolRuns = mockHttpRequests.filter(
        (req) => req.type === "createRun" && req.body.run_type === "tool"
      );
      expect(toolRuns.length).toBe(0);

      // Verify agent update run has response_metadata with steps
      const agentUpdateRun = mockHttpRequests.find(
        (req) =>
          req.type === "updateRun" &&
          req.body.extra?.metadata?.ai_sdk_method ===
            "ai.ToolLoopAgent.generate"
      );
      expect(agentUpdateRun).toBeDefined();
      expect(agentUpdateRun.body.outputs.response_metadata).toBeDefined();
      expect(agentUpdateRun.body.outputs.response_metadata.steps).toBeDefined();
    });

    it("should trace ToolLoopAgent.stream() without tools", async () => {
      const wrappedMethods = wrapAISDK(
        {
          wrapLanguageModel: ai.wrapLanguageModel,
          generateText: ai.generateText,
          streamText: ai.streamText,
          generateObject: ai.generateObject,
          streamObject: ai.streamObject,
          ToolLoopAgent: ai.ToolLoopAgent,
        },
        { client: mockClient as any }
      );

      const mockLangModel = new MockLanguageModelV3({
        modelId: "stream-no-tools-test",
        doStream: async () => ({
          stream: simulateReadableStream({
            chunks: [
              { type: "text-start", id: "text-1" },
              { type: "text-delta", id: "text-1", delta: "Stream response" },
              { type: "text-end", id: "text-1" },
              {
                type: "finish" as const,
                finishReason: { unified: "stop", raw: "stop" },
                usage: {
                  inputTokens: {
                    total: 15,
                    noCache: 15,
                    cacheRead: 0,
                    cacheWrite: 0,
                  },
                  outputTokens: { total: 5, text: 5, reasoning: 0 },
                  totalTokens: 20,
                },
              },
            ],
          }),
        }),
      });

      const agent = new wrappedMethods.ToolLoopAgent({
        model: mockLangModel,
        tools: {},
      });

      const result = await agent.stream({
        prompt: "Stream test",
      });

      // Consume the stream
      let fullText = "";
      for await (const textPart of result.textStream) {
        fullText += textPart;
      }

      expect(fullText).toBe("Stream response");

      await new Promise((resolve) => setTimeout(resolve, 100));

      // Verify agent stream run was created
      const agentRun = mockHttpRequests.find(
        (req) =>
          req.type === "createRun" &&
          req.body.extra.metadata.ai_sdk_method === "ai.ToolLoopAgent.stream"
      );
      expect(agentRun).toBeDefined();
      expect(agentRun.body.name).toBe("ToolLoopAgent");

      const agentUpdateRun = mockHttpRequests.find(
        (req) =>
          req.type === "updateRun" &&
          req.body.extra?.metadata?.ai_sdk_method === "ai.ToolLoopAgent.stream"
      );
      expect(agentUpdateRun).toBeDefined();
      expect(agentUpdateRun.body.outputs.response_metadata.steps).toBeDefined();
    });

    it("should handle ToolLoopAgent with custom processInputs/processOutputs", async () => {
      const wrappedMethods = wrapAISDK(
        {
          wrapLanguageModel: ai.wrapLanguageModel,
          generateText: ai.generateText,
          streamText: ai.streamText,
          generateObject: ai.generateObject,
          streamObject: ai.streamObject,
          ToolLoopAgent: ai.ToolLoopAgent,
        },
        { client: mockClient as any }
      );

      const mockLangModel = new MockLanguageModelV3({
        modelId: "agent-process-test",
        doGenerate: async () => ({
          content: [{ type: "text" as const, text: "Final answer" }],
          finishReason: { unified: "stop" as const, raw: "stop" },
          usage: {
            promptTokens: 30,
            completionTokens: 10,
            inputTokens: {
              total: 30,
              noCache: 30,
              cacheRead: 0,
              cacheWrite: 0,
            },
            outputTokens: { total: 10, text: 10, reasoning: 0 },
            totalTokens: 40,
          },
          warnings: [],
        }),
      });

      const lsConfig = createLangSmithProviderOptions({
        processInputs: (inputs) => ({
          ...inputs,
          prompt: "REDACTED_PROMPT",
        }),
        processOutputs: (outputs) => ({
          ...outputs.outputs,
          content: [{ type: "text", text: "REDACTED_OUTPUT" }],
        }),
        processChildLLMRunInputs: (inputs) => ({
          messages: inputs.prompt.map((msg: any) => ({
            ...msg,
            content: "REDACTED_CHILD_INPUT",
          })),
        }),
        processChildLLMRunOutputs: () => ({
          content: "REDACTED_CHILD_OUTPUT",
          role: "assistant",
        }),
      });

      const agent = new wrappedMethods.ToolLoopAgent({
        model: mockLangModel,
        tools: {},
        providerOptions: { langsmith: lsConfig },
      });

      await agent.generate({
        prompt: "Secret prompt that should be redacted",
      });

      await new Promise((resolve) => setTimeout(resolve, 100));

      // Verify parent agent run has redacted inputs/outputs
      const agentCreateRun = mockHttpRequests.find(
        (req) =>
          req.type === "createRun" &&
          req.body.extra.metadata.ai_sdk_method === "ai.ToolLoopAgent.generate"
      );
      expect(agentCreateRun).toBeDefined();
      expect(agentCreateRun.body.inputs.prompt).toBe("REDACTED_PROMPT");

      const agentUpdateRun = mockHttpRequests.find(
        (req) =>
          req.type === "updateRun" &&
          req.body.extra?.metadata?.ai_sdk_method ===
            "ai.ToolLoopAgent.generate"
      );
      expect(agentUpdateRun).toBeDefined();
      expect(agentUpdateRun.body.outputs.content[0].text).toBe(
        "REDACTED_OUTPUT"
      );

      // Verify child LLM run has redacted inputs/outputs
      const llmCreateRun = mockHttpRequests.find(
        (req) =>
          req.type === "createRun" &&
          req.body.extra.metadata.ai_sdk_method === "ai.doGenerate"
      );
      expect(llmCreateRun).toBeDefined();
      expect(llmCreateRun.body.inputs.messages[0].content).toBe(
        "REDACTED_CHILD_INPUT"
      );

      const llmUpdateRun = mockHttpRequests.find(
        (req) =>
          req.type === "updateRun" &&
          req.body.extra?.metadata?.ai_sdk_method === "ai.doGenerate"
      );
      expect(llmUpdateRun).toBeDefined();
      expect(llmUpdateRun.body.outputs.content).toBe("REDACTED_CHILD_OUTPUT");
    });

    it("should handle ToolLoopAgent with metadata config", async () => {
      const wrappedMethods = wrapAISDK(
        {
          wrapLanguageModel: ai.wrapLanguageModel,
          generateText: ai.generateText,
          streamText: ai.streamText,
          generateObject: ai.generateObject,
          streamObject: ai.streamObject,
          ToolLoopAgent: ai.ToolLoopAgent,
        },
        {
          client: mockClient as any,
          metadata: { testKey: "testValue" },
          tags: ["agent-test"],
        }
      );

      const mockLangModel = new MockLanguageModelV3({
        modelId: "metadata-test-model",
        doGenerate: async () => ({
          content: [{ type: "text" as const, text: "Response" }],
          finishReason: { unified: "stop" as const, raw: "stop" },
          usage: {
            promptTokens: 10,
            completionTokens: 5,
            inputTokens: {
              total: 10,
              noCache: 10,
              cacheRead: 0,
              cacheWrite: 0,
            },
            outputTokens: { total: 5, text: 5, reasoning: 0 },
            totalTokens: 15,
          },
          warnings: [],
        }),
      });

      const agent = new wrappedMethods.ToolLoopAgent({
        model: mockLangModel,
        tools: {},
      });

      await agent.generate({ prompt: "Test" });

      await new Promise((resolve) => setTimeout(resolve, 100));

      const agentRun = mockHttpRequests.find(
        (req) =>
          req.type === "createRun" &&
          req.body.extra.metadata.ai_sdk_method === "ai.ToolLoopAgent.generate"
      );
      expect(agentRun).toBeDefined();
      expect(agentRun.body.extra.metadata.testKey).toBe("testValue");
      expect(agentRun.body.tags).toContain("agent-test");
    });

    it("should trace LLM child runs (doGenerate/doStream) within ToolLoopAgent", async () => {
      const wrappedMethods = wrapAISDK(
        {
          wrapLanguageModel: ai.wrapLanguageModel,
          generateText: ai.generateText,
          streamText: ai.streamText,
          generateObject: ai.generateObject,
          streamObject: ai.streamObject,
          ToolLoopAgent: ai.ToolLoopAgent,
        },
        { client: mockClient as any }
      );

      const mockLangModel = new MockLanguageModelV3({
        modelId: "llm-tracing-test-model",
        doGenerate: async () => ({
          content: [{ type: "text" as const, text: "LLM response" }],
          finishReason: { unified: "stop" as const, raw: "stop" },
          usage: {
            promptTokens: 25,
            completionTokens: 12,
            inputTokens: {
              total: 25,
              noCache: 20,
              cacheRead: 5,
              cacheWrite: 0,
            },
            outputTokens: { total: 12, text: 10, reasoning: 2 },
            totalTokens: 37,
          },
          warnings: [],
        }),
        doStream: async () => ({
          stream: simulateReadableStream({
            chunks: [
              { type: "text-start", id: "text-1" },
              {
                type: "text-delta",
                id: "text-1",
                delta: "Streamed LLM response",
              },
              { type: "text-end", id: "text-1" },
              {
                type: "finish" as const,
                finishReason: { unified: "stop", raw: "stop" },
                usage: {
                  inputTokens: {
                    total: 30,
                    noCache: 25,
                    cacheRead: 5,
                    cacheWrite: 0,
                  },
                  outputTokens: { total: 15, text: 13, reasoning: 2 },
                  totalTokens: 45,
                },
              },
            ],
          }),
        }),
      });

      const agent = new wrappedMethods.ToolLoopAgent({
        model: mockLangModel,
        tools: {},
      });

      // Test generate() - should create doGenerate child run
      await agent.generate({ prompt: "Test generate" });
      await new Promise((resolve) => setTimeout(resolve, 100));

      const doGenerateCreateRun = mockHttpRequests.find(
        (req) =>
          req.type === "createRun" &&
          req.body.extra.metadata.ai_sdk_method === "ai.doGenerate"
      );
      expect(doGenerateCreateRun).toBeDefined();
      expect(doGenerateCreateRun.body.extra.metadata.ls_model_name).toBe(
        "llm-tracing-test-model"
      );

      const doGenerateUpdateRun = mockHttpRequests.find(
        (req) =>
          req.type === "updateRun" &&
          req.body.extra?.metadata?.ai_sdk_method === "ai.doGenerate"
      );
      expect(doGenerateUpdateRun).toBeDefined();
      expect(
        doGenerateUpdateRun.body.extra.metadata.usage_metadata
      ).toBeDefined();
      expect(
        doGenerateUpdateRun.body.extra.metadata.usage_metadata.input_tokens
      ).toBe(25);
      expect(
        doGenerateUpdateRun.body.extra.metadata.usage_metadata.output_tokens
      ).toBe(12);
      expect(
        doGenerateUpdateRun.body.extra.metadata.usage_metadata.total_tokens
      ).toBe(37);
      // Verify token details
      expect(
        doGenerateUpdateRun.body.extra.metadata.usage_metadata
          .input_token_details
      ).toBeDefined();
      expect(
        doGenerateUpdateRun.body.extra.metadata.usage_metadata
          .input_token_details.cache_read
      ).toBe(5);
      expect(
        doGenerateUpdateRun.body.extra.metadata.usage_metadata
          .output_token_details
      ).toBeDefined();
      expect(
        doGenerateUpdateRun.body.extra.metadata.usage_metadata
          .output_token_details.reasoning
      ).toBe(2);

      // Clear requests for stream test
      mockHttpRequests.length = 0;

      // Test stream() - should create doStream child run
      const streamResult = await agent.stream({ prompt: "Test stream" });
      let streamedText = "";
      for await (const chunk of streamResult.textStream) {
        streamedText += chunk;
      }
      expect(streamedText).toBe("Streamed LLM response");

      await new Promise((resolve) => setTimeout(resolve, 100));

      const doStreamCreateRun = mockHttpRequests.find(
        (req) =>
          req.type === "createRun" &&
          req.body.extra.metadata.ai_sdk_method === "ai.doStream"
      );
      expect(doStreamCreateRun).toBeDefined();
      expect(doStreamCreateRun.body.extra.metadata.ls_model_name).toBe(
        "llm-tracing-test-model"
      );

      const doStreamUpdateRun = mockHttpRequests.find(
        (req) =>
          req.type === "updateRun" &&
          req.body.extra?.metadata?.ai_sdk_method === "ai.doStream"
      );
      expect(doStreamUpdateRun).toBeDefined();
      expect(
        doStreamUpdateRun.body.extra.metadata.usage_metadata
      ).toBeDefined();
      expect(
        doStreamUpdateRun.body.extra.metadata.usage_metadata.input_tokens
      ).toBe(30);
      expect(
        doStreamUpdateRun.body.extra.metadata.usage_metadata.output_tokens
      ).toBe(15);
      expect(
        doStreamUpdateRun.body.extra.metadata.usage_metadata.total_tokens
      ).toBe(45);
      // Verify token details for streaming
      expect(
        doStreamUpdateRun.body.extra.metadata.usage_metadata.input_token_details
          .cache_read
      ).toBe(5);
      expect(
        doStreamUpdateRun.body.extra.metadata.usage_metadata
          .output_token_details.reasoning
      ).toBe(2);
    });
  });
});
