/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, test, expect, jest, beforeEach } from "@jest/globals";
import { OpenAIAgentsTracingProcessor } from "../wrappers/openai_agents.js";
import { mockClient } from "./utils/mock_client.js";
import { getAssumedTreeFromCalls } from "./utils/tree.js";
import { traceable } from "../traceable.js";

// Mock types matching @openai/agents-core/tracing
type MockSpanData =
  | {
      type: "agent";
      name: string;
      handoffs?: string[];
      tools?: string[];
      output_type?: string;
    }
  | { type: "function"; name: string; input: string; output: string }
  | {
      type: "generation";
      name?: string;
      input?: any[];
      output?: any[];
      model?: string;
      model_config?: Record<string, unknown>;
      usage?: {
        input_tokens?: number;
        output_tokens?: number;
        details?: Record<string, unknown> | null;
      };
    }
  | {
      type: "response";
      name?: string;
      response_id?: string;
      _input?: string | Record<string, any>[];
      _response?: Record<string, any>;
    }
  | { type: "handoff"; name?: string; from_agent?: string; to_agent?: string }
  | { type: "guardrail"; name: string; triggered: boolean }
  | { type: "custom"; name: string; data: Record<string, any> };

interface MockSpan {
  type: "trace.span";
  traceId: string;
  spanId: string;
  parentId: string | null;
  spanData: MockSpanData;
  error: { message: string; data?: Record<string, unknown> } | null;
  startedAt: string | null;
  endedAt: string | null;
  toJSON(): object | null;
}

interface MockTrace {
  type: "trace";
  traceId: string;
  name: string;
  groupId: string | null;
  metadata?: Record<string, unknown>;
  toJSON(): object | null;
}

function createMockSpan(
  traceId: string,
  spanId: string,
  parentId: string | null,
  spanData: MockSpanData,
  options?: {
    startedAt?: string;
    endedAt?: string;
    error?: { message: string; data?: Record<string, unknown> };
  }
): MockSpan {
  return {
    type: "trace.span",
    traceId,
    spanId,
    parentId,
    spanData,
    error: options?.error ?? null,
    startedAt: options?.startedAt ?? new Date().toISOString(),
    endedAt: options?.endedAt ?? null,
    toJSON: () => ({
      traceId,
      spanId,
      parentId,
      spanData,
    }),
  };
}

function createMockTrace(
  traceId: string,
  name: string,
  options?: {
    groupId?: string;
    metadata?: Record<string, unknown>;
  }
): MockTrace {
  return {
    type: "trace",
    traceId,
    name,
    groupId: options?.groupId ?? null,
    metadata: options?.metadata,
    toJSON: () => ({
      traceId,
      name,
      groupId: options?.groupId ?? null,
      metadata: options?.metadata,
    }),
  };
}

