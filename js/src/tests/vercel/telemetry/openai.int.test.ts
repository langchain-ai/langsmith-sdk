/* eslint-disable @typescript-eslint/no-non-null-assertion */
/**
 * Integration tests for createLangSmithTelemetry with OpenAI.
 *
 * These tests simulate the TelemetryIntegration lifecycle that the Vercel AI SDK
 * will call when `telemetryIntegration` is supported. Each test manually drives
 * the event sequence (onStart → onStepStart → onStepFinish → onFinish) using
 * real OpenAI model responses via the AI SDK.
 *
 * Once the AI SDK ships the `telemetryIntegration` option on generateText/streamText,
 * these tests can be simplified to just pass `telemetryIntegration: createLangSmithTelemetry()`.
 */
import { openai } from "@ai-sdk/openai";
import * as ai from "ai";
import z from "zod";
import { v4 } from "uuid";

import { Client } from "../../../index.js";
import { createLangSmithTelemetry } from "../../../experimental/vercel/telemetry.js";
import { waitUntilRunFound } from "../../utils.js";
import { mockClient } from "../../utils/mock_client.js";
import { traceable } from "../../../traceable.js";

const { tool, stepCountIs } = ai;

test("telemetry generateText basic", async () => {
  const { client, callSpy } = mockClient();

  const integration = createLangSmithTelemetry({
    client: client as any,
  });

  const model = openai("gpt-5-nano");

  // Call generateText directly and drive telemetry hooks with the result
  const result = await ai.generateText({
    model,
    messages: [
      {
        role: "user",
        content: "What color is the sky? Answer in one word.",
      },
    ],
  });

  // Simulate the telemetry lifecycle
  integration.onStart?.({
    model,
    messages: [
      { role: "user", content: "What color is the sky? Answer in one word." },
    ],
  });

  integration.onStepStart?.({
    stepNumber: 0,
    messages: [
      { role: "user", content: "What color is the sky? Answer in one word." },
    ],
  });

  await integration.onStepFinish?.({
    stepNumber: 0,
    text: result.text,
    toolCalls: [],
    toolResults: [],
    usage: result.usage,
    finishReason: result.finishReason,
    providerMetadata: result.providerMetadata,
  });

  await integration.onFinish?.({
    text: result.text,
    toolCalls: [],
    toolResults: [],
    usage: result.usage,
    totalUsage: result.usage,
    finishReason: result.finishReason,
    providerMetadata: result.providerMetadata,
    steps: [
      {
        text: result.text,
        usage: result.usage,
        finishReason: result.finishReason,
      },
    ],
  });

  expect(result.text).toBeDefined();
  expect(result.text.length).toBeGreaterThan(0);

  await client.awaitPendingTraceBatches();

  const postBodies = await Promise.all(
    callSpy.mock.calls
      .filter((call) => call[1]!.method === "POST")
      .map((call) => new Response(call[1]!.body).json())
  );
  const patchBodies = await Promise.all(
    callSpy.mock.calls
      .filter((call) => call[1]!.method === "PATCH")
      .map((call) => new Response(call[1]!.body).json())
  );

  // Should have root + step creates, and step + root updates
  expect(postBodies.length).toBe(2);
  expect(patchBodies.length).toBe(2);

  // Root run should be a chain
  const rootRun = postBodies.find((b) => b.run_type === "chain");
  expect(rootRun).toBeDefined();
  expect(rootRun!.inputs.messages).toBeDefined();

  // Step run should be an LLM
  const stepRun = postBodies.find((b) => b.run_type === "llm");
  expect(stepRun).toBeDefined();
  expect(stepRun!.parent_run_id).toBe(rootRun!.id);

  // Step update should have usage metadata
  const stepUpdate = patchBodies.find((b) => b.extra?.metadata?.usage_metadata);
  expect(stepUpdate).toBeDefined();
  expect(
    stepUpdate!.extra.metadata.usage_metadata.input_tokens
  ).toBeGreaterThan(0);
  expect(
    stepUpdate!.extra.metadata.usage_metadata.output_tokens
  ).toBeGreaterThan(0);
});

