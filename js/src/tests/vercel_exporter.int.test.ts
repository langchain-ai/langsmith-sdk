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

const telemetrySettings = {
  isEnabled: true,
  functionId: "functionId",
  metadata: {
    userId: "123",
    language: "english",
  },
};

test.concurrent("generateText", async () => {
  const traceExporter = new LangSmithAISDKExporter();
  const sdk = new NodeSDK({ traceExporter });
  sdk.start();

  function getOrders(userId: string) {
    return `User ${userId} has the following orders: 1`;
  }

  function getTrackingInformation(orderId: string) {
    return `Here is the tracking information for ${orderId}`;
  }

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
        execute: async ({ userId }) => getOrders(userId),
      }),
      viewTrackingInformation: tool({
        description: "view tracking information for a specific order",
        parameters: z.object({ orderId: z.string() }),
        execute: async ({ orderId }) => getTrackingInformation(orderId),
      }),
    },
    experimental_telemetry: telemetrySettings,
    maxSteps: 10,
  });

  await sdk.shutdown();
});

test.concurrent("streamText", async () => {
  const traceExporter = new LangSmithAISDKExporter();
  const sdk = new NodeSDK({ traceExporter });
  sdk.start();

  function getOrders(userId: string) {
    return `User ${userId} has the following orders: 1`;
  }

  function getTrackingInformation(orderId: string) {
    return `Here is the tracking information for ${orderId}`;
  }

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
        execute: async ({ userId }) => getOrders(userId),
      }),
      viewTrackingInformation: tool({
        description: "view tracking information for a specific order",
        parameters: z.object({ orderId: z.string() }),
        execute: async ({ orderId }) => getTrackingInformation(orderId),
      }),
    },
    experimental_telemetry: { isEnabled: true },
    maxSteps: 10,
  });

  for await (const _stream of result.fullStream) {
    // consume
  }

  await sdk.shutdown();
});

test.concurrent("generateObject", async () => {
  const traceExporter = new LangSmithAISDKExporter();
  const sdk = new NodeSDK({ traceExporter });
  sdk.start();

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

  await sdk.shutdown();
});

test.concurrent("streamObject", async () => {
  const traceExporter = new LangSmithAISDKExporter();
  const sdk = new NodeSDK({ traceExporter });
  sdk.start();

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

  for await (const _partialObject of result.partialObjectStream) {
    // pass
  }

  await sdk.shutdown();
});

test.concurrent("embed", async () => {
  const traceExporter = new LangSmithAISDKExporter();
  const sdk = new NodeSDK({ traceExporter });
  sdk.start();

  await embed({
    model: openai.embedding("text-embedding-3-small"),
    value: "prague castle at sunset",
    experimental_telemetry: telemetrySettings,
  });

  await sdk.shutdown();
});

test.concurrent("embedMany", async () => {
  const traceExporter = new LangSmithAISDKExporter();
  const sdk = new NodeSDK({ traceExporter });
  sdk.start();

  await embedMany({
    model: openai.embedding("text-embedding-3-small"),
    values: [
      "a peaceful meadow with wildflowers",
      "bustling city street at rush hour",
      "prague castle at sunset",
    ],
    experimental_telemetry: telemetrySettings,
  });

  await sdk.shutdown();
});

test.concurrent("generateText with image", async () => {
  const traceExporter = new LangSmithAISDKExporter();
  const sdk = new NodeSDK({ traceExporter });
  sdk.start();

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

  await sdk.shutdown();
});
