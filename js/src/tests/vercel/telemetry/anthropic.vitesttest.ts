/* eslint-disable @typescript-eslint/no-non-null-assertion */
import { describe, test, expect, vi } from "vitest";
import { anthropic } from "@ai-sdk/anthropic";
import * as ai from "ai";
import z from "zod";

import { createLangSmithTelemetry } from "../../../experimental/vercel/telemetry.js";
import { generateLongContext } from "../../utils.js";
import { getAssumedTreeFromCalls } from "../../utils/tree.js";
import { Client } from "../../../index.js";

const { tool, stepCountIs } = ai;

describe("anthropic telemetry", () => {
  test("telemetry generateText", async () => {
    const callSpy = vi.fn(fetch);
    const client = new Client({
      autoBatchTracing: false,
      fetchImplementation: callSpy,
    });

    const result = await ai.generateText({
      model: anthropic("claude-haiku-4-5"),
      messages: [
        {
          role: "user",
          content: "What are my orders? My user ID is 123. Always use tools.",
        },
      ],
      telemetry: { integrations: [createLangSmithTelemetry({ client })] },
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

    await client.awaitPendingTraceBatches();

    const runs = await getAssumedTreeFromCalls(callSpy.mock.calls, client);

    expect(runs).toMatchObject({
      edges: [
        ["anthropic.messages:0", "step 0:1"],
        ["step 0:1", "listOrders:2"],
        ["anthropic.messages:0", "step 1:3"],
      ],
      data: {
        "anthropic.messages:0": {
          run_type: "chain",
          inputs: {
            messages: [
              {
                role: "user",
                content:
                  "What are my orders? My user ID is 123. Always use tools.",
              },
            ],
            tools: ["listOrders"],
          },
          outputs: {
            content: expect.stringMatching(/order/i),
            finish_reason: "stop",
          },
        },
        "step 0:1": {
          run_type: "llm",
          inputs: {
            messages: [
              {
                role: "user",
                content:
                  "What are my orders? My user ID is 123. Always use tools.",
              },
            ],
          },
          outputs: {
            role: "assistant",
            content: "",
            tool_calls: expect.arrayContaining([
              expect.objectContaining({
                type: "function",
                function: { name: "listOrders" },
              }),
            ]),
            finish_reason: "tool-calls",
          },
        },
        "listOrders:2": {
          run_type: "tool",
          inputs: { userId: "123" },
          outputs: {},
        },
        "step 1:3": {
          run_type: "llm",
          inputs: {
            messages: expect.arrayContaining([
              {
                role: "user",
                content:
                  "What are my orders? My user ID is 123. Always use tools.",
              },
              expect.objectContaining({ role: "assistant" }),
              expect.objectContaining({ role: "tool" }),
            ]),
          },
          outputs: {
            role: "assistant",
            content: expect.stringMatching(/order/i),
            finish_reason: "stop",
          },
        },
      },
    });

    expect(
      runs.data["anthropic.messages:0"].extra?.metadata?.usage_metadata
        ?.total_tokens,
    ).toBeGreaterThan(0);
  });

  test("telemetry streamText", { timeout: 30_000 }, async () => {
    const callSpy = vi.fn(fetch);
    const client = new Client({
      autoBatchTracing: false,
      fetchImplementation: callSpy,
    });

    const streamResult = ai.streamText({
      model: anthropic("claude-haiku-4-5"),
      messages: [
        {
          role: "user",
          content: "What are my orders? My user ID is 123. Always use tools.",
        },
      ],
      telemetry: { integrations: [createLangSmithTelemetry({ client })] },
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
    for await (const chunk of streamResult.textStream) {
      total += chunk;
    }
    expect(total).toBeDefined();
    expect(total.length).toBeGreaterThan(0);

    await client.awaitPendingTraceBatches();

    const runs = await getAssumedTreeFromCalls(callSpy.mock.calls, client);

    expect(runs).toMatchObject({
      edges: [
        ["anthropic.messages:0", "step 0:1"],
        ["step 0:1", "listOrders:2"],
        ["anthropic.messages:0", "step 1:3"],
      ],
      data: {
        "anthropic.messages:0": {
          run_type: "chain",
          inputs: {
            messages: [
              {
                role: "user",
                content:
                  "What are my orders? My user ID is 123. Always use tools.",
              },
            ],
            tools: ["listOrders"],
          },
          outputs: {
            content: expect.stringMatching(/order/i),
            finish_reason: "stop",
          },
        },
        "step 0:1": {
          run_type: "llm",
          inputs: {
            messages: [
              {
                role: "user",
                content:
                  "What are my orders? My user ID is 123. Always use tools.",
              },
            ],
          },
          outputs: {
            role: "assistant",
            content: "",
            tool_calls: expect.arrayContaining([
              expect.objectContaining({
                type: "function",
                function: { name: "listOrders" },
              }),
            ]),
            finish_reason: "tool-calls",
          },
        },
        "listOrders:2": {
          run_type: "tool",
          inputs: { userId: "123" },
          outputs: {},
        },
        "step 1:3": {
          run_type: "llm",
          inputs: {
            messages: expect.arrayContaining([
              {
                role: "user",
                content:
                  "What are my orders? My user ID is 123. Always use tools.",
              },
              expect.objectContaining({ role: "assistant" }),
              expect.objectContaining({ role: "tool" }),
            ]),
          },
          outputs: {
            role: "assistant",
            content: expect.stringMatching(/order/i),
            finish_reason: "stop",
          },
        },
      },
    });
  });

  test("telemetry generateObject", async () => {
    const callSpy = vi.fn(fetch);
    const client = new Client({
      autoBatchTracing: false,
      fetchImplementation: callSpy,
    });

    const schema = z.object({ color: z.string() });
    const result = await ai.generateText({
      model: anthropic("claude-haiku-4-5"),
      messages: [
        {
          role: "user",
          content: "What color is the sky? Respond with JSON only.",
        },
      ],
      output: ai.Output.object({ schema }),
      telemetry: { integrations: [createLangSmithTelemetry({ client })] },
    });

    expect(result.output).toBeDefined();
    expect(schema.parse(result.output)).toBeDefined();

    await client.awaitPendingTraceBatches();

    const runs = await getAssumedTreeFromCalls(callSpy.mock.calls, client);

    expect(runs).toMatchObject({
      edges: [["anthropic.messages:0", "step 0:1"]],
      data: {
        "anthropic.messages:0": {
          run_type: "chain",
          inputs: {
            messages: [
              {
                role: "user",
                content: "What color is the sky? Respond with JSON only.",
              },
            ],
          },
          outputs: {
            content: expect.stringMatching(/"color"\s*:\s*"blue"/i),
            finish_reason: "stop",
          },
        },
        "step 0:1": {
          run_type: "llm",
          inputs: {
            messages: [
              {
                role: "user",
                content: "What color is the sky? Respond with JSON only.",
              },
            ],
          },
          outputs: {
            role: "assistant",
            content: expect.stringMatching(/"color"\s*:\s*"blue"/i),
            finish_reason: "stop",
          },
        },
      },
    });
  });

  test("telemetry streamObject via streamText with output", async () => {
    const callSpy = vi.fn(fetch);
    const client = new Client({
      autoBatchTracing: false,
      fetchImplementation: callSpy,
    });

    const schema = z.object({
      color: z.string(),
    });

    const streamResult = ai.streamText({
      model: anthropic("claude-haiku-4-5"),
      messages: [
        {
          role: "user",
          content: "What color is the sky? Respond with JSON only.",
        },
      ],
      output: ai.Output.object({ schema }),
      telemetry: { integrations: [createLangSmithTelemetry({ client })] },
    });

    const chunks = [];
    for await (const chunk of streamResult.partialOutputStream) {
      chunks.push(chunk);
    }
    expect(chunks.length).toBeGreaterThan(0);
    expect(schema.parse(chunks.at(-1))).toBeDefined();

    await client.awaitPendingTraceBatches();
    const runs = await getAssumedTreeFromCalls(callSpy.mock.calls, client);

    expect(runs).toMatchObject({
      edges: [["anthropic.messages:0", "step 0:1"]],
      data: {
        "anthropic.messages:0": {
          run_type: "chain",
          inputs: {
            messages: [
              {
                role: "user",
                content: "What color is the sky? Respond with JSON only.",
              },
            ],
          },
          outputs: {
            content: expect.stringMatching(/"color"\s*:\s*"blue"/i),
            finish_reason: "stop",
          },
        },
        "step 0:1": {
          run_type: "llm",
          inputs: {
            messages: [
              {
                role: "user",
                content: "What color is the sky? Respond with JSON only.",
              },
            ],
          },
          outputs: {
            role: "assistant",
            content: expect.stringMatching(/"color"\s*:\s*"blue"/i),
            finish_reason: "stop",
          },
        },
      },
    });
  });

  test("telemetry stream cancellation should finish spans cleanly", async () => {
    const callSpy = vi.fn(fetch);
    const client = new Client({
      autoBatchTracing: false,
      fetchImplementation: callSpy,
    });

    const abortController = new AbortController();

    const streamResult = ai.streamText({
      model: anthropic("claude-haiku-4-5"),
      messages: [
        {
          role: "user",
          content: "Tell me a long story about a cat.",
        },
      ],
      telemetry: { integrations: [createLangSmithTelemetry({ client })] },
      abortSignal: abortController.signal,
    });

    let i = 0;
    try {
      for await (const chunk of streamResult.fullStream) {
        if (chunk.type === "text-delta") {
          if (i++ > 5) {
            abortController.abort();
          }
        }
      }
    } catch {
      // Abort will throw
    }

    await client.awaitPendingTraceBatches();

    const runs = await getAssumedTreeFromCalls(callSpy.mock.calls, client);

    expect(runs).toMatchObject({
      edges: [["anthropic.messages:0", "step 0:1"]],
      data: {
        "anthropic.messages:0": {
          run_type: "chain",
          inputs: {
            messages: [
              {
                role: "user",
                content: "Tell me a long story about a cat.",
              },
            ],
          },
        },
        "step 0:1": {
          run_type: "llm",
          inputs: {
            messages: [
              {
                role: "user",
                content: "Tell me a long story about a cat.",
              },
            ],
          },
        },
      },
    });

    // Runs are created but not closed on abort (no end_time, no outputs)
    expect(runs.data["anthropic.messages:0"].end_time).toBeUndefined();
    expect(runs.data["step 0:1"].end_time).toBeUndefined();
  });

  // Skipped due to high token usage
  test.skip("anthropic cache read and write tokens", async () => {
    const callSpy = vi.fn(fetch);
    const client = new Client({
      autoBatchTracing: false,
      fetchImplementation: callSpy,
    });

    const errorMessage = generateLongContext();

    const res = await ai.generateText({
      model: anthropic("claude-3-5-haiku-20241022"),
      messages: [
        {
          role: "user",
          content: [
            { type: "text", text: "You are a JavaScript expert." },
            {
              type: "text",
              text: `Error message: ${errorMessage}`,
              providerOptions: {
                anthropic: { cacheControl: { type: "ephemeral" } },
              },
            },
            { type: "text", text: "Explain this error message briefly." },
          ],
        },
      ],
      telemetry: { integrations: [createLangSmithTelemetry({ client })] },
    });

    expect(res.text).toBeDefined();

    await client.awaitPendingTraceBatches();

    const runs = await getAssumedTreeFromCalls(callSpy.mock.calls, client);

    expect(runs).toMatchObject({
      edges: [["anthropic.messages:0", "step 0:1"]],
      data: {
        "anthropic.messages:0": { run_type: "chain" },
        "step 0:1": { run_type: "llm" },
      },
    });

    const stepData = runs.data["step 0:1"];
    expect(
      stepData.extra?.metadata?.usage_metadata?.input_tokens,
    ).toBeGreaterThan(0);
  });
});
