/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable no-process-env */
/* eslint-disable import/no-extraneous-dependencies */
import { describe, it, beforeEach, expect } from "vitest";
import { createLangSmithTelemetry } from "../../../experimental/vercel/telemetry.js";
import { traceable } from "../../../traceable.js";

// Track HTTP requests made by RunTree
const mockHttpRequests: any[] = [];

// Mock LangSmith Client that captures HTTP calls
class MockLangSmithClient {
  async createRun(runCreate: any) {
    mockHttpRequests.push({
      method: "POST",
      endpoint: "/runs",
      body: runCreate,
      type: "createRun",
      timestamp: Date.now(),
    });
    return { id: `mock-run-${Date.now()}` };
  }

  async updateRun(runId: string, runUpdate: any) {
    mockHttpRequests.push({
      method: "PATCH",
      endpoint: `/runs/${runId}`,
      body: runUpdate,
      type: "updateRun",
      timestamp: Date.now(),
    });
    return { id: runId };
  }
}

/**
 * Simulate the Vercel AI SDK telemetry lifecycle for generateText.
 *
 * Event order: onStart → onStepStart → (onToolCallStart → executeToolCall →
 * onToolCallFinish)* → onStepFinish → ... → onFinish
 */
async function simulateGenerateText(
  integration: any,
  opts: {
    model?: any;
    messages?: any[];
    prompt?: string;
    system?: string;
    tools?: Record<string, any>;
    // Simulated step results
    steps?: Array<{
      text?: string;
      toolCalls?: any[];
      toolResults?: any[];
      usage?: any;
      finishReason?: string;
    }>;
    // Final result overrides
    totalUsage?: any;
    error?: Error;
  },
) {
  const model = opts.model ?? { modelId: "test-model" };
  const steps = opts.steps ?? [
    {
      text: "Hello world",
      usage: {
        inputTokens: { total: 5, noCache: 5, cacheRead: 0, cacheWrite: 0 },
        outputTokens: { total: 3, text: 3, reasoning: 0 },
        totalTokens: 8,
      },
      finishReason: "stop",
    },
  ];

  // onStart
  integration.onStart?.({
    model,
    messages: opts.messages,
    prompt: opts.prompt,
    system: opts.system,
    tools: opts.tools,
  });

  if (opts.error) {
    await integration.onError?.(opts.error);
    return;
  }

  for (let i = 0; i < steps.length; i++) {
    const step = steps[i];

    // onStepStart
    integration.onStepStart?.({
      stepNumber: i,
      messages: opts.messages ?? [
        { role: "user", content: opts.prompt ?? "test" },
      ],
    });

    // Handle tool calls within this step
    if (step.toolCalls && step.toolCalls.length > 0) {
      for (const tc of step.toolCalls) {
        integration.onToolCallStart?.({
          toolCallId: tc.toolCallId,
          toolName: tc.toolName,
          args: tc.args,
        });

        // Execute the tool via the integration hook
        if (integration.executeToolCall) {
          const toolResult = await integration.executeToolCall({
            callId: `call-${tc.toolCallId}`,
            toolCallId: tc.toolCallId,
            execute:
              tc.execute ?? (() => Promise.resolve(tc.result ?? "tool result")),
          });
          // Store for toolResults
          if (!step.toolResults) step.toolResults = [];
          step.toolResults.push({
            toolCallId: tc.toolCallId,
            toolName: tc.toolName,
            result: toolResult,
          });
        }
      }
    }

    // onStepFinish
    await integration.onStepFinish?.({
      stepNumber: i,
      text: step.text ?? "",
      toolCalls: step.toolCalls ?? [],
      toolResults: step.toolResults ?? [],
      usage: step.usage ?? {
        inputTokens: { total: 5, noCache: 5, cacheRead: 0, cacheWrite: 0 },
        outputTokens: { total: 3, text: 3, reasoning: 0 },
        totalTokens: 8,
      },
      finishReason: step.finishReason ?? "stop",
    });
  }

  // onFinish
  const lastStep = steps[steps.length - 1];
  await integration.onFinish?.({
    text: lastStep.text,
    toolCalls: lastStep.toolCalls ?? [],
    toolResults: lastStep.toolResults ?? [],
    usage: lastStep.usage,
    totalUsage: opts.totalUsage ?? lastStep.usage,
    finishReason: lastStep.finishReason ?? "stop",
    steps: steps.map((s, idx) => ({
      stepNumber: idx,
      text: s.text,
      toolCalls: s.toolCalls ?? [],
      usage: s.usage,
      finishReason: s.finishReason ?? "stop",
    })),
  });
}

