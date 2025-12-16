/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable no-process-env */
import { generateText } from "ai";
import { anthropic } from "@ai-sdk/anthropic";
import { v4 as uuidv4 } from "uuid";

import { Client } from "../../../client.js";
import { traceable } from "../../../traceable.js";
import { generateLongContext } from "../../utils.js";

// Initialize basic OTEL setup
import { initializeOTEL } from "../../../experimental/otel/setup.js";

const { DEFAULT_LANGSMITH_SPAN_PROCESSOR } = initializeOTEL();

afterAll(async () => {
  await DEFAULT_LANGSMITH_SPAN_PROCESSOR.shutdown();
});

// Token intensive test, so skipping by default
describe.skip("Anthropic Cache OTEL Integration Tests", () => {
  beforeEach(() => {
    process.env.LANGSMITH_TRACING = "true";
  });

  afterEach(() => {
    delete process.env.LANGSMITH_OTEL_ENABLED;
    delete process.env.LANGSMITH_TRACING;
  });

  it.skip("anthropic cache read and write tokens with OTEL exporter", async () => {
    process.env.LANGSMITH_OTEL_ENABLED = "true";

    const meta = uuidv4();
    const client = new Client();
    const aiSDKResponses: any[] = [];

    const errorMessage = generateLongContext();

    const wrapper = traceable(
      async () => {
        // First call - creates cache with long error message
        try {
          const res1 = await generateText({
            model: anthropic("claude-3-5-haiku-20241022"),
            experimental_telemetry: {
              isEnabled: true,
            },
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
            experimental_telemetry: {
              isEnabled: true,
            },
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
                  { type: "text", text: "Provide a solution for this error." },
                ],
              },
            ],
          });
          aiSDKResponses.push(res2);
          console.log("Cache read response:", res2.providerMetadata?.anthropic);
        } catch (error) {
          console.error("Cache read error:", error);
        }

        return "Anthropic cache test completed";
      },
      {
        name: "Anthropic Cache Test Wrapper",
        metadata: { testKey: meta },
        client,
      }
    );

    await wrapper();
    await client.awaitPendingTraceBatches();
  });

  it.skip("anthropic cache read and write 1h cached tokens with OTEL exporter", async () => {
    process.env.LANGSMITH_OTEL_ENABLED = "true";

    const meta = uuidv4();
    const client = new Client();
    const aiSDKResponses: any[] = [];

    const errorMessage = generateLongContext();

    const wrapper = traceable(
      async () => {
        // First call - creates cache with long error message
        try {
          const res1 = await generateText({
            model: anthropic("claude-sonnet-4-20250514"),
            headers: {
              "anthropic-beta": "extended-cache-ttl-2025-04-11",
            },
            experimental_telemetry: {
              isEnabled: true,
            },
            messages: [
              {
                role: "user",
                content: [
                  { type: "text", text: "You are a JavaScript expert." },
                  {
                    type: "text",
                    text: `Error message: ${errorMessage}`,
                    providerOptions: {
                      anthropic: {
                        cacheControl: { type: "ephemeral", ttl: "1h" },
                      },
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
            model: anthropic("claude-sonnet-4-20250514"),
            headers: {
              "anthropic-beta": "extended-cache-ttl-2025-04-11",
            },
            experimental_telemetry: {
              isEnabled: true,
            },
            messages: [
              {
                role: "user",
                content: [
                  { type: "text", text: "You are a JavaScript expert." },
                  {
                    type: "text",
                    text: `Error message: ${errorMessage}`,
                    providerOptions: {
                      anthropic: {
                        cacheControl: { type: "ephemeral", ttl: "1h" },
                      },
                    },
                  },
                  { type: "text", text: "Provide a solution for this error." },
                ],
              },
            ],
          });
          aiSDKResponses.push(res2);
          console.log("Cache read response:", res2.providerMetadata?.anthropic);
        } catch (error) {
          console.error("Cache read error:", error);
        }

        return "Anthropic cache test completed";
      },
      {
        name: "Anthropic Cache Test Wrapper",
        metadata: { testKey: meta },
        client,
      }
    );

    await wrapper();
    await client.awaitPendingTraceBatches();
  });
});
