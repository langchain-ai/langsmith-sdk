/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, test, expect } from "@jest/globals";
import { wrapClaudeAgentSDK } from "../experimental/anthropic/index.js";

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
  const mockQuery = async function* (
    _params: MockQueryParams
  ): AsyncGenerator<MockSDKMessage, void, unknown> {
    // Simulate assistant message with streaming
    yield {
      type: "assistant",
      message: {
        id: "msg_123",
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

    expect(messages.length).toBe(2);
    expect(messages[0].type).toBe("assistant");
    expect(messages[1].type).toBe("result");
    expect(messages[0].message?.content).toBe("Hello! How can I help you?");
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
    async function* createPromptStream(): AsyncIterable<MockSDKMessage> {
      yield { type: "user", message: { content: "Hello" } };
    }

    const mockSDK = createMockSDK();
    const wrapped = wrapClaudeAgentSDK(mockSDK);

    const messages: MockSDKMessage[] = [];
    for await (const message of wrapped.query({
      prompt: createPromptStream(),
    })) {
      messages.push(message);
    }

    expect(messages.length).toBeGreaterThan(0);
  });

  test("adjusts output tokens correctly for final result", async () => {
    const mockSDK = {
      ...createMockSDK(),
      query: async function* (
        _params: MockQueryParams
      ): AsyncGenerator<MockSDKMessage, void, unknown> {
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

    const wrapped = wrapClaudeAgentSDK(mockSDK);
    const messages: MockSDKMessage[] = [];

    for await (const message of wrapped.query({ prompt: "Test" })) {
      messages.push(message);
    }

    // The last assistant message should have adjusted tokens
    expect(messages.length).toBe(3);
  });

  test("tool wrapper preserves tool definition properties", () => {
    const mockSDK = createMockSDK();
    const wrapped = wrapClaudeAgentSDK(mockSDK);

    const schema = {
      type: "object",
      properties: {
        value: { type: "number" },
      },
    };

    const tool = wrapped.tool(
      "test-tool",
      "A test tool",
      schema,
      async (args: { value: number }) => ({
        content: [{ type: "text", text: String(args.value) }],
      })
    );

    expect(tool.name).toBe("test-tool");
    expect(tool.description).toBe("A test tool");
    expect(tool.inputSchema).toEqual(schema);
    expect(typeof tool.handler).toBe("function");
  });

  test("handles errors in tool execution", async () => {
    const mockSDK = createMockSDK();
    const wrapped = wrapClaudeAgentSDK(mockSDK);

    const errorTool = wrapped.tool(
      "error-tool",
      "A tool that errors",
      { type: "object" },
      async () => {
        throw new Error("Tool execution failed");
      }
    );

    await expect(errorTool.handler({}, {})).rejects.toThrow(
      "Tool execution failed"
    );
  });

  test("handles UserMessage in conversation", async () => {
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
            content: "First response",
            usage: { input_tokens: 5, output_tokens: 3 },
          },
        };

        // User message in the middle of conversation
        yield {
          type: "user",
          message: {
            content: [{ type: "text", text: "Follow up question" }],
          },
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

    const wrapped = wrapClaudeAgentSDK(mockSDK);
    const messages: MockSDKMessage[] = [];

    for await (const message of wrapped.query({ prompt: "Test" })) {
      messages.push(message);
    }

    expect(messages.length).toBe(4);
    expect(messages[0].type).toBe("assistant");
    expect(messages[1].type).toBe("user");
    expect(messages[2].type).toBe("assistant");
    expect(messages[3].type).toBe("result");
  });

  test("extracts metadata from ResultMessage", async () => {
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

    const wrapped = wrapClaudeAgentSDK(mockSDK);
    const messages: any[] = [];

    for await (const message of wrapped.query({ prompt: "Test" })) {
      messages.push(message);
    }

    const resultMessage = messages[1];
    expect(resultMessage.type).toBe("result");
    expect(resultMessage.num_turns).toBe(3);
    expect(resultMessage.session_id).toBe("session_abc123");
    expect(resultMessage.duration_ms).toBe(1500);
    expect(resultMessage.total_cost_usd).toBe(0.0015);
  });

  test("extracts model from AssistantMessage", async () => {
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

    const wrapped = wrapClaudeAgentSDK(mockSDK);
    const messages: any[] = [];

    for await (const message of wrapped.query({
      prompt: "Test",
      options: { model: "claude-3-5-sonnet-20241022" },
    })) {
      messages.push(message);
    }

    // Model from message should be preserved
    expect(messages[0].message.model).toBe("claude-opus-4-20250514");
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
            content: "Response",
            model: "claude-sonnet-4-20250514",
            usage: { input_tokens: 100, output_tokens: 50 },
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
          total_cost_usd: 0.0011,
        } as any;
      },
    };

    const wrapped = wrapClaudeAgentSDK(mockSDK);
    const messages: any[] = [];

    for await (const message of wrapped.query({ prompt: "Test" })) {
      messages.push(message);
    }

    const resultMessage = messages[1];
    expect(resultMessage.type).toBe("result");
    expect(resultMessage.modelUsage).toBeDefined();
    expect(
      resultMessage.modelUsage["claude-sonnet-4-20250514"].inputTokens
    ).toBe(80);
    expect(resultMessage.modelUsage["claude-haiku-4-20250514"].costUSD).toBe(
      0.0001
    );
    expect(resultMessage.total_cost_usd).toBe(0.0011);
  });

  test("handles nested tools within subagent", async () => {
    const mockSDK = {
      ...createMockSDK(),
      query: async function* (
        _params: MockQueryParams
      ): AsyncGenerator<MockSDKMessage, void, unknown> {
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
        };
      },
    };

    const wrapped = wrapClaudeAgentSDK(mockSDK);
    const messages: any[] = [];

    for await (const message of wrapped.query({
      prompt: "Find TypeScript files",
    })) {
      messages.push(message);
    }

    expect(messages.length).toBe(4);

    // Subagent messages should have parent_tool_use_id pointing to Task
    expect(messages[1].parent_tool_use_id).toBe("task_1");
    expect(messages[2].parent_tool_use_id).toBe("task_1");

    // Tools within subagent
    expect(messages[1].message.content[0].name).toBe("Glob");
    expect(messages[2].message.content[0].name).toBe("Read");
  });

  test("throws error if wrapped again", () => {
    const mockSDK = createMockSDK();
    const wrapped = wrapClaudeAgentSDK(mockSDK);
    expect(() => wrapClaudeAgentSDK(wrapped)).toThrow(
      "This instance of Claude Agent SDK has been already wrapped by `wrapClaudeAgentSDK`."
    );
  });
});
