// import { generateText, stepCountIs, tool, wrapLanguageModel } from "ai";
import { openai } from "@ai-sdk/openai";
import { tool, stepCountIs, streamObject } from "ai";
import z from "zod";

import {
  generateText,
  streamText,
  generateObject,
} from "../../../experimental/vercel/index.js";

test("wrap generateText", async () => {
  const result = await generateText({
    model: openai("gpt-4.1-nano"),
    messages: [
      {
        role: "user",
        content:
          "What are my orders and where are they? My user ID is 123. Always use tools.",
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
  console.log(result);
});

test("wrap streamText", async () => {
  const result = await streamText({
    model: openai("gpt-4.1-nano"),
    messages: [
      {
        role: "user",
        content:
          "What are my orders and where are they? My user ID is 123. Always use tools.",
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
  await result.consumeStream();
});

test.only("wrap generateObject", async () => {
  const result = await generateObject({
    model: openai("gpt-4.1-nano"),
    messages: [
      {
        role: "user",
        content: "What color is the sky?",
      },
    ],
    schema: z.object({
      color: z.string(),
    }),
  });
  console.log(result);
  expect(result.object).toBeDefined();
});

test("wrap streamObject", async () => {
  const result = streamObject({
    model: openai("gpt-4.1-nano"),
    messages: [
      {
        role: "user",
        content: "What color is the sky?",
      },
    ],
    schema: z.object({
      color: z.string(),
    }),
  });
  for await (const chunk of result.partialObjectStream) {
    console.log(chunk);
  }
});