describe("OpenAIAgentsTracingProcessor", () => {
  let processor: OpenAIAgentsTracingProcessor;
  let client: ReturnType<typeof mockClient>["client"];
  let callSpy: ReturnType<typeof mockClient>["callSpy"];

  beforeEach(() => {
    const mock = mockClient();
    client = mock.client;
    callSpy = mock.callSpy;
    processor = new OpenAIAgentsTracingProcessor({
      client,
      metadata: { custom: "metadata" },
      tags: ["test-tag"],
      projectName: "test-project",
    });
  });

  describe("constructor", () => {
    test("creates processor with default client", () => {
      const defaultProcessor = new OpenAIAgentsTracingProcessor();
      expect(defaultProcessor).toBeDefined();
    });

    test("accepts configuration options", () => {
      const configuredProcessor = new OpenAIAgentsTracingProcessor({
        metadata: { key: "value" },
        tags: ["tag1", "tag2"],
        projectName: "my-project",
        name: "My Agent",
      });
      expect(configuredProcessor).toBeDefined();
    });
  });

  describe("trace lifecycle", () => {
    test("handles trace start and end", async () => {
      const trace = createMockTrace("trace-1", "Test Agent");

      await processor.onTraceStart(trace);
      await processor.onTraceEnd(trace);

      await client.awaitPendingTraceBatches();

      // Should have made POST and PATCH calls
      const calls = callSpy.mock.calls;
      expect(calls.length).toBeGreaterThan(0);
    });

    test("uses custom trace name", async () => {
      const customProcessor = new OpenAIAgentsTracingProcessor({
        client,
        name: "Custom Workflow",
      });

      const trace = createMockTrace("trace-2", "Agent Name");
      await customProcessor.onTraceStart(trace);
      await customProcessor.onTraceEnd(trace);

      await client.awaitPendingTraceBatches();

      const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
      expect(tree.nodes.some((n) => n.includes("Custom Workflow"))).toBe(true);
    });

    test("includes groupId as thread_id in metadata", async () => {
      const trace = createMockTrace("trace-3", "Agent", {
        groupId: "group-123",
      });

      await processor.onTraceStart(trace);
      await processor.onTraceEnd(trace);

      await client.awaitPendingTraceBatches();

      const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
      const rootNode = tree.nodes.find((n) => n.includes("Agent"));
      expect(rootNode).toBeDefined();
      if (rootNode) {
        expect(tree.data[rootNode].extra?.metadata?.thread_id).toBe(
          "group-123"
        );
      }
    });
  });

  describe("span handling", () => {
    test("handles agent span", async () => {
      const trace = createMockTrace("trace-4", "Test Agent");
      const agentSpan = createMockSpan("trace-4", "span-1", null, {
        type: "agent",
        name: "MyAgent",
        tools: ["tool1", "tool2"],
        handoffs: ["Agent2"],
        output_type: "string",
      });

      await processor.onTraceStart(trace);
      await processor.onSpanStart(agentSpan);
      await processor.onSpanEnd(agentSpan);
      await processor.onTraceEnd(trace);

      await client.awaitPendingTraceBatches();

      const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
      expect(tree.nodes.some((n) => n.includes("MyAgent"))).toBe(true);
    });

    test("derives agent inputs and outputs from child response spans", async () => {
      const trace = createMockTrace("trace-4b", "Test Agent");
      const agentSpan = createMockSpan("trace-4b", "span-agent", null, {
        type: "agent",
        name: "WeatherAgent",
        tools: ["get_weather"],
        output_type: "string",
      });
      const firstResponseSpan = createMockSpan(
        "trace-4b",
        "span-resp-1",
        "span-agent",
        {
          type: "response",
          _input: "What's the weather in San Francisco?",
          _response: {
            instructions:
              "You are a weather assistant. Use the get_weather tool when asked about weather.",
            output: [{ type: "message", content: "Calling tool..." }],
            model: "gpt-4.1-mini",
          },
        }
      );
      const secondResponseSpan = createMockSpan(
        "trace-4b",
        "span-resp-2",
        "span-agent",
        {
          type: "response",
          _input: [
            {
              type: "function_call_output",
              call_id: "call_123",
              output:
                '{"city":"San Francisco","temperature":"72°F","condition":"sunny"}',
            },
          ],
          _response: {
            instructions:
              "You are a weather assistant. Use the get_weather tool when asked about weather.",
            output: [{ type: "message", content: "It's sunny and 72°F." }],
            model: "gpt-4.1-mini",
          },
        }
      );

      await processor.onTraceStart(trace);
      await processor.onSpanStart(agentSpan);
      await processor.onSpanStart(firstResponseSpan);
      await processor.onSpanEnd(firstResponseSpan);
      await processor.onSpanStart(secondResponseSpan);
      await processor.onSpanEnd(secondResponseSpan);
      await processor.onSpanEnd(agentSpan);
      await processor.onTraceEnd(trace);

      await client.awaitPendingTraceBatches();

      const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
      const agentNode = tree.nodes.find((n) => n.includes("WeatherAgent"));
      expect(agentNode).toBeDefined();
      if (agentNode) {
        expect(tree.data[agentNode].inputs).toMatchObject({
          input: "What's the weather in San Francisco?",
          instructions:
            "You are a weather assistant. Use the get_weather tool when asked about weather.",
        });
        expect(tree.data[agentNode].outputs).toMatchObject({
          output: [{ type: "message", content: "It's sunny and 72°F." }],
        });
      }
    });

    test("handles function span (tool)", async () => {
      const trace = createMockTrace("trace-5", "Test Agent");
      const functionSpan = createMockSpan("trace-5", "span-2", null, {
        type: "function",
        name: "get_weather",
        input: '{"city": "New York"}',
        output: '{"weather": "sunny"}',
      });

      await processor.onTraceStart(trace);
      await processor.onSpanStart(functionSpan);
      await processor.onSpanEnd(functionSpan);
      await processor.onTraceEnd(trace);

      await client.awaitPendingTraceBatches();

      const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
      expect(tree.nodes.some((n) => n.includes("get_weather"))).toBe(true);
    });

    test("handles generation span (LLM)", async () => {
      const trace = createMockTrace("trace-6", "Test Agent");
      const generationSpan = createMockSpan("trace-6", "span-3", null, {
        type: "generation",
        input: [{ role: "user", content: "Hello" }],
        output: [{ role: "assistant", content: "Hi there!" }],
        model: "gpt-4.1-mini",
        model_config: { temperature: 0.7 },
        usage: { input_tokens: 10, output_tokens: 5 },
      });

      await processor.onTraceStart(trace);
      await processor.onSpanStart(generationSpan);
      await processor.onSpanEnd(generationSpan);
      await processor.onTraceEnd(trace);

      await client.awaitPendingTraceBatches();

      const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
      expect(tree.nodes.some((n) => n.includes("Generation"))).toBe(true);
    });

    test("handles response span and preserves instructions in inputs", async () => {
      const trace = createMockTrace("trace-7", "Test Agent");
      const responseSpan = createMockSpan("trace-7", "span-4", null, {
        type: "response",
        response_id: "resp-123",
        _input: "What is the weather?",
        _response: {
          instructions: "Answer briefly.",
          model: "gpt-4.1-mini",
          output: [{ type: "message", content: "It's sunny!" }],
          usage: { input_tokens: 8, output_tokens: 12 },
        },
      });

      await processor.onTraceStart(trace);
      await processor.onSpanStart(responseSpan);
      await processor.onSpanEnd(responseSpan);
      await processor.onTraceEnd(trace);

      await client.awaitPendingTraceBatches();

      const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
      const responseNode = tree.nodes.find((n) => n.includes("Response"));
      expect(responseNode).toBeDefined();
      if (responseNode) {
        expect(tree.data[responseNode].inputs).toMatchObject({
          input: "What is the weather?",
          instructions: "Answer briefly.",
        });
      }
    });

    test("normalizes response item arrays into replayable responses-api input", async () => {
      const trace = createMockTrace("trace-7b", "Test Agent");
      const responseSpan = createMockSpan("trace-7b", "span-4b", null, {
        type: "response",
        response_id: "resp-456",
        _input: [
          {
            type: "message",
            role: "user",
            content: "What's the weather in San Francisco?",
          },
          {
            type: "reasoning",
            content: [],
            id: "rs_123",
            providerData: { type: "reasoning" },
          },
          {
            type: "function_call",
            name: "get_weather",
            callId: "call_123",
            arguments: '{"city":"San Francisco"}',
            status: "completed",
            id: "fc_123",
            providerData: { type: "function_call" },
          },
          {
            type: "function_call_result",
            name: "get_weather",
            callId: "call_123",
            output: {
              type: "text",
              text: '{"city":"San Francisco","temperature":"72°F","condition":"sunny"}',
            },
            status: "completed",
          },
        ],
        _response: {
          instructions:
            "You are a weather assistant. Use the get_weather tool when asked about weather.",
          model: "gpt-4.1-mini",
          output: [{ type: "message", content: "It's sunny!" }],
        },
      });

      await processor.onTraceStart(trace);
      await processor.onSpanStart(responseSpan);
      await processor.onSpanEnd(responseSpan);
      await processor.onTraceEnd(trace);

      await client.awaitPendingTraceBatches();

      const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
      const responseNode = tree.nodes.find((n) => n.includes("Response"));
      expect(responseNode).toBeDefined();
      if (responseNode) {
        expect(tree.data[responseNode].inputs).toMatchObject({
          input: [
            {
              type: "message",
              role: "user",
              content: "What's the weather in San Francisco?",
            },
            {
              type: "reasoning",
              id: "rs_123",
              content: [],
            },
            {
              type: "function_call",
              id: "fc_123",
              call_id: "call_123",
              name: "get_weather",
              arguments: '{"city":"San Francisco"}',
            },
            {
              type: "function_call_output",
              call_id: "call_123",
              output:
                '{"city":"San Francisco","temperature":"72°F","condition":"sunny"}',
            },
          ],
          instructions:
            "You are a weather assistant. Use the get_weather tool when asked about weather.",
        });
      }
    });

    test("handles handoff span", async () => {
      const trace = createMockTrace("trace-8", "Test Agent");
      const handoffSpan = createMockSpan("trace-8", "span-5", null, {
        type: "handoff",
        from_agent: "Agent1",
        to_agent: "Agent2",
      });

      await processor.onTraceStart(trace);
      await processor.onSpanStart(handoffSpan);
      await processor.onSpanEnd(handoffSpan);
      await processor.onTraceEnd(trace);

      await client.awaitPendingTraceBatches();

      const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
      const handoffNode = tree.nodes.find((n) => n.includes("Handoff"));
      expect(handoffNode).toBeDefined();
      if (handoffNode) {
        expect(tree.data[handoffNode].inputs).toMatchObject({
          from_agent: "Agent1",
        });
        expect(tree.data[handoffNode].outputs).toMatchObject({
          to_agent: "Agent2",
        });
      }
    });

    test("handles guardrail span", async () => {
      const trace = createMockTrace("trace-9", "Test Agent");
      const guardrailSpan = createMockSpan("trace-9", "span-6", null, {
        type: "guardrail",
        name: "safety_check",
        triggered: true,
      });

      await processor.onTraceStart(trace);
      await processor.onSpanStart(guardrailSpan);
      await processor.onSpanEnd(guardrailSpan);
      await processor.onTraceEnd(trace);

      await client.awaitPendingTraceBatches();

      const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
      expect(tree.nodes.some((n) => n.includes("safety_check"))).toBe(true);
    });

    test("handles custom span", async () => {
      const trace = createMockTrace("trace-10", "Test Agent");
      const customSpan = createMockSpan("trace-10", "span-7", null, {
        type: "custom",
        name: "custom_operation",
        data: { key: "value", count: 42 },
      });

      await processor.onTraceStart(trace);
      await processor.onSpanStart(customSpan);
      await processor.onSpanEnd(customSpan);
      await processor.onTraceEnd(trace);

      await client.awaitPendingTraceBatches();

      const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
      expect(tree.nodes.some((n) => n.includes("custom_operation"))).toBe(true);
    });
  });

  describe("nested spans", () => {
    test("handles parent-child span relationships", async () => {
      const trace = createMockTrace("trace-11", "Test Agent");

      // Parent span (agent)
      const parentSpan = createMockSpan("trace-11", "span-parent", null, {
        type: "agent",
        name: "ParentAgent",
      });

      // Child span (function)
      const childSpan = createMockSpan(
        "trace-11",
        "span-child",
        "span-parent",
        {
          type: "function",
          name: "child_tool",
          input: "{}",
          output: "{}",
        }
      );

      await processor.onTraceStart(trace);
      await processor.onSpanStart(parentSpan);
      await processor.onSpanStart(childSpan);
      await processor.onSpanEnd(childSpan);
      await processor.onSpanEnd(parentSpan);
      await processor.onTraceEnd(trace);

      await client.awaitPendingTraceBatches();

      const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);

      // Should have edges between parent and child
      expect(tree.edges.length).toBeGreaterThan(0);
    });

    test("marks agent spans under function spans as subagents", async () => {
      const trace = createMockTrace("trace-11b", "Test Agent");

      const functionSpan = createMockSpan("trace-11b", "span-fn", null, {
        type: "function",
        name: "invoke_subagent",
        input: "{}",
        output: "{}",
      });

      const subagentSpan = createMockSpan(
        "trace-11b",
        "span-agent",
        "span-fn",
        {
          type: "agent",
          name: "SubAgent",
        }
      );

      await processor.onTraceStart(trace);
      await processor.onSpanStart(functionSpan);
      await processor.onSpanStart(subagentSpan);
      await processor.onSpanEnd(subagentSpan);
      await processor.onSpanEnd(functionSpan);
      await processor.onTraceEnd(trace);

      await client.awaitPendingTraceBatches();

      const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
      const subagentNode = tree.nodes.find((n) => n.includes("SubAgent"));
      expect(subagentNode).toBeDefined();
      if (subagentNode) {
        expect(tree.data[subagentNode].extra?.metadata?.ls_agent_type).toBe(
          "subagent"
        );
      }
    });

    test("does not mark handoff agents as subagents", async () => {
      const trace = createMockTrace("trace-11c", "Test Agent");

      const functionSpan = createMockSpan("trace-11c", "span-fn", null, {
        type: "function",
        name: "invoke_handoff",
        input: "{}",
        output: "{}",
      });

      const handoffSpan = createMockSpan(
        "trace-11c",
        "span-handoff",
        "span-fn",
        {
          type: "handoff",
          from_agent: "ParentAgent",
          to_agent: "HandoffAgent",
        }
      );

      await processor.onTraceStart(trace);
      await processor.onSpanStart(functionSpan);
      await processor.onSpanStart(handoffSpan);
      await processor.onSpanEnd(handoffSpan);
      await processor.onSpanEnd(functionSpan);
      await processor.onTraceEnd(trace);

      await client.awaitPendingTraceBatches();

      const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
      const handoffNode = tree.nodes.find((n) => n.includes("Handoff"));
      expect(handoffNode).toBeDefined();
      if (handoffNode) {
        expect(tree.data[handoffNode].extra?.metadata?.ls_agent_type).not.toBe(
          "subagent"
        );
      }
    });

    test("posts root trace on trace end when no response or generation spans occur", async () => {
      const trace = createMockTrace("trace-11d", "No Response Trace");
      const agentSpan = createMockSpan("trace-11d", "span-agent-only", null, {
        type: "agent",
        name: "AgentOnly",
      });

      await processor.onTraceStart(trace);
      await processor.onSpanStart(agentSpan);
      await processor.onSpanEnd(agentSpan);
      await processor.onTraceEnd(trace);

      await client.awaitPendingTraceBatches();

      const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
      const rootNode = tree.nodes.find((n) => n.includes("No Response Trace"));
      expect(rootNode).toBeDefined();
      if (rootNode) {
        expect(tree.data[rootNode].inputs).toEqual({});
      }
    });

    test("gracefully skips orphan spans with missing parents", async () => {
      const trace = createMockTrace("trace-11e", "Orphan Trace");
      const orphanSpan = createMockSpan(
        "trace-11e",
        "span-orphan",
        "missing-parent",
        {
          type: "function",
          name: "orphan_tool",
          input: "{}",
          output: "{}",
        }
      );

      await processor.onTraceStart(trace);
      await processor.onSpanStart(orphanSpan);
      await processor.onSpanEnd(orphanSpan);
      await processor.onTraceEnd(trace);

      await client.awaitPendingTraceBatches();

      const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
      expect(tree.nodes.some((n) => n.includes("orphan_tool"))).toBe(false);
      expect(tree.nodes.some((n) => n.includes("Orphan Trace"))).toBe(true);
    });

    test("nested traceable called inside a function (tool) span nests under the function span", async () => {
      const trace = createMockTrace("trace-11f", "Agent With Traceable");
      const agentSpan = createMockSpan(
        "trace-11f",
        "span-agent-traceable",
        null,
        {
          type: "agent",
          name: "TraceableParentAgent",
        }
      );
      const functionSpan = createMockSpan(
        "trace-11f",
        "span-fn-traceable",
        "span-agent-traceable",
        {
          type: "function",
          name: "get_weather",
          input: '{"city":"Tokyo"}',
          output: "{}",
        }
      );

      const innerTraceable = traceable(
        async (city: string) => {
          return `mock-${city}`;
        },
        { name: "nested_traceable", client }
      );

      await processor.onTraceStart(trace);
      await processor.onSpanStart(agentSpan);
      await processor.onSpanStart(functionSpan);

      // Simulate a traceable() call happening during tool execution
      // between the function span's onSpanStart and onSpanEnd.
      const result = await innerTraceable("Tokyo");
      expect(result).toBe("mock-Tokyo");

      await processor.onSpanEnd(functionSpan);
      await processor.onSpanEnd(agentSpan);
      await processor.onTraceEnd(trace);

      await client.awaitPendingTraceBatches();
      await Promise.resolve();
      await client.awaitPendingTraceBatches();

      const postedRuns = callSpy.mock.calls
        .map((call) => {
          const fetchArgs = call.at(-1) as { body?: string | Uint8Array };
          const body = fetchArgs?.body;
          if (typeof body === "string") {
            return JSON.parse(body);
          }
          // eslint-disable-next-line no-instanceof/no-instanceof
          if (body instanceof Uint8Array) {
            return JSON.parse(new TextDecoder().decode(body));
          }
          return undefined;
        })
        .filter((run): run is Record<string, unknown> => run != null);

      const nestedRun = postedRuns.find(
        (run) => run.name === "nested_traceable"
      );
      const toolRun = postedRuns.find((run) => run.name === "get_weather");
      expect(nestedRun).toBeDefined();
      expect(toolRun).toBeDefined();
      expect(nestedRun?.parent_run_id).toBe(toolRun?.id);
    });
  });

  describe("error handling", () => {
    test("captures span errors", async () => {
      const trace = createMockTrace("trace-12", "Test Agent");
      const errorSpan = createMockSpan(
        "trace-12",
        "span-error",
        null,
        {
          type: "function",
          name: "failing_tool",
          input: "{}",
          output: "",
        },
        {
          error: { message: "Tool execution failed" },
        }
      );

      await processor.onTraceStart(trace);
      await processor.onSpanStart(errorSpan);
      await processor.onSpanEnd(errorSpan);
      await processor.onTraceEnd(trace);

      await client.awaitPendingTraceBatches();

      // Check that error was captured
      const calls = callSpy.mock.calls;
      const patchCall = calls.find((call: any[]) => {
        const url = call[0] as string;
        return url.includes("/runs/") && (call[1] as any)?.method === "PATCH";
      });

      if (patchCall) {
        const body = JSON.parse((patchCall[1] as any).body);
        expect(body.error).toBe("Tool execution failed");
      }
    });
  });

  describe("usage metadata", () => {
    test("extracts usage from generation span (details shape)", async () => {
      const trace = createMockTrace("trace-13", "Test Agent");
      const generationSpan = createMockSpan("trace-13", "span-gen", null, {
        type: "generation",
        model: "gpt-4.1-mini",
        usage: {
          input_tokens: 100,
          output_tokens: 50,
          details: {
            cached_tokens: 20,
            reasoning_tokens: 10,
            audio_tokens: 5,
          },
        },
      });

      await processor.onTraceStart(trace);
      await processor.onSpanStart(generationSpan);
      await processor.onSpanEnd(generationSpan);
      await processor.onTraceEnd(trace);

      await client.awaitPendingTraceBatches();

      const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
      const generationNode = tree.nodes.find((n) => n.includes("Generation"));
      expect(generationNode).toBeDefined();
      expect(
        tree.data[generationNode!].extra?.metadata?.usage_metadata
      ).toEqual({
        input_tokens: 100,
        output_tokens: 50,
        total_tokens: 150,
        input_token_details: { cache_read: 20, audio: 5 },
        output_token_details: { reasoning: 10 },
      });
    });

    test("extracts usage from response span (Responses API shape)", async () => {
      const trace = createMockTrace("trace-13b", "Test Agent");
      const responseSpan = createMockSpan("trace-13b", "span-resp", null, {
        type: "response",
        response_id: "resp-usage",
        _input: "hello",
        _response: {
          model: "gpt-4.1-mini",
          output: [{ type: "message", content: "hi" }],
          usage: {
            input_tokens: 80,
            output_tokens: 40,
            total_tokens: 120,
            input_tokens_details: { cached_tokens: 30 },
            output_tokens_details: { reasoning_tokens: 7 },
          },
        },
      });

      await processor.onTraceStart(trace);
      await processor.onSpanStart(responseSpan);
      await processor.onSpanEnd(responseSpan);
      await processor.onTraceEnd(trace);

      await client.awaitPendingTraceBatches();

      const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
      const responseNode = tree.nodes.find((n) => n.includes("Response"));
      expect(responseNode).toBeDefined();
      expect(tree.data[responseNode!].extra?.metadata?.usage_metadata).toEqual({
        input_tokens: 80,
        output_tokens: 40,
        total_tokens: 120,
        input_token_details: { cache_read: 30 },
        output_token_details: { reasoning: 7 },
      });
    });
  });

  describe("shutdown and flush", () => {
    test("forceFlush calls client flush", async () => {
      const flushSpy = jest.spyOn(client, "flush").mockResolvedValue();

      await processor.forceFlush();

      expect(flushSpy).toHaveBeenCalled();
      flushSpy.mockRestore();
    });

    test("shutdown calls client flush", async () => {
      const flushSpy = jest.spyOn(client, "flush").mockResolvedValue();

      await processor.shutdown();

      expect(flushSpy).toHaveBeenCalled();
      flushSpy.mockRestore();
    });
  });
});
