import { NodeSDK } from "@opentelemetry/sdk-node";
import { getNodeAutoInstrumentations } from "@opentelemetry/auto-instrumentations-node";
import { v4 as uuid } from "uuid";
import { generateText } from "ai";
import { anthropic } from "@ai-sdk/anthropic";

import { AISDKExporter } from "../../vercel.js";
import { traceable } from "../../traceable.js";
import { generateLongContext } from "../utils.js";

// Token intensive test, so skipping by default
describe.skip("Anthropic Cache Completion Tests", () => {
  test("anthropic cache read and write tokens with AISDKExporter", async () => {
    const sdk = new NodeSDK({
      traceExporter: new AISDKExporter(),
      instrumentations: [getNodeAutoInstrumentations()],
    });

    sdk.start();

    const runId = uuid();
    const aiSDKResponses: any[] = [];

    const errorMessage = generateLongContext();

    const wrapper = traceable(
      async () => {
        // First call - creates cache with long error message
        try {
          const res1 = await generateText({
            model: anthropic("claude-3-5-haiku-20241022"),
            experimental_telemetry: AISDKExporter.getSettings({
              runName: "Anthropic Cache Create",
            }),
            messages: [
              {
                role: "user",
                content: [
                  { type: "text", text: "You are a JavaScript expert." },
                  {
                    type: "text",
                    text: `Error message: ${errorMessage}`,
                    providerOptions: {
                      anthropic: { cacheControl: { type: "ephemeral" } },
                    },
                  },
                  { type: "text", text: "Explain this error message briefly." },
                ],
              },
            ],
          });
          aiSDKResponses.push(res1);
          console.log(
            "Cache create response:",
            res1.providerMetadata?.anthropic,
            res1.usage
          );
        } catch (error) {
          console.error("Cache create error:", error);
        }

        // Second call - should read from cache with same error message
        try {
          const res2 = await generateText({
            model: anthropic("claude-3-5-haiku-20241022"),
            experimental_telemetry: AISDKExporter.getSettings({
              runName: "Anthropic Cache Read",
            }),
            messages: [
              {
                role: "user",
                content: [
                  { type: "text", text: "You are a JavaScript expert." },
                  {
                    type: "text",
                    text: `Error message: ${errorMessage}`,
                    providerOptions: {
                      anthropic: { cacheControl: { type: "ephemeral" } },
                    },
                  },
                  { type: "text", text: "Explain this error message briefly." },
                ],
              },
            ],
          });
          aiSDKResponses.push(res2);
          console.log("Cache read response:", res2.providerMetadata?.anthropic);
        } catch (error) {
          console.error("Cache read error:", error);
        }

        return "Cache test completed";
      },
      {
        name: "Anthropic Cache Test Wrapper",
        id: runId,
        project_name: "lsjs-test",
      }
    );

    await wrapper();
    await sdk.shutdown();
  });
});
