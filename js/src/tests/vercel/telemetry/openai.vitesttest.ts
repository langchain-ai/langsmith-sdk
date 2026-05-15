/* eslint-disable @typescript-eslint/no-non-null-assertion */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { openai } from "@ai-sdk/openai";
import * as ai from "ai";
import z from "zod";
import { describe, test, expect, vi } from "vitest";

import { createLangSmithTelemetry } from "../../../experimental/vercel/telemetry.js";
import { getAssumedTreeFromCalls } from "../../utils/tree.js";
import { traceable } from "../../../traceable.js";
import { Client } from "../../../index.js";

const { tool, stepCountIs } = ai;

type RunsTree = Awaited<ReturnType<typeof getAssumedTreeFromCalls>>;

function telemetryChainRoot(runs: RunsTree) {
  const entry = Object.entries(runs.data).find(
    ([, r]) =>
      r.run_type === "chain" &&
      r.extra?.metadata?.ls_integration === "vercel-ai-sdk-telemetry",
  );
  expect(entry).toBeDefined();
  return entry![0];
}

function llmStepKey(runs: RunsTree, stepNumber: number) {
  const entry = Object.entries(runs.data).find(
    ([, r]) =>
      r.run_type === "llm" && r.extra?.metadata?.step_number === stepNumber,
  );
  expect(entry).toBeDefined();
  return entry![0];
}

function toolRunKey(runs: RunsTree, toolName: string) {
  const entry = Object.entries(runs.data).find(
    ([, r]) => r.run_type === "tool" && r.name === toolName,
  );
  expect(entry).toBeDefined();
  return entry![0];
}

function outerTraceableKey(runs: RunsTree) {
  const entry = Object.entries(runs.data).find(
    ([, r]) => r.name === "outer-traceable",
  );
  expect(entry).toBeDefined();
  return entry![0];
}

