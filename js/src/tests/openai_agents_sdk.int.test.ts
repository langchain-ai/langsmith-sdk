/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable no-process-env */
/* eslint-disable import/no-extraneous-dependencies */
import { describe, beforeAll, afterAll, test, expect } from "@jest/globals";
import {
  Agent,
  run,
  tool,
  setTraceProcessors,
  setTracingDisabled,
  handoff,
} from "@openai/agents";
import { z } from "zod";
import { OpenAIAgentsTracingProcessor } from "../wrappers/openai_agents.js";
import { Client } from "../client.js";

// Note: These tests require an OPENAI_API_KEY environment variable.
// They are skipped by default to avoid requiring API keys in CI.

describe("OpenAIAgentsTracingProcessor - Real API Integration", () => {
  let processor: OpenAIAgentsTracingProcessor;
  let client: Client;

  beforeAll(() => {
    if (!process.env.OPENAI_API_KEY) {
      throw new Error("OPENAI_API_KEY environment variable is required");
    }

    client = new Client();

    processor = new OpenAIAgentsTracingProcessor({
      client,
      metadata: {
        test: "openai-agents-sdk-integration",
      },
      tags: ["integration-test"],
    });

    // OpenAI Agents disables tracing by default when NODE_ENV=test.
    // Force-enable it for this integration test.
    setTracingDisabled(false);
    setTraceProcessors([processor]);
  });

  afterAll(async () => {
    // Clean up and flush any pending traces
    await processor.forceFlush();
    await client.awaitPendingTraceBatches();
  });

  test("simple agent run creates trace", async () => {
    const agent = new Agent({
      name: "TestAgent",
      instructions: "You are a helpful assistant. Be concise.",
      model: "gpt-5-nano",
    });

    const result = await run(
      agent,
      "Say 'Hello from LangSmith!' and nothing else."
    );

    console.log("Result:", {
      finalOutput: result.finalOutput,
      lastAgent: result.lastAgent?.name,
    });

    expect(result.finalOutput).toBeDefined();
    expect(typeof result.finalOutput).toBe("string");
  }, 30000);

  test("agent with tool creates nested spans", async () => {
    const weatherTool = tool({
      name: "get_weather",
      description: "Get the current weather for a city",
      parameters: z.object({
        city: z.string().describe("The city to get weather for"),
      }),
      execute: async ({ city }: { city: string }) => {
        // Mock weather data
        return JSON.stringify({
          city,
          temperature: "72°F",
          condition: "sunny",
        });
      },
    });

    const agent = new Agent({
      name: "WeatherAgent",
      instructions:
        "You are a weather assistant. Use the get_weather tool when asked about weather.",
      model: "gpt-5-nano",
      tools: [weatherTool],
    });

    const result = await run(agent, "What's the weather in San Francisco?");

    console.log("Weather result:", {
      finalOutput: result.finalOutput,
    });

    expect(result.finalOutput).toBeDefined();
  }, 60000);

  test("agent with handoff creates handoff span", async () => {
    // Create a specialist agent
    const haikuAgent = new Agent({
      name: "HaikuAgent",
      instructions: "You only respond in haikus (5-7-5 syllable pattern).",
      model: "gpt-5-nano",
    });

    // Create a main agent that can hand off
    const mainAgent = new Agent({
      name: "MainAgent",
      instructions:
        "You are a helpful assistant. If asked for a haiku, hand off to the HaikuAgent.",
      model: "gpt-5-nano",
      handoffs: [handoff(haikuAgent)],
    });

    const result = await run(mainAgent, "Write a haiku about coding.");

    console.log("Handoff result:", {
      finalOutput: result.finalOutput,
      lastAgent: result.lastAgent?.name,
    });

    expect(result.finalOutput).toBeDefined();
  }, 60000);

  test("streaming agent run creates trace", async () => {
    const agent = new Agent({
      name: "StreamingAgent",
      instructions: "You are a helpful assistant. Be concise.",
      model: "gpt-5-nano",
    });

    const streamedResult = await run(agent, "Count from 1 to 5.", {
      stream: true,
    });

    const events: any[] = [];
    for await (const event of streamedResult) {
      events.push(event);
    }

    // Wait for completion
    await streamedResult.completed;

    console.log("Streaming result:", {
      finalOutput: streamedResult.finalOutput,
      eventCount: events.length,
    });

    expect(streamedResult.finalOutput).toBeDefined();
    expect(events.length).toBeGreaterThan(0);
  }, 60000);

  test("agent with custom model settings", async () => {
    const agent = new Agent({
      name: "CustomAgent",
      instructions: "You are a helpful assistant.",
      model: "gpt-5-nano",
      modelSettings: {
        temperature: 0,
      },
    });

    const result = await run(agent, "Say 'test' and nothing else.");

    expect(result.finalOutput).toBeDefined();
  }, 30000);

  test("multiple runs create separate traces", async () => {
    const agent = new Agent({
      name: "MultiRunAgent",
      instructions: "You are a helpful assistant. Be very concise.",
      model: "gpt-5-nano",
    });

    // Run multiple times
    const results = await Promise.all([
      run(agent, "Say 'one'"),
      run(agent, "Say 'two'"),
      run(agent, "Say 'three'"),
    ]);

    expect(results).toHaveLength(3);
    results.forEach((result: any, idx: number) => {
      console.log(`Result ${idx + 1}:`, result.finalOutput);
      expect(result.finalOutput).toBeDefined();
    });

    // Flush to ensure all traces are sent
    await processor.forceFlush();
  }, 60000);
});
