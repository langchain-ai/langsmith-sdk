import { NodeSDK } from "@opentelemetry/sdk-node";
import { getNodeAutoInstrumentations } from "@opentelemetry/auto-instrumentations-node";
import { v4 as uuid } from "uuid";
import { generateText } from "ai";
import { google } from "@ai-sdk/google";

import { AISDKExporter } from "../../vercel.js";
import { traceable } from "../../traceable.js";
import { generateLongContext } from "./utils.js";

// Token intensive test, so skipping by default
describe("Gemini Cache Completion Tests", () => {
  test("gemini cache with large prompt for automatic caching", async () => {
    const sdk = new NodeSDK({
      traceExporter: new AISDKExporter(),
      instrumentations: [getNodeAutoInstrumentations()],
    });

    sdk.start();

    const runId = uuid();
    const aiSDKResponses: any[] = [];

    // Create a large prompt to trigger Gemini's automatic context caching
    const largeProgrammingContext = generateLongContext();
    const wrapper = traceable(
      async () => {
        // First call - should create cache due to large prompt
        try {
          const res1 = await generateText({
            model: google("gemini-2.5-flash"),
            experimental_telemetry: AISDKExporter.getSettings({
              runName: "Gemini Cache Create",
            }),
            prompt: largeProgrammingContext,
          });
          aiSDKResponses.push(res1);
          console.log(
            "Cache create response:",
            res1.usage,
            res1.providerMetadata,
            res1.response.body,
          );
        } catch (error) {
          console.error("Cache create error:", error);
        }
        
        await new Promise(resolve => setTimeout(resolve, 5000));

        // Second call - should read from cache with same large context
        try {
          const res2 = await generateText({
            model: google("gemini-2.5-flash"),
            experimental_telemetry: AISDKExporter.getSettings({
              runName: "Gemini Cache Read",
            }),
            prompt: largeProgrammingContext,
          });
          aiSDKResponses.push(res2);
          console.log(
            "Cache read response:",
            res2.usage,
            res2.providerMetadata,
            res2.response.body,
          );
        } catch (error) {
          console.error("Cache read error:", error);
        }

        return "Gemini cache test completed";
      },
      {
        name: "Gemini Cache Test Wrapper",
        id: runId,
        project_name: "lsjs-test",
      }
    );

    await wrapper();
    await sdk.shutdown();
  });
});