test("telemetry generateText with tools", async () => {
  const { client, callSpy } = mockClient();

  const integration = createLangSmithTelemetry({
    client: client as any,
  });

  const model = openai("gpt-5-nano");
  const tools = {
    listOrders: tool({
      description: "list all orders",
      inputSchema: z.object({ userId: z.string() }),
      execute: async ({ userId }) =>
        `User ${userId} has the following orders: 1`,
    }),
  };

  // Do the real AI SDK call
  const result = await ai.generateText({
    model,
    messages: [
      {
        role: "user",
        content: "What are my orders? My user ID is 123. Always use tools.",
      },
    ],
    tools,
    stopWhen: stepCountIs(10),
  });

  expect(result.text).toBeDefined();
  expect(result.text.length).toBeGreaterThan(0);

  // Now simulate the telemetry lifecycle using the real result
  integration.onStart?.({
    model,
    messages: [
      {
        role: "user",
        content: "What are my orders? My user ID is 123. Always use tools.",
      },
    ],
    tools,
  });

  // Drive each step from result.steps
  for (let i = 0; i < result.steps.length; i++) {
    const step = result.steps[i];

    integration.onStepStart?.({
      stepNumber: i,
      messages: [
        {
          role: "user",
          content: "What are my orders? My user ID is 123. Always use tools.",
        },
      ],
    });

    // If step has tool calls, drive the tool lifecycle
    if (step.toolCalls && step.toolCalls.length > 0) {
      for (const tc of step.toolCalls) {
        integration.onToolCallStart?.({
          toolCallId: tc.toolCallId,
          toolName: tc.toolName,
          args: tc.args,
        });

        // Execute via the integration hook
        if (integration.executeToolCall) {
          await integration.executeToolCall({
            callId: `call-${tc.toolCallId}`,
            toolCallId: tc.toolCallId,
            execute: () =>
              Promise.resolve(
                step.toolResults?.find(
                  (tr: any) => tr.toolCallId === tc.toolCallId
                )?.result ?? "result"
              ),
          });
        }
      }
    }

    await integration.onStepFinish?.({
      stepNumber: i,
      text: step.text,
      toolCalls: step.toolCalls ?? [],
      toolResults: step.toolResults ?? [],
      usage: step.usage,
      finishReason: step.finishReason,
    });
  }

  await integration.onFinish?.({
    text: result.text,
    toolCalls: result.toolCalls ?? [],
    toolResults: result.toolResults ?? [],
    usage: result.usage,
    totalUsage: result.usage,
    finishReason: result.finishReason,
    steps: result.steps.map((s: any, idx: number) => ({
      stepNumber: idx,
      text: s.text,
      toolCalls: s.toolCalls ?? [],
      usage: s.usage,
      finishReason: s.finishReason,
    })),
  });

  await client.awaitPendingTraceBatches();

  const postBodies = await Promise.all(
    callSpy.mock.calls
      .filter((call) => call[1]!.method === "POST")
      .map((call) => new Response(call[1]!.body).json())
  );

  // Should have root, multiple steps, and tool runs
  const rootRun = postBodies.find((b) => b.run_type === "chain");
  const stepRuns = postBodies.filter((b) => b.run_type === "llm");
  const toolRuns = postBodies.filter((b) => b.run_type === "tool");

  expect(rootRun).toBeDefined();
  expect(stepRuns.length).toBeGreaterThanOrEqual(1);
  expect(toolRuns.length).toBeGreaterThanOrEqual(1);

  // All step runs should be children of the root
  for (const step of stepRuns) {
    expect(step.parent_run_id).toBe(rootRun!.id);
  }

  // Tool runs should be children of a step
  for (const toolRun of toolRuns) {
    const parentIsStep = stepRuns.some((s) => s.id === toolRun.parent_run_id);
    expect(parentIsStep).toBe(true);
  }
});

