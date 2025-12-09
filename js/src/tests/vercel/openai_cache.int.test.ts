import { NodeSDK } from "@opentelemetry/sdk-node";
import { getNodeAutoInstrumentations } from "@opentelemetry/auto-instrumentations-node";
import { v4 as uuid } from "uuid";
import { generateText } from "ai";
import { openai } from "@ai-sdk/openai";

import { AISDKExporter } from "../../vercel.js";
import { traceable } from "../../traceable.js";
import { generateLongContext } from "../utils.js";

// Token intensive test, so skipping by default
describe.skip("OpenAI Cache Completion Tests", () => {
  test("openai cache with large prompt for automatic caching", async () => {
    const sdk = new NodeSDK({
      traceExporter: new AISDKExporter(),
      instrumentations: [getNodeAutoInstrumentations()],
    });

    sdk.start();

    const runId = uuid();
    const aiSDKResponses: any[] = [];

    // Create a large prompt (>1024 tokens) to trigger OpenAI's automatic prompt caching
    const largeProgrammingContext = generateLongContext();
    const wrapper = traceable(
      async () => {
        // First call - should create cache due to large prompt (>1024 tokens)
        try {
          const res1 = await generateText({
            model: openai("gpt-4.1-nano"),
            experimental_telemetry: AISDKExporter.getSettings({
              runName: "OpenAI Cache Create",
            }),
            messages: [
              {
                role: "system",
                content: largeProgrammingContext,
              },
            ],
          });
          aiSDKResponses.push(res1);
          console.log(
            "Cache create response:",
            res1.usage,
            res1.providerMetadata
          );
        } catch (error) {
          console.error("Cache create error:", error);
        }

        // Second call - should read from cache with same large context
        try {
          const res2 = await generateText({
            model: openai("gpt-4.1-nano"),
            experimental_telemetry: AISDKExporter.getSettings({
              runName: "OpenAI Cache Read",
            }),
            messages: [
              {
                role: "system",
                content: largeProgrammingContext,
              },
            ],
          });
          aiSDKResponses.push(res2);
          console.log(
            "Cache read response:",
            res2.usage,
            res2.providerMetadata
          );
        } catch (error) {
          console.error("Cache read error:", error);
        }

        return "OpenAI cache test completed";
      },
      {
        name: "OpenAI Cache Test Wrapper",
        id: runId,
        project_name: "lsjs-test",
      }
    );

    await wrapper();
    await sdk.shutdown();
  });
});
