/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable no-process-env */
import { generateText, stepCountIs, tool } from "ai";
import { openai } from "@ai-sdk/openai";
import { z } from "zod";
import { v4 as uuidv4 } from "uuid";
import { trace } from "@opentelemetry/api";

import { Client } from "../../client.js";
import { traceable } from "../../traceable.js";
import { toArray, waitUntilRunFoundByMetaField } from "../utils.js";
import { getLangSmithEnvironmentVariable } from "../../utils/env.js";

// Initialize basic OTEL setup
import { initializeOTEL } from "../../experimental/otel/setup.js";

const { DEFAULT_LANGSMITH_SPAN_PROCESSOR } = initializeOTEL();

// Deprecated
describe.skip("Traceable OTEL Integration Tests", () => {
  beforeEach(() => {
    process.env.LANGCHAIN_TRACING = "true";
  });

  afterEach(() => {
    delete process.env.LANGSMITH_OTEL_ENABLED;
    delete process.env.LANGCHAIN_TRACING;
  });

  afterAll(async () => {
    await DEFAULT_LANGSMITH_SPAN_PROCESSOR.shutdown();
  });

  it("handles nested calls with OTEL context", async () => {
    process.env.LANGSMITH_OTEL_ENABLED = "true";

    const meta = uuidv4();
    const client = new Client();

    const childFunction = traceable(
      async (input: string) => {
        return { content: `child: ${input}`, role: "assistant" };
      },
      { name: "child-function", run_type: "llm", client }
    );

    const parentFunction = traceable(
      async (input: string) => {
        const childResult = await childFunction(input);
        return `parent: ${childResult.content}`;
      },
      { name: "parent-function", metadata: { hackyKey: meta } }
    );

    const result = await parentFunction("test");
    expect(result).toBe("parent: child: test");

    await client.awaitPendingTraceBatches();

    const projectName = getLangSmithEnvironmentVariable("PROJECT") ?? "default";
    await waitUntilRunFoundByMetaField(
      client,
      projectName,
      "hackyKey",
      meta,
      true
    );
    const storedRun = await toArray(
      client.listRuns({
        projectName,
        filter: `and(eq(metadata_key, "hackyKey"), eq(metadata_value, "${meta}"))`,
      })
    );
    expect(storedRun.length).toBe(1);
    const runWithChildren = await client.readRun(storedRun[0].id, {
      loadChildRuns: true,
    });
    expect(runWithChildren.child_runs?.length).toBe(1);
    expect(runWithChildren.child_runs?.[0].name).toBe("child-function");
  });

  it("traces as root even when nested within an irrelevant span", async () => {
    process.env.LANGSMITH_OTEL_ENABLED = "true";

    const meta = uuidv4();
    const client = new Client();

    const tracer = trace.getTracer("irrelevant-span");

    const result = await tracer.startActiveSpan("irrelevant-span", () => {
      const childFunction = traceable(
        async (input: string) => {
          return { content: `child: ${input}`, role: "assistant" };
        },
        { name: "child-function", run_type: "llm", client }
      );

      const parentFunction = traceable(
        async (input: string) => {
          const childResult = await childFunction(input);
          return `parent: ${childResult.content}`;
        },
        { name: "parent-function", metadata: { hackyKey: meta } }
      );

      trace.getActiveSpan()?.end(new Date());

      return parentFunction("test");
    });

    expect(result).toBe("parent: child: test");

    await client.awaitPendingTraceBatches();

    const projectName = getLangSmithEnvironmentVariable("PROJECT") ?? "default";
    await waitUntilRunFoundByMetaField(
      client,
      projectName,
      "hackyKey",
      meta,
      true
    );
    const storedRun = await toArray(
      client.listRuns({
        projectName,
        filter: `and(eq(metadata_key, "hackyKey"), eq(metadata_value, "${meta}"))`,
      })
    );
    expect(storedRun.length).toBe(1);
    expect(storedRun[0].trace_id).toBe(storedRun[0].id);
    const runWithChildren = await client.readRun(storedRun[0].id, {
      loadChildRuns: true,
    });
    expect(runWithChildren.child_runs?.length).toBe(1);
    expect(runWithChildren.child_runs?.[0].name).toBe("child-function");
  });

  it("works with AI SDK", async () => {
    process.env.LANGSMITH_OTEL_ENABLED = "true";

    const meta = uuidv4();
    const client = new Client();
    const wrappedText = traceable(
      async (content: string) => {
        const { text } = await generateText({
          model: openai("gpt-4.1-nano"),
          messages: [{ role: "user", content }],
          tools: {
            listOrders: tool({
              description: "list all orders",
              inputSchema: z.object({ userId: z.string() }),
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
              inputSchema: z.object({ orderId: z.string() }),
              execute: async ({ orderId }) =>
                `Here is the tracking information for ${orderId}`,
            }),
          },
          experimental_telemetry: {
            isEnabled: true,
          },
          stopWhen: stepCountIs(10),
        });

        return { text };
      },
      { name: "parentTraceable", metadata: { hackyKey: meta }, client }
    );

    await wrappedText(
      "What are my orders and where are they? My user ID is 123. Use available tools."
    );
    await client.awaitPendingTraceBatches();
    const projectName = getLangSmithEnvironmentVariable("PROJECT") ?? "default";
    await waitUntilRunFoundByMetaField(
      client,
      projectName,
      "hackyKey",
      meta,
      true
    );
    const storedRun = await toArray(
      client.listRuns({
        projectName,
        filter: `and(eq(metadata_key, "hackyKey"), eq(metadata_value, "${meta}"))`,
      })
    );
    expect(storedRun.length).toBe(1);
    const runWithChildren = await client.readRun(storedRun[0].id, {
      loadChildRuns: true,
    });
    expect(runWithChildren.child_runs?.length).toBe(1);
    expect(runWithChildren.child_runs?.[0].name).toBe("ai.generateText");
    expect(runWithChildren.child_runs?.[0].child_runs?.[0].name).toBe(
      "ai.generateText.doGenerate"
    );
    const listToolRuns = runWithChildren.child_runs?.[0].child_runs?.filter(
      (run) => run.name === "listOrders"
    );
    expect(listToolRuns?.length).toBeGreaterThan(0);
    expect(listToolRuns?.[0].name).toBe("listOrders");
    expect(listToolRuns?.[0].child_runs?.[0].name).toBe("getOrderNumber");
  });
});
