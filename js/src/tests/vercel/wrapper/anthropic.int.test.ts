// import { generateText, stepCountIs, tool, wrapLanguageModel } from "ai";
import { anthropic } from "@ai-sdk/anthropic";
import * as ai from "ai";
import z from "zod";

import { wrapAISDK } from "../../../experimental/vercel/index.js";
import { generateLongContext } from "../../utils.js";
import { traceable } from "../../../traceable.js";
import { v4 } from "uuid";
import { Client } from "../../../index.js";

const { tool, stepCountIs } = ai;

const { generateText, streamText, generateObject, streamObject } =
  wrapAISDK(ai);

// No Anthropic key in CI
describe("anthropic", () => {
  test.skip("wrap generateText", async () => {
    const result = await generateText({
      model: anthropic("claude-3-5-haiku-latest"),
      messages: [
        {
          role: "user",
          content: "What are my orders? My user ID is 123. Always use tools.",
        },
      ],
      tools: {
        listOrders: tool({
          description: "list all orders",
          inputSchema: z.object({ userId: z.string() }),
          execute: async ({ userId }) =>
            `User ${userId} has the following orders: 1`,
        }),
      },
      stopWhen: stepCountIs(10),
    });
    expect(result.text).toBeDefined();
    expect(result.text.length).toBeGreaterThan(0);
    expect(result.usage).toBeDefined();
    expect(result.providerMetadata).toBeDefined();
  });

  test.skip("wrap streamText", async () => {
    const result = streamText({
      model: anthropic("claude-3-5-haiku-latest"),
      messages: [
        {
          role: "user",
          content: "What are my orders? My user ID is 123. Always use tools.",
        },
      ],
      tools: {
        listOrders: tool({
          description: "list all orders",
          inputSchema: z.object({ userId: z.string() }),
          execute: async ({ userId }) =>
            `User ${userId} has the following orders: 1`,
        }),
      },
      stopWhen: stepCountIs(10),
    });
    let total = "";
    for await (const chunk of result.textStream) {
      total += chunk;
    }
    expect(total).toBeDefined();
    expect(total.length).toBeGreaterThan(0);
    expect(result.usage).toBeDefined();
    expect(result.providerMetadata).toBeDefined();
  });

  test.skip("wrap generateObject", async () => {
    const schema = z.object({
      color: z.string(),
    });
    const result = await generateObject({
      model: anthropic("claude-3-5-haiku-latest"),
      messages: [
        {
          role: "user",
          content: "What color is the sky?",
        },
      ],
      schema,
    });
    expect(result.object).toBeDefined();
    expect(schema.parse(result.object)).toBeDefined();
    expect(result.usage).toBeDefined();
    expect(result.providerMetadata).toBeDefined();
  });

  test.skip("wrap streamObject", async () => {
    const schema = z.object({
      color: z.string(),
    });
    const result = streamObject({
      model: anthropic("claude-3-5-haiku-latest"),
      messages: [
        {
          role: "user",
          content: "What color is the sky?",
        },
      ],
      schema,
    });
    const chunks = [];
    for await (const chunk of result.partialObjectStream) {
      chunks.push(chunk);
    }
    expect(chunks.length).toBeGreaterThan(0);
    expect(schema.parse(chunks.at(-1))).toBeDefined();
    expect(result.usage).toBeDefined();
    expect(result.providerMetadata).toBeDefined();
  });

  test.skip("stream cancellation with abortController should finish normally", async () => {
    const abortController = new AbortController();

    const result = streamText({
      model: anthropic("claude-3-5-haiku-latest"),
      messages: [
        {
          role: "user",
          content: [
            {
              type: "text",
              text: "tell me lorem ipsum poem",
            },
          ],
        },
      ],
      abortSignal: abortController.signal,
    });

    let i = 0;
    for await (const p of result.fullStream) {
      if (p.type === "text-delta") {
        console.log(p.text);

        if (i++ > 5) {
          abortController.abort();
          console.log("aborted");
        }
      }
    }
  });

  it.skip("anthropic cache read and write tokens with OTEL exporter", async () => {
    const meta = v4();
    const client = new Client();
    const aiSDKResponses: unknown[] = [];

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
    const meta = v4();
    const client = new Client();
    const aiSDKResponses: unknown[] = [];

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
