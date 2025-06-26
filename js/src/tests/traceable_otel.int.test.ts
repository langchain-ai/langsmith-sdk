/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable no-process-env */
import { generateText, tool } from "ai";
import { openai } from "@ai-sdk/openai";
import { z } from "zod";

import { traceable } from "../traceable.js";
import { __version__ } from "../index.js";

describe("Traceable OTEL Integration Tests", () => {
  beforeEach(() => {
    process.env.LANGCHAIN_TRACING = "true";
  });

  afterEach(() => {
    delete process.env.OTEL_ENABLED;
    delete process.env.LANGCHAIN_TRACING;
  });

  it("works gracefully when OTEL_ENABLED is true but packages not available", async () => {
    process.env.OTEL_ENABLED = "true";

    const testFunction = traceable(
      (input: string) => {
        return `result: ${input}`;
      },
      { name: "test-function" }
    );

    // Should work even if OTEL packages aren't installed
    const result = await testFunction("test");
    expect(result).toBe("result: test");
  });

  it("handles nested calls with OTEL context", async () => {
    process.env.OTEL_ENABLED = "true";

    const childFunction = traceable(
      async (input: string) => {
        return { content: `child: ${input}`, role: "assistant" };
      },
      { name: "child-function", run_type: "llm" }
    );

    const parentFunction = traceable(
      async (input: string) => {
        const childResult = await childFunction(input);
        return `parent: ${childResult.content}`;
      },
      { name: "parent-function" }
    );

    const result = await parentFunction("test");
    await new Promise((resolve) => setTimeout(resolve, 5000));
    expect(result).toBe("parent: child: test");
  });

  it.only("works with AI SDK", async () => {
    process.env.OTEL_ENABLED = "true";
    const wrappedText = traceable(
      async (content: string) => {
        const { text } = await generateText({
          model: openai("gpt-4.1-nano"),
          messages: [{ role: "user", content }],
          tools: {
            listOrders: tool({
              description: "list all orders",
              parameters: z.object({ userId: z.string() }),
              execute: async ({ userId }) => {
                const getOrderNumber = traceable(
                  async () => {
                    return "1234";
                  },
                  { name: "getOrderNumber" }
                );
                const orderNumber = await getOrderNumber();
                return `User ${userId} has the following orders: ${orderNumber}`;
              },
            }),
            viewTrackingInformation: tool({
              description: "view tracking information for a specific order",
              parameters: z.object({ orderId: z.string() }),
              execute: async ({ orderId }) =>
                `Here is the tracking information for ${orderId}`,
            }),
          },
          experimental_telemetry: {
            isEnabled: true,
          },
          maxSteps: 10,
        });

        // const foo = traceable(
        //   async () => {
        //     return "bar";
        //   },
        //   { name: "foo" }
        // );

        // await foo();

        return { text };
      },
      { name: "parentTraceable" }
    );

    const result = await wrappedText(
      "What are my orders and where are they? My user ID is 123. Use available tools."
    );
    console.log(result);
    await new Promise((resolve) => setTimeout(resolve, 5000));
    // await waitUntilRunFound(client, runId, true);
    // const storedRun = await client.readRun(runId);
    // expect(storedRun.outputs).toEqual(result);
  });
});
