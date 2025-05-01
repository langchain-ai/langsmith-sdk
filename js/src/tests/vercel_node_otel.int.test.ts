import { NodeSDK } from "@opentelemetry/sdk-node";
import { getNodeAutoInstrumentations } from "@opentelemetry/auto-instrumentations-node";
import { v4 as uuid } from "uuid";
import { generateText, tool } from "ai";
import { openai } from "@ai-sdk/openai";
import { z } from "zod";

import { AISDKExporter } from "../vercel.js";
import { waitUntilRunFound } from "./utils.js";
import { Client } from "../index.js";
import { traceable } from "../traceable.js";

const client = new Client();

test("nested generateText", async () => {
  const sdk = new NodeSDK({
    traceExporter: new AISDKExporter(),
    instrumentations: [getNodeAutoInstrumentations()],
  });

  sdk.start();

  const runId = uuid();

  const wrapper = traceable(
    async () => {
      return generateText({
        model: openai("gpt-4.1-mini"),
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
            execute: async ({}) => {
              await generateText({
                model: openai("gpt-4.1-mini"),
                experimental_telemetry: AISDKExporter.getSettings({}),
                messages: [
                  {
                    role: "user",
                    content: `How are you feeling?`,
                  },
                ],
              });
              await generateText({
                model: openai("gpt-4.1-mini"),
                experimental_telemetry: AISDKExporter.getSettings({}),
                messages: [
                  {
                    role: "user",
                    content: `How are you feeling?`,
                  },
                ],
              });
              // TODO: This messes up tracing, fix in the future by making traceable
              // truly OTEL compatible.
              // const generateTrackingInformation = traceable(async (orderId: string) => {
              //   const res = await generateText({
              //     model: openai("gpt-4.1-mini"),
              //     experimental_telemetry: AISDKExporter.getSettings({}),
              //     messages: [
              //       {
              //         role: "user",
              //         content: `Generate a random tracking information, include order ID ${orderId}`,
              //       },
              //     ],
              //   });
              //   return res.text;
              // }, {
              //   name: "generateTrackingInformationWrapper",
              //   parent_run_id: aiSdkRunId,
              // });
              // const res = await generateTrackingInformation(orderId);
              // return res;
              return "foo";
            },
          }),
        },
        experimental_telemetry: AISDKExporter.getSettings({
          functionId: "functionId",
          metadata: { userId: "123", language: "english" },
        }),
        maxSteps: 10,
      });
    },
    { name: "AI SDK Agent Wrapper", id: runId }
  );

  await wrapper();

  await sdk.shutdown();

  await waitUntilRunFound(client, runId, true);

  const storedRun = await client.readRun(runId);
  expect(storedRun.id).toEqual(runId);
});
