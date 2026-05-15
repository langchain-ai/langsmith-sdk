/* eslint-disable @typescript-eslint/no-non-null-assertion */
import { openai } from "@ai-sdk/openai";
import * as ai from "ai";
import z from "zod";
import { test, expect, vi } from "vitest";

import { createLangSmithTelemetry } from "../../../experimental/vercel/telemetry.js";
import { getAssumedTreeFromCalls } from "../../utils/tree.js";
import { traceable } from "../../../traceable.js";
import { Client } from "../../../index.js";
import type { Run } from "../../../schemas.js";

const { tool, stepCountIs } = ai;

function isTelemetryRoot(r: Run): boolean {
  return (
    r.run_type === "chain" &&
    r.extra?.metadata?.ls_integration === "vercel-ai-sdk-telemetry"
  );
}

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
  const root = Object.values(runs.data).find(isTelemetryRoot);
  const step0 = Object.values(runs.data).find(
    (r) => r.run_type === "llm" && r.extra?.metadata?.step_number === 0,
  );

  expect(root).toBeDefined();
  expect(step0).toBeDefined();
  expect(step0!.parent_run_id).toBe(root!.id);

  expect(root).toMatchObject({
    run_type: "chain",
    inputs: {
      messages: [{ role: "user", content: userMessage }],
    },
    outputs: {
      content: expect.stringMatching(/blue/i),
      finish_reason: "stop",
    },
  });

  expect(step0).toMatchObject({
    run_type: "llm",
    inputs: {
      messages: [{ role: "user", content: userMessage }],
    },
    outputs: {
      role: "assistant",
      content: expect.stringMatching(/blue/i),
      finish_reason: "stop",
    },
  });

  expect(root!.extra?.metadata?.usage_metadata?.total_tokens).toBeGreaterThan(
    0,
  );
  expect(step0!.extra?.metadata?.usage_metadata?.input_tokens).toBeGreaterThan(
    0,
  );
  expect(step0!.extra?.metadata?.usage_metadata?.output_tokens).toBeGreaterThan(
    0,
  );
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
  const root = Object.values(runs.data).find(isTelemetryRoot);
  const step0 = Object.values(runs.data).find(
    (r) => r.run_type === "llm" && r.extra?.metadata?.step_number === 0,
  );
  const step1 = Object.values(runs.data).find(
    (r) => r.run_type === "llm" && r.extra?.metadata?.step_number === 1,
  );
  const listOrders = Object.values(runs.data).find(
    (r) => r.run_type === "tool" && r.name === "listOrders",
  );

  expect(root).toBeDefined();
  expect(step0).toBeDefined();
  expect(step1).toBeDefined();
  expect(listOrders).toBeDefined();
  expect(step0!.parent_run_id).toBe(root!.id);
  expect(listOrders!.parent_run_id).toBe(step0!.id);
  expect(step1!.parent_run_id).toBe(root!.id);

  expect(root).toMatchObject({
    run_type: "chain",
    inputs: {
      messages: [{ role: "user", content: userContent }],
      tools: ["listOrders"],
    },
    outputs: {
      content: expect.stringMatching(/order/i),
      finish_reason: "stop",
    },
  });

  expect(step0).toMatchObject({
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
  });

  expect(listOrders).toMatchObject({
    run_type: "tool",
    inputs: { userId: "123" },
    outputs: {},
  });

  expect(step1).toMatchObject({
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
  });

  expect(root!.extra?.metadata?.usage_metadata?.total_tokens).toBeGreaterThan(
    0,
  );
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
  const root = Object.values(runs.data).find(isTelemetryRoot);
  const step0 = Object.values(runs.data).find(
    (r) => r.run_type === "llm" && r.extra?.metadata?.step_number === 0,
  );
  const step1 = Object.values(runs.data).find(
    (r) => r.run_type === "llm" && r.extra?.metadata?.step_number === 1,
  );
  const listOrders = Object.values(runs.data).find(
    (r) => r.run_type === "tool" && r.name === "listOrders",
  );

  expect(root).toBeDefined();
  expect(step0).toBeDefined();
  expect(step1).toBeDefined();
  expect(listOrders).toBeDefined();
  expect(step0!.parent_run_id).toBe(root!.id);
  expect(listOrders!.parent_run_id).toBe(step0!.id);
  expect(step1!.parent_run_id).toBe(root!.id);

  expect(root).toMatchObject({
    run_type: "chain",
    inputs: {
      messages: [{ role: "user", content: userContent }],
      tools: ["listOrders"],
    },
    outputs: {
      content: expect.stringMatching(/order/i),
      finish_reason: "stop",
    },
  });

  expect(step0).toMatchObject({
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
  });

  expect(listOrders).toMatchObject({
    run_type: "tool",
    inputs: { userId: "123" },
    outputs: {},
  });

  expect(step1).toMatchObject({
    run_type: "llm",
    outputs: {
      role: "assistant",
      content: expect.stringMatching(/order/i),
      finish_reason: "stop",
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
    const root = Object.values(runs.data).find(isTelemetryRoot);
    const step0 = Object.values(runs.data).find(
      (r) => r.run_type === "llm" && r.extra?.metadata?.step_number === 0,
    );

    expect(root).toBeDefined();
    expect(step0).toBeDefined();
    expect(step0!.parent_run_id).toBe(root!.id);

    expect(root).toMatchObject({
      run_type: "chain",
      inputs: {
        messages: [{ role: "user", content: userMessage }],
      },
      outputs: {
        content: expect.stringMatching(/blue/i),
        finish_reason: "stop",
      },
    });

    expect(step0).toMatchObject({
      run_type: "llm",
      outputs: {
        role: "assistant",
        content: expect.stringMatching(/blue/i),
        finish_reason: "stop",
      },
    });

    const usageMetadata = step0!.extra?.metadata?.usage_metadata;
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
  const root = Object.values(runs.data).find(isTelemetryRoot);
  const step0 = Object.values(runs.data).find(
    (r) => r.run_type === "llm" && r.extra?.metadata?.step_number === 0,
  );

  expect(root).toBeDefined();
  expect(step0).toBeDefined();
  expect(step0!.parent_run_id).toBe(root!.id);

  expect(root).toMatchObject({
    run_type: "chain",
    inputs: {
      messages: [{ role: "user", content: userMessage }],
    },
    outputs: {
      content: expect.stringMatching(/"color"\s*:\s*"blue"/i),
      finish_reason: "stop",
    },
  });

  expect(step0).toMatchObject({
    run_type: "llm",
    inputs: {
      messages: [{ role: "user", content: userMessage }],
    },
    outputs: {
      role: "assistant",
      content: expect.stringMatching(/"color"\s*:\s*"blue"/i),
      finish_reason: "stop",
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
    const root = Object.values(runs.data).find(isTelemetryRoot);
    const step0 = Object.values(runs.data).find(
      (r) => r.run_type === "llm" && r.extra?.metadata?.step_number === 0,
    );

    expect(root).toBeDefined();
    expect(step0).toBeDefined();
    expect(step0!.parent_run_id).toBe(root!.id);

    expect(root).toMatchObject({
      run_type: "chain",
      inputs: {
        messages: [{ role: "user", content: userMessage }],
      },
      outputs: {
        content: expect.stringMatching(/"color"\s*:\s*"blue"/i),
        finish_reason: "stop",
      },
    });

    expect(step0).toMatchObject({
      run_type: "llm",
      inputs: {
        messages: [{ role: "user", content: userMessage }],
      },
      outputs: {
        role: "assistant",
        content: expect.stringMatching(/"color"\s*:\s*"blue"/i),
        finish_reason: "stop",
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
    const root = Object.values(runs.data).find(isTelemetryRoot);
    const step0 = Object.values(runs.data).find(
      (r) => r.run_type === "llm" && r.extra?.metadata?.step_number === 0,
    );

    expect(root).toBeDefined();
    expect(step0).toBeDefined();
    expect(step0!.parent_run_id).toBe(root!.id);

    expect(root).toMatchObject({
      run_type: "chain",
      inputs: {
        messages: [{ role: "user", content: userMessage }],
      },
    });

    expect(step0).toMatchObject({
      run_type: "llm",
      inputs: {
        messages: [{ role: "user", content: userMessage }],
      },
    });

    if (abortedAfterDeltas) {
      expect(root!.end_time).toBeUndefined();
      expect(step0!.end_time).toBeUndefined();
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
    const root = Object.values(runs.data).find(isTelemetryRoot);
    const step0 = Object.values(runs.data).find(
      (r) => r.run_type === "llm" && r.extra?.metadata?.step_number === 0,
    );

    expect(root).toBeDefined();
    expect(step0).toBeDefined();
    expect(step0!.parent_run_id).toBe(root!.id);

    expect(root).toMatchObject({
      inputs: { prompt: "REDACTED" },
      outputs: { content: "REDACTED" },
    });

    expect(step0).toMatchObject({
      inputs: {
        messages: [
          expect.objectContaining({ content: "REDACTED CHILD INPUTS" }),
        ],
      },
      outputs: { content: "REDACTED CHILD OUTPUTS" },
    });
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
    const outer = Object.values(runs.data).find(
      (r) => r.name === "outer-traceable",
    );
    const telemetryRoot = Object.values(runs.data).find(isTelemetryRoot);

    expect(outer).toBeDefined();
    expect(telemetryRoot).toBeDefined();
    expect(telemetryRoot!.parent_run_id).toBe(outer!.id);
    expect(telemetryRoot!.trace_id).toBe(outer!.trace_id);

    expect(outer).toMatchObject({
      name: "outer-traceable",
    });

    expect(telemetryRoot).toMatchObject({
      run_type: "chain",
      extra: {
        metadata: expect.objectContaining({
          ls_integration: "vercel-ai-sdk-telemetry",
        }),
      },
    });
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
    const drive = integration as any;

    const model = openai("gpt-5-nano");

    const subAgent = traceable(
      async (query: string) => `Sub-agent result for: ${query}`,
      { name: "sub-agent", run_type: "chain", client },
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
    const root = Object.values(runs.data).find(isTelemetryRoot);
    const step0 = Object.values(runs.data).find(
      (r) => r.run_type === "llm" && r.extra?.metadata?.step_number === 0,
    );
    const step1 = Object.values(runs.data).find(
      (r) => r.run_type === "llm" && r.extra?.metadata?.step_number === 1,
    );
    const research = Object.values(runs.data).find(
      (r) => r.run_type === "tool" && r.name === "research",
    );
    const subAgentRun = Object.values(runs.data).find(
      (r) => r.name === "sub-agent",
    );

    expect(root).toBeDefined();
    expect(step0).toBeDefined();
    expect(step1).toBeDefined();
    expect(research).toBeDefined();
    expect(subAgentRun).toBeDefined();

    expect(step0!.parent_run_id).toBe(root!.id);
    expect(research!.parent_run_id).toBe(step0!.id);
    expect(step1!.parent_run_id).toBe(root!.id);
    expect(subAgentRun!.parent_run_id).toBe(research!.id);

    expect(subAgentRun!.trace_id).toBe(root!.trace_id);
    expect(research!.trace_id).toBe(root!.trace_id);

    expect(root).toMatchObject({
      outputs: {
        content: expect.stringMatching(/trending|research/i),
      },
    });

    expect(research).toMatchObject({
      run_type: "tool",
      name: "research",
    });

    expect(subAgentRun).toMatchObject({
      name: "sub-agent",
    });
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

  expect(errorRuns).toHaveLength(2);
  expect(errorRuns.map((r) => String(r.error))).toEqual(
    expect.arrayContaining([
      expect.stringContaining("TOTALLY EXPECTED MOCK ERROR"),
      expect.stringContaining("TOTALLY EXPECTED MOCK ERROR"),
    ]),
  );
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

    const firstRuns = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
    const firstRoot = Object.values(firstRuns.data).find(isTelemetryRoot);
    expect(firstRoot).toBeDefined();

    expect(firstRoot).toMatchObject({
      inputs: { prompt: "What color is the sky? One word: blue." },
      outputs: { content: expect.stringMatching(/blue/i) },
    });

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
    const secondRoot = Object.values(secondRuns.data).find(isTelemetryRoot);
    expect(secondRoot).toBeDefined();

    expect(secondRoot!.id).not.toBe(firstRoot!.id);
    expect(secondRoot!.trace_id).not.toBe(firstRoot!.trace_id);

    expect(secondRoot).toMatchObject({
      inputs: { prompt: "What color is grass? One word: green." },
      outputs: { content: expect.stringMatching(/green/i) },
    });

    const secondPosts = callSpy.mock.calls.filter(
      (call) => (call[1] as { method?: string })?.method === "POST",
    );
    expect(secondPosts.length).toBe(2);
  },
);
