/* eslint-disable @typescript-eslint/no-non-null-assertion */
/**
 * Integration tests for createLangSmithTelemetry with Anthropic.
 *
 * These tests simulate the TelemetryIntegration lifecycle that the Vercel AI SDK
 * will call when `telemetryIntegration` is supported. Each test manually drives
 * the event sequence (onStart → onStepStart → onStepFinish → onFinish) using
 * real Anthropic model responses via the AI SDK.
 *
 * Once the AI SDK ships the `telemetryIntegration` option on generateText/streamText,
 * these tests can be simplified to just pass `telemetryIntegration: createLangSmithTelemetry()`.
 */
import { anthropic } from "@ai-sdk/anthropic";
import * as ai from "ai";
import z from "zod";
import { v4 } from "uuid";

import { Client } from "../../../index.js";
import { createLangSmithTelemetry } from "../../../experimental/vercel/telemetry.js";
import { generateLongContext } from "../../utils.js";
import { mockClient } from "../../utils/mock_client.js";
import { traceable } from "../../../traceable.js";

const { tool, stepCountIs } = ai;

// No Anthropic key in CI
describe("anthropic telemetry", () => {
  test.skip("telemetry generateText", async () => {
    const { client, callSpy } = mockClient();

    const integration = createLangSmithTelemetry({
      client: client as any,
    });

    const model = anthropic("claude-3-5-haiku-latest");

    const result = await ai.generateText({
      model,
      messages: [
        {
          role: "user",
          content: "What are my orders? My user ID is 123. Always use tools.",
        },
      ],
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

    // Drive telemetry lifecycle with real results
    integration.onStart?.({
      model,
      messages: [
        {
          role: "user",
          content: "What are my orders? My user ID is 123. Always use tools.",
        },
      ],
      tools: { listOrders: {} },
    });

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

      if (step.toolCalls && step.toolCalls.length > 0) {
        for (const tc of step.toolCalls) {
          integration.onToolCallStart?.({
            toolCallId: tc.toolCallId,
            toolName: tc.toolName,
            args: tc.args,
          });

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
      providerMetadata: result.providerMetadata,
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

    const rootRun = postBodies.find((b) => b.run_type === "chain");
    const stepRuns = postBodies.filter((b) => b.run_type === "llm");
    const toolRuns = postBodies.filter((b) => b.run_type === "tool");

    expect(rootRun).toBeDefined();
    expect(stepRuns.length).toBeGreaterThanOrEqual(1);

    // If tool was called, verify tool run nesting
    if (toolRuns.length > 0) {
      for (const toolRun of toolRuns) {
        const parentIsStep = stepRuns.some(
          (s) => s.id === toolRun.parent_run_id
        );
        expect(parentIsStep).toBe(true);
      }
    }

    // Verify usage metadata on step updates
    const patchBodies = await Promise.all(
      callSpy.mock.calls
        .filter((call) => call[1]!.method === "PATCH")
        .map((call) => new Response(call[1]!.body).json())
    );
    const stepUpdate = patchBodies.find(
      (b) => b.extra?.metadata?.usage_metadata
    );
    expect(stepUpdate).toBeDefined();
    expect(
      stepUpdate!.extra.metadata.usage_metadata.input_tokens
    ).toBeGreaterThan(0);
  });

  test.skip("telemetry streamText", async () => {
    const { client, callSpy } = mockClient();

    const integration = createLangSmithTelemetry({
      client: client as any,
    });

    const model = anthropic("claude-3-5-haiku-latest");

    const streamResult = ai.streamText({
      model,
      messages: [
        {
          role: "user",
          content: "What are my orders? My user ID is 123. Always use tools.",
        },
      ],
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

    // Drive telemetry lifecycle — for streaming, we simulate as a single step
    // since we consumed the whole stream
    integration.onStart?.({
      model,
      messages: [
        {
          role: "user",
          content: "What are my orders? My user ID is 123. Always use tools.",
        },
      ],
    });

    integration.onStepStart?.({
      stepNumber: 0,
      messages: [
        {
          role: "user",
          content: "What are my orders? My user ID is 123. Always use tools.",
        },
      ],
    });

    // Simulate onChunk calls
    integration.onChunk?.({ type: "text-delta", delta: total.slice(0, 10) });
    integration.onChunk?.({ type: "text-delta", delta: total.slice(10) });

    await integration.onStepFinish?.({
      stepNumber: 0,
      text: total,
      usage: await streamResult.usage,
      finishReason: await streamResult.finishReason,
    });

    await integration.onFinish?.({
      text: total,
      usage: await streamResult.usage,
      totalUsage: await streamResult.usage,
      finishReason: await streamResult.finishReason,
      steps: [
        {
          text: total,
          usage: await streamResult.usage,
          finishReason: await streamResult.finishReason,
        },
      ],
    });

    await client.awaitPendingTraceBatches();

    const postBodies = await Promise.all(
      callSpy.mock.calls
        .filter((call) => call[1]!.method === "POST")
        .map((call) => new Response(call[1]!.body).json())
    );

    const rootRun = postBodies.find((b) => b.run_type === "chain");
    const stepRun = postBodies.find((b) => b.run_type === "llm");

    expect(rootRun).toBeDefined();
    expect(stepRun).toBeDefined();
    expect(stepRun!.parent_run_id).toBe(rootRun!.id);
  });

  test.skip("telemetry generateObject", async () => {
    const { client, callSpy } = mockClient();

    const schema = z.object({
      color: z.string(),
    });

    const integration = createLangSmithTelemetry({
      client: client as any,
    });

    const model = anthropic("claude-3-5-haiku-latest");

    const result = await ai.generateText({
      model,
      messages: [{ role: "user", content: "What color is the sky?" }],
      output: ai.Output.object({ schema }),
    });

    expect(result.output).toBeDefined();
    expect(schema.parse(result.output)).toBeDefined();

    // Drive telemetry
    integration.onStart?.({
      model,
      messages: [{ role: "user", content: "What color is the sky?" }],
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

    const postBodies = await Promise.all(
      callSpy.mock.calls
        .filter((call) => call[1]!.method === "POST")
        .map((call) => new Response(call[1]!.body).json())
    );

    const rootRun = postBodies.find((b) => b.run_type === "chain");
    expect(rootRun).toBeDefined();
  });

  test.skip("telemetry streamObject via streamText with output", async () => {
    const { client, callSpy } = mockClient();

    const schema = z.object({
      color: z.string(),
    });
    const output = ai.Output.object({ schema });

    const integration = createLangSmithTelemetry({
      client: client as any,
    });

    const model = anthropic("claude-3-5-haiku-latest");

    const streamResult = ai.streamText({
      model,
      messages: [{ role: "user", content: "What color is the sky?" }],
      output,
    });

    const chunks = [];
    for await (const chunk of streamResult.partialOutputStream) {
      chunks.push(chunk);
    }
    expect(chunks.length).toBeGreaterThan(0);
    expect(schema.parse(chunks.at(-1))).toBeDefined();

    // Drive telemetry
    const finalOutput = chunks.at(-1);
    integration.onStart?.({
      model,
      messages: [{ role: "user", content: "What color is the sky?" }],
    });
    integration.onStepStart?.({
      stepNumber: 0,
      messages: [{ role: "user", content: "What color is the sky?" }],
    });
    await integration.onStepFinish?.({
      stepNumber: 0,
      text: JSON.stringify(finalOutput),
      usage: await streamResult.usage,
      finishReason: await streamResult.finishReason,
    });
    await integration.onFinish?.({
      text: JSON.stringify(finalOutput),
      object: finalOutput,
      usage: await streamResult.usage,
      totalUsage: await streamResult.usage,
      finishReason: await streamResult.finishReason,
      steps: [
        {
          text: JSON.stringify(finalOutput),
          usage: await streamResult.usage,
          finishReason: await streamResult.finishReason,
        },
      ],
    });

    await client.awaitPendingTraceBatches();

    const postBodies = await Promise.all(
      callSpy.mock.calls
        .filter((call) => call[1]!.method === "POST")
        .map((call) => new Response(call[1]!.body).json())
    );

    const rootRun = postBodies.find((b) => b.run_type === "chain");
    const stepRun = postBodies.find((b) => b.run_type === "llm");
    expect(rootRun).toBeDefined();
    expect(stepRun).toBeDefined();
    expect(stepRun!.parent_run_id).toBe(rootRun!.id);
  });

  test.skip("telemetry stream cancellation should finish spans cleanly", async () => {
    const { client, callSpy } = mockClient();

    const integration = createLangSmithTelemetry({
      client: client as any,
    });

    const model = anthropic("claude-3-5-haiku-latest");

    const abortController = new AbortController();

    const streamResult = ai.streamText({
      model,
      messages: [
        {
          role: "user",
          content: "Tell me a long story about a cat.",
        },
      ],
      abortSignal: abortController.signal,
    });

    // Drive onStart and onStepStart
    integration.onStart?.({
      model,
      messages: [
        { role: "user", content: "Tell me a long story about a cat." },
      ],
    });
    integration.onStepStart?.({
      stepNumber: 0,
      messages: [
        { role: "user", content: "Tell me a long story about a cat." },
      ],
    });

    let i = 0;
    let collectedText = "";
    try {
      for await (const chunk of streamResult.fullStream) {
        if (chunk.type === "text-delta") {
          collectedText += chunk.textDelta;
          integration.onChunk?.({ type: "text-delta", delta: chunk.textDelta });
          if (i++ > 5) {
            abortController.abort();
          }
        }
      }
    } catch {
      // Abort will throw — treat as error
      await integration.onError?.(new Error("Stream aborted by user"));
    }

    await client.awaitPendingTraceBatches();

    const patchBodies = await Promise.all(
      callSpy.mock.calls
        .filter((call) => call[1]!.method === "PATCH")
        .map((call) => new Response(call[1]!.body).json())
    );

    // Both step and root should be closed (with error)
    const errorUpdates = patchBodies.filter((b) => b.error);
    expect(errorUpdates.length).toBe(2);
  });

  // Skipped due to high token usage
  test.skip("anthropic cache read and write tokens", async () => {
    const { client, callSpy } = mockClient();

    const integration = createLangSmithTelemetry({
      client: client as any,
    });

    const model = anthropic("claude-3-5-haiku-20241022");

    const errorMessage = generateLongContext();

    // First call - creates cache with long error message
    const res1 = await ai.generateText({
      model,
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
    });

    // Drive telemetry for first call
    integration.onStart?.({
      model,
      messages: [
        {
          role: "user",
          content: "Cache create call",
        },
      ],
    });
    integration.onStepStart?.({
      stepNumber: 0,
      messages: [{ role: "user", content: "Cache create call" }],
    });
    await integration.onStepFinish?.({
      stepNumber: 0,
      text: res1.text,
      usage: res1.usage,
      finishReason: res1.finishReason,
      providerMetadata: res1.providerMetadata,
    });
    await integration.onFinish?.({
      text: res1.text,
      usage: res1.usage,
      totalUsage: res1.usage,
      finishReason: res1.finishReason,
      providerMetadata: res1.providerMetadata,
      steps: [
        {
          text: res1.text,
          usage: res1.usage,
          finishReason: res1.finishReason,
        },
      ],
    });

    await client.awaitPendingTraceBatches();

    const patchBodies = await Promise.all(
      callSpy.mock.calls
        .filter((call) => call[1]!.method === "PATCH")
        .map((call) => new Response(call[1]!.body).json())
    );

    const stepUpdate = patchBodies.find(
      (b) => b.extra?.metadata?.usage_metadata
    );
    expect(stepUpdate).toBeDefined();
    const usageMetadata = stepUpdate!.extra.metadata.usage_metadata;
    expect(usageMetadata.input_tokens).toBeGreaterThan(0);
  });
});
