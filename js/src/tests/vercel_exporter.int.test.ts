import { openai } from "@ai-sdk/openai";
import { NodeSDK } from "@opentelemetry/sdk-node";
import { z } from "zod";
import { LangSmithAISDKExporter } from "../wrappers/vercel.js";

import {
  generateText,
  streamText,
  generateObject,
  streamObject,
  embed,
  embedMany,
} from "ai";
import { tool } from "ai";
import { gatherIterator } from "./utils/iterator.js";

const telemetrySettings = {
  isEnabled: true,
  functionId: "functionId",
  metadata: {
    userId: "123",
    language: "english",
  },
};

const traceExporter = new LangSmithAISDKExporter();
const sdk = new NodeSDK({ traceExporter });
sdk.start();

test("generateText", async () => {
  await generateText({
    model: openai("gpt-4o-mini"),
    messages: [
      {
        role: "user",
        content: "What are my orders and where are they? My user ID is 123",
      },
    ],
    tools: {
      listOrders: tool({
        description: "list all orders",
        parameters: z.object({ userId: z.string() }),
        execute: async ({ userId }) =>
          `User ${userId} has the following orders: 1`,
      }),
      viewTrackingInformation: tool({
        description: "view tracking information for a specific order",
        parameters: z.object({ orderId: z.string() }),
        execute: async ({ orderId }) =>
          `Here is the tracking information for ${orderId}`,
      }),
    },
    experimental_telemetry: telemetrySettings,
    maxSteps: 10,
  });

  await traceExporter.forceFlush?.();
});

test("generateText with image", async () => {
  await generateText({
    model: openai("gpt-4o-mini"),
    messages: [
      {
        role: "user",
        content: [
          {
            type: "text",
            text: "What's in this picture?",
          },
          {
            type: "image",
            image: new URL("https://picsum.photos/200/300"),
          },
        ],
      },
    ],
    experimental_telemetry: telemetrySettings,
  });

  await traceExporter.forceFlush?.();
});

test("streamText", async () => {
  const result = await streamText({
    model: openai("gpt-4o-mini"),
    messages: [
      {
        role: "user",
        content: "What are my orders and where are they? My user ID is 123",
      },
    ],
    tools: {
      listOrders: tool({
        description: "list all orders",
        parameters: z.object({ userId: z.string() }),
        execute: async ({ userId }) =>
          `User ${userId} has the following orders: 1`,
      }),
      viewTrackingInformation: tool({
        description: "view tracking information for a specific order",
        parameters: z.object({ orderId: z.string() }),
        execute: async ({ orderId }) =>
          `Here is the tracking information for ${orderId}`,
      }),
    },
    experimental_telemetry: { isEnabled: true },
    maxSteps: 10,
  });

  await gatherIterator(result.fullStream);
  await traceExporter.forceFlush?.();
});

test("generateObject", async () => {
  await generateObject({
    model: openai("gpt-4o-mini", { structuredOutputs: true }),
    schema: z.object({
      recipe: z.object({
        city: z.string(),
        unit: z.union([z.literal("celsius"), z.literal("fahrenheit")]),
      }),
    }),
    prompt: "What's the weather in Prague?",
    experimental_telemetry: telemetrySettings,
  });

  await traceExporter.forceFlush?.();
});

test("streamObject", async () => {
  const result = await streamObject({
    model: openai("gpt-4o-mini", { structuredOutputs: true }),
    schema: z.object({
      recipe: z.object({
        city: z.string(),
        unit: z.union([z.literal("celsius"), z.literal("fahrenheit")]),
      }),
    }),
    prompt: "What's the weather in Prague?",
    experimental_telemetry: telemetrySettings,
  });

  await gatherIterator(result.partialObjectStream);
  await traceExporter.forceFlush?.();
});

test("embed", async () => {
  await embed({
    model: openai.embedding("text-embedding-3-small"),
    value: "prague castle at sunset",
    experimental_telemetry: telemetrySettings,
  });

  await traceExporter.forceFlush?.();
});

test("embedMany", async () => {
  await embedMany({
    model: openai.embedding("text-embedding-3-small"),
    values: [
      "a peaceful meadow with wildflowers",
      "bustling city street at rush hour",
      "prague castle at sunset",
    ],
    experimental_telemetry: telemetrySettings,
  });

  await traceExporter.forceFlush?.();
});

afterAll(async () => {
  await sdk.shutdown();
});
