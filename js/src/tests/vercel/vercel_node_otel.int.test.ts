import { NodeSDK } from "@opentelemetry/sdk-node";
import { getNodeAutoInstrumentations } from "@opentelemetry/auto-instrumentations-node";
import { v4 as uuid } from "uuid";
import { generateText, stepCountIs, tool } from "ai";
import { openai } from "@ai-sdk/openai";
import { z } from "zod";

import { AISDKExporter } from "../../vercel.js";
import { waitUntilRunFound } from "../utils.js";
import { Client } from "../../index.js";
import { traceable } from "../../traceable.js";

const client = new Client();

describe.skip("Legacy AI SDK tests", () => {
  test("nested generateText", async () => {
    const sdk = new NodeSDK({
      traceExporter: new AISDKExporter(),
      instrumentations: [getNodeAutoInstrumentations()],
    });

    sdk.start();

    const runId = uuid();

    const aiSDKResponses: any[] = [];

    const wrapper = traceable(
      async () => {
        const mainResult = await generateText({
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
            viewTrackingInformation: tool({
              description: "view tracking information for a specific order",
              inputSchema: z.object({ orderId: z.string() }),
              execute: async ({ orderId }) => {
                const res1 = await generateText({
                  model: openai("gpt-4.1-nano"),
                  experimental_telemetry: AISDKExporter.getSettings({
                    runName: "How are you 1",
                  }),
                  messages: [
                    {
                      role: "user",
                      content: [
                        {
                          type: "text",
                          text: "What is up?",
                        },
                      ],
                    },
                  ],
                });
                aiSDKResponses.push(res1);

                const res2 = await generateText({
                  model: openai("gpt-4.1-nano"),
                  experimental_telemetry: AISDKExporter.getSettings({
                    runName: "How are you 2",
                  }),
                  messages: [
                    {
                      role: "user",
                      content: `How are you feeling?`,
                    },
                  ],
                });
                aiSDKResponses.push(res2);

                const res3 = await generateText({
                  model: openai("gpt-4.1-nano"),
                  experimental_telemetry: AISDKExporter.getSettings({
                    runName: "How are you 3",
                  }),
                  messages: [
                    {
                      role: "user",
                      content: `Generate a random tracking information, include order ID ${orderId}`,
                    },
                  ],
                });
                aiSDKResponses.push(res3);

                return res3.text;
              },
            }),
          },
          experimental_telemetry: AISDKExporter.getSettings({
            functionId: "functionId",
            metadata: { userId: "123", language: "english" },
          }),
          stopWhen: stepCountIs(10),
        });
        return mainResult;
      },
      { name: "AI SDK Agent Wrapper", id: runId }
    );

    await wrapper();

    await sdk.shutdown();

    await waitUntilRunFound(client, runId, true);

    const storedRun = await client.readRun(runId, { loadChildRuns: true });
    expect(storedRun.id).toEqual(runId);
    // OpenAI call, listOrders, OpenAI call, viewTrackingInformation
    expect(storedRun.child_runs?.[0]?.child_runs?.[3]?.name).toEqual(
      "viewTrackingInformation"
    );
    expect(
      storedRun.child_runs?.[0]?.child_runs?.[3]?.child_runs?.length
    ).toEqual(3);
    expect(
      storedRun.child_runs?.[0]?.child_runs?.[3]?.child_runs?.[0].name
    ).toEqual("How are you 1");
    expect(
      storedRun.child_runs?.[0]?.child_runs?.[3]?.child_runs?.[1].name
    ).toEqual("How are you 2");
    expect(
      storedRun.child_runs?.[0]?.child_runs?.[3]?.child_runs?.[2].name
    ).toEqual("How are you 3");
  });
});