test("telemetry generateText with flex service tier", async () => {
  const { client, callSpy } = mockClient();

  const integration = createLangSmithTelemetry({
    client: client as any,
  });

  const model = openai("gpt-5-mini");

  const result = await ai.generateText({
    model,
    messages: [
      {
        role: "user",
        content: "What color is the sky in one word?",
      },
    ],
    providerOptions: {
      openai: {
        serviceTier: "flex",
      },
    },
  });

  // Drive telemetry
  integration.onStart?.({
    model,
    messages: [{ role: "user", content: "What color is the sky in one word?" }],
  });
  integration.onStepStart?.({
    stepNumber: 0,
    messages: [{ role: "user", content: "What color is the sky in one word?" }],
  });
  await integration.onStepFinish?.({
    stepNumber: 0,
    text: result.text,
    usage: result.usage,
    finishReason: result.finishReason,
    providerMetadata: result.providerMetadata,
  });
  await integration.onFinish?.({
    text: result.text,
    usage: result.usage,
    totalUsage: result.usage,
    finishReason: result.finishReason,
    providerMetadata: result.providerMetadata,
    steps: [
      {
        text: result.text,
        usage: result.usage,
        finishReason: result.finishReason,
      },
    ],
  });

  expect(result.text.length).toBeGreaterThan(0);

  await client.awaitPendingTraceBatches();

  const patchBodies = await Promise.all(
    callSpy.mock.calls
      .filter((call) => call[1]!.method === "PATCH")
      .map((call) => new Response(call[1]!.body).json())
  );

  const stepUpdate = patchBodies.find(
    (body) => body.extra?.metadata?.usage_metadata
  );
  expect(stepUpdate).toBeDefined();

  const usageMetadata = stepUpdate!.extra.metadata.usage_metadata;
  expect(usageMetadata.input_tokens).toBeGreaterThan(0);
  expect(usageMetadata.output_tokens).toBeGreaterThan(0);
});

test("telemetry generateText with output schema", async () => {
  const { client, callSpy } = mockClient();

  const schema = z.object({
    color: z.string(),
  });
  const output = ai.Output.object({ schema });

  const integration = createLangSmithTelemetry({
    client: client as any,
  });

  const model = openai("gpt-5-nano");

  const result = await ai.generateText({
    model,
    messages: [{ role: "user", content: "What color is the sky in one word?" }],
    output,
  });

  expect(result.output).toBeDefined();
  expect(schema.parse(result.output)).toBeDefined();

  // Drive telemetry
  integration.onStart?.({
    model,
    messages: [{ role: "user", content: "What color is the sky in one word?" }],
  });
  integration.onStepStart?.({
    stepNumber: 0,
    messages: [{ role: "user", content: "What color is the sky in one word?" }],
  });
  await integration.onStepFinish?.({
    stepNumber: 0,
    text: result.text,
    usage: result.usage,
    finishReason: result.finishReason,
  });
  await integration.onFinish?.({
    text: result.text,
    object: result.output,
    usage: result.usage,
    totalUsage: result.usage,
    finishReason: result.finishReason,
    steps: [
      {
        text: result.text,
        usage: result.usage,
        finishReason: result.finishReason,
      },
    ],
  });

  await client.awaitPendingTraceBatches();

  const patchBodies = await Promise.all(
    callSpy.mock.calls
      .filter((call) => call[1]!.method === "PATCH")
      .map((call) => new Response(call[1]!.body).json())
  );

  // Root update should have the structured object output
  const rootUpdate = patchBodies.find(
    (b) => b.extra?.metadata?.ls_integration === "vercel-ai-sdk-telemetry"
  );
  expect(rootUpdate).toBeDefined();
  expect(rootUpdate!.outputs.object).toBeDefined();
});

