/* eslint-disable @typescript-eslint/no-non-null-assertion */
import { openai } from "@ai-sdk/openai";
import * as ai from "ai";
import z from "zod";
import { test, expect, vi } from "vitest";

import { createLangSmithTelemetry } from "../../../experimental/vercel/telemetry.js";
import { getAssumedTreeFromCalls } from "../../utils/tree.js";
import { traceable } from "../../../traceable.js";
import { Client } from "../../../index.js";

const { tool, stepCountIs } = ai;

class GreaterThanMatcher {
  constructor(private threshold: number) {}
  asymmetricMatch(actual: unknown) {
    return typeof actual === "number" && actual > this.threshold;
  }
  getExpectedType() {
    return "number";
  }
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

  expect(
    await getAssumedTreeFromCalls(callSpy.mock.calls, client),
  ).toMatchObject({
    edges: [["openai.responses:0", "step 0:1"]],
    data: {
      "openai.responses:0": {
        run_type: "chain",
        inputs: {
          messages: [{ role: "user", content: userMessage }],
        },
        outputs: {
          content: expect.stringMatching(/blue/i),
          finish_reason: "stop",
        },
        extra: {
          metadata: {
            usage_metadata: { total_tokens: new GreaterThanMatcher(0) },
          },
        },
      },
      "step 0:1": {
        run_type: "llm",
        inputs: {
          messages: [{ role: "user", content: userMessage }],
        },
        outputs: {
          role: "assistant",
          content: expect.stringMatching(/blue/i),
          finish_reason: "stop",
        },
        extra: {
          metadata: {
            usage_metadata: {
              input_tokens: new GreaterThanMatcher(0),
              output_tokens: new GreaterThanMatcher(0),
            },
          },
        },
      },
    },
  });
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

