/* eslint-disable @typescript-eslint/no-explicit-any */
import { MockLanguageModelV2 } from "ai/test";
import * as ai from "ai";
import { simulateReadableStream } from "ai";
import { z } from "zod";
import { wrapAISDK } from "../../../experimental/vercel/index.js";

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

      // Verify custom metadata was applied in HTTP requests
      expect(mockHttpRequests.length).toBe(4); // 2 createRun + 2 updateRun

      // Verify sequence: createRun, createRun, updateRun, updateRun
      expect(mockHttpRequests[0].type).toBe("createRun");
      expect(mockHttpRequests[1].type).toBe("createRun");
      expect(mockHttpRequests[2].type).toBe("updateRun");
      expect(mockHttpRequests[3].type).toBe("updateRun");

      // The first createRun should have the AI SDK metadata with custom fields
      const generateTextRun = mockHttpRequests[0];
      expect(generateTextRun.body.extra.metadata).toMatchObject({
        customField: "test-value",
        version: "2.0",
        ai_sdk_method: "ai.generateText",
      });
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
          throw new Error("Model generation failed");
        },
      });

      try {
        await wrappedMethodsWithMock.generateText({
          model: mockLangModel,
          prompt: "This should fail",
        });
        expect(true).toBe(false); // Should not reach here
      } catch (error: any) {
        expect(error.message).toContain("Model generation failed");
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
      expect(updateRunCall.body.error).toContain("Model generation failed");
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

      const result = await wrappedMethods.streamText({
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

      const generateTextRun = mockHttpRequests.find(
        (req) =>
          req.type === "createRun" &&
          req.body.extra.metadata.ai_sdk_method === "ai.streamText"
      );
      expect(generateTextRun).toBeDefined();
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
          throw new Error("doStream failed");
        },
      });

      const result = await wrappedMethods.streamText({
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
      expect(updateRunCall.body.error).toContain("doStream failed");
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
          throw new Error("Object generation failed");
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
        expect(error.message).toContain("Object generation failed");
      }

      // Add delay for async operations
      await new Promise((resolve) => setTimeout(resolve, 100));

      // Verify error was captured in LangSmith
      const updateRunCall = mockHttpRequests.find(
        (req) => req.type === "updateRun" && req.body.error
      );
      expect(updateRunCall).toBeDefined();
      expect(updateRunCall.body.error).toContain("Object generation failed");
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

      await wrappedMethods.streamObject({
        model: mockLangModel,
        prompt: "Generate an object",
        schema: z.object({
          name: z.string(),
        }),
      });

      // Verify HTTP requests were made for streamObject tracing
      expect(mockHttpRequests.length).toBeGreaterThan(0);

      const streamObjectRun = mockHttpRequests.find(
        (req) =>
          req.type === "createRun" &&
          req.body.extra.metadata.ai_sdk_method === "ai.streamObject"
      );
      expect(streamObjectRun).toBeDefined();
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
          throw new Error("streamObject doStream failed");
        },
      });

      const result = await wrappedMethods.streamObject({
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
        "streamObject doStream failed"
      );
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

      // Verify the trace was created with proper model name
      expect(mockHttpRequests.length).toBe(4); // 2 createRun + 2 updateRun

      // Verify sequence and that first run uses the custom provider name
      expect(mockHttpRequests[0].type).toBe("createRun");
      expect(mockHttpRequests[0].body.name).toBe("custom-provider");
    });
  });
});
