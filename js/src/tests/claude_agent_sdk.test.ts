/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, test, expect, jest } from "@jest/globals";
import { wrapClaudeAgentSDK } from "../experimental/anthropic/index.js";
import { mockClient } from "./utils/mock_client.js";
import { getAssumedTreeFromCalls } from "./utils/tree.js";

// Mock Claude Agent SDK types and functions
type MockSDKMessage = {
  type: string;
  message?: {
    id?: string;
    role?: string;
    content?: unknown;
    model?: string;
    usage?: {
      input_tokens?: number;
      output_tokens?: number;
      cache_read_input_tokens?: number;
      cache_creation_input_tokens?: number;
    };
  };
  usage?: {
    input_tokens?: number;
    output_tokens?: number;
    cache_read_input_tokens?: number;
    cache_creation_input_tokens?: number;
  };
  num_turns?: number;
  session_id?: string;
};

type MockQueryParams = {
  prompt?: string | AsyncIterable<MockSDKMessage>;
  options?: Record<string, unknown>;
};

// Mock Claude Agent SDK
const createMockSDK = () => {
  const inputSpy = jest.fn();

  const mockQuery = async function* (
    params: MockQueryParams
  ): AsyncGenerator<MockSDKMessage, void, unknown> {
    // Simulate system message
    const prompt =
      typeof params.prompt === "string" ? [params.prompt] : params.prompt ?? [];

    for await (const message of prompt) {
      inputSpy(message, { createdAt: Date.now() });

      yield {
        type: "system",
        session_id: "session_456",
      };

      // Simulate assistant message with streaming
      yield {
        type: "assistant",
        message: {
          id: `msg_123_${crypto.randomUUID()}`,
          role: "assistant",
          content: "Hello! How can I help you?",
          model: "claude-3-5-sonnet-20241022",
          usage: {
            input_tokens: 10,
            output_tokens: 8,
            cache_read_input_tokens: 0,
            cache_creation_input_tokens: 0,
          },
        },
      };

      // Simulate result message
      yield {
        type: "result",
        usage: {
          input_tokens: 10,
          output_tokens: 8,
          cache_read_input_tokens: 0,
          cache_creation_input_tokens: 0,
        },
        num_turns: 1,
        session_id: "session_456",
      };
    }
  };

  const mockTool = <T>(
    name: string,
    description: string,
    inputSchema: unknown,
    handler: (
      args: T,
      extra: unknown
    ) => Promise<{
      content: Array<unknown>;
      isError?: boolean;
    }>
  ) => {
    return {
      name,
      description,
      inputSchema,
      handler,
    };
  };

  const mockCreateSdkMcpServer = () => {
    return {
      listen: () => Promise.resolve(),
    };
  };

  return {
    query: mockQuery,
    tool: mockTool,
    createSdkMcpServer: mockCreateSdkMcpServer,

    spy: { input: inputSpy },
  };
};