  expect(
    await getAssumedTreeFromCalls(callSpy.mock.calls, client),
  ).toMatchObject({
    edges: [
      ["openai.responses:0", "step 0:1"],
      ["step 0:1", "listOrders:2"],
      ["openai.responses:0", "step 1:3"],
    ],
    data: {
      "openai.responses:0": {
        run_type: "chain",
        inputs: {
          messages: [{ role: "user", content: userContent }],
          tools: ["listOrders"],
        },
        outputs: {
          content: expect.stringMatching(/order/i),
          finish_reason: "stop",
        },
        extra: {
          metadata: {
            usage_metadata: { total_tokens: new GreaterThanMatcher(0) },
          },
        },
      },
      "step 0:1": {
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
      "listOrders:2": {
        run_type: "tool",
        inputs: { userId: "123" },
        outputs: {
          output: expect.stringMatching(/User 123 has the following orders/),
        },
      },
      "step 1:3": {
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

  expect(
    await getAssumedTreeFromCalls(callSpy.mock.calls, client),
  ).toMatchObject({
    edges: [
      ["openai.responses:0", "step 0:1"],
      ["step 0:1", "listOrders:2"],
      ["openai.responses:0", "step 1:3"],
    ],
    data: {
      "openai.responses:0": {
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
      "step 0:1": {
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
      "listOrders:2": {
        run_type: "tool",
        inputs: { userId: "123" },
        outputs: {
          output: expect.stringMatching(/User 123 has the following orders/),
        },
      },
      "step 1:3": {
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
      providerOptions: { openai: { serviceTier: "flex" } },
      telemetry: { integrations: [createLangSmithTelemetry({ client })] },
    });

    expect(result.text.length).toBeGreaterThan(0);
    await client.awaitPendingTraceBatches();

    expect(
      await getAssumedTreeFromCalls(callSpy.mock.calls, client),
    ).toMatchObject({
      edges: [["openai.responses:0", "step 0:1"]],
      data: {
        "openai.responses:0": {
          run_type: "chain",
          inputs: {
            messages: [{ role: "user", content: userMessage }],
          },
          outputs: {
            content: expect.stringMatching(/blue/i),
            finish_reason: "stop",
          },
        },
        "step 0:1": {
          run_type: "llm",
          outputs: {
            role: "assistant",
            content: expect.stringMatching(/blue/i),
            finish_reason: "stop",
          },
          extra: {
            metadata: {
              usage_metadata: {
                input_tokens: new GreaterThanMatcher(0),
                output_tokens: new GreaterThanMatcher(0),
              },
            },
          },
        },
      },
    });
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

  expect(
    await getAssumedTreeFromCalls(callSpy.mock.calls, client),
  ).toMatchObject({
    edges: [["openai.responses:0", "step 0:1"]],
    data: {
      "openai.responses:0": {
        run_type: "chain",
        inputs: {
          messages: [{ role: "user", content: userMessage }],
        },
        outputs: {
          content: expect.stringMatching(/"color"\s*:\s*"blue"/i),
          finish_reason: "stop",
        },
      },
      "step 0:1": {
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

    expect(
      await getAssumedTreeFromCalls(callSpy.mock.calls, client),
    ).toMatchObject({
      edges: [["openai.responses:0", "step 0:1"]],
      data: {
        "openai.responses:0": {
          run_type: "chain",
          inputs: {
            messages: [{ role: "user", content: userMessage }],
          },
          outputs: {
            content: expect.stringMatching(/"color"\s*:\s*"blue"/i),
            finish_reason: "stop",
          },
        },
        "step 0:1": {
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

    expect(runs).toMatchObject({
      edges: [["openai.responses:0", "step 0:1"]],
      data: {
        "openai.responses:0": {
          run_type: "chain",
          inputs: {
            messages: [{ role: "user", content: userMessage }],
          },
        },
        "step 0:1": {
          run_type: "llm",
          inputs: {
            messages: [{ role: "user", content: userMessage }],
          },
        },
      },
    });

    if (abortedAfterDeltas) {
      expect(runs.data["openai.responses:0"].end_time).toBeUndefined();
      expect(runs.data["step 0:1"].end_time).toBeUndefined();
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

    expect(
      await getAssumedTreeFromCalls(callSpy.mock.calls, client),
    ).toMatchObject({
      edges: [["openai.responses:0", "step 0:1"]],
      data: {
        "openai.responses:0": {
          inputs: { prompt: "REDACTED" },
          outputs: { content: "REDACTED" },
        },
        "step 0:1": {
          inputs: {
            messages: [
              expect.objectContaining({ content: "REDACTED CHILD INPUTS" }),
            ],
          },
          outputs: { content: "REDACTED CHILD OUTPUTS" },
        },
      },
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
    expect(runs).toMatchObject({
      nodes: ["outer-traceable:0", "openai.responses:1", "step 0:2"],
      edges: [
        ["outer-traceable:0", "openai.responses:1"],
        ["openai.responses:1", "step 0:2"],
      ],

      data: {
        "outer-traceable:0": {
          name: "outer-traceable",
        },
        "openai.responses:1": {
          trace_id: runs.data["outer-traceable:0"].trace_id,
          run_type: "chain",
          extra: {
            metadata: expect.objectContaining({
              ls_integration: "vercel-ai-sdk-telemetry",
            }),
          },
        },
        "step 0:2": expect.objectContaining({
          run_type: "llm",
          trace_id: runs.data["outer-traceable:0"].trace_id,
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

    const integration = createLangSmithTelemetry({ client });
    const model = openai("gpt-5-nano");

    const subAgent = traceable(
      async (query: string) => {
        const subagent = await ai.generateText({
          model,
          prompt: `Only say '${query}' and nothing else`,
          telemetry: { integrations: [integration] },
        });

        return subagent.text;
      },
      { name: "sub-agent", run_type: "chain", client },
    );

    await ai.generateText({
      model,
      prompt: "Call the research tool to search for 'AI trends'",
      tools: {
        research: tool({
          description: "Search for AI trends",
          inputSchema: z.object({ query: z.string() }),
          execute: async ({ query }) => subAgent(query),
        }),
      },
      telemetry: { integrations: [integration] },
    });

    await client.awaitPendingTraceBatches();
    const runs = await getAssumedTreeFromCalls(callSpy.mock.calls, client);

    console.dir(runs, { depth: null });
    expect(runs).toMatchObject({
      edges: [
        ["openai.responses:0", "step 0:1"],
        ["step 0:1", "research:2"],
        ["research:2", "sub-agent:3"],
        ["sub-agent:3", "openai.responses:4"],
        ["openai.responses:4", "step 0:5"],
      ],
      data: {
        "openai.responses:0": {
          run_type: "chain",
          inputs: {
            messages: [
              {
                role: "user",
                content: "Call the research tool to search for 'AI trends'",
              },
            ],
            tools: ["research"],
          },
          outputs: {
            tool_calls: [{ type: "function", function: { name: "research" } }],
            finish_reason: "tool-calls",
          },
        },
        "step 0:1": {
          run_type: "llm",
          inputs: {
            messages: [
              {
                role: "user",
                content: "Call the research tool to search for 'AI trends'",
              },
            ],
          },
          outputs: {
            role: "assistant",
            tool_calls: [{ type: "function", function: { name: "research" } }],
            finish_reason: "tool-calls",
          },
        },
        "research:2": {
          run_type: "tool",
          inputs: { query: "AI trends" },
          outputs: { output: "AI trends" },
        },
        "sub-agent:3": {
          run_type: "chain",
          inputs: { input: "AI trends" },
          outputs: { outputs: "AI trends" },
        },
        "openai.responses:4": {
          run_type: "chain",
          inputs: {
            messages: [
              {
                role: "user",
                content: "Only say 'AI trends' and nothing else",
              },
            ],
          },
          outputs: { content: "AI trends", finish_reason: "stop" },
        },
        "step 0:5": {
          run_type: "llm",
          inputs: {
            messages: [
              {
                role: "user",
                content: "Only say 'AI trends' and nothing else",
              },
            ],
          },
          outputs: { role: "assistant", finish_reason: "stop" },
        },
      },
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
  const [parentKey, childKey] = runs.edges[0]!;

  expect(runs).toMatchObject({
    edges: [[parentKey, childKey]],
    data: {
      [parentKey]: {
        error: expect.stringContaining("TOTALLY EXPECTED MOCK ERROR"),
      },
      [childKey]: {
        error: expect.stringContaining("TOTALLY EXPECTED MOCK ERROR"),
      },
    },
  });
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
    expect(firstRuns).toMatchObject({
      edges: [["openai.responses:0", "step 0:1"]],
      data: {
        "openai.responses:0": {
          inputs: {
            messages: [
              {
                role: "user",
                content: "What color is the sky? One word: blue.",
              },
            ],
          },
          outputs: { content: expect.stringMatching(/blue/i) },
        },
        "step 0:1": expect.objectContaining({ run_type: "llm" }),
      },
    });
    const firstChain = firstRuns.data["openai.responses:0"]!;

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
    expect(secondRuns).toMatchObject({
      edges: [["openai.responses:0", "step 0:1"]],
      data: {
        "openai.responses:0": {
          inputs: {
            messages: [
              {
                role: "user",
                content: "What color is grass? One word: green.",
              },
            ],
          },
          outputs: { content: expect.stringMatching(/green/i) },
        },
        "step 0:1": expect.objectContaining({ run_type: "llm" }),
      },
    });
    const secondChain = secondRuns.data["openai.responses:0"]!;

    expect(secondChain.id).not.toBe(firstChain.id);
    expect(secondChain.trace_id).not.toBe(firstChain.trace_id);

    const secondPosts = callSpy.mock.calls.filter(
      (call) => (call[1] as { method?: string })?.method === "POST",
    );
    expect(secondPosts.length).toBe(2);
  },
);