test("telemetry processInputs and processOutputs", async () => {
  const { client, callSpy } = mockClient();

  const integration = createLangSmithTelemetry({
    client: client as any,
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
    prompt: "What is the capital of France?",
  });

  // Drive telemetry
  integration.onStart?.({
    model,
    prompt: "What is the capital of France?",
  });
  integration.onStepStart?.({
    stepNumber: 0,
    messages: [{ role: "user", content: "What is the capital of France?" }],
  });
  await integration.onStepFinish?.({
    stepNumber: 0,
    text: result.text,
    usage: result.usage,
    finishReason: result.finishReason,
  });
  await integration.onFinish?.({
    text: result.text,
    usage: result.usage,
    totalUsage: result.usage,
    finishReason: result.finishReason,
    steps: [
      {
        text: result.text,
        usage: result.usage,
        finishReason: result.finishReason,
      },
    ],
  });

  expect(result.text).not.toContain("REDACTED");

  await client.awaitPendingTraceBatches();

  const postBodies = await Promise.all(
    callSpy.mock.calls
      .filter((call) => call[1]!.method === "POST")
      .map((call) => new Response(call[1]!.body).json())
  );
  const patchBodies = await Promise.all(
    callSpy.mock.calls
      .filter((call) => call[1]!.method === "PATCH")
      .map((call) => new Response(call[1]!.body).json())
  );

  // Root create should have redacted inputs
  const rootCreate = postBodies.find((b) => b.run_type === "chain");
  expect(rootCreate).toBeDefined();
  expect(rootCreate!.inputs.prompt).toBe("REDACTED");

  // Root update should have redacted outputs
  const rootUpdate = patchBodies.find(
    (b) => b.extra?.metadata?.ls_integration === "vercel-ai-sdk-telemetry"
  );
  expect(rootUpdate).toBeDefined();
  expect(rootUpdate!.outputs.content).toBe("REDACTED");

  // Child LLM create should have redacted inputs
  const stepCreate = postBodies.find((b) => b.run_type === "llm");
  expect(stepCreate).toBeDefined();
  expect(stepCreate!.inputs.messages[0].content).toBe("REDACTED CHILD INPUTS");

  // Child LLM update should have redacted outputs
  const stepUpdate = patchBodies.find(
    (b) => b.extra?.metadata?.ai_sdk_method === "ai.step"
  );
  expect(stepUpdate).toBeDefined();
  expect(stepUpdate!.outputs.content).toBe("REDACTED CHILD OUTPUTS");
});

test("telemetry nested under traceable parent", async () => {
  const { client, callSpy } = mockClient();

  const model = openai("gpt-5-nano");

  const outerFn = traceable(
    async () => {
      const integration = createLangSmithTelemetry({
        client: client as any,
      });

      const result = await ai.generateText({
        model,
        prompt: "What color is the sky?",
      });

      integration.onStart?.({
        model,
        prompt: "What color is the sky?",
      });
      integration.onStepStart?.({
        stepNumber: 0,
        messages: [{ role: "user", content: "What color is the sky?" }],
      });
      await integration.onStepFinish?.({
        stepNumber: 0,
        text: result.text,
        usage: result.usage,
        finishReason: result.finishReason,
      });
      await integration.onFinish?.({
        text: result.text,
        usage: result.usage,
        totalUsage: result.usage,
        finishReason: result.finishReason,
        steps: [
          {
            text: result.text,
            usage: result.usage,
            finishReason: result.finishReason,
          },
        ],
      });

      return result.text;
    },
    {
      name: "outer-traceable",
      client: client as any,
    }
  );

  const text = await outerFn();
  expect(text.length).toBeGreaterThan(0);

  await client.awaitPendingTraceBatches();

  const postBodies = await Promise.all(
    callSpy.mock.calls
      .filter((call) => call[1]!.method === "POST")
      .map((call) => new Response(call[1]!.body).json())
  );

  const outerRun = postBodies.find((b) => b.name === "outer-traceable");
  const telemetryRoot = postBodies.find(
    (b) =>
      b.run_type === "chain" &&
      b.extra?.metadata?.ls_integration === "vercel-ai-sdk-telemetry"
  );

  expect(outerRun).toBeDefined();
  expect(telemetryRoot).toBeDefined();
  expect(telemetryRoot!.parent_run_id).toBe(outerRun!.id);
  expect(telemetryRoot!.trace_id).toBe(outerRun!.trace_id);
});

