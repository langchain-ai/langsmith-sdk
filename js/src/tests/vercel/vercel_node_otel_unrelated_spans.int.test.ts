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
import { trace } from "@opentelemetry/api";
import { LangSmithOTLPSpanProcessor } from "../../experimental/otel/processor.js";

const client = new Client();

describe.skip("Legacy AI SDK tests", () => {
  test("nested generateText", async () => {
    const tracer = trace.getTracer("langsmith");

    await tracer.startActiveSpan("test-initialization", {}, async () => {
      await tracer.startActiveSpan("sdk-configuration", {}, async () => {
        await tracer.startActiveSpan(
          "preparing-span-processors",
          {},
          async () => {}
        );
        await tracer.startActiveSpan(
          "loading-instrumentations",
          {},
          async () => {}
        );
      });
    });

    const sdk = new NodeSDK({
      spanProcessors: [new LangSmithOTLPSpanProcessor(new AISDKExporter())],
      instrumentations: [getNodeAutoInstrumentations()],
    });

    await tracer.startActiveSpan("sdk-startup-sequence", {}, async () => {
      await tracer.startActiveSpan(
        "pre-startup-validation",
        {},
        async () => {}
      );
      sdk.start();
      await tracer.startActiveSpan(
        "post-startup-verification",
        {},
        async () => {}
      );
    });

    await tracer.startActiveSpan("uuid-generation-ceremony", {}, async () => {
      await tracer.startActiveSpan(
        "checking-entropy-levels",
        {},
        async () => {}
      );
      await tracer.startActiveSpan("validating-randomness", {}, async () => {});
    });
    const runId = uuid();

    await tracer.startActiveSpan(
      "response-array-initialization",
      {},
      async () => {
        await tracer.startActiveSpan(
          "allocating-memory-space",
          {},
          async () => {}
        );
      }
    );
    const aiSDKResponses: any[] = [];

    await tracer.startActiveSpan("wrapper-creation-process", {}, async () => {
      await tracer.startActiveSpan(
        "analyzing-traceable-options",
        {},
        async () => {}
      );
      await tracer.startActiveSpan(
        "preparing-execution-context",
        {},
        async () => {}
      );
    });

    const wrapper = traceable(
      async () => {
        return tracer.startActiveSpan("grandparent", {}, async () => {
          await tracer.startActiveSpan("thinking-deeply", {}, async () => {});
          await tracer.startActiveSpan(
            "contemplating-existence",
            {},
            async () => {}
          );
          return tracer.startActiveSpan("parent", {}, async () => {
            await tracer.startActiveSpan(
              "preparing-for-greatness",
              {},
              async () => {}
            );
            await tracer.startActiveSpan(
              "channeling-ai-energy",
              {},
              async () => {}
            );
            await tracer.startActiveSpan(
              "main-ai-invocation-ritual",
              {},
              async () => {
                await tracer.startActiveSpan(
                  "summoning-gpt-powers",
                  {},
                  async () => {}
                );
                await tracer.startActiveSpan(
                  "aligning-cosmic-forces",
                  {},
                  async () => {}
                );
                await tracer.startActiveSpan(
                  "whispering-to-tokens",
                  {},
                  async () => {}
                );
              }
            );
            return await generateText({
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
                  execute: async ({ userId }) => {
                    return tracer.startActiveSpan(
                      "listOrders-tool-execution",
                      {},
                      async () => {
                        await tracer.startActiveSpan(
                          "validating-user-id",
                          {},
                          async () => {}
                        );
                        await tracer.startActiveSpan(
                          "querying-order-database",
                          {},
                          async () => {}
                        );
                        await tracer.startActiveSpan(
                          "formatting-order-response",
                          {},
                          async () => {}
                        );
                        return `User ${userId} has the following orders: 1`;
                      }
                    );
                  },
                }),
                viewTrackingInformation: tool({
                  description: "view tracking information for a specific order",
                  inputSchema: z.object({ orderId: z.string() }),
                  execute: async ({ orderId }) => {
                    return tracer.startActiveSpan(
                      "viewTrackingInformation-tool-execution",
                      {},
                      async () => {
                        await tracer.startActiveSpan(
                          "parsing-order-id",
                          {},
                          async () => {}
                        );
                        await tracer.startActiveSpan(
                          "initializing-tracking-lookup",
                          {},
                          async () => {}
                        );

                        const res1 = await tracer.startActiveSpan(
                          "first-ai-call-preparation",
                          {},
                          async () => {
                            await tracer.startActiveSpan(
                              "model-selection-process",
                              {},
                              async () => {}
                            );
                            await tracer.startActiveSpan(
                              "building-message-context",
                              {},
                              async () => {}
                            );
                            await tracer.startActiveSpan(
                              "preparing-telemetry-settings",
                              {},
                              async () => {}
                            );
                            return await generateText({
                              model: openai("gpt-4.1-nano"),
                              experimental_telemetry: AISDKExporter.getSettings(
                                {
                                  runName: "How are you 1",
                                }
                              ),
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
                          }
                        );
                        await tracer.startActiveSpan(
                          "processing-first-response",
                          {},
                          async () => {}
                        );
                        aiSDKResponses.push(res1);

                        const res2 = await tracer.startActiveSpan(
                          "second-ai-call-setup",
                          {},
                          async () => {
                            await tracer.startActiveSpan(
                              "analyzing-conversation-context",
                              {},
                              async () => {}
                            );
                            await tracer.startActiveSpan(
                              "optimizing-prompt-structure",
                              {},
                              async () => {}
                            );
                            return await generateText({
                              model: openai("gpt-4.1-nano"),
                              experimental_telemetry: AISDKExporter.getSettings(
                                {
                                  runName: "How are you 2",
                                }
                              ),
                              messages: [
                                {
                                  role: "user",
                                  content: `How are you feeling?`,
                                },
                              ],
                            });
                          }
                        );
                        await tracer.startActiveSpan(
                          "second-response-analysis",
                          {},
                          async () => {}
                        );
                        aiSDKResponses.push(res2);

                        const res3 = await tracer.startActiveSpan(
                          "final-ai-call-orchestration",
                          {},
                          async () => {
                            await tracer.startActiveSpan(
                              "generating-tracking-data",
                              {},
                              async () => {}
                            );
                            await tracer.startActiveSpan(
                              "customizing-response-format",
                              {},
                              async () => {}
                            );
                            await tracer.startActiveSpan(
                              "injecting-order-metadata",
                              {},
                              async () => {}
                            );
                            return await generateText({
                              model: openai("gpt-4.1-nano"),
                              experimental_telemetry: AISDKExporter.getSettings(
                                {
                                  runName: "How are you 3",
                                }
                              ),
                              messages: [
                                {
                                  role: "user",
                                  content: `Generate a random tracking information, include order ID ${orderId}`,
                                },
                              ],
                            });
                          }
                        );
                        await tracer.startActiveSpan(
                          "final-response-processing",
                          {},
                          async () => {}
                        );
                        aiSDKResponses.push(res3);

                        await tracer.startActiveSpan(
                          "extracting-response-text",
                          {},
                          async () => {}
                        );
                        return res3.text;
                      }
                    );
                  },
                }),
              },
              experimental_telemetry: AISDKExporter.getSettings({
                functionId: "functionId",
                metadata: { userId: "123", language: "english" },
              }),
              stopWhen: stepCountIs(10),
            });
          });
        });
      },
      { name: "AI SDK Agent Wrapper", id: runId }
    );

    await tracer.startActiveSpan("wrapper-execution-phase", {}, async () => {
      await tracer.startActiveSpan(
        "invoking-the-chosen-one",
        {},
        async () => {}
      );
      await tracer.startActiveSpan(
        "crossing-dimensional-boundaries",
        {},
        async () => {}
      );
      await wrapper();
      await tracer.startActiveSpan(
        "celebrating-completion",
        {},
        async () => {}
      );
    });

    await tracer.startActiveSpan("sdk-shutdown-ceremony", {}, async () => {
      await tracer.startActiveSpan(
        "gracefully-terminating-processes",
        {},
        async () => {}
      );
      await tracer.startActiveSpan("cleaning-up-resources", {}, async () => {});
      await sdk.shutdown();
      await tracer.startActiveSpan("final-goodbye", {}, async () => {});
    });

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