describe("openai telemetry", () => {
  test("telemetry generateText basic", { timeout: 30_000 }, async () => {
    const callSpy = vi.fn(fetch);
    const client = new Client({
      autoBatchTracing: false,
      fetchImplementation: callSpy,
    });

    const model = openai("gpt-5-nano");
    const userMessage = "What color is the sky? Answer in one word: blue.";

    const result = await ai.generateText({
      model,
      messages: [{ role: "user", content: userMessage }],
      telemetry: { integrations: [createLangSmithTelemetry({ client })] },
    });

    expect(result.text).toBeDefined();
    expect(result.text.length).toBeGreaterThan(0);

    await client.awaitPendingTraceBatches();

    const runs = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
    const rootKey = telemetryChainRoot(runs);
    const step0Key = llmStepKey(runs, 0);

    expect(runs.edges).toEqual(expect.arrayContaining([[rootKey, step0Key]]));

    expect(runs).toMatchObject({
      data: {
        [rootKey]: {
          run_type: "chain",
          inputs: {
            messages: [{ role: "user", content: userMessage }],
          },
          outputs: {
            content: expect.stringMatching(/blue/i),
            finish_reason: "stop",
          },
        },
        [step0Key]: {
          run_type: "llm",
          inputs: {
            messages: [{ role: "user", content: userMessage }],
          },
          outputs: {
            role: "assistant",
            content: expect.stringMatching(/blue/i),
            finish_reason: "stop",
          },
        },
      },
    });

    expect(
      runs.data[rootKey].extra?.metadata?.usage_metadata?.total_tokens,
    ).toBeGreaterThan(0);
    expect(
      runs.data[step0Key].extra?.metadata?.usage_metadata?.input_tokens,
    ).toBeGreaterThan(0);
    expect(
      runs.data[step0Key].extra?.metadata?.usage_metadata?.output_tokens,
    ).toBeGreaterThan(0);
  });

  test("telemetry generateText with tools", { timeout: 30_000 }, async () => {
    const callSpy = vi.fn(fetch);
    const client = new Client({
      autoBatchTracing: false,
      fetchImplementation: callSpy,
    });

    const model = openai("gpt-5-nano");
    const userContent =
      "What are my orders? My user ID is 123. Always use tools.";
    const tools = {
      listOrders: tool({
        description: "list all orders",
        inputSchema: z.object({ userId: z.string() }),
        execute: async ({ userId }) =>
          `User ${userId} has the following orders: 1`,
      }),
    };

    const result = await ai.generateText({
      model,
      messages: [{ role: "user", content: userContent }],
      tools,
      stopWhen: stepCountIs(10),
      telemetry: { integrations: [createLangSmithTelemetry({ client })] },
    });

    expect(result.text).toBeDefined();
    expect(result.text.length).toBeGreaterThan(0);

    await client.awaitPendingTraceBatches();

    const runs = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
    const rootKey = telemetryChainRoot(runs);
    const step0Key = llmStepKey(runs, 0);
    const step1Key = llmStepKey(runs, 1);
    const ordersToolKey = toolRunKey(runs, "listOrders");

    expect(runs.edges).toEqual(
      expect.arrayContaining([
        [rootKey, step0Key],
        [step0Key, ordersToolKey],
        [rootKey, step1Key],
      ]),
    );

    expect(runs).toMatchObject({
      data: {
        [rootKey]: {
          run_type: "chain",
          inputs: {
            messages: [{ role: "user", content: userContent }],
            tools: ["listOrders"],
          },
          outputs: {
            content: expect.stringMatching(/order/i),
            finish_reason: "stop",
          },
        },
        [step0Key]: {
          run_type: "llm",
          inputs: {
            messages: [{ role: "user", content: userContent }],
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
        [ordersToolKey]: {
          run_type: "tool",
          inputs: { userId: "123" },
          outputs: {},
        },
        [step1Key]: {
          run_type: "llm",
          inputs: {
            messages: expect.arrayContaining([
              { role: "user", content: userContent },
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
      runs.data[rootKey].extra?.metadata?.usage_metadata?.total_tokens,
    ).toBeGreaterThan(0);
  });

  test("telemetry streamText", { timeout: 30_000 }, async () => {
    const callSpy = vi.fn(fetch);
    const client = new Client({
      autoBatchTracing: false,
      fetchImplementation: callSpy,
    });

    const userContent =
      "What are my orders? My user ID is 123. Always use tools.";
    const streamResult = ai.streamText({
      model: openai("gpt-5-nano"),
      messages: [{ role: "user", content: userContent }],
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
    expect(total.length).toBeGreaterThan(0);

    await client.awaitPendingTraceBatches();

    const runs = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
    const rootKey = telemetryChainRoot(runs);
    const step0Key = llmStepKey(runs, 0);
    const step1Key = llmStepKey(runs, 1);
    const ordersToolKey = toolRunKey(runs, "listOrders");

    expect(runs.edges).toEqual(
      expect.arrayContaining([
        [rootKey, step0Key],
        [step0Key, ordersToolKey],
        [rootKey, step1Key],
      ]),
    );

    expect(runs).toMatchObject({
      data: {
        [rootKey]: {
          run_type: "chain",
          inputs: {
            messages: [{ role: "user", content: userContent }],
            tools: ["listOrders"],
          },
          outputs: {
            content: expect.stringMatching(/order/i),
            finish_reason: "stop",
          },
        },
        [step0Key]: {
          run_type: "llm",
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
        [ordersToolKey]: {
          run_type: "tool",
          inputs: { userId: "123" },
          outputs: {},
        },
        [step1Key]: {
          run_type: "llm",
          outputs: {
            role: "assistant",
            content: expect.stringMatching(/order/i),
            finish_reason: "stop",
          },
        },
      },
    });
  });

  test(
    "telemetry generateText with flex service tier",
    { timeout: 30_000 },
    async () => {
      const callSpy = vi.fn(fetch);
      const client = new Client({
        autoBatchTracing: false,
        fetchImplementation: callSpy,
      });

      const model = openai("gpt-5-mini");
      const userMessage = "What color is the sky in one word: blue.";

      const result = await ai.generateText({
        model,
        messages: [{ role: "user", content: userMessage }],
        providerOptions: {
          openai: {
            serviceTier: "flex",
          },
        },
        telemetry: { integrations: [createLangSmithTelemetry({ client })] },
      });

      expect(result.text.length).toBeGreaterThan(0);

      await client.awaitPendingTraceBatches();

      const runs = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
      const rootKey = telemetryChainRoot(runs);
      const step0Key = llmStepKey(runs, 0);

      expect(runs.edges).toEqual(expect.arrayContaining([[rootKey, step0Key]]));

      expect(runs).toMatchObject({
        data: {
          [rootKey]: {
            run_type: "chain",
            inputs: {
              messages: [{ role: "user", content: userMessage }],
            },
            outputs: {
              content: expect.stringMatching(/blue/i),
              finish_reason: "stop",
            },
          },
          [step0Key]: {
            run_type: "llm",
            outputs: {
              role: "assistant",
              content: expect.stringMatching(/blue/i),
              finish_reason: "stop",
            },
          },
        },
      });

      const usageMetadata = runs.data[step0Key].extra?.metadata?.usage_metadata;
      expect(usageMetadata?.input_tokens).toBeGreaterThan(0);
      expect(usageMetadata?.output_tokens).toBeGreaterThan(0);
    },
  );

  test("telemetry generateObject", { timeout: 30_000 }, async () => {
    const callSpy = vi.fn(fetch);
    const client = new Client({
      autoBatchTracing: false,
      fetchImplementation: callSpy,
    });

    const schema = z.object({
      color: z.string(),
    });
    const output = ai.Output.object({ schema });
    const model = openai("gpt-5-nano");
    const userMessage = "What color is the sky? Respond with JSON only.";

    const result = await ai.generateText({
      model,
      messages: [{ role: "user", content: userMessage }],
      output,
      telemetry: { integrations: [createLangSmithTelemetry({ client })] },
    });

    expect(result.output).toBeDefined();
    expect(schema.parse(result.output)).toBeDefined();

    await client.awaitPendingTraceBatches();

    const runs = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
    const rootKey = telemetryChainRoot(runs);
    const step0Key = llmStepKey(runs, 0);

    expect(runs.edges).toEqual(expect.arrayContaining([[rootKey, step0Key]]));

    expect(runs).toMatchObject({
      data: {
        [rootKey]: {
          run_type: "chain",
          inputs: {
            messages: [{ role: "user", content: userMessage }],
          },
          outputs: {
            content: expect.stringMatching(/"color"\s*:\s*"blue"/i),
            finish_reason: "stop",
          },
        },
        [step0Key]: {
          run_type: "llm",
          inputs: {
            messages: [{ role: "user", content: userMessage }],
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

  test(
    "telemetry streamObject via streamText with output",
    { timeout: 30_000 },
    async () => {
      const callSpy = vi.fn(fetch);
      const client = new Client({
        autoBatchTracing: false,
        fetchImplementation: callSpy,
      });

      const schema = z.object({ color: z.string() });
      const userMessage = "What color is the sky? Respond with JSON only.";

      const streamResult = ai.streamText({
        model: openai("gpt-5-nano"),
        messages: [{ role: "user", content: userMessage }],
        output: ai.Output.object({ schema }),
        telemetry: { integrations: [createLangSmithTelemetry({ client })] },
      });

      const chunks: unknown[] = [];
      for await (const chunk of streamResult.partialOutputStream) {
        chunks.push(chunk);
      }
      expect(chunks.length).toBeGreaterThan(0);
      expect(schema.parse(chunks.at(-1))).toBeDefined();

      await client.awaitPendingTraceBatches();
      const runs = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
      const rootKey = telemetryChainRoot(runs);
      const step0Key = llmStepKey(runs, 0);

      expect(runs.edges).toEqual(expect.arrayContaining([[rootKey, step0Key]]));

      expect(runs).toMatchObject({
        data: {
          [rootKey]: {
            run_type: "chain",
            inputs: {
              messages: [{ role: "user", content: userMessage }],
            },
            outputs: {
              content: expect.stringMatching(/"color"\s*:\s*"blue"/i),
              finish_reason: "stop",
            },
          },
          [step0Key]: {
            run_type: "llm",
            inputs: {
              messages: [{ role: "user", content: userMessage }],
            },
            outputs: {
              role: "assistant",
              content: expect.stringMatching(/"color"\s*:\s*"blue"/i),
              finish_reason: "stop",
            },
          },
        },
      });
    },
  );

  test(
    "telemetry stream cancellation should finish spans cleanly",
    { timeout: 30_000 },
    async () => {
      const callSpy = vi.fn(fetch);
      const client = new Client({
        autoBatchTracing: false,
        fetchImplementation: callSpy,
      });

      const abortController = new AbortController();
      const userMessage = "Tell me a long story about a cat.";

      const streamResult = ai.streamText({
        model: openai("gpt-5-nano"),
        messages: [{ role: "user", content: userMessage }],
        telemetry: { integrations: [createLangSmithTelemetry({ client })] },
        abortSignal: abortController.signal,
      });

      let abortedAfterDeltas = false;
      let i = 0;
      try {
        for await (const chunk of streamResult.fullStream) {
          if (chunk.type === "text-delta") {
            if (i++ > 5) {
              abortController.abort();
              abortedAfterDeltas = true;
            }
          }
        }
      } catch {
        // Abort may throw
      }

      await client.awaitPendingTraceBatches();

      const runs = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
      const rootKey = telemetryChainRoot(runs);
      const step0Key = llmStepKey(runs, 0);

      expect(runs.edges).toEqual(expect.arrayContaining([[rootKey, step0Key]]));

      expect(runs).toMatchObject({
        data: {
          [rootKey]: {
            run_type: "chain",
            inputs: {
              messages: [{ role: "user", content: userMessage }],
            },
          },
          [step0Key]: {
            run_type: "llm",
            inputs: {
              messages: [{ role: "user", content: userMessage }],
            },
          },
        },
      });

      // Same as Anthropic: mid-stream abort leaves root/step open. If the request
      // errors before any deltas (or the provider ends the run), spans may close.
      if (abortedAfterDeltas) {
        expect(runs.data[rootKey].end_time).toBeUndefined();
        expect(runs.data[step0Key].end_time).toBeUndefined();
      }
    },
  );

  test(
    "telemetry processInputs and processOutputs",
    { timeout: 30_000 },
    async () => {
      const callSpy = vi.fn(fetch);
      const client = new Client({
        autoBatchTracing: false,
        fetchImplementation: callSpy,
      });

      const integration = createLangSmithTelemetry({
        client,
        processInputs: (inputs) => ({
          ...inputs,
          prompt: "REDACTED",
          messages: (inputs.messages ?? []).map((m: any) => ({
            ...m,
            content: "REDACTED",
          })),
        }),
        processOutputs: (outputs) => ({
          ...outputs,
          content: "REDACTED",
        }),
        processChildLLMRunInputs: (inputs) => ({
          messages: (inputs.messages ?? []).map((m: any) => ({
            ...m,
            content: "REDACTED CHILD INPUTS",
          })),
        }),
        processChildLLMRunOutputs: (outputs) => ({
          ...outputs,
          content: "REDACTED CHILD OUTPUTS",
          role: "assistant",
        }),
      });

      const model = openai("gpt-5-nano");

      const result = await ai.generateText({
        model,
        prompt: "What is the capital of France? Answer: Paris.",
        telemetry: { integrations: [integration] },
      });

      expect(result.text).not.toContain("REDACTED");

      await client.awaitPendingTraceBatches();

      const runs = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
      const rootKey = telemetryChainRoot(runs);
      const step0Key = llmStepKey(runs, 0);

      expect(runs.data[rootKey].inputs?.prompt).toBe("REDACTED");
      expect(runs.data[rootKey].outputs?.content).toBe("REDACTED");

      expect(runs.data[step0Key].inputs?.messages?.[0]?.content).toBe(
        "REDACTED CHILD INPUTS",
      );
      expect(runs.data[step0Key].outputs?.content).toBe(
        "REDACTED CHILD OUTPUTS",
      );
    },
  );

  test(
    "telemetry nested under traceable parent",
    { timeout: 30_000 },
    async () => {
      const callSpy = vi.fn(fetch);
      const client = new Client({
        autoBatchTracing: false,
        fetchImplementation: callSpy,
      });

      const model = openai("gpt-5-nano");
      const prompt = "What color is the sky? One word: blue.";

      const outerFn = traceable(
        async () => {
          const result = await ai.generateText({
            model,
            prompt,
            telemetry: { integrations: [createLangSmithTelemetry({ client })] },
          });
          return result.text;
        },
        { name: "outer-traceable", client },
      );

      const text = await outerFn();
      expect(text.length).toBeGreaterThan(0);

      await client.awaitPendingTraceBatches();

      const runs = await getAssumedTreeFromCalls(callSpy.mock.calls, client);

      const outerKey = outerTraceableKey(runs);
      const telemetryRoot = Object.values(runs.data).find(
        (r) =>
          r.run_type === "chain" &&
          r.extra?.metadata?.ls_integration === "vercel-ai-sdk-telemetry",
      );

      expect(telemetryRoot).toBeDefined();
      expect(telemetryRoot!.parent_run_id).toBe(runs.data[outerKey].id);
      expect(telemetryRoot!.trace_id).toBe(runs.data[outerKey].trace_id);

      expect(runs.edges).toEqual(
        expect.arrayContaining([[outerKey, telemetryChainRoot(runs)]]),
      );
    },
  );

  test(
    "telemetry tool with nested traceable (sub-agent pattern)",
    { timeout: 30_000 },
    async () => {
      const callSpy = vi.fn(fetch);
      const client = new Client({
        autoBatchTracing: false,
        fetchImplementation: callSpy,
      });

      const integration = createLangSmithTelemetry({
        client,
      });
      // Manual lifecycle — use loose payloads (SDK events are wider than tests need).
      const drive = integration as any;

      const model = openai("gpt-5-nano");

      const subAgent = traceable(
        async (query: string) => {
          return `Sub-agent result for: ${query}`;
        },
        {
          name: "sub-agent",
          run_type: "chain",
          client: client as any,
        },
      );

      drive.onStart?.({
        model,
        prompt: "Use the research tool",
        tools: { research: {} },
      });

      drive.onStepStart?.({
        stepNumber: 0,
        messages: [{ role: "user", content: "Use the research tool" }],
      });

      drive.onToolExecutionStart?.({
        callId: "call-1",
        messages: [],
        toolCall: {
          type: "tool-call",
          toolCallId: "tc-1",
          toolName: "research",
          input: { query: "AI trends" },
        },
        toolContext: undefined,
      });

      const toolResult = await integration.executeTool!({
        callId: "call-1",
        toolCallId: "tc-1",
        execute: () => subAgent("AI trends"),
      });

      expect(toolResult).toBe("Sub-agent result for: AI trends");

      await drive.onStepFinish?.({
        stepNumber: 0,
        text: "",
        toolCalls: [
          {
            toolCallId: "tc-1",
            toolName: "research",
            args: { query: "AI trends" },
          },
        ],
        usage: {
          inputTokens: { total: 10, noCache: 10, cacheRead: 0, cacheWrite: 0 },
          outputTokens: { total: 5, text: 0, reasoning: 0 },
          totalTokens: 15,
        },
        finishReason: "tool-calls",
      });

      drive.onStepStart?.({
        stepNumber: 1,
        messages: [{ role: "user", content: "Use the research tool" }],
      });

      await drive.onStepFinish?.({
        stepNumber: 1,
        text: "Based on the research, AI is trending.",
        usage: {
          inputTokens: { total: 20, noCache: 20, cacheRead: 0, cacheWrite: 0 },
          outputTokens: { total: 10, text: 10, reasoning: 0 },
          totalTokens: 30,
        },
        finishReason: "stop",
      });

      await drive.onEnd?.({
        text: "Based on the research, AI is trending.",
        usage: {
          inputTokens: { total: 30, noCache: 30, cacheRead: 0, cacheWrite: 0 },
          outputTokens: { total: 15, text: 10, reasoning: 0 },
          totalTokens: 45,
        },
        totalUsage: {
          inputTokens: { total: 30, noCache: 30, cacheRead: 0, cacheWrite: 0 },
          outputTokens: { total: 15, text: 10, reasoning: 0 },
          totalTokens: 45,
        },
        finishReason: "stop",
        steps: [],
      });

      await client.awaitPendingTraceBatches();

      const runs = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
      const rootKey = telemetryChainRoot(runs);
      const step0Key = llmStepKey(runs, 0);
      const step1Key = llmStepKey(runs, 1);
      const researchToolKey = toolRunKey(runs, "research");

      const subAgentRun = Object.values(runs.data).find(
        (r) => r.name === "sub-agent",
      );
      expect(subAgentRun).toBeDefined();

      expect(runs.edges).toEqual(
        expect.arrayContaining([
          [rootKey, step0Key],
          [step0Key, researchToolKey],
          [rootKey, step1Key],
        ]),
      );

      expect(subAgentRun!.parent_run_id).toBe(runs.data[researchToolKey].id);
      expect(runs.data[researchToolKey].trace_id).toBe(
        runs.data[rootKey].trace_id,
      );
      expect(subAgentRun!.trace_id).toBe(runs.data[rootKey].trace_id);

      expect(String(runs.data[rootKey].outputs?.content)).toMatch(
        /trending|research/i,
      );
    },
  );

  test("telemetry error handling", { timeout: 30_000 }, async () => {
    const callSpy = vi.fn(fetch);
    const client = new Client({
      autoBatchTracing: false,
      fetchImplementation: callSpy,
    });

    const integration = createLangSmithTelemetry({ client });
    const drive = integration as any;

    const model = openai("gpt-5-nano");

    drive.onStart?.({
      model,
      prompt: "This will fail",
    });

    drive.onStepStart?.({
      stepNumber: 0,
      messages: [{ role: "user", content: "This will fail" }],
    });

    await integration.onError?.(new Error("TOTALLY EXPECTED MOCK ERROR"));

    await client.awaitPendingTraceBatches();

    const runs = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
    const errorRuns = Object.values(runs.data).filter((r) => r.error);

    expect(errorRuns.length).toBe(2);
    expect(String(errorRuns[0].error)).toContain("TOTALLY EXPECTED MOCK ERROR");
    expect(String(errorRuns[1].error)).toContain("TOTALLY EXPECTED MOCK ERROR");
  });

  test(
    "telemetry reuse across sequential generateText calls",
    { timeout: 30_000 },
    async () => {
      const callSpy = vi.fn(fetch);
      const client = new Client({
        autoBatchTracing: false,
        fetchImplementation: callSpy,
      });

      const integration = createLangSmithTelemetry({ client });

      const model = openai("gpt-5-nano");

      const result1 = await ai.generateText({
        model,
        prompt: "What color is the sky? One word: blue.",
        telemetry: { integrations: [integration] },
      });

      expect(result1.text.length).toBeGreaterThan(0);

      await client.awaitPendingTraceBatches();

      const firstRuns = await getAssumedTreeFromCalls(
        callSpy.mock.calls,
        client,
      );
      const firstRoot = Object.values(firstRuns.data).find(
        (r) =>
          r.run_type === "chain" &&
          r.extra?.metadata?.ls_integration === "vercel-ai-sdk-telemetry",
      );
      expect(firstRoot).toBeDefined();

      const firstPosts = callSpy.mock.calls.filter(
        (call) => (call[1] as { method?: string })?.method === "POST",
      );
      expect(firstPosts.length).toBe(2);

      callSpy.mockClear();

      const result2 = await ai.generateText({
        model,
        prompt: "What color is grass? One word: green.",
        telemetry: { integrations: [integration] },
      });

      expect(result2.text.length).toBeGreaterThan(0);

      await client.awaitPendingTraceBatches();

      const secondRuns = await getAssumedTreeFromCalls(
        callSpy.mock.calls,
        client,
      );
      const secondRoot = Object.values(secondRuns.data).find(
        (r) =>
          r.run_type === "chain" &&
          r.extra?.metadata?.ls_integration === "vercel-ai-sdk-telemetry",
      );
      expect(secondRoot).toBeDefined();

      expect(secondRoot!.id).not.toBe(firstRoot!.id);
      expect(secondRoot!.trace_id).not.toBe(firstRoot!.trace_id);

      expect(secondRoot!.inputs?.prompt).toBe(
        "What color is grass? One word: green.",
      );

      expect(String(secondRoot!.outputs?.content)).toMatch(/green/i);

      const secondPosts = callSpy.mock.calls.filter(
        (call) => (call[1] as { method?: string })?.method === "POST",
      );
      expect(secondPosts.length).toBe(2);
    },
  );
});