test("telemetry tool with nested traceable (sub-agent pattern)", async () => {
  const { client, callSpy } = mockClient();

  const integration = createLangSmithTelemetry({
    client: client as any,
  });

  const model = openai("gpt-5-nano");

  // A traceable function simulating a sub-agent
  const subAgent = traceable(
    async (query: string) => {
      return `Sub-agent result for: ${query}`;
    },
    {
      name: "sub-agent",
      run_type: "chain",
      client: client as any,
    }
  );

  // Drive the telemetry lifecycle
  integration.onStart?.({
    model,
    prompt: "Use the research tool",
    tools: { research: {} },
  });

  integration.onStepStart?.({
    stepNumber: 0,
    messages: [{ role: "user", content: "Use the research tool" }],
  });

  // Tool call
  integration.onToolCallStart?.({
    toolCallId: "tc-1",
    toolName: "research",
    args: { query: "AI trends" },
  });

  // Execute tool with nested traceable via executeToolCall
  const toolResult = await integration.executeToolCall!({
    callId: "call-1",
    toolCallId: "tc-1",
    execute: () => subAgent("AI trends"),
  });

  expect(toolResult).toBe("Sub-agent result for: AI trends");

  await integration.onStepFinish?.({
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

  integration.onStepStart?.({
    stepNumber: 1,
    messages: [{ role: "user", content: "Use the research tool" }],
  });

  await integration.onStepFinish?.({
    stepNumber: 1,
    text: "Based on the research, AI is trending.",
    usage: {
      inputTokens: { total: 20, noCache: 20, cacheRead: 0, cacheWrite: 0 },
      outputTokens: { total: 10, text: 10, reasoning: 0 },
      totalTokens: 30,
    },
    finishReason: "stop",
  });

  await integration.onFinish?.({
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

  const postBodies = await Promise.all(
    callSpy.mock.calls
      .filter((call) => call[1]!.method === "POST")
      .map((call) => new Response(call[1]!.body).json())
  );

  const rootRun = postBodies.find(
    (b) =>
      b.run_type === "chain" &&
      b.extra?.metadata?.ls_integration === "vercel-ai-sdk-telemetry"
  );
  const stepRuns = postBodies.filter((b) => b.run_type === "llm");
  const toolRun = postBodies.find(
    (b) => b.run_type === "tool" && b.name === "research"
  );
  const subAgentRun = postBodies.find((b) => b.name === "sub-agent");

  expect(rootRun).toBeDefined();
  expect(stepRuns.length).toBe(2);
  expect(toolRun).toBeDefined();
  expect(subAgentRun).toBeDefined();

  // Tool should be child of step 0
  expect(toolRun!.parent_run_id).toBe(stepRuns[0].id);

  // Sub-agent should be child of tool
  expect(subAgentRun!.parent_run_id).toBe(toolRun!.id);

  // All share the same trace_id
  expect(toolRun!.trace_id).toBe(rootRun!.trace_id);
  expect(subAgentRun!.trace_id).toBe(rootRun!.trace_id);
});

test("telemetry error handling", async () => {
  const { client, callSpy } = mockClient();

  const integration = createLangSmithTelemetry({
    client: client as any,
  });

  const model = openai("gpt-5-nano");

  integration.onStart?.({
    model,
    prompt: "This will fail",
  });

  integration.onStepStart?.({
    stepNumber: 0,
    messages: [{ role: "user", content: "This will fail" }],
  });

  await integration.onError?.(new Error("TOTALLY EXPECTED MOCK ERROR"));

  await client.awaitPendingTraceBatches();

  const patchBodies = await Promise.all(
    callSpy.mock.calls
      .filter((call) => call[1]!.method === "PATCH")
      .map((call) => new Response(call[1]!.body).json())
  );

  const errorUpdates = patchBodies.filter((b) => b.error);
  // Both step and root should have error
  expect(errorUpdates.length).toBe(2);
  expect(errorUpdates[0].error).toContain("TOTALLY EXPECTED MOCK ERROR");
  expect(errorUpdates[1].error).toContain("TOTALLY EXPECTED MOCK ERROR");
});

test("telemetry reuse across sequential generateText calls", async () => {
  const { client, callSpy } = mockClient();

  // Create ONE integration and reuse it
  const integration = createLangSmithTelemetry({
    client: client as any,
  });

  const model = openai("gpt-5-nano");

  // --- First call ---
  const result1 = await ai.generateText({
    model,
    prompt: "What color is the sky?",
  });

  integration.onStart?.({
    model,
    prompt: "What color is the sky?",
  });
  integration.onStepStart?.({
    stepNumber: 0,
    messages: [{ role: "user", content: "What color is the sky?" }],
  });
  await integration.onStepFinish?.({
    stepNumber: 0,
    text: result1.text,
    usage: result1.usage,
    finishReason: result1.finishReason,
  });
  await integration.onFinish?.({
    text: result1.text,
    usage: result1.usage,
    totalUsage: result1.usage,
    finishReason: result1.finishReason,
    steps: [
      {
        text: result1.text,
        usage: result1.usage,
        finishReason: result1.finishReason,
      },
    ],
  });

  await client.awaitPendingTraceBatches();

  // Snapshot first call
  const firstCallPosts = await Promise.all(
    callSpy.mock.calls
      .filter((call) => call[1]!.method === "POST")
      .map((call) => new Response(call[1]!.body).json())
  );
  const firstRoot = firstCallPosts.find((b) => b.run_type === "chain");
  expect(firstRoot).toBeDefined();

  // Reset spy
  callSpy.mockClear();

  // --- Second call with SAME integration ---
  const result2 = await ai.generateText({
    model,
    prompt: "What color is grass?",
  });

  integration.onStart?.({
    model,
    prompt: "What color is grass?",
  });
  integration.onStepStart?.({
    stepNumber: 0,
    messages: [{ role: "user", content: "What color is grass?" }],
  });
  await integration.onStepFinish?.({
    stepNumber: 0,
    text: result2.text,
    usage: result2.usage,
    finishReason: result2.finishReason,
  });
  await integration.onFinish?.({
    text: result2.text,
    usage: result2.usage,
    totalUsage: result2.usage,
    finishReason: result2.finishReason,
    steps: [
      {
        text: result2.text,
        usage: result2.usage,
        finishReason: result2.finishReason,
      },
    ],
  });

  await client.awaitPendingTraceBatches();

  const secondCallPosts = await Promise.all(
    callSpy.mock.calls
      .filter((call) => call[1]!.method === "POST")
      .map((call) => new Response(call[1]!.body).json())
  );
  const secondRoot = secondCallPosts.find((b) => b.run_type === "chain");
  expect(secondRoot).toBeDefined();

  // Each call should have its own distinct root and trace
  expect(secondRoot!.id).not.toBe(firstRoot!.id);
  expect(secondRoot!.trace_id).not.toBe(firstRoot!.trace_id);

  // Second call should have its own input
  expect(secondRoot!.inputs.prompt).toBe("What color is grass?");

  // Both calls should produce root + step (2 creates each)
  expect(firstCallPosts.length).toBe(2);
  expect(secondCallPosts.length).toBe(2);
});
