import { NodeTracerProvider } from "@opentelemetry/sdk-trace-node";
import { BatchSpanProcessor } from "@opentelemetry/sdk-trace-base";

import {
  generateText,
  streamText,
  generateObject,
  streamObject,
  tool,
  stepCountIs,
} from "ai";
import { openai } from "@ai-sdk/openai";

import { v4 as uuid } from "uuid";
import { z } from "zod";
import { AISDKExporter } from "../../vercel.js";
import { Client } from "../../index.js";
import { traceable } from "../../traceable.js";
import { waitUntilRunFound, toArray } from "../utils.js";

const client = new Client();
// Not using @opentelemetry/sdk-node because we need to force flush
// the spans to ensure they are sent to LangSmith between tests
const provider = new NodeTracerProvider({
  spanProcessors: [new BatchSpanProcessor(new AISDKExporter({ client }))],
});
provider.register();

// Deprecating
describe.skip("Legacy AI SDK tests", () => {
  test("generateText", async () => {
    const runId = uuid();

    await generateText({
      model: openai("gpt-4.1-nano"),
      messages: [
        {
          role: "user",
          content: "What are my orders and where are they? My user ID is 123",
        },
      ],
      tools: {
        listOrders: tool({
          description: "list all orders",
          inputSchema: z.object({ userId: z.string() }),
          execute: async ({ userId }) =>
            `User ${userId} has the following orders: 1`,
        }),
        viewTrackingInformation: tool({
          description: "view tracking information for a specific order",
          inputSchema: z.object({ orderId: z.string() }),
          execute: async ({ orderId }) =>
            `Here is the tracking information for ${orderId}`,
        }),
      },
      experimental_telemetry: AISDKExporter.getSettings({
        isEnabled: true,
        runId,
        functionId: "functionId",
        metadata: { userId: "123", language: "english" },
      }),
      stopWhen: stepCountIs(10),
    });

    await provider.forceFlush();
    await waitUntilRunFound(client, runId, true);

    const storedRun = await client.readRun(runId);
    expect(storedRun.id).toEqual(runId);
  });

  test("generateText with image", async () => {
    const runId = uuid();
    await generateText({
      model: openai("gpt-4.1-nano"),
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
      experimental_telemetry: AISDKExporter.getSettings({
        isEnabled: true,
        runId,
        runName: "vercelImageTest",
        functionId: "functionId",
        metadata: { userId: "123", language: "english" },
      }),
    });

    await provider.forceFlush();
    await waitUntilRunFound(client, runId, true);

    const storedRun = await client.readRun(runId);
    expect(storedRun.id).toEqual(runId);
  });

  test("streamText", async () => {
    const runId = uuid();
    const result = await streamText({
      model: openai("gpt-4.1-nano"),
      messages: [
        {
          role: "user",
          content: "What are my orders and where are they? My user ID is 123",
        },
      ],
      tools: {
        listOrders: tool({
          description: "list all orders",
          inputSchema: z.object({ userId: z.string() }),
          execute: async ({ userId }) =>
            `User ${userId} has the following orders: 1`,
        }),
        viewTrackingInformation: tool({
          description: "view tracking information for a specific order",
          inputSchema: z.object({ orderId: z.string() }),
          execute: async ({ orderId }) =>
            `Here is the tracking information for ${orderId}`,
        }),
      },
      experimental_telemetry: AISDKExporter.getSettings({
        isEnabled: true,
        runId,
        functionId: "functionId",
        metadata: { userId: "123", language: "english" },
      }),
      stopWhen: stepCountIs(10),
    });

    await toArray(result.fullStream);
    await provider.forceFlush();
    await waitUntilRunFound(client, runId, true);

    const storedRun = await client.readRun(runId);
    expect(storedRun.id).toEqual(runId);
  });

  test("generateObject", async () => {
    const runId = uuid();
    await generateObject({
      model: openai("gpt-4.1-nano"),
      schema: z.object({
        weather: z.object({
          city: z.string(),
          unit: z.union([z.literal("celsius"), z.literal("fahrenheit")]),
        }),
      }),
      prompt: "What's the weather in Prague?",
      experimental_telemetry: AISDKExporter.getSettings({
        isEnabled: true,
        runId,
        functionId: "functionId",
        metadata: { userId: "123", language: "english" },
      }),
    });

    await provider.forceFlush();
    await waitUntilRunFound(client, runId, true);

    const storedRun = await client.readRun(runId);
    expect(storedRun.id).toEqual(runId);
  });

  test("streamObject", async () => {
    const runId = uuid();
    const result = await streamObject({
      model: openai("gpt-4.1-nano"),
      schema: z.object({
        weather: z.object({
          city: z.string(),
          unit: z.union([z.literal("celsius"), z.literal("fahrenheit")]),
        }),
      }),
      prompt: "What's the weather in Prague?",
      experimental_telemetry: AISDKExporter.getSettings({
        isEnabled: true,
        runId,
        functionId: "functionId",
        metadata: {
          userId: "123",
          language: "english",
        },
      }),
    });

    await toArray(result.partialObjectStream);
    await provider.forceFlush();
    await waitUntilRunFound(client, runId, true);

    const storedRun = await client.readRun(runId);
    expect(storedRun.id).toEqual(runId);
  });

  test("traceable", async () => {
    const runId = uuid();

    const wrappedText = traceable(
      async (content: string) => {
        const { text } = await generateText({
          model: openai("gpt-4.1-nano"),
          messages: [{ role: "user", content }],
          tools: {
            listOrders: tool({
              description: "list all orders",
              inputSchema: z.object({ userId: z.string() }),
              execute: async ({ userId }) =>
                `User ${userId} has the following orders: 1`,
            }),
            viewTrackingInformation: tool({
              description: "view tracking information for a specific order",
              inputSchema: z.object({ orderId: z.string() }),
              execute: async ({ orderId }) =>
                `Here is the tracking information for ${orderId}`,
            }),
          },
          experimental_telemetry: AISDKExporter.getSettings({
            isEnabled: true,
            functionId: "functionId",
            runName: "nestedVercelTrace",
            metadata: { userId: "123", language: "english" },
          }),
          stopWhen: stepCountIs(10),
        });

        const foo = traceable(
          async () => {
            return "bar";
          },
          { name: "foo" }
        );

        await foo();

        return { text };
      },
      { name: "parentTraceable", id: runId }
    );

    const result = await wrappedText(
      "What are my orders and where are they? My user ID is 123. Use available tools."
    );
    await waitUntilRunFound(client, runId, true);
    const storedRun = await client.readRun(runId);
    expect(storedRun.outputs).toEqual(result);
  });

  afterAll(async () => {
    await provider.shutdown();
  });
});
