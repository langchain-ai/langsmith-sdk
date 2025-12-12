/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable no-process-env */
import { generateText, streamText } from "ai";
import { openai } from "@ai-sdk/openai";
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
describe("OpenAI Cache OTEL Integration Tests", () => {
  beforeEach(() => {
    process.env.LANGSMITH_TRACING = "true";
  });

  afterEach(() => {
    delete process.env.LANGSMITH_OTEL_ENABLED;
    delete process.env.LANGSMITH_TRACING;
  });

  it.skip("openai cache with large prompt for automatic caching using OTEL", async () => {
    process.env.LANGSMITH_OTEL_ENABLED = "true";

    const meta = uuidv4();
    const client = new Client();
    const aiSDKResponses: any[] = [];

    // Create a large prompt (>1024 tokens) to trigger OpenAI's automatic prompt caching
    const largeProgrammingContext = generateLongContext();

    const wrapper = traceable(
      async () => {
        // First call - should create cache due to large prompt (>1024 tokens)
        try {
          const res1 = await generateText({
            model: openai("gpt-4o-mini"),
            experimental_telemetry: {
              isEnabled: true,
            },
            messages: [
              {
                role: "system",
                content: largeProgrammingContext,
              },
              {
                role: "user",
                content:
                  "What are the top 3 memory optimization strategies you would recommend for this Java service?",
              },
            ],
          });
          aiSDKResponses.push(res1);
          console.log("Cache create response:", res1.usage);
        } catch (error) {
          console.error("Cache create error:", error);
        }

        // Second call - should read from cache with same large context
        try {
          const res2 = await generateText({
            model: openai("gpt-4o-mini"),
            experimental_telemetry: {
              isEnabled: true,
            },
            messages: [
              {
                role: "system",
                content: largeProgrammingContext,
              },
              {
                role: "user",
                content:
                  "How would you redesign the database access pattern to reduce connection pool pressure?",
              },
            ],
          });
          aiSDKResponses.push(res2);
          console.log("Cache read response:", res2.usage);
        } catch (error) {
          console.error("Cache read error:", error);
        }

        return "OpenAI cache test completed";
      },
      {
        name: "OpenAI Cache Test Wrapper",
        metadata: { testKey: meta },
        client,
      }
    );

    await wrapper();

    await client.awaitPendingTraceBatches();
  });

  it.skip("openai cache with streamText using OTEL", async () => {
    process.env.LANGSMITH_OTEL_ENABLED = "true";

    const meta = uuidv4();
    const client = new Client();
    const aiSDKResponses: any[] = [];

    // Create a large prompt (>1024 tokens) to trigger OpenAI's automatic prompt caching
    const largeProgrammingContext = generateLongContext();

    const wrapper = traceable(
      async () => {
        // First call - should create cache due to large prompt (>1024 tokens)
        try {
          const { textStream } = streamText({
            model: openai("gpt-4o-mini"),
            experimental_telemetry: {
              isEnabled: true,
            },
            messages: [
              {
                role: "system",
                content: largeProgrammingContext,
              },
              {
                role: "user",
                content:
                  "What are the top 3 memory optimization strategies you would recommend for this Java service?",
              },
            ],
          });

          let fullText = "";
          for await (const chunk of textStream) {
            fullText += chunk;
          }
          aiSDKResponses.push({ text: fullText });
          console.log("Cache create response with streamText");
        } catch (error) {
          console.error("Cache create error:", error);
        }

        // Second call - should read from cache with same large context
        try {
          const { textStream } = streamText({
            model: openai("gpt-4o-mini"),
            experimental_telemetry: {
              isEnabled: true,
            },
            messages: [
              {
                role: "system",
                content: largeProgrammingContext,
              },
              {
                role: "user",
                content:
                  "How would you redesign the database access pattern to reduce connection pool pressure?",
              },
            ],
            providerOptions: {
              openai: {
                stream_options: {
                  include_usage: true,
                },
              },
            },
          });

          let fullText = "";
          for await (const chunk of textStream) {
            fullText += chunk;
          }
          aiSDKResponses.push({ text: fullText });
          console.log("Cache read response with streamText");
        } catch (error) {
          console.error("Cache read error:", error);
        }

        return "OpenAI cache streamText test completed";
      },
      {
        name: "OpenAI Cache StreamText Test Wrapper",
        metadata: { testKey: meta },
        client,
      }
    );

    await wrapper();

    await client.awaitPendingTraceBatches();
  });
});
