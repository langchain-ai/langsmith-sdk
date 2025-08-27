import { NodeSDK } from "@opentelemetry/sdk-node";
import { getNodeAutoInstrumentations } from "@opentelemetry/auto-instrumentations-node";
import { v4 as uuid } from "uuid";
import { generateText } from "ai";
import { MockLanguageModelV2 } from "ai/test";

import { AISDKExporter } from "../../vercel.js";
import { waitUntilRunFound } from "../utils.js";
import { Client } from "../../index.js";
import { traceable } from "../../traceable.js";

const client = new Client();

describe.skip("Legacy AI SDK tests", () => {
  test("rate limit errors with token tracking", async () => {
    const sdk = new NodeSDK({
      traceExporter: new AISDKExporter(),
      instrumentations: [getNodeAutoInstrumentations()],
    });

    sdk.start();

    const runId = uuid();
    const aiSDKResponses: any[] = [];
    const errors: any[] = [];

    // Create mock models for different scenarios
    const successfulModel1 = new MockLanguageModelV2({
      provider: "openai",
      modelId: "gpt-4.1-nano",
      doGenerate: async () => ({
        rawCall: { rawPrompt: null, rawSettings: {} },
        finishReason: "stop",
        usage: { inputTokens: 5, outputTokens: 5, totalTokens: 10 },
        content: [{ type: "text", text: "Hello world response" }],
        warnings: [],
      }),
    });

    const successfulModel2 = new MockLanguageModelV2({
      provider: "openai",
      modelId: "gpt-4.1-nano",
      doGenerate: async () => ({
        rawCall: { rawPrompt: null, rawSettings: {} },
        finishReason: "stop",
        usage: { inputTokens: 8, outputTokens: 7, totalTokens: 15 },
        content: [{ type: "text", text: "Another successful response" }],
        warnings: [],
      }),
    });

    const rateLimitModel = new MockLanguageModelV2({
      provider: "openai",
      modelId: "gpt-4.1-nano",
      doGenerate: async () => {
        const error = new Error("Rate limit exceeded");
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
            experimental_telemetry: AISDKExporter.getSettings({
              runName: "Successful call 1",
            }),
            messages: [
              {
                role: "user",
                content: "Hello world",
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
            experimental_telemetry: AISDKExporter.getSettings({
              runName: "Successful call 2",
            }),
            messages: [
              {
                role: "user",
                content: "Another message",
              },
            ],
          });
          aiSDKResponses.push(res2);
        } catch (error) {
          errors.push(error);
        }

        // Rate limited calls
        for (let i = 0; i < 3; i++) {
          try {
            const res = await generateText({
              model: rateLimitModel,
              experimental_telemetry: AISDKExporter.getSettings({
                runName: `Rate limited call ${i + 1}`,
              }),
              messages: [
                {
                  role: "user",
                  content: `Rate limit test ${i + 1}`,
                },
              ],
            });
            aiSDKResponses.push(res);
          } catch (error) {
            errors.push(error);
          }
        }

        return "completed";
      },
      { name: "Rate Limit Test Wrapper", id: runId, project_name: "lsjs-test" }
    );

    await wrapper();
    await sdk.shutdown();
    await waitUntilRunFound(client, runId, true);

    const storedRun = await client.readRun(runId, { loadChildRuns: true });
    expect(storedRun.id).toEqual(runId);

    // Sum token counts from successful AI SDK responses only
    const totalSuccessfulTokens = aiSDKResponses.reduce((sum, response) => {
      return sum + (response.usage?.totalTokens || 0);
    }, 0);

    // Verify that only successful calls contribute to token count
    expect(storedRun.total_tokens).toEqual(totalSuccessfulTokens);

    // Verify we have exactly 2 successful calls and 3 errors
    expect(aiSDKResponses.length).toBe(2);
    expect(errors.length).toBe(3);

    // Verify token counts are correct (5+5 + 8+7 = 25)
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
