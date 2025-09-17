// import { generateText, stepCountIs, tool, wrapLanguageModel } from "ai";
import { anthropic } from "@ai-sdk/anthropic";
import * as ai from "ai";
import z from "zod";

import { wrapAISDK } from "../../../experimental/vercel/index.js";

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
    const result = await streamText({
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
    const result = await streamObject({
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
});
