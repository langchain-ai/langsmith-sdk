import { NodeSDK } from "@opentelemetry/sdk-node";
import { getNodeAutoInstrumentations } from "@opentelemetry/auto-instrumentations-node";
import { v4 as uuid } from "uuid";
import { generateText, tool } from "ai";
import { openai } from "@ai-sdk/openai";
import { z } from "zod";

import * as fs from "fs";
import { fileURLToPath } from "url";
import path from "path";

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
            parameters: z.object({ userId: z.string() }),
            execute: async ({ userId }) =>
              `User ${userId} has the following orders: 1`,
          }),
          viewTrackingInformation: tool({
            description: "view tracking information for a specific order",
            parameters: z.object({ orderId: z.string() }),
            execute: async () => {
              const pathname = path.join(
                path.dirname(fileURLToPath(import.meta.url)),
                "test_data",
                "parrot-icon.png"
              );
              const buffer = fs.readFileSync(pathname);
              await generateText({
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
                        text: "What is this?",
                      },
                      // Node Buffer
                      {
                        type: "image",
                        image: Buffer.from(buffer),
                      },
                      // ArrayBuffer
                      {
                        type: "image",
                        image: buffer.buffer.slice(
                          buffer.byteOffset,
                          buffer.byteOffset + buffer.byteLength
                        ),
                      },
                      {
                        type: "image",
                        image: new Uint8Array(buffer),
                      },
                      {
                        type: "image",
                        image: buffer.toString("base64"),
                      },
                      {
                        type: "image",
                        image:
                          "https://png.pngtree.com/png-vector/20221025/ourmid/pngtree-navigation-bar-3d-search-url-png-image_6360655.png",
                      },
                    ],
                  },
                ],
              });
              await generateText({
                model: openai("gpt-4.1-mini"),
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

  const storedRun = await client.readRun(runId, { loadChildRuns: true });
  expect(storedRun.id).toEqual(runId);
  // OpenAI call, listOrders, OpenAI call, viewTrackingInformation
  expect(storedRun.child_runs?.[0]?.child_runs?.[3]?.name).toEqual(
    "viewTrackingInformation"
  );
  expect(
    storedRun.child_runs?.[0]?.child_runs?.[3]?.child_runs?.length
  ).toEqual(2);
  expect(
    storedRun.child_runs?.[0]?.child_runs?.[3]?.child_runs?.[0].name
  ).toEqual("How are you 1");
  expect(
    storedRun.child_runs?.[0]?.child_runs?.[3]?.child_runs?.[1].name
  ).toEqual("How are you 2");
  expect(
    storedRun.child_runs?.[0]?.child_runs?.[3]?.child_runs?.[0].child_runs
      ?.length
  ).toEqual(1);
  expect(
    storedRun.child_runs?.[0]?.child_runs?.[3]?.child_runs?.[1].child_runs
      ?.length
  ).toEqual(1);
});
