// import { generateText, stepCountIs, tool, wrapLanguageModel } from "ai";
import { openai } from "@ai-sdk/openai";
import * as ai from "ai";
import z from "zod";
import { v4 } from "uuid";

import { Client } from "../../../index.js";
import { wrapAISDK } from "../../../experimental/vercel/index.js";
import { waitUntilRunFound } from "../../utils.js";

const { tool, stepCountIs } = ai;

const { generateText, streamText, generateObject, streamObject } =
  wrapAISDK(ai);

test("wrap generateText", async () => {
  const result = await generateText({
    model: openai("gpt-4.1-nano"),
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

test("wrap streamText", async () => {
  const result = await streamText({
    model: openai("gpt-4.1-nano"),
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

test("wrap generateObject", async () => {
  const schema = z.object({
    color: z.string(),
  });
  const result = await generateObject({
    model: openai("gpt-4.1-nano"),
    messages: [
      {
        role: "user",
        content: "What color is the sky in one word?",
      },
    ],
    schema,
  });
  expect(result.object).toBeDefined();
  expect(schema.parse(result.object)).toBeDefined();
  expect(result.usage).toBeDefined();
  expect(result.providerMetadata).toBeDefined();
});

test("wrap streamObject", async () => {
  const schema = z.object({
    color: z.string(),
  });
  const result = await streamObject({
    model: openai("gpt-4.1-nano"),
    messages: [
      {
        role: "user",
        content: "What color is the sky in one word?",
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

test("can set run id", async () => {
  const runId = v4();
  const client = new Client();
  const { generateText } = wrapAISDK(ai, { id: runId });
  await generateText({
    model: openai("gpt-4.1-nano"),
    messages: [
      {
        role: "user",
        content: "What color is the sky in one word?",
      },
    ],
  });
  await waitUntilRunFound(client, runId);
  const run = await client.readRun(runId);
  expect(run.id).toBe(runId);
});
