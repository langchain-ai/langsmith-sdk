/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable no-process-env */
/* eslint-disable import/no-extraneous-dependencies */
import { MockLanguageModelV2 } from "ai/test";
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
      const mockLangModel = new MockLanguageModelV2({
        modelId: "trace-test-model",
        doGenerate: async () => ({
          content: [{ type: "text" as const, text: "Test response" }],
          finishReason: "stop" as const,
          usage: {
            promptTokens: 5,
            completionTokens: 3,
            inputTokens: 5,
            outputTokens: 3,
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

      const mockLangModel = new MockLanguageModelV2({
        modelId: "metadata-test-model",
        doGenerate: async () => ({
          content: [{ type: "text" as const, text: "Metadata test" }],
          finishReason: "stop" as const,
          usage: {
            promptTokens: 5,
            completionTokens: 3,
            inputTokens: 5,
            outputTokens: 3,
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

      const mockLangModel = new MockLanguageModelV2({
        modelId: "metadata-test-model",
        doGenerate: async () => ({
          content: [{ type: "text" as const, text: "Metadata test" }],
          finishReason: "stop" as const,
          usage: {
            promptTokens: 5,
            completionTokens: 3,
            inputTokens: 5,
            outputTokens: 3,
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

      const mockLangModel = new MockLanguageModelV2({
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

      const mockLangModel = new MockLanguageModelV2({
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
                finishReason: "stop",
                usage: {
                  inputTokens: 5,
                  outputTokens: 2,
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

      const mockLangModel = new MockLanguageModelV2({
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
                finishReason: "stop",
                usage: {
                  inputTokens: 5,
                  outputTokens: 2,
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
      const mockLangModel = new MockLanguageModelV2({
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

      const mockLangModel = new MockLanguageModelV2({
        modelId: "object-test-model",
        doGenerate: async () => ({
          content: [
            {
              type: "text" as const,
              text: '{"name": "John", "age": 30}',
            },
          ],
          finishReason: "stop" as const,
          usage: {
            promptTokens: 10,
            completionTokens: 8,
            inputTokens: 10,
            outputTokens: 8,
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

      const mockLangModel = new MockLanguageModelV2({
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

      const mockLangModel = new MockLanguageModelV2({
        modelId: "object-generics-test-model",
        doGenerate: async () => ({
          content: [
            {
              type: "text" as const,
              text: '{"key": "test-value"}',
            },
          ],
          finishReason: "stop" as const,
          usage: {
            promptTokens: 10,
            completionTokens: 8,
            inputTokens: 10,
            outputTokens: 8,
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

      const mockLangModel = new MockLanguageModelV2({
        modelId: "stream-object-trace-test",
        doStream: async () => ({
          stream: simulateReadableStream({
            chunks: [
              { type: "text-start", id: "text-1" },
              { type: "text-delta", id: "text-1", delta: '{ "name": "John" }' },
              { type: "text-end", id: "text-1" },
              {
                type: "finish",
                finishReason: "stop",
                usage: {
                  inputTokens: 10,
                  outputTokens: 5,
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
      const mockLangModel = new MockLanguageModelV2({
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
      const mockLangModel = new MockLanguageModelV2({
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
                  finishReason: "stop",
                  usage: {
                    inputTokens: 5,
                    outputTokens: 3,
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
      const mockLangModel = new MockLanguageModelV2({
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
            finishReason: "stop" as const,
            usage: {
              promptTokens: 10,
              completionTokens: 5,
              inputTokens: 10,
              outputTokens: 5,
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

      const mockLangModel = new MockLanguageModelV2({
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
                finishReason: "stop",
                usage: {
                  inputTokens: 5,
                  outputTokens: 8,
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

      const mockLangModel = new MockLanguageModelV2({
        modelId: "config-merge-test",
        doGenerate: async () => ({
          content: [{ type: "text" as const, text: "Config test" }],
          finishReason: "stop" as const,
          usage: {
            promptTokens: 5,
            completionTokens: 3,
            inputTokens: 5,
            outputTokens: 3,
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

      const mockLangModel = new MockLanguageModelV2({
        modelId: "config-provider-test",
        doGenerate: async () => ({
          content: [{ type: "text" as const, text: "Config test" }],
          finishReason: "stop" as const,
          usage: {
            promptTokens: 5,
            completionTokens: 3,
            inputTokens: 5,
            outputTokens: 3,
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
      const modelWithConfig = new MockLanguageModelV2({
        modelId: "custom-model",
        doGenerate: async () => ({
          content: [{ type: "text" as const, text: "Config test" }],
          finishReason: "stop" as const,
          usage: {
            promptTokens: 5,
            completionTokens: 3,
            inputTokens: 5,
            outputTokens: 3,
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

      const mockLangModel = new MockLanguageModelV2({
        modelId: "experimental-output-test",
        doGenerate: async () => ({
          content: [
            {
              type: "text" as const,
              text: '{"city":"Prague","temperature":15,"unit":"celsius","conditions":"sunny"}',
            },
          ],
          finishReason: "stop" as const,
          usage: {
            promptTokens: 10,
            completionTokens: 20,
            inputTokens: 10,
            outputTokens: 20,
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

      const mockLangModel = new MockLanguageModelV2({
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
                type: "finish",
                finishReason: "stop",
                usage: {
                  inputTokens: 10,
                  outputTokens: 20,
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
});
