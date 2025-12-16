/* eslint-disable no-process-env */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { v4 as uuid } from "uuid";
import { generateText } from "ai";
import { MockLanguageModelV2 } from "ai/test";

import { toArray, waitUntilRunFoundByMetaField } from "../utils.js";
import { Client } from "../../index.js";
import { traceable } from "../../traceable.js";
import { initializeOTEL } from "../../experimental/otel/setup.js";
import { getLangSmithEnvironmentVariable } from "../../utils/env.js";

const client = new Client();

const { DEFAULT_LANGSMITH_SPAN_PROCESSOR } = initializeOTEL();

// Deprecated
describe.skip("OTEL Rate Limit Error Tests", () => {
  beforeEach(() => {
    // Initialize native OTEL exporter
    initializeOTEL();

    // Enable OTEL tracing
    process.env.LANGSMITH_OTEL_ENABLED = "true";
    process.env.LANGCHAIN_TRACING = "true";
  });

  afterEach(() => {
    // Clean up environment
    delete process.env.LANGSMITH_OTEL_ENABLED;
    delete process.env.LANGCHAIN_TRACING;
  });

  afterAll(async () => {
    await DEFAULT_LANGSMITH_SPAN_PROCESSOR.shutdown();
  });

  test("rate limit errors with native OTEL exporter", async () => {
    const testId = uuid();
    const aiSDKResponses: any[] = [];
    const errors: any[] = [];

    // Create mock models for different scenarios
    const successfulModel1 = new MockLanguageModelV2({
      provider: "openai",
      modelId: "gpt-4.1-nano",
      doGenerate: async () => ({
        rawCall: { rawPrompt: null, rawSettings: {} },
        finishReason: "stop",
        usage: { inputTokens: 6, outputTokens: 4, totalTokens: 10 },
        content: [{ type: "text", text: "OTEL success response 1" }],
        warnings: [],
      }),
    });

    const successfulModel2 = new MockLanguageModelV2({
      provider: "openai",
      modelId: "gpt-4.1-nano",
      doGenerate: async () => ({
        rawCall: { rawPrompt: null, rawSettings: {} },
        finishReason: "stop",
        usage: { inputTokens: 9, outputTokens: 6, totalTokens: 15 },
        content: [{ type: "text", text: "OTEL success response 2" }],
        warnings: [],
      }),
    });

    const rateLimitModel = new MockLanguageModelV2({
      provider: "openai",
      modelId: "gpt-4.1-nano",
      doGenerate: async () => {
        const error = new Error("OTEL Rate limit exceeded");
        error.name = "RateLimitError";
        throw error;
      },
    });

    const wrapper = traceable(
      async () => {
        // First successful call
        try {
          const res1 = await generateText({
            model: successfulModel1,
            experimental_telemetry: {
              isEnabled: true,
              metadata: { runName: "OTEL Successful call 1" },
            },
            messages: [
              {
                role: "user",
                content: "Hello OTEL world",
              },
            ],
          });
          aiSDKResponses.push(res1);
        } catch (error) {
          errors.push(error);
        }

        // Second successful call
        try {
          const res2 = await generateText({
            model: successfulModel2,
            experimental_telemetry: {
              isEnabled: true,
              metadata: { runName: "OTEL Successful call 2" },
            },
            messages: [
              {
                role: "user",
                content: "Another OTEL message",
              },
            ],
          });
          aiSDKResponses.push(res2);
        } catch (error) {
          errors.push(error);
        }

        // Rate limited calls
        for (let i = 0; i < 2; i++) {
          try {
            const res = await generateText({
              model: rateLimitModel,
              experimental_telemetry: {
                isEnabled: true,
                metadata: { runName: `OTEL Rate limited call ${i + 1}` },
              },
              messages: [
                {
                  role: "user",
                  content: `OTEL Rate limit test ${i + 1}`,
                },
              ],
            });
            aiSDKResponses.push(res);
          } catch (error) {
            errors.push(error);
          }
        }

        return "OTEL completed";
      },
      { name: "OTEL Rate Limit Test Wrapper", metadata: { testId } }
    );

    await wrapper();

    // Allow time for OTEL spans to be exported and batches to be processed
    await client.awaitPendingTraceBatches();
    await new Promise((resolve) => setTimeout(resolve, 1000));

    const projectName = getLangSmithEnvironmentVariable("PROJECT") ?? "default";
    await waitUntilRunFoundByMetaField(
      client,
      projectName,
      "testId",
      testId,
      true
    );

    const storedRuns = await toArray(
      client.listRuns({
        projectName,
        filter: `and(eq(metadata_key, "testId"), eq(metadata_value, "${testId}"))`,
      })
    );

    expect(storedRuns.length).toBe(1);
    const storedRun = await client.readRun(storedRuns[0].id, {
      loadChildRuns: true,
    });

    // Sum token counts from successful AI SDK responses only
    const totalSuccessfulTokens = aiSDKResponses.reduce((sum, response) => {
      return sum + (response.usage?.totalTokens || 0);
    }, 0);

    // Verify that only successful calls contribute to token count
    expect(storedRun.total_tokens).toEqual(totalSuccessfulTokens);

    // Verify we have exactly 2 successful calls and 2 errors
    expect(aiSDKResponses.length).toBe(2);
    expect(errors.length).toBe(2);

    // Verify token counts are correct (6+4 + 9+6 = 25)
    expect(totalSuccessfulTokens).toBe(25);

    // Verify that error runs still exist in the trace but don't contribute tokens
    const childRuns = storedRun.child_runs || [];
    expect(childRuns.length).toBeGreaterThan(0);

    // Verify all errors are rate limit errors
    errors.forEach((error) => {
      expect(error.name).toBe("RateLimitError");
    });
  });
});
