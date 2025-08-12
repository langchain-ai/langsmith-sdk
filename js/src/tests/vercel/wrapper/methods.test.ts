import { MockLanguageModelV2 } from "ai/test";
import * as ai from "ai";
import { wrapAISDK } from "../../../experimental/vercel/index.js";

// Track HTTP requests made by the real traceable function
let mockHttpRequests: any[] = [];

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

    it("should create separate LangSmith runs for each retry attempt", async () => {
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

      let attempts = 0;
      const mockLangModel = new MockLanguageModelV2({
        modelId: "retry-error-model",
        doGenerate: async () => {
          attempts++;
          // Always fail to test retry behavior
          throw new Error(`Attempt ${attempts} failed`);
        },
      });

      try {
        await wrappedMethodsWithMock.generateText({
          model: mockLangModel,
          prompt: "This will retry and fail",
          maxRetries: 2, // AI SDK will retry 2 times (3 total attempts)
        });
        expect(true).toBe(false); // Should not reach here
      } catch (error: any) {
        expect(error.message).toContain("failed");
      }

      // Add delay to allow all async operations to complete
      await new Promise((resolve) => setTimeout(resolve, 200));

      // Verify we captured multiple attempts - AI SDK creates separate runs for each retry
      expect(mockHttpRequests.length).toBeGreaterThan(2);

      // Should have multiple createRun calls (one for each attempt)
      const createRunCalls = mockHttpRequests.filter(
        (req) => req.type === "createRun"
      );
      expect(createRunCalls.length).toBeGreaterThanOrEqual(2); // At least original + 1 retry

      // Should have corresponding updateRun calls with errors
      const updateRunCalls = mockHttpRequests.filter(
        (req) => req.type === "updateRun" && req.body.error
      );
      expect(updateRunCalls.length).toBeGreaterThanOrEqual(2);

      // Verify the requests are in the correct order: createRun -> updateRun for each attempt
      const requestSequence = mockHttpRequests.map((req) => req.type);
      expect(requestSequence.indexOf("createRun")).toBeLessThan(
        requestSequence.indexOf("updateRun")
      );

      // Verify all createRun calls have the same input (either prompt or messages format)
      createRunCalls.forEach((call) => {
        const inputs = call.body.inputs;
        const hasPrompt = inputs.prompt === "This will retry and fail";
        const hasMessages =
          inputs.messages?.[0]?.content?.[0]?.text ===
          "This will retry and fail";
        expect(hasPrompt || hasMessages).toBe(true);
      });

      // Verify all error messages contain failure information
      const errorMessages = updateRunCalls.map((call) => call.body.error);
      expect(errorMessages.every((msg) => msg.includes("failed"))).toBe(true);

      // The key verification: AI SDK with retries creates multiple LangSmith runs
      // Each retry attempt gets its own LangSmith run for proper observability
      expect(createRunCalls.length).toBeGreaterThanOrEqual(2);
      expect(updateRunCalls.length).toBeGreaterThanOrEqual(2);
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