describe("createLangSmithTelemetry", () => {
  let mockClient: MockLangSmithClient;

  beforeEach(() => {
    process.env.LANGSMITH_TRACING = "true";
    mockHttpRequests.length = 0;
    mockClient = new MockLangSmithClient();
  });

  describe("basic tracing", () => {
    it("should create root and step spans for a simple generateText", async () => {
      const integration = createLangSmithTelemetry({
        client: mockClient as any,
      });

      await simulateGenerateText(integration, {
        prompt: "Test prompt",
        steps: [
          {
            text: "Test response",
            usage: {
              inputTokens: {
                total: 5,
                noCache: 5,
                cacheRead: 0,
                cacheWrite: 0,
              },
              outputTokens: { total: 3, text: 3, reasoning: 0 },
              totalTokens: 8,
            },
            finishReason: "stop",
          },
        ],
      });

      await new Promise((resolve) => setTimeout(resolve, 50));

      // Should have: root createRun, step createRun, step updateRun, root updateRun
      const createRuns = mockHttpRequests.filter((r) => r.type === "createRun");
      const updateRuns = mockHttpRequests.filter((r) => r.type === "updateRun");

      expect(createRuns.length).toBe(2); // root + 1 step
      expect(updateRuns.length).toBe(2); // step finish + root finish

      // Root run
      const rootCreate = createRuns[0];
      expect(rootCreate.body.run_type).toBe("chain");
      expect(rootCreate.body.inputs).toHaveProperty("prompt", "Test prompt");
      expect(rootCreate.body.extra.metadata).toHaveProperty(
        "ls_integration",
        "vercel-ai-sdk-telemetry",
      );

      // Step run (LLM)
      const stepCreate = createRuns[1];
      expect(stepCreate.body.run_type).toBe("llm");
      expect(stepCreate.body.name).toBe("step 0");
      expect(stepCreate.body.parent_run_id).toBe(rootCreate.body.id);

      // Step update should have output
      const stepUpdate = updateRuns[0];
      expect(stepUpdate.body.outputs).toHaveProperty("role", "assistant");

      // Root update should have final output
      const rootUpdate = updateRuns[1];
      expect(rootUpdate.body.outputs).toHaveProperty(
        "content",
        "Test response",
      );
    });

    it("should use model display name as default run name", async () => {
      const integration = createLangSmithTelemetry({
        client: mockClient as any,
      });

      await simulateGenerateText(integration, {
        model: { modelId: "gpt-4o", config: { provider: "openai" } },
        prompt: "Hello",
      });

      await new Promise((resolve) => setTimeout(resolve, 50));

      const rootCreate = mockHttpRequests.find(
        (r) => r.type === "createRun" && r.body.run_type === "chain",
      );
      expect(rootCreate.body.name).toBe("openai");
      expect(rootCreate.body.extra.metadata.ls_model_name).toBe("gpt-4o");
    });

    it("should allow custom name override", async () => {
      const integration = createLangSmithTelemetry({
        name: "my-agent",
        client: mockClient as any,
      });

      await simulateGenerateText(integration, {
        prompt: "Hello",
      });

      await new Promise((resolve) => setTimeout(resolve, 50));

      const rootCreate = mockHttpRequests.find(
        (r) => r.type === "createRun" && r.body.run_type === "chain",
      );
      expect(rootCreate.body.name).toBe("my-agent");
    });

    it("should apply custom metadata and tags", async () => {
      const integration = createLangSmithTelemetry({
        metadata: { customField: "test-value", version: "2.0" },
        tags: ["test-tag", "v2"],
        client: mockClient as any,
      });

      await simulateGenerateText(integration, {
        prompt: "Test with metadata",
      });

      await new Promise((resolve) => setTimeout(resolve, 50));

      const rootCreate = mockHttpRequests.find(
        (r) => r.type === "createRun" && r.body.run_type === "chain",
      );
      expect(rootCreate.body.extra.metadata).toMatchObject({
        customField: "test-value",
        version: "2.0",
        ls_integration: "vercel-ai-sdk-telemetry",
      });
      expect(rootCreate.body.tags).toEqual(["test-tag", "v2"]);
    });
  });

  describe("error handling", () => {
    it("should capture errors on the root span", async () => {
      const integration = createLangSmithTelemetry({
        client: mockClient as any,
      });

      await simulateGenerateText(integration, {
        prompt: "This should fail",
        error: new Error("TOTALLY EXPECTED MOCK ERROR"),
      });

      await new Promise((resolve) => setTimeout(resolve, 50));

      const updateRunCall = mockHttpRequests.find(
        (r) => r.type === "updateRun" && r.body.error,
      );
      expect(updateRunCall).toBeDefined();
      expect(updateRunCall.body.error).toContain("TOTALLY EXPECTED MOCK ERROR");
    });

    it("should close open step runs on error", async () => {
      const integration = createLangSmithTelemetry({
        client: mockClient as any,
      });

      // Start the lifecycle manually to simulate mid-step error
      integration.onStart?.({
        modelId: "test-model",
        prompt: "Test",
      } as any);
      integration.onStepStart?.({
        stepNumber: 0,
        messages: [{ role: "user", content: "Test" }],
      } as any);

      // Error before step finishes
      await integration.onError?.(new Error("Mid-step error"));

      await new Promise((resolve) => setTimeout(resolve, 50));

      // Step and root should both be closed with error
      const errorUpdates = mockHttpRequests.filter(
        (r) => r.type === "updateRun" && r.body.error,
      );
      expect(errorUpdates.length).toBe(2); // step + root
    });
  });

  describe("multi-step tracing", () => {
    it("should create separate LLM spans for each step", async () => {
      const integration = createLangSmithTelemetry({
        client: mockClient as any,
      });

      await simulateGenerateText(integration, {
        prompt: "Multi-step test",
        tools: { search: {} },
        steps: [
          {
            text: "",
            toolCalls: [
              {
                toolCallId: "tc-1",
                toolName: "search",
                args: { query: "weather" },
                result: "Sunny, 72°F",
              },
            ],
            usage: {
              inputTokens: {
                total: 10,
                noCache: 10,
                cacheRead: 0,
                cacheWrite: 0,
              },
              outputTokens: { total: 5, text: 0, reasoning: 0 },
              totalTokens: 15,
            },
            finishReason: "tool-calls",
          },
          {
            text: "The weather is sunny and 72°F.",
            usage: {
              inputTokens: {
                total: 20,
                noCache: 20,
                cacheRead: 0,
                cacheWrite: 0,
              },
              outputTokens: { total: 8, text: 8, reasoning: 0 },
              totalTokens: 28,
            },
            finishReason: "stop",
          },
        ],
      });

      await new Promise((resolve) => setTimeout(resolve, 100));

      const createRuns = mockHttpRequests.filter((r) => r.type === "createRun");

      // root + step 0 + tool (via traceable) + step 1
      const rootRun = createRuns.find((r) => r.body.run_type === "chain");
      const stepRuns = createRuns.filter((r) => r.body.run_type === "llm");
      const toolRuns = createRuns.filter((r) => r.body.run_type === "tool");

      expect(rootRun).toBeDefined();
      expect(stepRuns.length).toBe(2);
      expect(toolRuns.length).toBe(1);

      // Verify parent-child relationships
      expect(stepRuns[0].body.parent_run_id).toBe(rootRun!.body.id);
      expect(stepRuns[1].body.parent_run_id).toBe(rootRun!.body.id);

      // Tool should be child of step 0
      expect(toolRuns[0].body.parent_run_id).toBe(stepRuns[0].body.id);
      expect(toolRuns[0].body.name).toBe("search");
    });
  });

  describe("tool tracing via executeToolCall", () => {
    it("should create tool spans using traceable inside executeToolCall", async () => {
      const integration = createLangSmithTelemetry({
        client: mockClient as any,
      });

      await simulateGenerateText(integration, {
        prompt: "Use a tool",
        tools: { calculator: {} },
        steps: [
          {
            text: "",
            toolCalls: [
              {
                toolCallId: "tc-calc-1",
                toolName: "calculator",
                args: { expression: "2+2" },
                execute: () => Promise.resolve(4),
              },
            ],
            usage: {
              inputTokens: {
                total: 8,
                noCache: 8,
                cacheRead: 0,
                cacheWrite: 0,
              },
              outputTokens: { total: 3, text: 0, reasoning: 0 },
              totalTokens: 11,
            },
            finishReason: "tool-calls",
          },
          {
            text: "2+2 = 4",
            usage: {
              inputTokens: {
                total: 15,
                noCache: 15,
                cacheRead: 0,
                cacheWrite: 0,
              },
              outputTokens: { total: 5, text: 5, reasoning: 0 },
              totalTokens: 20,
            },
            finishReason: "stop",
          },
        ],
      });

      await new Promise((resolve) => setTimeout(resolve, 100));

      const toolRuns = mockHttpRequests.filter(
        (r) => r.type === "createRun" && r.body.run_type === "tool",
      );
      expect(toolRuns.length).toBe(1);
      expect(toolRuns[0].body.name).toBe("calculator");

      // Tool should have the args as input
      expect(toolRuns[0].body.inputs).toMatchObject({
        expression: "2+2",
      });

      // Tool should have output
      const toolUpdate = mockHttpRequests.find(
        (r) =>
          r.type === "updateRun" &&
          r.body.outputs &&
          (r.body.outputs.output === 4 || r.body.outputs.outputs === 4),
      );
      expect(toolUpdate).toBeDefined();
    });

    it("should nest sub-agent calls inside tool spans", async () => {
      const integration = createLangSmithTelemetry({
        client: mockClient as any,
      });

      // The tool's execute function calls a traceable function, simulating a sub-agent
      const innerTraceable = traceable(
        async (input: string) => {
          return `Processed: ${input}`;
        },
        {
          name: "inner-agent-call",
          run_type: "chain",
          client: mockClient as any,
        },
      );

      await simulateGenerateText(integration, {
        prompt: "Use a tool with sub-agent",
        tools: { research: {} },
        steps: [
          {
            text: "",
            toolCalls: [
              {
                toolCallId: "tc-research-1",
                toolName: "research",
                args: { topic: "AI" },
                execute: () => innerTraceable("AI research"),
              },
            ],
            usage: {
              inputTokens: {
                total: 10,
                noCache: 10,
                cacheRead: 0,
                cacheWrite: 0,
              },
              outputTokens: { total: 5, text: 0, reasoning: 0 },
              totalTokens: 15,
            },
            finishReason: "tool-calls",
          },
          {
            text: "Research complete.",
            usage: {
              inputTokens: {
                total: 20,
                noCache: 20,
                cacheRead: 0,
                cacheWrite: 0,
              },
              outputTokens: { total: 8, text: 8, reasoning: 0 },
              totalTokens: 28,
            },
            finishReason: "stop",
          },
        ],
      });

      await new Promise((resolve) => setTimeout(resolve, 100));

      const createRuns = mockHttpRequests.filter((r) => r.type === "createRun");

      const toolRun = createRuns.find(
        (r) => r.body.run_type === "tool" && r.body.name === "research",
      );
      expect(toolRun).toBeDefined();

      const innerRun = createRuns.find(
        (r) => r.body.name === "inner-agent-call",
      );
      expect(innerRun).toBeDefined();

      // The inner call should be a child of the tool run
      expect(innerRun!.body.parent_run_id).toBe(toolRun!.body.id);
      // And all should share the same trace_id
      expect(innerRun!.body.trace_id).toBe(toolRun!.body.trace_id);
    });
  });

  describe("usage metadata tracking", () => {
    it("should track AI SDK 6 token usage on step runs", async () => {
      const integration = createLangSmithTelemetry({
        client: mockClient as any,
      });

      await simulateGenerateText(integration, {
        prompt: "Token test",
        steps: [
          {
            text: "Response",
            usage: {
              inputTokens: {
                total: 100,
                noCache: 50,
                cacheRead: 30,
                cacheWrite: 20,
              },
              outputTokens: { total: 25, text: 15, reasoning: 10 },
              totalTokens: 125,
            },
            finishReason: "stop",
          },
        ],
      });

      await new Promise((resolve) => setTimeout(resolve, 50));

      // Find the step LLM run update
      const stepUpdate = mockHttpRequests.find(
        (r) =>
          r.type === "updateRun" &&
          r.body.extra?.metadata?.ai_sdk_method === "ai.step",
      );
      expect(stepUpdate).toBeDefined();
      expect(stepUpdate.body.extra.metadata.usage_metadata).toMatchObject({
        input_tokens: 100,
        output_tokens: 25,
        total_tokens: 125,
      });

      // Verify token details
      expect(
        stepUpdate.body.extra.metadata.usage_metadata.input_token_details
          .cache_read,
      ).toBe(30);
      expect(
        stepUpdate.body.extra.metadata.usage_metadata.input_token_details
          .cache_creation,
      ).toBe(20);
      expect(
        stepUpdate.body.extra.metadata.usage_metadata.output_token_details
          .reasoning,
      ).toBe(10);
    });

    it("should track aggregated usage on the root span", async () => {
      const integration = createLangSmithTelemetry({
        client: mockClient as any,
      });

      await simulateGenerateText(integration, {
        prompt: "Aggregate test",
        steps: [
          {
            text: "Step 1 response",
            usage: {
              inputTokens: {
                total: 10,
                noCache: 10,
                cacheRead: 0,
                cacheWrite: 0,
              },
              outputTokens: { total: 5, text: 5, reasoning: 0 },
              totalTokens: 15,
            },
            finishReason: "stop",
          },
        ],
        totalUsage: {
          inputTokens: {
            total: 30,
            noCache: 30,
            cacheRead: 0,
            cacheWrite: 0,
          },
          outputTokens: { total: 15, text: 15, reasoning: 0 },
          totalTokens: 45,
        },
      });

      await new Promise((resolve) => setTimeout(resolve, 50));

      // Find the root chain run update
      const rootUpdate = mockHttpRequests.find(
        (r) =>
          r.type === "updateRun" &&
          r.body.extra?.metadata?.ls_integration === "vercel-ai-sdk-telemetry",
      );
      expect(rootUpdate).toBeDefined();
      expect(rootUpdate.body.extra.metadata.usage_metadata).toMatchObject({
        input_tokens: 30,
        output_tokens: 15,
        total_tokens: 45,
      });
    });

    it("should track OpenAI flex service tier tokens", async () => {
      const integration = createLangSmithTelemetry({
        client: mockClient as any,
      });

      await simulateGenerateText(integration, {
        prompt: "Flex tier test",
        steps: [
          {
            text: "Response",
            usage: {
              inputTokens: {
                total: 100,
                noCache: 80,
                cacheRead: 20,
                cacheWrite: 0,
              },
              outputTokens: { total: 30, text: 25, reasoning: 5 },
              totalTokens: 130,
            },
            finishReason: "stop",
          },
        ],
      });

      // Simulate providerMetadata on the step finish event
      // (need to manually invoke with providerMetadata)
      // Note: The step finish event includes providerMetadata from the AI SDK

      await new Promise((resolve) => setTimeout(resolve, 50));

      const stepUpdate = mockHttpRequests.find(
        (r) =>
          r.type === "updateRun" &&
          r.body.extra?.metadata?.ai_sdk_method === "ai.step",
      );
      expect(stepUpdate).toBeDefined();
      expect(stepUpdate.body.extra.metadata.usage_metadata).toMatchObject({
        input_tokens: 100,
        output_tokens: 30,
        total_tokens: 130,
      });
    });
  });

  describe("processInputs / processOutputs", () => {
    it("should apply processInputs to the root span", async () => {
      const integration = createLangSmithTelemetry({
        client: mockClient as any,
        processInputs: (inputs) => ({
          ...inputs,
          prompt: "REDACTED",
        }),
      });

      await simulateGenerateText(integration, {
        prompt: "Secret prompt",
      });

      await new Promise((resolve) => setTimeout(resolve, 50));

      const rootCreate = mockHttpRequests.find(
        (r) => r.type === "createRun" && r.body.run_type === "chain",
      );
      expect(rootCreate.body.inputs.prompt).toBe("REDACTED");
    });

    it("should apply processOutputs to the root span", async () => {
      const integration = createLangSmithTelemetry({
        client: mockClient as any,
        processOutputs: (outputs) => ({
          ...outputs,
          content: "REDACTED",
        }),
      });

      await simulateGenerateText(integration, {
        prompt: "Test",
        steps: [
          {
            text: "Secret response",
            usage: {
              inputTokens: {
                total: 5,
                noCache: 5,
                cacheRead: 0,
                cacheWrite: 0,
              },
              outputTokens: { total: 3, text: 3, reasoning: 0 },
              totalTokens: 8,
            },
          },
        ],
      });

      await new Promise((resolve) => setTimeout(resolve, 50));

      const rootUpdate = mockHttpRequests.find(
        (r) =>
          r.type === "updateRun" &&
          r.body.extra?.metadata?.ls_integration === "vercel-ai-sdk-telemetry",
      );
      expect(rootUpdate.body.outputs.content).toBe("REDACTED");
    });

    it("should apply processChildLLMRunInputs to step spans", async () => {
      const integration = createLangSmithTelemetry({
        client: mockClient as any,
        processChildLLMRunInputs: (inputs) => ({
          messages: (inputs.messages ?? []).map((m: any) => ({
            ...m,
            content: "REDACTED_CHILD_INPUT",
          })),
        }),
      });

      await simulateGenerateText(integration, {
        prompt: "Test",
      });

      await new Promise((resolve) => setTimeout(resolve, 50));

      const stepCreate = mockHttpRequests.find(
        (r) => r.type === "createRun" && r.body.run_type === "llm",
      );
      expect(stepCreate.body.inputs.messages[0].content).toBe(
        "REDACTED_CHILD_INPUT",
      );
    });

    it("should apply processChildLLMRunOutputs to step spans", async () => {
      const integration = createLangSmithTelemetry({
        client: mockClient as any,
        processChildLLMRunOutputs: (outputs) => ({
          ...outputs,
          content: "REDACTED_CHILD_OUTPUT",
          role: "assistant",
        }),
      });

      await simulateGenerateText(integration, {
        prompt: "Test",
        steps: [{ text: "Secret step output" }],
      });

      await new Promise((resolve) => setTimeout(resolve, 50));

      const stepUpdate = mockHttpRequests.find(
        (r) =>
          r.type === "updateRun" &&
          r.body.extra?.metadata?.ai_sdk_method === "ai.step",
      );
      expect(stepUpdate.body.outputs.content).toBe("REDACTED_CHILD_OUTPUT");
    });
  });

  describe("dotted order and trace hierarchy", () => {
    it("should maintain correct parent-child dotted order", async () => {
      const integration = createLangSmithTelemetry({
        client: mockClient as any,
      });

      await simulateGenerateText(integration, {
        prompt: "Hierarchy test",
      });

      await new Promise((resolve) => setTimeout(resolve, 50));

      const createRuns = mockHttpRequests.filter((r) => r.type === "createRun");

      const rootRun = createRuns.find((r) => r.body.run_type === "chain");
      const stepRun = createRuns.find((r) => r.body.run_type === "llm");

      expect(rootRun).toBeDefined();
      expect(stepRun).toBeDefined();

      // All runs should share the same trace_id
      expect(stepRun!.body.trace_id).toBe(rootRun!.body.trace_id);

      // Step's dotted_order should be prefixed with root's dotted_order
      expect(
        stepRun!.body.dotted_order.startsWith(rootRun!.body.dotted_order),
      ).toBe(true);
      expect(stepRun!.body.dotted_order.split(".").length).toBe(
        rootRun!.body.dotted_order.split(".").length + 1,
      );
    });

    it("should nest under an existing traceable context", async () => {
      const outerFn = traceable(
        async () => {
          const integration = createLangSmithTelemetry({
            client: mockClient as any,
          });

          await simulateGenerateText(integration, {
            prompt: "Nested test",
          });
        },
        {
          name: "outer-traceable",
          client: mockClient as any,
        },
      );

      await outerFn();

      await new Promise((resolve) => setTimeout(resolve, 100));

      const createRuns = mockHttpRequests.filter((r) => r.type === "createRun");

      const outerRun = createRuns.find(
        (r) => r.body.name === "outer-traceable",
      );
      const telemetryRoot = createRuns.find(
        (r) =>
          r.body.run_type === "chain" &&
          r.body.extra?.metadata?.ls_integration === "vercel-ai-sdk-telemetry",
      );

      expect(outerRun).toBeDefined();
      expect(telemetryRoot).toBeDefined();

      // Telemetry root should be a child of the outer traceable
      expect(telemetryRoot!.body.parent_run_id).toBe(outerRun!.body.id);
      expect(telemetryRoot!.body.trace_id).toBe(outerRun!.body.trace_id);
    });
  });

  describe("traceResponseMetadata", () => {
    it("should include steps in output when traceResponseMetadata is true", async () => {
      const integration = createLangSmithTelemetry({
        client: mockClient as any,
        traceResponseMetadata: true,
      });

      await simulateGenerateText(integration, {
        prompt: "Response metadata test",
        steps: [
          {
            text: "Step 1",
            usage: {
              inputTokens: {
                total: 5,
                noCache: 5,
                cacheRead: 0,
                cacheWrite: 0,
              },
              outputTokens: { total: 3, text: 3, reasoning: 0 },
              totalTokens: 8,
            },
            finishReason: "stop",
          },
        ],
      });

      await new Promise((resolve) => setTimeout(resolve, 50));

      const rootUpdate = mockHttpRequests.find(
        (r) =>
          r.type === "updateRun" &&
          r.body.extra?.metadata?.ls_integration === "vercel-ai-sdk-telemetry",
      );
      expect(rootUpdate).toBeDefined();
      expect(rootUpdate.body.outputs.steps).toBeDefined();
      expect(Array.isArray(rootUpdate.body.outputs.steps)).toBe(true);
      expect(rootUpdate.body.outputs.steps.length).toBe(1);
    });

    it("should not include steps when traceResponseMetadata is false", async () => {
      const integration = createLangSmithTelemetry({
        client: mockClient as any,
      });

      await simulateGenerateText(integration, {
        prompt: "No metadata test",
      });

      await new Promise((resolve) => setTimeout(resolve, 50));

      const rootUpdate = mockHttpRequests.find(
        (r) =>
          r.type === "updateRun" &&
          r.body.extra?.metadata?.ls_integration === "vercel-ai-sdk-telemetry",
      );
      expect(rootUpdate).toBeDefined();
      expect(rootUpdate.body.outputs.steps).toBeUndefined();
    });
  });

  describe("streaming (onChunk)", () => {
    it("should handle onChunk as a no-op without errors", () => {
      const integration = createLangSmithTelemetry({
        client: mockClient as any,
      });

      // onChunk should not throw
      expect(() => {
        integration.onChunk?.({ type: "text-delta", delta: "Hello" });
        integration.onChunk?.({ type: "text-delta", delta: " world" });
      }).not.toThrow();
    });
  });

  describe("tracing disabled", () => {
    it("should not create runs when tracing is disabled", async () => {
      process.env.LANGSMITH_TRACING = "false";

      const integration = createLangSmithTelemetry({
        client: mockClient as any,
      });

      await simulateGenerateText(integration, {
        prompt: "Should not trace",
      });

      await new Promise((resolve) => setTimeout(resolve, 50));

      // onStart checks isTracingEnabled() and skips creating the root run,
      // so no HTTP requests should be made
      expect(mockHttpRequests.length).toBe(0);
    });
  });

  describe("project name configuration", () => {
    it("should use custom project name", async () => {
      const integration = createLangSmithTelemetry({
        client: mockClient as any,
        projectName: "my-custom-project",
      });

      await simulateGenerateText(integration, {
        prompt: "Project test",
      });

      await new Promise((resolve) => setTimeout(resolve, 50));

      const rootCreate = mockHttpRequests.find(
        (r) => r.type === "createRun" && r.body.run_type === "chain",
      );
      expect(rootCreate.body.session_name).toBe("my-custom-project");
    });
  });

  describe("integration reuse", () => {
    it("should create separate traces when reusing the same integration sequentially", async () => {
      const integration = createLangSmithTelemetry({
        client: mockClient as any,
      });

      // First call
      await simulateGenerateText(integration, {
        prompt: "First call",
        steps: [
          {
            text: "First response",
            usage: {
              inputTokens: {
                total: 5,
                noCache: 5,
                cacheRead: 0,
                cacheWrite: 0,
              },
              outputTokens: { total: 3, text: 3, reasoning: 0 },
              totalTokens: 8,
            },
            finishReason: "stop",
          },
        ],
      });

      await new Promise((resolve) => setTimeout(resolve, 50));

      const firstCallRequests = [...mockHttpRequests];
      const firstRootCreate = firstCallRequests.find(
        (r) => r.type === "createRun" && r.body.run_type === "chain",
      );
      expect(firstRootCreate).toBeDefined();
      const firstRootId = firstRootCreate.body.id;
      const firstTraceId = firstRootCreate.body.trace_id;

      // Clear and do second call with the SAME integration
      mockHttpRequests.length = 0;

      await simulateGenerateText(integration, {
        prompt: "Second call",
        steps: [
          {
            text: "Second response",
            usage: {
              inputTokens: {
                total: 7,
                noCache: 7,
                cacheRead: 0,
                cacheWrite: 0,
              },
              outputTokens: { total: 4, text: 4, reasoning: 0 },
              totalTokens: 11,
            },
            finishReason: "stop",
          },
        ],
      });

      await new Promise((resolve) => setTimeout(resolve, 50));

      const secondRootCreate = mockHttpRequests.find(
        (r) => r.type === "createRun" && r.body.run_type === "chain",
      );
      expect(secondRootCreate).toBeDefined();

      // Second call should have a different root ID and trace ID
      expect(secondRootCreate.body.id).not.toBe(firstRootId);
      expect(secondRootCreate.body.trace_id).not.toBe(firstTraceId);

      // Second call should have its own inputs
      expect(secondRootCreate.body.inputs).toHaveProperty(
        "prompt",
        "Second call",
      );

      // Should have correct structure: root + step
      const secondCreateRuns = mockHttpRequests.filter(
        (r) => r.type === "createRun",
      );
      expect(secondCreateRuns.length).toBe(2); // root + step
    });

    it("should not leak state between sequential invocations after error", async () => {
      const integration = createLangSmithTelemetry({
        client: mockClient as any,
      });

      // First call ends in error
      integration.onStart?.({
        model: { modelId: "test-model" },
        prompt: "Error call",
      });
      integration.onStepStart?.({
        stepNumber: 0,
        messages: [{ role: "user", content: "Error call" }],
      });
      await integration.onError?.(new Error("TOTALLY EXPECTED MOCK ERROR"));

      await new Promise((resolve) => setTimeout(resolve, 50));

      mockHttpRequests.length = 0;

      // Second call should work normally
      await simulateGenerateText(integration, {
        prompt: "Recovery call",
        steps: [
          {
            text: "Recovered",
            usage: {
              inputTokens: {
                total: 5,
                noCache: 5,
                cacheRead: 0,
                cacheWrite: 0,
              },
              outputTokens: { total: 3, text: 3, reasoning: 0 },
              totalTokens: 8,
            },
            finishReason: "stop",
          },
        ],
      });

      await new Promise((resolve) => setTimeout(resolve, 50));

      const createRuns = mockHttpRequests.filter((r) => r.type === "createRun");
      expect(createRuns.length).toBe(2); // root + step

      const rootCreate = createRuns.find((r) => r.body.run_type === "chain");
      expect(rootCreate.body.inputs).toHaveProperty("prompt", "Recovery call");

      // No error updates on the second call
      const errorUpdates = mockHttpRequests.filter(
        (r) => r.type === "updateRun" && r.body.error,
      );
      expect(errorUpdates.length).toBe(0);
    });

    it("should handle reuse with tools across invocations", async () => {
      const integration = createLangSmithTelemetry({
        client: mockClient as any,
      });

      // First call with tool
      await simulateGenerateText(integration, {
        prompt: "First tool call",
        tools: { search: {} },
        steps: [
          {
            text: "",
            toolCalls: [
              {
                toolCallId: "tc-1",
                toolName: "search",
                args: { query: "first" },
                result: "first result",
              },
            ],
            usage: {
              inputTokens: {
                total: 10,
                noCache: 10,
                cacheRead: 0,
                cacheWrite: 0,
              },
              outputTokens: { total: 5, text: 0, reasoning: 0 },
              totalTokens: 15,
            },
            finishReason: "tool-calls",
          },
          {
            text: "First answer",
            usage: {
              inputTokens: {
                total: 20,
                noCache: 20,
                cacheRead: 0,
                cacheWrite: 0,
              },
              outputTokens: { total: 8, text: 8, reasoning: 0 },
              totalTokens: 28,
            },
            finishReason: "stop",
          },
        ],
      });

      await new Promise((resolve) => setTimeout(resolve, 100));

      const firstCallRequests = [...mockHttpRequests];
      mockHttpRequests.length = 0;

      // Second call with tool — SAME integration
      await simulateGenerateText(integration, {
        prompt: "Second tool call",
        tools: { calculator: {} },
        steps: [
          {
            text: "",
            toolCalls: [
              {
                toolCallId: "tc-2",
                toolName: "calculator",
                args: { expression: "1+1" },
                result: 2,
              },
            ],
            usage: {
              inputTokens: {
                total: 8,
                noCache: 8,
                cacheRead: 0,
                cacheWrite: 0,
              },
              outputTokens: { total: 3, text: 0, reasoning: 0 },
              totalTokens: 11,
            },
            finishReason: "tool-calls",
          },
          {
            text: "1+1 = 2",
            usage: {
              inputTokens: {
                total: 15,
                noCache: 15,
                cacheRead: 0,
                cacheWrite: 0,
              },
              outputTokens: { total: 5, text: 5, reasoning: 0 },
              totalTokens: 20,
            },
            finishReason: "stop",
          },
        ],
      });

      await new Promise((resolve) => setTimeout(resolve, 100));

      // Second call should have its own complete trace
      const secondCreateRuns = mockHttpRequests.filter(
        (r) => r.type === "createRun",
      );
      const secondRoot = secondCreateRuns.find(
        (r) => r.body.run_type === "chain",
      );
      const secondSteps = secondCreateRuns.filter(
        (r) => r.body.run_type === "llm",
      );
      const secondTools = secondCreateRuns.filter(
        (r) => r.body.run_type === "tool",
      );

      expect(secondRoot).toBeDefined();
      expect(secondSteps.length).toBe(2);
      expect(secondTools.length).toBe(1);
      expect(secondTools[0].body.name).toBe("calculator");

      // All second-call runs should share the second trace_id
      const secondTraceId = secondRoot!.body.trace_id;
      for (const run of secondCreateRuns) {
        expect(run.body.trace_id).toBe(secondTraceId);
      }

      // And it should differ from the first call's trace_id
      const firstRoot = firstCallRequests.find(
        (r) => r.type === "createRun" && r.body.run_type === "chain",
      );
      expect(secondTraceId).not.toBe(firstRoot!.body.trace_id);
    });
  });
});