describe("wrapClaudeAgentSDK", () => {
  test("wraps query function and traces agent interactions", async () => {
    const mockSDK = createMockSDK();
    const wrapped = wrapClaudeAgentSDK(mockSDK);

    const messages: MockSDKMessage[] = [];
    for await (const message of wrapped.query({
      prompt: "Hello, Claude!",
      options: { model: "claude-3-5-sonnet-20241022" },
    })) {
      messages.push(message);
    }

    expect(messages).toMatchObject([
      { type: "system", session_id: "session_456" },
      {
        type: "assistant",
        message: { content: "Hello! How can I help you?" },
      },
      { type: "result" },
    ]);
  });

  test("wraps tool handler with tracing", async () => {
    const mockSDK = createMockSDK();
    const wrapped = wrapClaudeAgentSDK(mockSDK);

    const calculator = wrapped.tool(
      "calculator",
      "Performs basic math operations",
      { type: "object", properties: { expression: { type: "string" } } },
      async (args: { expression: string }) => {
        return {
          content: [{ type: "text", text: `Result: ${eval(args.expression)}` }],
        };
      }
    );

    expect(calculator.name).toBe("calculator");
    expect(calculator.description).toBe("Performs basic math operations");

    const result = await calculator.handler({ expression: "2 + 2" }, {});
    expect(result.content).toBeDefined();
    expect(result.content.length).toBeGreaterThan(0);
  });

  test("handles multiple message groups with different IDs", async () => {
    const mockSDK = {
      ...createMockSDK(),
      query: async function* (
        _params: MockQueryParams
      ): AsyncGenerator<MockSDKMessage, void, unknown> {
        // First message group
        yield {
          type: "assistant",
          message: {
            id: "msg_1",
            role: "assistant",
            content: "First response",
            usage: { input_tokens: 5, output_tokens: 3 },
          },
        };

        // Second message group
        yield {
          type: "assistant",
          message: {
            id: "msg_2",
            role: "assistant",
            content: "Second response",
            usage: { input_tokens: 3, output_tokens: 4 },
          },
        };

        // Result
        yield {
          type: "result",
          usage: { input_tokens: 8, output_tokens: 7 },
          num_turns: 2,
        };
      },
    };

    const wrapped = wrapClaudeAgentSDK(mockSDK);
    const messages: MockSDKMessage[] = [];

    for await (const message of wrapped.query({ prompt: "Test" })) {
      messages.push(message);
    }

    expect(messages.length).toBe(3);
    expect(messages[0].message?.id).toBe("msg_1");
    expect(messages[1].message?.id).toBe("msg_2");
    expect(messages[2].type).toBe("result");
  });

  test("extracts and tracks token usage correctly", async () => {
    const mockSDK = {
      ...createMockSDK(),
      query: async function* (
        _params: MockQueryParams
      ): AsyncGenerator<MockSDKMessage, void, unknown> {
        yield {
          type: "assistant",
          message: {
            id: "msg_1",
            role: "assistant",
            content: "Response with cache",
            usage: {
              input_tokens: 100,
              output_tokens: 50,
              cache_read_input_tokens: 20,
              cache_creation_input_tokens: 10,
            },
          },
        };

        yield {
          type: "result",
          usage: {
            input_tokens: 100,
            output_tokens: 50,
            cache_read_input_tokens: 20,
            cache_creation_input_tokens: 10,
          },
        };
      },
    };

    const wrapped = wrapClaudeAgentSDK(mockSDK);
    const messages: MockSDKMessage[] = [];

    for await (const message of wrapped.query({ prompt: "Test" })) {
      messages.push(message);
    }

    const assistantMessage = messages[0];
    expect(assistantMessage.message?.usage?.input_tokens).toBe(100);
    expect(assistantMessage.message?.usage?.output_tokens).toBe(50);
    expect(assistantMessage.message?.usage?.cache_read_input_tokens).toBe(20);
    expect(assistantMessage.message?.usage?.cache_creation_input_tokens).toBe(
      10
    );
  });

  test("passes through createSdkMcpServer unchanged", () => {
    const mockSDK = createMockSDK();
    const wrapped = wrapClaudeAgentSDK(mockSDK);

    expect(wrapped.createSdkMcpServer).toBeDefined();
    expect(typeof wrapped.createSdkMcpServer).toBe("function");
  });

  test("accepts custom configuration", async () => {
    const mockSDK = createMockSDK();
    const wrapped = wrapClaudeAgentSDK(mockSDK, {
      project_name: "test-project",
      metadata: { custom: "metadata" },
      tags: ["test-tag"],
    });

    const messages: MockSDKMessage[] = [];
    for await (const message of wrapped.query({ prompt: "Test" })) {
      messages.push(message);
    }

    expect(messages.length).toBeGreaterThan(0);
  });

  test("handles async iterable prompt", async () => {
    const { client, callSpy } = mockClient();
    const mockSDK = createMockSDK();

    const wrapped = wrapClaudeAgentSDK(mockSDK, {
      client,
      tracingEnabled: true,
    });

    async function* promptStream(): AsyncIterable<MockSDKMessage> {
      yield { type: "user", message: { role: "user", content: "Hello" } };

      await new Promise((resolve) => setTimeout(resolve, 500));

      yield {
        type: "user",
        message: { role: "user", content: "How are you?" },
      };
    }

    const messages: MockSDKMessage[] = [];
    for await (const message of wrapped.query({ prompt: promptStream() })) {
      messages.push(message);
    }

    expect(mockSDK.spy.input).toHaveBeenCalledTimes(2);
    expect(mockSDK.spy.input).toHaveBeenCalledWith(
      { type: "user", message: { role: "user", content: "Hello" } },
      { createdAt: expect.any(Number) }
    );
    expect(mockSDK.spy.input).toHaveBeenCalledWith(
      { type: "user", message: { role: "user", content: "How are you?" } },
      { createdAt: expect.any(Number) }
    );

    const extractDuration = (call: unknown[]) => {
      const [, { createdAt }] = call as [unknown, { createdAt: number }];
      return createdAt;
    };

    expect(
      extractDuration(mockSDK.spy.input.mock.calls[1]) -
        extractDuration(mockSDK.spy.input.mock.calls[0])
    ).toBeGreaterThan(250);

    expect(
      await getAssumedTreeFromCalls(callSpy.mock.calls, client)
    ).toMatchObject({
      nodes: [
        "claude.assistant.turn:0",
        "claude.assistant.turn:1",
        "claude.conversation:2",
      ],
      edges: [
        ["claude.conversation:2", "claude.assistant.turn:0"],
        ["claude.conversation:2", "claude.assistant.turn:1"],
      ],
      data: {
        "claude.conversation:2": {
          run_type: "chain",
          extra: {
            metadata: {
              ls_integration: "claude-agent-sdk",
              ls_integration_version: expect.any(String),
            },
          },
          inputs: {
            messages: [
              { content: "Hello", role: "user" },
              { content: "How are you?", role: "user" },
            ],
          },
          outputs: {
            output: {
              messages: [
                { role: "assistant", content: "Hello! How can I help you?" },
                { role: "assistant", content: "Hello! How can I help you?" },
              ],
            },
          },
        },
        "claude.assistant.turn:0": {
          run_type: "llm",
          inputs: { messages: [{ content: "Hello", role: "user" }] },
          outputs: {
            output: {
              messages: [
                { role: "assistant", content: "Hello! How can I help you?" },
              ],
            },
          },
        },
        "claude.assistant.turn:1": {
          run_type: "llm",
          inputs: {
            messages: [
              { content: "Hello", role: "user" },
              { role: "assistant", content: "Hello! How can I help you?" },
              { role: "user", content: "How are you?" },
            ],
          },
          outputs: {
            output: {
              messages: [
                { role: "assistant", content: "Hello! How can I help you?" },
              ],
            },
          },
        },
      },
    });
  });

  test("adjusts output tokens correctly for final result", async () => {
    const { client, callSpy } = mockClient();
    const mockSDK = {
      ...createMockSDK(),
      query: async function* (
        _params: MockQueryParams
      ): AsyncGenerator<MockSDKMessage, void, unknown> {
        yield { type: "system" };

        // First message
        yield {
          type: "assistant",
          message: {
            id: "msg_1",
            role: "assistant",
            content: "Part 1",
            usage: { input_tokens: 10, output_tokens: 5 },
          },
        };

        // Second message with same ID (streaming)
        yield {
          type: "assistant",
          message: {
            id: "msg_1",
            role: "assistant",
            content: "Part 1 complete",
            usage: { input_tokens: 10, output_tokens: 8 },
          },
        };

        // Result with total tokens
        yield {
          type: "result",
          usage: { input_tokens: 10, output_tokens: 15 },
        };
      },
    };

    const wrapped = wrapClaudeAgentSDK(mockSDK, {
      client,
      tracingEnabled: true,
    });
    const messages: MockSDKMessage[] = [];

    for await (const message of wrapped.query({ prompt: "Test" })) {
      messages.push(message);
    }

    // The last assistant message should have adjusted tokens
    expect(messages.length).toBe(4);

    expect(
      await getAssumedTreeFromCalls(callSpy.mock.calls, client)
    ).toMatchObject({
      nodes: ["claude.conversation:0", "claude.assistant.turn:1"],
      edges: [["claude.conversation:0", "claude.assistant.turn:1"]],
      data: {
        "claude.conversation:0": {
          run_type: "chain",
          extra: {
            metadata: {
              usage_metadata: {
                input_tokens: 10,
                output_tokens: 15,
                total_tokens: 25,
              },
            },
          },
          inputs: { messages: [{ content: "Test", role: "user" }] },
          outputs: {
            output: {
              messages: [
                { role: "assistant", content: "Part 1" },
                { role: "assistant", content: "Part 1 complete" },
              ],
            },
          },
        },
        "claude.assistant.turn:1": {
          run_type: "llm",
          extra: {
            metadata: {
              usage_metadata: {
                input_tokens: 10,
                output_tokens: 8,
                total_tokens: 18,
              },
            },
          },
          inputs: {
            messages: [{ role: "user", content: "Test" }],
          },
          outputs: {
            output: {
              messages: [
                { role: "assistant", content: "Part 1" },
                { role: "assistant", content: "Part 1 complete" },
              ],
            },
          },
        },
      },
    });
  });

  test("handles UserMessage in conversation", async () => {
    const { client, callSpy } = mockClient();
    const mockSDK = {
      ...createMockSDK(),
      query: async function* (
        _params: MockQueryParams
      ): AsyncGenerator<MockSDKMessage, void, unknown> {
        yield {
          type: "system",
          session_id: "session_456",
        };

        yield {
          type: "assistant",
          message: {
            id: "msg_1",
            role: "assistant",
            content: "First response",
            usage: { input_tokens: 5, output_tokens: 3 },
          },
        };

        // User message in the middle of conversation
        yield {
          type: "user",
          message: { content: [{ type: "text", text: "Follow up question" }] },
        };

        yield {
          type: "assistant",
          message: {
            id: "msg_2",
            role: "assistant",
            content: "Second response",
            usage: { input_tokens: 8, output_tokens: 5 },
          },
        };

        yield {
          type: "result",
          usage: { input_tokens: 13, output_tokens: 8 },
          num_turns: 2,
        };
      },
    };

    const wrapped = wrapClaudeAgentSDK(mockSDK, {
      client,
      tracingEnabled: true,
    });
    const messages: MockSDKMessage[] = [];

    for await (const message of wrapped.query({ prompt: "Test" })) {
      messages.push(message);
    }

    expect(messages).toMatchObject([
      { type: "system", session_id: "session_456" },
      {
        type: "assistant",
        message: {
          id: "msg_1",
          role: "assistant",
          content: "First response",
          usage: { input_tokens: 5, output_tokens: 3 },
        },
      },
      {
        type: "user",
        message: { content: [{ type: "text", text: "Follow up question" }] },
      },
      {
        type: "assistant",
        message: {
          id: "msg_2",
          role: "assistant",
          content: "Second response",
          usage: { input_tokens: 8, output_tokens: 5 },
        },
      },
      {
        type: "result",
        usage: { input_tokens: 13, output_tokens: 8 },
        num_turns: 2,
      },
    ]);

    expect(
      await getAssumedTreeFromCalls(callSpy.mock.calls, client)
    ).toMatchObject({
      nodes: [
        "claude.conversation:0",
        "claude.assistant.turn:1",
        "claude.assistant.turn:2",
      ],
      edges: [
        ["claude.conversation:0", "claude.assistant.turn:1"],
        ["claude.conversation:0", "claude.assistant.turn:2"],
      ],
      data: {
        "claude.conversation:0": {
          run_type: "chain",
          inputs: { messages: [{ content: "Test", role: "user" }] },
          extra: {
            metadata: {
              usage_metadata: {
                input_tokens: 13,
                output_tokens: 8,
                total_tokens: 21,
              },
              num_turns: 2,
            },
          },
          outputs: {
            output: {
              messages: [
                { role: "assistant", content: "First response" },
                { content: [{ type: "text", text: "Follow up question" }] },
                { role: "assistant", content: "Second response" },
              ],
            },
          },
        },
        "claude.assistant.turn:1": {
          run_type: "llm",
          inputs: { messages: [{ content: "Test", role: "user" }] },
          outputs: {
            output: {
              messages: [{ role: "assistant", content: "First response" }],
            },
          },
        },
        "claude.assistant.turn:2": {
          run_type: "llm",
          inputs: {
            messages: [
              { content: "Test", role: "user" },
              { content: "First response", role: "assistant" },
              {
                content: [{ type: "text", text: "Follow up question" }],
                role: "user",
              },
            ],
          },
          outputs: {
            output: {
              messages: [{ role: "assistant", content: "Second response" }],
            },
          },
        },
      },
    });
  });

  test("extracts metadata from ResultMessage", async () => {
    const { client, callSpy } = mockClient();
    const mockSDK = {
      ...createMockSDK(),
      query: async function* (
        _params: MockQueryParams
      ): AsyncGenerator<MockSDKMessage, void, unknown> {
        yield { type: "system", session_id: "session_abc123" };

        yield {
          type: "assistant",
          message: {
            id: "msg_1",
            role: "assistant",
            content: "Response",
            usage: { input_tokens: 10, output_tokens: 5 },
          },
        };

        yield {
          type: "result",
          usage: { input_tokens: 10, output_tokens: 5 },
          num_turns: 3,
          session_id: "session_abc123",
          duration_ms: 1500,
          duration_api_ms: 1200,
          is_error: false,
          stop_reason: "end_turn",
          total_cost_usd: 0.0015,
        } as any;
      },
    };

    const wrapped = wrapClaudeAgentSDK(mockSDK, {
      client,
      tracingEnabled: true,
    });
    const messages: any[] = [];

    for await (const message of wrapped.query({ prompt: "Test" })) {
      messages.push(message);
    }

    expect(messages).toMatchObject([
      { type: "system", session_id: "session_abc123" },
      {
        type: "assistant",
        message: { content: "Response" },
      },
      {
        type: "result",
        num_turns: 3,
        session_id: "session_abc123",
        duration_ms: 1500,
        total_cost_usd: 0.0015,
      },
    ]);

    const res = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
    expect(res).toMatchObject({
      nodes: ["claude.conversation:0", "claude.assistant.turn:1"],
      edges: [["claude.conversation:0", "claude.assistant.turn:1"]],
      data: {
        "claude.conversation:0": {
          run_type: "chain",
          inputs: { messages: [{ content: "Test", role: "user" }] },
          outputs: {
            output: { messages: [{ role: "assistant", content: "Response" }] },
          },
          extra: {
            metadata: {
              num_turns: 3,
              is_error: false,
              session_id: "session_abc123",

              duration_ms: 1500,
              duration_api_ms: 1200,

              usage_metadata: {
                input_tokens: 10,
                output_tokens: 5,
                total_tokens: 15,
                total_cost: 0.0015,
              },
            },
          },
        },
        "claude.assistant.turn:1": {
          run_type: "llm",
          inputs: { messages: [{ content: "Test", role: "user" }] },
          outputs: {
            output: {
              messages: [{ role: "assistant", content: "Response" }],
            },
          },
        },
      },
    });
  });

  test("extracts model from AssistantMessage", async () => {
    const { client, callSpy } = mockClient();
    const mockSDK = {
      ...createMockSDK(),
      query: async function* (
        _params: MockQueryParams
      ): AsyncGenerator<MockSDKMessage, void, unknown> {
        yield { type: "system", session_id: "session_abc123" };

        yield {
          type: "assistant",
          message: {
            id: "msg_1",
            role: "assistant",
            content: "Response",
            model: "claude-opus-4-20250514",
            usage: { input_tokens: 10, output_tokens: 5 },
          },
        };

        yield {
          type: "result",
          usage: { input_tokens: 10, output_tokens: 5 },
        };
      },
    };

    const wrapped = wrapClaudeAgentSDK(mockSDK, {
      client,
      tracingEnabled: true,
    });
    const messages: any[] = [];

    for await (const message of wrapped.query({
      prompt: "Test",
      options: { model: "claude-3-5-sonnet-20241022" },
    })) {
      messages.push(message);
    }

    // Model from message should be preserved
    expect(messages).toMatchObject([
      { type: "system", session_id: "session_abc123" },
      {
        type: "assistant",
        message: { content: "Response", model: "claude-opus-4-20250514" },
      },
      { type: "result", usage: { input_tokens: 10, output_tokens: 5 } },
    ]);

    const res = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
    expect(res).toMatchObject({
      nodes: ["claude.conversation:0", "claude.assistant.turn:1"],
      edges: [["claude.conversation:0", "claude.assistant.turn:1"]],
      data: {
        "claude.conversation:0": {
          run_type: "chain",
          inputs: {
            messages: [{ content: "Test", role: "user" }],
            options: { model: "claude-3-5-sonnet-20241022" },
          },
          outputs: {
            output: { messages: [{ role: "assistant", content: "Response" }] },
          },
        },
        "claude.assistant.turn:1": {
          run_type: "llm",
          inputs: { messages: [{ content: "Test", role: "user" }] },
          outputs: {
            output: { messages: [{ role: "assistant", content: "Response" }] },
          },
          extra: { metadata: { ls_model_name: "claude-opus-4-20250514" } },
        },
      },
    });
  });

  test("handles Task tool for subagent tracing", async () => {
    const mockSDK = {
      ...createMockSDK(),
      query: async function* (
        _params: MockQueryParams
      ): AsyncGenerator<MockSDKMessage, void, unknown> {
        // Main agent spawns a Task (subagent)
        yield {
          type: "assistant",
          parent_tool_use_id: null,
          message: {
            id: "msg_1",
            role: "assistant",
            content: [
              { type: "text", text: "Let me search for that." },
              {
                type: "tool_use",
                id: "tool_use_1",
                name: "Task",
                input: {
                  subagent_type: "code-reviewer",
                  prompt: "Review this code",
                  description: "Review code for bugs",
                },
              },
            ],
            usage: { input_tokens: 20, output_tokens: 15 },
          },
        } as any;

        // Subagent responds (parent_tool_use_id points to the Task tool)
        yield {
          type: "assistant",
          parent_tool_use_id: "tool_use_1",
          message: {
            id: "msg_2",
            role: "assistant",
            content: [
              { type: "text", text: "I found some issues." },
              {
                type: "tool_use",
                id: "tool_use_2",
                name: "Read",
                input: { file_path: "/src/main.ts" },
              },
            ],
            usage: { input_tokens: 10, output_tokens: 8 },
          },
        } as any;

        // Main agent continues after subagent completes
        yield {
          type: "assistant",
          parent_tool_use_id: null,
          message: {
            id: "msg_3",
            role: "assistant",
            content: [{ type: "text", text: "The review is complete." }],
            usage: { input_tokens: 15, output_tokens: 10 },
          },
        } as any;

        yield {
          type: "result",
          usage: { input_tokens: 45, output_tokens: 33 },
          num_turns: 3,
        };
      },
    };

    const wrapped = wrapClaudeAgentSDK(mockSDK);
    const messages: any[] = [];

    for await (const message of wrapped.query({ prompt: "Review my code" })) {
      messages.push(message);
    }

    expect(messages.length).toBe(4);

    // First message spawns Task tool
    expect(messages[0].type).toBe("assistant");
    expect(messages[0].parent_tool_use_id).toBeNull();
    expect(messages[0].message.content[1].name).toBe("Task");

    // Second message is from subagent
    expect(messages[1].type).toBe("assistant");
    expect(messages[1].parent_tool_use_id).toBe("tool_use_1");

    // Third message is back to main agent
    expect(messages[2].type).toBe("assistant");
    expect(messages[2].parent_tool_use_id).toBeNull();

    // Result
    expect(messages[3].type).toBe("result");
  });

  test("captures per-model usage from modelUsage", async () => {
    const { client, callSpy } = mockClient();
    const mockSDK = {
      ...createMockSDK(),
      query: async function* (
        _params: MockQueryParams
      ): AsyncGenerator<MockSDKMessage, void, unknown> {
        yield { type: "system", session_id: "session_abc123" };

        yield {
          type: "assistant",
          message: {
            id: "msg_1",
            role: "assistant",
            content: "Response",
            model: "claude-sonnet-4-20250514",
            usage: { input_tokens: 100, output_tokens: 40 },
          },
        };

        yield {
          type: "result",
          usage: { input_tokens: 100, output_tokens: 50 },
          modelUsage: {
            "claude-sonnet-4-20250514": {
              inputTokens: 80,
              outputTokens: 40,
              cacheReadInputTokens: 10,
              cacheCreationInputTokens: 10,
              webSearchRequests: 0,
              costUSD: 0.001,
              contextWindow: 200000,
            },
            "claude-haiku-4-20250514": {
              inputTokens: 20,
              outputTokens: 10,
              cacheReadInputTokens: 0,
              cacheCreationInputTokens: 0,
              webSearchRequests: 0,
              costUSD: 0.0001,
              contextWindow: 200000,
            },
          },
          session_id: "session_abc123",
          total_cost_usd: 0.0011,
        } as any;
      },
    };

    const wrapped = wrapClaudeAgentSDK(mockSDK, {
      client,
      tracingEnabled: true,
    });
    const messages: any[] = [];

    for await (const message of wrapped.query({ prompt: "Test" })) {
      messages.push(message);
    }

    expect(messages).toMatchObject([
      { type: "system", session_id: "session_abc123" },
      { type: "assistant", message: { content: "Response" } },
      {
        type: "result",
        modelUsage: {
          "claude-sonnet-4-20250514": { inputTokens: 80 },
          "claude-haiku-4-20250514": { inputTokens: 20, costUSD: 0.0001 },
        },
        total_cost_usd: 0.0011,
      },
    ]);

    const res = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
    expect(res).toMatchObject({
      nodes: ["claude.conversation:0", "claude.assistant.turn:1"],
      edges: [["claude.conversation:0", "claude.assistant.turn:1"]],
      data: {
        "claude.conversation:0": {
          run_type: "chain",
          inputs: { messages: [{ content: "Test", role: "user" }] },
          outputs: {
            output: { messages: [{ role: "assistant", content: "Response" }] },
          },
          extra: {
            metadata: {
              usage_metadata: {
                input_tokens: 120,
                output_tokens: 50,
                total_tokens: 170,
                input_token_details: { cache_read: 10, cache_creation: 10 },
                total_cost: 0.0011,
              },
              session_id: "session_abc123",
            },
          },
        },
        "claude.assistant.turn:1": {
          run_type: "llm",
          inputs: { messages: [{ content: "Test", role: "user" }] },
          outputs: {
            output: { messages: [{ role: "assistant", content: "Response" }] },
          },
          extra: {
            metadata: {
              usage_metadata: {
                input_token_details: {
                  ephemeral_5m_input_tokens: 10,
                  cache_read: 10,
                },
                input_tokens: 100,
                output_tokens: 40,
                total_tokens: 140,
              },
            },
          },
        },
      },
    });
  });

  test("handles nested tools within subagent", async () => {
    const { client, callSpy } = mockClient();
    const mockSDK = {
      ...createMockSDK(),
      query: async function* (
        _params: MockQueryParams
      ): AsyncGenerator<MockSDKMessage, void, unknown> {
        yield { type: "system", session_id: "session_abc123" };
        // Main agent spawns a Task
        yield {
          type: "assistant",
          parent_tool_use_id: null,
          message: {
            id: "msg_1",
            role: "assistant",
            content: [
              {
                type: "tool_use",
                id: "task_1",
                name: "Task",
                input: { subagent_type: "explorer", prompt: "Find files" },
              },
            ],
            usage: { input_tokens: 10, output_tokens: 5 },
          },
        } as any;

        // Subagent uses Glob tool
        yield {
          type: "assistant",
          parent_tool_use_id: "task_1",
          message: {
            id: "msg_2",
            role: "assistant",
            content: [
              {
                type: "tool_use",
                id: "glob_1",
                name: "Glob",
                input: { pattern: "**/*.ts" },
              },
            ],
            usage: { input_tokens: 5, output_tokens: 3 },
          },
        } as any;

        // Subagent uses Read tool
        yield {
          type: "assistant",
          parent_tool_use_id: "task_1",
          message: {
            id: "msg_3",
            role: "assistant",
            content: [
              {
                type: "tool_use",
                id: "read_1",
                name: "Read",
                input: { file_path: "/src/index.ts" },
              },
            ],
            usage: { input_tokens: 8, output_tokens: 4 },
          },
        } as any;

        yield {
          type: "result",
          usage: { input_tokens: 23, output_tokens: 12 },
          session_id: "session_abc123",
        };
      },
    };

    const wrapped = wrapClaudeAgentSDK(mockSDK, {
      client,
      tracingEnabled: true,
    });
    const messages: any[] = [];

    for await (const message of wrapped.query({
      prompt: "Find TypeScript files",
    })) {
      messages.push(message);
    }

    expect(messages).toMatchObject([
      { type: "system", session_id: "session_abc123" },
      {
        type: "assistant",
        parent_tool_use_id: null,
        message: {
          id: "msg_1",
          role: "assistant",
          content: [
            {
              type: "tool_use",
              id: "task_1",
              name: "Task",
              input: { subagent_type: "explorer", prompt: "Find files" },
            },
          ],
        },
      },
      {
        type: "assistant",
        parent_tool_use_id: "task_1",
        message: {
          role: "assistant",
          content: [{ type: "tool_use", name: "Glob" }],
        },
      },
      {
        type: "assistant",
        parent_tool_use_id: "task_1",
        message: {
          role: "assistant",
          content: [{ type: "tool_use", name: "Read" }],
        },
      },
      { type: "result", session_id: "session_abc123" },
    ]);

    const res = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
    expect(res).toMatchObject({
      nodes: [
        "claude.conversation:0",
        "explorer:1",
        "claude.assistant.turn:2",
        "Glob:3",
        "claude.assistant.turn:4",
        "Read:5",
        "claude.assistant.turn:6",
      ],
      edges: [
        ["claude.conversation:0", "explorer:1"],
        ["claude.conversation:0", "claude.assistant.turn:2"],
        ["explorer:1", "Glob:3"],
        ["explorer:1", "claude.assistant.turn:4"],
        ["explorer:1", "Read:5"],
        ["explorer:1", "claude.assistant.turn:6"],
      ],
      data: {
        "claude.conversation:0": {
          run_type: "chain",
          inputs: {
            messages: [{ content: "Find TypeScript files", role: "user" }],
          },
          outputs: {
            output: {
              messages: [
                {
                  role: "assistant",
                  content: [
                    {
                      type: "tool_use",
                      id: "task_1",
                      name: "Task",
                      input: {
                        subagent_type: "explorer",
                        prompt: "Find files",
                      },
                    },
                  ],
                },
              ],
            },
          },
        },
        "explorer:1": {
          run_type: "chain",
          inputs: { subagent_type: "explorer", prompt: "Find files" },
          error: "Run not completed (conversation ended)",
        },
        "Glob:3": {
          run_type: "tool",
          inputs: { input: { pattern: "**/*.ts" } },
          error: "Run not completed (conversation ended)",
        },
        "claude.assistant.turn:2": {
          run_type: "llm",
          inputs: {
            messages: [{ content: "Find TypeScript files", role: "user" }],
          },
          outputs: {
            output: {
              messages: [
                {
                  role: "assistant",
                  content: [
                    {
                      type: "tool_use",
                      id: "task_1",
                      name: "Task",
                      input: {
                        subagent_type: "explorer",
                        prompt: "Find files",
                      },
                    },
                  ],
                },
              ],
            },
          },
        },
        "Read:5": {
          run_type: "tool",
          inputs: { input: { file_path: "/src/index.ts" } },
          error: "Run not completed (conversation ended)",
        },
        "claude.assistant.turn:4": {
          name: "claude.assistant.turn",
          run_type: "llm",
          inputs: {
            messages: [
              { content: "Find TypeScript files", role: "user" },
              {
                content: [
                  {
                    type: "tool_use",
                    id: "task_1",
                    name: "Task",
                    input: { subagent_type: "explorer", prompt: "Find files" },
                  },
                ],
                role: "assistant",
              },
            ],
          },
          outputs: {
            output: {
              messages: [
                {
                  content: [
                    {
                      type: "tool_use",
                      id: "glob_1",
                      name: "Glob",
                      input: { pattern: "**/*.ts" },
                    },
                  ],
                  role: "assistant",
                },
              ],
            },
          },
        },
        "claude.assistant.turn:6": {
          run_type: "llm",
          inputs: {
            messages: [
              { content: "Find TypeScript files", role: "user" },
              {
                content: [
                  {
                    type: "tool_use",
                    id: "task_1",
                    name: "Task",
                    input: {
                      subagent_type: "explorer",
                      prompt: "Find files",
                    },
                  },
                ],
                role: "assistant",
              },
              {
                content: [
                  {
                    type: "tool_use",
                    id: "glob_1",
                    name: "Glob",
                    input: {
                      pattern: "**/*.ts",
                    },
                  },
                ],
                role: "assistant",
              },
            ],
          },
          outputs: {
            output: {
              messages: [
                {
                  content: [
                    {
                      type: "tool_use",
                      id: "read_1",
                      name: "Read",
                      input: {
                        file_path: "/src/index.ts",
                      },
                    },
                  ],
                  role: "assistant",
                },
              ],
            },
          },
        },
      },
    });
  });

  test("throws error if wrapped again", () => {
    const mockSDK = createMockSDK();
    const wrapped = wrapClaudeAgentSDK(mockSDK);
    expect(() => wrapClaudeAgentSDK(wrapped)).toThrow(
      "This instance of Claude Agent SDK has been already wrapped by `wrapClaudeAgentSDK`."
    );
  });

  test("subagent tool calling snapshot", async () => {
    const { client, callSpy } = mockClient();
    const mockSDK = {
      ...createMockSDK(),
      query: async function* (_params: MockQueryParams) {
        yield {
          type: "system",
          model: "claude-sonnet-4-6",
          claude_code_version: "2.1.50",
          session_id: "f8df5951-2251-47b9-a335-6d307c5223d6",
          uuid: "cb58646c-20e1-4d23-9a5e-4a0424ce9cdc",
        };

        yield {
          type: "assistant",
          message: {
            model: "claude-sonnet-4-6",
            id: "msg_01R2VbKy9UktL9xxDUybWSdi",
            type: "message",
            role: "assistant",
            content: [
              {
                type: "thinking",
                thinking:
                  "The user wants me to tell a joke about the latest date using the joke-agent. The current date is 2026-02-21. Let me launch the joke-agent with this information.",
              },
            ],
            stop_reason: null,
            stop_sequence: null,
            usage: {
              input_tokens: 3,
              cache_creation_input_tokens: 0,
              cache_read_input_tokens: 16021,
              cache_creation: {
                ephemeral_5m_input_tokens: 0,
                ephemeral_1h_input_tokens: 0,
              },
              output_tokens: 0,
              service_tier: "standard",
              inference_geo: "global",
            },
            context_management: null,
          },
          parent_tool_use_id: null,
          session_id: "f8df5951-2251-47b9-a335-6d307c5223d6",
          uuid: "38dad3e7-43c3-4d5d-8712-b5e6e891b723",
        };
        yield {
          type: "assistant",
          message: {
            model: "claude-sonnet-4-6",
            id: "msg_01R2VbKy9UktL9xxDUybWSdi",
            type: "message",
            role: "assistant",
            content: [
              {
                type: "tool_use",
                id: "toolu_01DEeFdMw6T3H28A3yynMUdd",
                name: "Task",
                input: {
                  description: "Tell a joke about today's date",
                  subagent_type: "joke-agent",
                  prompt:
                    "Tell me a funny joke about today's date: February 21, 2026.",
                },
                caller: { type: "direct" },
              },
            ],
            stop_reason: null,
            stop_sequence: null,
            usage: {
              input_tokens: 3,
              cache_creation_input_tokens: 0,
              cache_read_input_tokens: 16021,
              cache_creation: {
                ephemeral_5m_input_tokens: 0,
                ephemeral_1h_input_tokens: 0,
              },
              output_tokens: 0,
              service_tier: "standard",
              inference_geo: "global",
            },
            context_management: null,
          },
          parent_tool_use_id: null,
          session_id: "f8df5951-2251-47b9-a335-6d307c5223d6",
          uuid: "708d075a-c43c-44f2-988d-f8d99361e143",
        };
        yield {
          type: "user",
          message: {
            role: "user",
            content: [
              {
                type: "text",
                text: "Tell me a funny joke about today's date: February 21, 2026.",
              },
            ],
          },
          parent_tool_use_id: "toolu_01DEeFdMw6T3H28A3yynMUdd",
          session_id: "f8df5951-2251-47b9-a335-6d307c5223d6",
          uuid: "ece31846-d44f-4fa7-8746-a9f8cda2a538",
        };
        yield {
          type: "assistant",
          message: {
            model: "claude-sonnet-4-6",
            id: "msg_01N5XS2zZLpyHfN7kVtNQ9wL",
            type: "message",
            role: "assistant",
            content: [
              {
                type: "tool_use",
                id: "toolu_01PWkmKr2GaPemM7CLBLaxd2",
                name: "Bash",
                input: {
                  command: "date",
                  description: "Get current date and time",
                },
                caller: { type: "direct" },
              },
            ],
            stop_reason: null,
            stop_sequence: null,
            usage: {
              input_tokens: 3,
              cache_creation_input_tokens: 416,
              cache_read_input_tokens: 4814,
              cache_creation: {
                ephemeral_5m_input_tokens: 416,
                ephemeral_1h_input_tokens: 0,
              },
              output_tokens: 1,
              service_tier: "standard",
              inference_geo: "global",
            },
            context_management: null,
          },
          parent_tool_use_id: "toolu_01DEeFdMw6T3H28A3yynMUdd",
          session_id: "f8df5951-2251-47b9-a335-6d307c5223d6",
          uuid: "fca6d684-6471-4832-bfad-50709af185ab",
        };
        yield {
          type: "user",
          message: {
            role: "user",
            content: [
              {
                tool_use_id: "toolu_01PWkmKr2GaPemM7CLBLaxd2",
                type: "tool_result",
                content: "Sat Feb 21 20:13:00 CET 2026",
                is_error: false,
              },
            ],
          },
          parent_tool_use_id: "toolu_01DEeFdMw6T3H28A3yynMUdd",
          session_id: "f8df5951-2251-47b9-a335-6d307c5223d6",
          uuid: "33e50d92-5d44-4b1c-a41d-11e0834261e8",
        };
        yield {
          type: "user",
          message: {
            role: "user",
            content: [
              {
                tool_use_id: "toolu_01DEeFdMw6T3H28A3yynMUdd",
                type: "tool_result",
                content: [
                  {
                    type: "text",
                    text: 'The date is confirmed: Saturday, February 21, 2026. Here is your timely joke:\n\n---\n\nIt is February 21st, and I have to say -- this date is really underrated. January gets all the "new year, new me" hype, and February 14th gets all the roses... but February 21st? It just shows up, does the work, and asks for nothing in return.\n\nKind of like a senior developer on a Friday afternoon.\n\n---\n\nAnd a bonus one-liner for the date nerds:\n\nWhy did February 21st break up with February 22nd?\n\nBecause it said, "I need space -- and you always come after me."',
                  },
                  {
                    type: "text",
                    text: "agentId: a7bf945f9f2425f6f (for resuming to continue this agent's work if needed)\n<usage>total_tokens: 5501\ntool_uses: 1\nduration_ms: 8420</usage>",
                  },
                ],
              },
            ],
          },
          parent_tool_use_id: null,
          session_id: "f8df5951-2251-47b9-a335-6d307c5223d6",
          uuid: "25155ced-34a0-44aa-87c9-48660e801147",
          tool_use_result: {
            status: "completed",
            prompt:
              "Tell me a funny joke about today's date: February 21, 2026.",
            agentId: "a7bf945f9f2425f6f",
            content: [
              {
                type: "text",
                text: 'The date is confirmed: Saturday, February 21, 2026. Here is your timely joke:\n\n---\n\nIt is February 21st, and I have to say -- this date is really underrated. January gets all the "new year, new me" hype, and February 14th gets all the roses... but February 21st? It just shows up, does the work, and asks for nothing in return.\n\nKind of like a senior developer on a Friday afternoon.\n\n---\n\nAnd a bonus one-liner for the date nerds:\n\nWhy did February 21st break up with February 22nd?\n\nBecause it said, "I need space -- and you always come after me."',
              },
            ],
            totalDurationMs: 8420,
            totalTokens: 5501,
            totalToolUseCount: 1,
            usage: {
              input_tokens: 1,
              cache_creation_input_tokens: 117,
              cache_read_input_tokens: 5230,
              output_tokens: 153,
              server_tool_use: {
                web_search_requests: 0,
                web_fetch_requests: 0,
              },
              service_tier: "standard",
              cache_creation: {
                ephemeral_1h_input_tokens: 0,
                ephemeral_5m_input_tokens: 117,
              },
              inference_geo: "",
              iterations: [],
              speed: "standard",
            },
          },
        };
        yield {
          type: "assistant",
          message: {
            model: "claude-sonnet-4-6",
            id: "msg_01JRsr4U5QfWhSkNoErECJqQ",
            type: "message",
            role: "assistant",
            content: [
              {
                type: "text",
                text: 'Here\'s what the joke-agent came up with for today\'s date, **February 21, 2026**:\n\n---\n\nFebruary 21st is really underrated. January gets all the "new year, new me" hype, and February 14th gets all the roses... but February 21st? It just shows up, does the work, and asks for nothing in return.\n\n*Kind of like a senior developer on a Friday afternoon.* 😄\n\n---\n\n**Bonus one-liner:**\n\nWhy did February 21st break up with February 22nd?\n\nBecause it said, *"I need space — and you always come after me."* 😂',
              },
            ],
            stop_reason: null,
            stop_sequence: null,
            usage: {
              input_tokens: 1,
              cache_creation_input_tokens: 390,
              cache_read_input_tokens: 16021,
              cache_creation: {
                ephemeral_5m_input_tokens: 390,
                ephemeral_1h_input_tokens: 0,
              },
              output_tokens: 1,
              service_tier: "standard",
              inference_geo: "global",
            },
            context_management: null,
          },
          parent_tool_use_id: null,
          session_id: "f8df5951-2251-47b9-a335-6d307c5223d6",
          uuid: "15f0964b-4f58-43d7-a828-0a282c7d62bb",
        };
        yield {
          type: "system",
          subtype: "task_started",
          task_id: "a7bf945f9f2425f6f",
          tool_use_id: "toolu_01DEeFdMw6T3H28A3yynMUdd",
          description: "Tell a joke about today's date",
          task_type: "local_agent",
          uuid: "d878891c-1aab-4ce1-8b63-a13a2651ddb6",
          session_id: "f8df5951-2251-47b9-a335-6d307c5223d6",
        };
        yield {
          type: "result",
          subtype: "success",
          is_error: false,
          num_turns: 2,
          result:
            'Here\'s what the joke-agent came up with for today\'s date, **February 21, 2026**:\n\n---\n\nFebruary 21st is really underrated. January gets all the "new year, new me" hype, and February 14th gets all the roses... but February 21st? It just shows up, does the work, and asks for nothing in return.\n\n*Kind of like a senior developer on a Friday afternoon.* 😄\n\n---\n\n**Bonus one-liner:**\n\nWhy did February 21st break up with February 22nd?\n\nBecause it said, *"I need space — and you always come after me."* 😂',
          stop_reason: null,
          session_id: "f8df5951-2251-47b9-a335-6d307c5223d6",
          total_cost_usd: 0.041286750000000004,
          usage: {
            input_tokens: 4,
            cache_creation_input_tokens: 390,
            cache_read_input_tokens: 32042,
            output_tokens: 319,
            server_tool_use: { web_search_requests: 0, web_fetch_requests: 0 },
            service_tier: "standard",
            cache_creation: {
              ephemeral_1h_input_tokens: 0,
              ephemeral_5m_input_tokens: 390,
            },
            inference_geo: "",
            iterations: [],
            speed: "standard",
          },
          modelUsage: {
            "claude-sonnet-4-6": {
              inputTokens: 8,
              outputTokens: 558,
              cacheReadInputTokens: 42086,
              cacheCreationInputTokens: 923,
              webSearchRequests: 0,
              costUSD: 0.040801750000000005,
              contextWindow: 200000,
              maxOutputTokens: 32000,
            },
            "claude-haiku-4-5-20251001": {
              inputTokens: 325,
              outputTokens: 32,
              cacheReadInputTokens: 0,
              cacheCreationInputTokens: 0,
              webSearchRequests: 0,
              costUSD: 0.00048499999999999997,
              contextWindow: 200000,
              maxOutputTokens: 32000,
            },
          },
          uuid: "bfa7563d-e3c9-4a60-955d-d770ce56d024",
        };
      },
    };

    const wrapped = wrapClaudeAgentSDK(mockSDK, {
      client,
      tracingEnabled: true,
    });

    const result: unknown[] = [];
    for await (const message of wrapped.query({
      prompt: "List available files in the current directory",
      options: {
        maxTurns: 10,
        allowedTools: ["Read", "Grep"],
      },
    })) {
      result.push(message);
    }

    const res = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
    expect(res).toMatchObject({
      nodes: [
        "claude.conversation:0",
        "claude.assistant.turn:1",
        "joke-agent:2",
        "Bash:3",
        "claude.assistant.turn:4",
        "claude.assistant.turn:5",
      ],
      edges: [
        ["claude.conversation:0", "claude.assistant.turn:1"],
        ["claude.conversation:0", "joke-agent:2"],
        ["joke-agent:2", "Bash:3"],
        ["joke-agent:2", "claude.assistant.turn:4"],
        ["claude.conversation:0", "claude.assistant.turn:5"],
      ],
      data: {
        "claude.conversation:0": {
          run_type: "chain",
          inputs: {
            messages: [
              {
                content: "List available files in the current directory",
                role: "user",
              },
            ],
            options: {
              maxTurns: 10,
              allowedTools: ["Read", "Grep"],
            },
          },
          outputs: {
            output: {
              messages: [
                {
                  role: "assistant",
                  content: [
                    {
                      type: "thinking",
                      thinking:
                        "The user wants me to tell a joke about the latest date using the joke-agent. The current date is 2026-02-21. Let me launch the joke-agent with this information.",
                      signature: "",
                    },
                  ],
                },
                {
                  role: "assistant",
                  content: [
                    {
                      type: "tool_use",
                      id: "toolu_01DEeFdMw6T3H28A3yynMUdd",
                      name: "Task",
                      input: {
                        description: "Tell a joke about today's date",
                        subagent_type: "joke-agent",
                        prompt:
                          "Tell me a funny joke about today's date: February 21, 2026.",
                      },
                    },
                  ],
                },
                {
                  type: "tool_result",
                  tool_use_id: "toolu_01DEeFdMw6T3H28A3yynMUdd",
                  content: [
                    {
                      type: "text",
                      text: 'The date is confirmed: Saturday, February 21, 2026. Here is your timely joke:\n\n---\n\nIt is February 21st, and I have to say -- this date is really underrated. January gets all the "new year, new me" hype, and February 14th gets all the roses... but February 21st? It just shows up, does the work, and asks for nothing in return.\n\nKind of like a senior developer on a Friday afternoon.\n\n---\n\nAnd a bonus one-liner for the date nerds:\n\nWhy did February 21st break up with February 22nd?\n\nBecause it said, "I need space -- and you always come after me."',
                    },
                    {
                      type: "text",
                      text: "agentId: a7bf945f9f2425f6f (for resuming to continue this agent's work if needed)\n<usage>total_tokens: 5501\ntool_uses: 1\nduration_ms: 8420</usage>",
                    },
                  ],
                  is_error: false,
                  role: "tool",
                },
                {
                  role: "assistant",
                  content: [
                    {
                      type: "text",
                      text: 'Here\'s what the joke-agent came up with for today\'s date, **February 21, 2026**:\n\n---\n\nFebruary 21st is really underrated. January gets all the "new year, new me" hype, and February 14th gets all the roses... but February 21st? It just shows up, does the work, and asks for nothing in return.\n\n*Kind of like a senior developer on a Friday afternoon.* 😄\n\n---\n\n**Bonus one-liner:**\n\nWhy did February 21st break up with February 22nd?\n\nBecause it said, *"I need space — and you always come after me."* 😂',
                    },
                  ],
                },
              ],
            },
          },
        },
        "claude.assistant.turn:1": {
          run_type: "llm",
          inputs: {
            messages: [
              {
                content: "List available files in the current directory",
                role: "user",
              },
            ],
          },
          outputs: {
            output: {
              messages: [
                {
                  content: [
                    {
                      type: "thinking",
                      thinking:
                        "The user wants me to tell a joke about the latest date using the joke-agent. The current date is 2026-02-21. Let me launch the joke-agent with this information.",
                      signature: "",
                    },
                  ],
                  role: "assistant",
                },
                {
                  content: [
                    {
                      type: "tool_use",
                      id: "toolu_01DEeFdMw6T3H28A3yynMUdd",
                      name: "Task",
                      input: {
                        description: "Tell a joke about today's date",
                        subagent_type: "joke-agent",
                        prompt:
                          "Tell me a funny joke about today's date: February 21, 2026.",
                      },
                    },
                  ],
                  role: "assistant",
                },
              ],
            },
          },
        },
        "joke-agent:2": {
          run_type: "chain",
          inputs: {
            description: "Tell a joke about today's date",
            subagent_type: "joke-agent",
            prompt:
              "Tell me a funny joke about today's date: February 21, 2026.",
          },
          outputs: {
            status: "completed",
            prompt:
              "Tell me a funny joke about today's date: February 21, 2026.",
            agentId: "a7bf945f9f2425f6f",
            content: [
              {
                type: "text",
                text: 'The date is confirmed: Saturday, February 21, 2026. Here is your timely joke:\n\n---\n\nIt is February 21st, and I have to say -- this date is really underrated. January gets all the "new year, new me" hype, and February 14th gets all the roses... but February 21st? It just shows up, does the work, and asks for nothing in return.\n\nKind of like a senior developer on a Friday afternoon.\n\n---\n\nAnd a bonus one-liner for the date nerds:\n\nWhy did February 21st break up with February 22nd?\n\nBecause it said, "I need space -- and you always come after me."',
              },
            ],
            totalDurationMs: 8420,
            totalTokens: 5501,
            totalToolUseCount: 1,
          },
        },
        "Bash:3": {
          run_type: "tool",
          inputs: {
            input: {
              command: "date",
              description: "Get current date and time",
            },
          },
          outputs: {
            content: "Sat Feb 21 20:13:00 CET 2026",
          },
        },
        "claude.assistant.turn:4": {
          run_type: "llm",
          inputs: {
            messages: [
              {
                content: "List available files in the current directory",
                role: "user",
              },
              {
                content: [
                  {
                    type: "thinking",
                    thinking:
                      "The user wants me to tell a joke about the latest date using the joke-agent. The current date is 2026-02-21. Let me launch the joke-agent with this information.",
                    signature: "",
                  },
                ],
                role: "assistant",
              },
              {
                content: [
                  {
                    type: "tool_use",
                    id: "toolu_01DEeFdMw6T3H28A3yynMUdd",
                    name: "Task",
                    input: {
                      description: "Tell a joke about today's date",
                      subagent_type: "joke-agent",
                      prompt:
                        "Tell me a funny joke about today's date: February 21, 2026.",
                    },
                  },
                ],
                role: "assistant",
              },
              {
                content: [
                  {
                    type: "text",
                    text: "Tell me a funny joke about today's date: February 21, 2026.",
                  },
                ],
                role: "user",
              },
            ],
          },
          outputs: {
            output: {
              messages: [
                {
                  content: [
                    {
                      type: "tool_use",
                      id: "toolu_01PWkmKr2GaPemM7CLBLaxd2",
                      name: "Bash",
                      input: {
                        command: "date",
                        description: "Get current date and time",
                      },
                    },
                  ],
                  role: "assistant",
                },
              ],
            },
          },
        },
        "claude.assistant.turn:5": {
          run_type: "llm",
          inputs: {
            messages: [
              {
                content: "List available files in the current directory",
                role: "user",
              },
              {
                content: [
                  {
                    type: "thinking",
                    thinking:
                      "The user wants me to tell a joke about the latest date using the joke-agent. The current date is 2026-02-21. Let me launch the joke-agent with this information.",
                    signature: "",
                  },
                ],
                role: "assistant",
              },
              {
                content: [
                  {
                    type: "tool_use",
                    id: "toolu_01DEeFdMw6T3H28A3yynMUdd",
                    name: "Task",
                    input: {
                      description: "Tell a joke about today's date",
                      subagent_type: "joke-agent",
                      prompt:
                        "Tell me a funny joke about today's date: February 21, 2026.",
                    },
                  },
                ],
                role: "assistant",
              },
              {
                type: "tool_result",
                tool_use_id: "toolu_01DEeFdMw6T3H28A3yynMUdd",
                content: [
                  {
                    type: "text",
                    text: 'The date is confirmed: Saturday, February 21, 2026. Here is your timely joke:\n\n---\n\nIt is February 21st, and I have to say -- this date is really underrated. January gets all the "new year, new me" hype, and February 14th gets all the roses... but February 21st? It just shows up, does the work, and asks for nothing in return.\n\nKind of like a senior developer on a Friday afternoon.\n\n---\n\nAnd a bonus one-liner for the date nerds:\n\nWhy did February 21st break up with February 22nd?\n\nBecause it said, "I need space -- and you always come after me."',
                  },
                  {
                    type: "text",
                    text: "agentId: a7bf945f9f2425f6f (for resuming to continue this agent's work if needed)\n<usage>total_tokens: 5501\ntool_uses: 1\nduration_ms: 8420</usage>",
                  },
                ],
                is_error: false,
                role: "tool",
              },
            ],
          },
          outputs: {
            output: {
              messages: [
                {
                  content: [
                    {
                      type: "text",
                      text: 'Here\'s what the joke-agent came up with for today\'s date, **February 21, 2026**:\n\n---\n\nFebruary 21st is really underrated. January gets all the "new year, new me" hype, and February 14th gets all the roses... but February 21st? It just shows up, does the work, and asks for nothing in return.\n\n*Kind of like a senior developer on a Friday afternoon.* 😄\n\n---\n\n**Bonus one-liner:**\n\nWhy did February 21st break up with February 22nd?\n\nBecause it said, *"I need space — and you always come after me."* 😂',
                    },
                  ],
                  role: "assistant",
                },
              ],
            },
          },
        },
      },
    });
  });

  test("tool calling snapshot", async () => {
    const { client, callSpy } = mockClient();
    const mockSDK = {
      ...createMockSDK(),
      query: async function* (_params: MockQueryParams) {
        yield {
          type: "system",
          session_id: "session_123",
          model: "claude-sonnet-4-5-20250929",
        };

        yield {
          type: "assistant",
          message: {
            model: "claude-sonnet-4-5-20250929",
            id: "msg_01Ln71J2foBvg5RRnPyxwLDr",
            type: "message",
            role: "assistant",
            content: [
              {
                type: "text",
                text: "I'll list the files in the current directory for you.",
              },
            ],
            stop_reason: null,
            stop_sequence: null,
            usage: {
              input_tokens: 3,
              cache_creation_input_tokens: 0,
              cache_read_input_tokens: 15157,
              cache_creation: {
                ephemeral_5m_input_tokens: 0,
                ephemeral_1h_input_tokens: 0,
              },
              output_tokens: 5,
              service_tier: "standard",
            },
            context_management: null,
          },
          parent_tool_use_id: null,
          session_id: "session_123",
        };

        yield {
          type: "assistant",
          message: {
            model: "claude-sonnet-4-5-20250929",
            id: "msg_01Ln71J2foBvg5RRnPyxwLDr",
            type: "message",
            role: "assistant",
            content: [
              {
                type: "tool_use",
                id: "toolu_01C6pxkyGufmwfL2fGAot85b",
                name: "Bash",
                input: {
                  command: "ls -la",
                  description: "List files in current directory",
                },
              },
            ],
            stop_reason: null,
            stop_sequence: null,
            usage: {
              input_tokens: 3,
              cache_creation_input_tokens: 0,
              cache_read_input_tokens: 15157,
              cache_creation: {
                ephemeral_5m_input_tokens: 0,
                ephemeral_1h_input_tokens: 0,
              },
              output_tokens: 88,
              service_tier: "standard",
            },
            context_management: null,
          },
          parent_tool_use_id: null,
          session_id: "session_123",
        };

        yield {
          type: "user",
          message: {
            role: "user",
            content: [
              {
                tool_use_id: "toolu_01C6pxkyGufmwfL2fGAot85b",
                type: "tool_result",
                content: "total 0",
                is_error: false,
              },
            ],
          },
          parent_tool_use_id: null,
          session_id: "session_123",
          tool_use_result: {
            stdout: "total 0",
            stderr: "",
            interrupted: false,
            isImage: false,
          },
        };

        yield {
          type: "assistant",
          message: {
            model: "claude-sonnet-4-5-20250929",
            id: "msg_01XraJX1NbRz2WsTNYqyqAdf",
            type: "message",
            role: "assistant",
            content: [
              {
                type: "text",
                text: "Here are the files",
              },
            ],
            stop_reason: null,
            stop_sequence: null,
            usage: {
              input_tokens: 6,
              cache_creation_input_tokens: 0,
              cache_read_input_tokens: 17833,
              cache_creation: {
                ephemeral_5m_input_tokens: 0,
                ephemeral_1h_input_tokens: 0,
              },
              output_tokens: 342,
              service_tier: "standard",
            },
            context_management: null,
          },
          parent_tool_use_id: null,
          session_id: "session_123",
        };

        yield {
          type: "result",
          subtype: "success",
          is_error: false,
          duration_ms: 9036,
          duration_api_ms: 19639,
          num_turns: 2,
          result: "Here are the files",
          session_id: "session_123",
          total_cost_usd: 0.0261164,
          usage: {
            input_tokens: 9,
            cache_creation_input_tokens: 0,
            cache_read_input_tokens: 32990,
            output_tokens: 430,
            server_tool_use: { web_search_requests: 0, web_fetch_requests: 0 },
            service_tier: "standard",
            cache_creation: {
              ephemeral_1h_input_tokens: 0,
              ephemeral_5m_input_tokens: 0,
            },
          },
          modelUsage: {
            "claude-sonnet-4-5-20250929": {
              inputTokens: 12,
              outputTokens: 732,
              cacheReadInputTokens: 34118,
              cacheCreationInputTokens: 0,
              webSearchRequests: 0,
              costUSD: 0.021251400000000004,
              contextWindow: 200000,
            },
            "claude-haiku-4-5-20251001": {
              inputTokens: 3890,
              outputTokens: 195,
              cacheReadInputTokens: 0,
              cacheCreationInputTokens: 0,
              webSearchRequests: 0,
              costUSD: 0.0048649999999999995,
              contextWindow: 200000,
            },
          },
          permission_denials: [],
        };
      },
    };

    const wrapped = wrapClaudeAgentSDK(mockSDK, {
      client,
      tracingEnabled: true,
    });

    const result: unknown[] = [];
    for await (const message of wrapped.query({
      prompt: "List available files in the current directory",
      options: {
        maxTurns: 10,
        allowedTools: ["Read", "Grep"],
      },
    })) {
      result.push(message);
    }

    const res = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
    expect(res).toMatchObject({
      nodes: [
        "claude.conversation:0",
        "claude.assistant.turn:1",
        "Bash:2",
        "claude.assistant.turn:3",
      ],
      edges: [
        ["claude.conversation:0", "claude.assistant.turn:1"],
        ["claude.conversation:0", "Bash:2"],
        ["claude.conversation:0", "claude.assistant.turn:3"],
      ],
      data: {
        "claude.conversation:0": {
          run_type: "chain",
          inputs: {
            messages: [
              {
                content: "List available files in the current directory",
                role: "user",
              },
            ],
            options: {
              allowedTools: ["Read", "Grep"],
              maxTurns: 10,
            },
          },
          outputs: {
            output: {
              messages: [
                {
                  role: "assistant",
                  content: [
                    {
                      text: "I'll list the files in the current directory for you.",
                      type: "text",
                    },
                  ],
                },
                {
                  role: "assistant",
                  content: [
                    {
                      id: "toolu_01C6pxkyGufmwfL2fGAot85b",
                      input: {
                        command: "ls -la",
                        description: "List files in current directory",
                      },
                      name: "Bash",
                      type: "tool_use",
                    },
                  ],
                },
                {
                  role: "tool",
                  type: "tool_result",
                  tool_use_id: "toolu_01C6pxkyGufmwfL2fGAot85b",
                  content: "total 0",
                },
                {
                  role: "assistant",
                  content: [
                    {
                      text: "Here are the files",
                      type: "text",
                    },
                  ],
                },
              ],
            },
          },
        },
        "claude.assistant.turn:1": {
          run_type: "llm",
          inputs: {
            messages: [
              {
                content: "List available files in the current directory",
                role: "user",
              },
            ],
          },
          outputs: {
            output: {
              messages: [
                {
                  content: [
                    {
                      text: "I'll list the files in the current directory for you.",
                      type: "text",
                    },
                  ],
                  role: "assistant",
                },
                {
                  content: [
                    {
                      id: "toolu_01C6pxkyGufmwfL2fGAot85b",
                      input: {
                        command: "ls -la",
                        description: "List files in current directory",
                      },
                      name: "Bash",
                      type: "tool_use",
                    },
                  ],
                  role: "assistant",
                },
              ],
            },
          },
        },
        "Bash:2": {
          run_type: "tool",
          inputs: { input: { command: "ls -la" } },
          outputs: {
            stdout: "total 0",
          },
        },
        "claude.assistant.turn:3": {
          run_type: "llm",
          inputs: {
            messages: [
              {
                content: "List available files in the current directory",
                role: "user",
              },
              {
                content: [
                  {
                    text: "I'll list the files in the current directory for you.",
                    type: "text",
                  },
                ],
                role: "assistant",
              },
              {
                content: [
                  {
                    id: "toolu_01C6pxkyGufmwfL2fGAot85b",
                    input: {
                      command: "ls -la",
                      description: "List files in current directory",
                    },
                    name: "Bash",
                    type: "tool_use",
                  },
                ],
                role: "assistant",
              },
              {
                role: "tool",
                tool_use_id: "toolu_01C6pxkyGufmwfL2fGAot85b",
                content: "total 0",
              },
            ],
          },
          outputs: {
            output: {
              messages: [
                {
                  content: [{ text: "Here are the files", type: "text" }],
                  role: "assistant",
                },
              ],
            },
          },
        },
      },
    });
  });
});
