/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable no-process-env */
/* eslint-disable import/no-extraneous-dependencies */
import { describe, beforeAll, test, expect } from "@jest/globals";
import * as claudeSDK from "@anthropic-ai/claude-agent-sdk";
import { z } from "zod";
import { wrapClaudeAgentSDK } from "../experimental/anthropic/index.js";
import { traceable } from "../traceable.js";
import { mockClient } from "./utils/mock_client.js";
import { getAssumedTreeFromCalls } from "./utils/tree.js";

// Note: These tests require an ANTHROPIC_API_KEY environment variable.
// They are skipped by default to avoid requiring API keys in CI.
//
// To run these tests:
// 1. Set ANTHROPIC_API_KEY environment variable
// 2. Remove .skip from the describe block

describe("wrapClaudeAgentSDK - Real API Integration", () => {
  const wrappedSDK = wrapClaudeAgentSDK(claudeSDK, {
    project_name: "claude-agent-sdk-test",
    tags: ["integration-test"],
  }) as typeof claudeSDK;

  beforeAll(() => {
    if (!process.env.ANTHROPIC_API_KEY) {
      throw new Error("ANTHROPIC_API_KEY environment variable is required");
    }
  });

  const WEATHER_PROMPT =
    "You have a get_weather tool. When the user asks about weather, call it. Only call the tool once.";

  const allowAllTools = async (
    _toolName: string,
    input: Record<string, unknown>
  ) => ({
    behavior: "allow" as const,
    updatedInput: input,
  });

  const consumeQuery = async (
    query: AsyncIterable<claudeSDK.SDKMessage>
  ): Promise<any[]> => {
    const messages: any[] = [];
    for await (const message of query) {
      messages.push(message);
    }
    return messages;
  };

  const toolUseNames = (messages: any[]) =>
    messages.flatMap((message) =>
      message.type === "assistant" && Array.isArray(message.message?.content)
        ? message.message.content
            .filter((block: any) => block.type === "tool_use")
            .map((block: any) => block.name)
        : []
    );

  const stringifyToolResultContent = (content: any): string => {
    if (typeof content === "string") return content;
    if (content == null) return "";
    if (Array.isArray(content)) {
      return content.map(stringifyToolResultContent).join("\n");
    }
    if (typeof content === "object") {
      if (typeof content.text === "string") return content.text;
      try {
        return JSON.stringify(content);
      } catch {
        return String(content);
      }
    }
    return String(content);
  };

  const toolResultContents = (messages: any[]) =>
    messages.flatMap((message) =>
      message.type === "user" && Array.isArray(message.message?.content)
        ? message.message.content
            .filter((block: any) => block.type === "tool_result")
            .map((block: any) => stringifyToolResultContent(block.content))
        : []
    );

  test("query with simple prompt", async () => {
    const messages: any[] = [];

    for await (const message of wrappedSDK.query({
      prompt: "Say 'Hello from LangSmith!' and nothing else.",
      options: {
        model: "haiku",
        maxTurns: 1,
      },
    })) {
      // Debug: log each message type and key properties
      const msg = message as any;
      console.log("Message:", {
        type: msg.type,
        id: msg.message?.id || msg.uuid,
        hasMessage: !!msg.message,
        messageModel: msg.message?.model,
        messageUsage: msg.message?.usage,
        usage: msg.usage,
        model: msg.model,
        stopReason: msg.message?.stop_reason,
      });
      messages.push(message);
    }

    // Log summary
    console.log("Total messages:", messages.length);
    console.log(
      "Message types:",
      messages.map((m) => m.type)
    );

    // Should have at least assistant message and result message
    expect(messages.length).toBeGreaterThan(0);

    // Find assistant message
    const assistantMessage = messages.find((m) => m.type === "assistant");
    expect(assistantMessage).toBeDefined();
    expect(assistantMessage.message?.content).toBeDefined();

    // Find result message
    const resultMessage = messages.find((m) => m.type === "result");
    expect(resultMessage).toBeDefined();
    expect(resultMessage.usage).toBeDefined();
    expect(resultMessage.usage.input_tokens).toBeGreaterThan(0);
    expect(resultMessage.usage.output_tokens).toBeGreaterThan(0);
  });

  test("query with subagent usage", async () => {
    const messages: any[] = [];

    // Configure a subagent that can do calculations
    for await (const message of wrappedSDK.query({
      prompt:
        "I need to calculate 25 * 4 + 100. Please delegate this to the calculator subagent.",
      options: {
        model: "haiku",
        maxTurns: 10,
        agents: {
          calculator: {
            description: "A subagent that performs mathematical calculations",
            prompt:
              "You are a calculator assistant. Perform the requested calculation and return the result.",
            tools: [],
            model: "haiku",
          },
        },
      },
    })) {
      messages.push(message);
    }

    expect(messages.length).toBeGreaterThan(0);

    // Verify we have assistant messages
    const assistantMessages = messages.filter((m) => m.type === "assistant");
    expect(assistantMessages.length).toBeGreaterThan(0);

    const resultMessage = messages.find((m) => m.type === "result");
    expect(resultMessage).toBeDefined();
    expect(resultMessage.usage).toBeDefined();
    expect(resultMessage.modelUsage).toBeDefined();

    // Verify token usage
    expect(resultMessage.usage.output_tokens).toBeGreaterThan(0);
    expect(resultMessage.usage.input_tokens).toBeGreaterThan(0);
  });

  test("query with MCP tool usage", async () => {
    const calculator = wrappedSDK.tool(
      "calculator",
      "Performs basic arithmetic operations",
      {
        operation: z.enum(["add", "subtract", "multiply", "divide"]),
        a: z.number(),
        b: z.number(),
      },
      async (args: any) => {
        let result: number;
        switch (args.operation) {
          case "add":
            result = args.a + args.b;
            break;
          case "subtract":
            result = args.a - args.b;
            break;
          case "multiply":
            result = args.a * args.b;
            break;
          case "divide":
            result = args.a / args.b;
            break;
          default:
            throw new Error("Unknown operation");
        }
        return {
          content: [{ type: "text", text: `Result: ${result}` }],
        };
      }
    );

    // Create SDK MCP server with the tool
    const mcpServer = wrappedSDK.createSdkMcpServer({
      name: "calculator-server",
      tools: [calculator],
    });

    const messages: any[] = [];

    for await (const message of wrappedSDK.query({
      prompt:
        "Use the calculator tool to compute 42 + 17, then tell me the result.",
      options: {
        model: "haiku",
        maxTurns: 5,
        allowDangerouslySkipPermissions: true,
        permissionMode: "bypassPermissions",
        mcpServers: {
          calculator: mcpServer,
        },
      },
    })) {
      messages.push(message);
    }

    expect(messages.length).toBeGreaterThan(0);

    // Verify basic message structure
    const assistantMessages = messages.filter((m) => m.type === "assistant");
    expect(assistantMessages.length).toBeGreaterThan(0);

    const resultMessage = messages.find((m) => m.type === "result");
    expect(resultMessage).toBeDefined();
    expect(resultMessage.usage).toBeDefined();
    expect(resultMessage.modelUsage).toBeDefined();

    // Verify that multiple models are tracked (including hidden ones)
    expect(Object.keys(resultMessage.modelUsage).length).toBeGreaterThan(0);

    // Verify server_tool_use is captured if present
    if (resultMessage.usage.server_tool_use) {
      expect(resultMessage.usage.server_tool_use).toBeDefined();
      expect(
        resultMessage.usage.server_tool_use.web_search_requests
      ).toBeDefined();
      expect(
        resultMessage.usage.server_tool_use.web_fetch_requests
      ).toBeDefined();
    }
  });

  test("tracks token usage including cache tokens", async () => {
    const messages: any[] = [];

    // Use a longer prompt that might benefit from caching
    const longPrompt = `
      Here is some context that might be cached:
      ${"Lorem ipsum dolor sit amet. ".repeat(100)}

      Now answer this simple question: What is 2+2?
    `.trim();

    for await (const message of wrappedSDK.query({
      prompt: longPrompt,
      options: {
        model: "haiku",
        maxTurns: 1,
      },
    })) {
      messages.push(message);
    }

    const assistantMessage = messages.find((m) => m.type === "assistant");
    expect(assistantMessage?.message?.usage).toBeDefined();
    expect(assistantMessage.message.usage.input_tokens).toBeGreaterThan(0);
    expect(assistantMessage.message.usage.output_tokens).toBeGreaterThan(0);

    const resultMessage = messages.find((m) => m.type === "result");
    expect(resultMessage?.usage).toBeDefined();
  });

  test("handles streaming messages correctly", async () => {
    const messages: any[] = [];
    let lastMessageId: string | undefined;
    let _messageIdChanges = 0;

    for await (const message of wrappedSDK.query({
      prompt: "Write a haiku about programming.",
      options: {
        allowDangerouslySkipPermissions: true,
        permissionMode: "bypassPermissions",
        includePartialMessages: true,
        model: "haiku",
        maxTurns: 1,
      },
    })) {
      messages.push(message);

      if (message.type === "assistant" && message.message?.id) {
        if (lastMessageId && lastMessageId !== message.message.id) {
          _messageIdChanges += 1;
        }
        lastMessageId = message.message.id;
      }
    }

    expect(messages.length).toBeGreaterThan(0);
    expect(messages.some((m) => m.type === "assistant")).toBe(true);
    expect(messages.some((m) => m.type === "result")).toBe(true);
  });

  test("custom configuration is applied", async () => {
    const customWrappedSDK = wrapClaudeAgentSDK(claudeSDK, {
      project_name: "custom-project",
      metadata: { test: "custom-metadata" },
      tags: ["custom", "test"],
    });

    const messages: any[] = [];

    for await (const message of customWrappedSDK.query({
      prompt: "Say hello.",
      options: {
        model: "haiku",
        maxTurns: 1,
      },
    })) {
      messages.push(message);
    }

    expect(messages.length).toBeGreaterThan(0);
  });

  test("tool with error handling", async () => {
    const { client, callSpy } = mockClient();
    const tracedSDK = wrapClaudeAgentSDK(claudeSDK, {
      client,
      tracingEnabled: true,
      name: "test.mcp_tool_error",
    }) as typeof claudeSDK;

    const errorTool = tracedSDK.tool(
      "error-tool",
      "A tool that always errors",
      {},
      async () => ({
        content: [{ type: "text", text: "Error occurred" }],
        isError: true,
      })
    );

    const messages = await consumeQuery(
      tracedSDK.query({
        prompt: "Try to use the error-tool from the error-server.",
        options: {
          model: "haiku",
          maxTurns: 5,
          mcpServers: {
            errorTool: tracedSDK.createSdkMcpServer({
              name: "error-server",
              tools: [errorTool],
            }),
          },
          canUseTool: allowAllTools,
        },
      })
    );

    expect(messages.length).toBeGreaterThan(0);
    const resultMessage = messages.find((m) => m.type === "result");
    expect(resultMessage).toBeDefined();

    const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
    const errorToolRuns = Object.values(tree.data).filter(
      (run) => run.name.includes("error-tool") && run.run_type === "tool"
    );
    expect(errorToolRuns.length).toBeGreaterThanOrEqual(1);
    expect(errorToolRuns.some((run) => run.error != null)).toBe(true);
  });

  test("query with tool usage traces correctly", async () => {
    // This test verifies that streaming messages are properly grouped by ID
    // and that the final token counts are used (not the initial streaming count of 1)
    const calculator = wrappedSDK.tool(
      "calculator",
      "Performs basic arithmetic operations",
      {
        operation: z.enum(["add", "subtract", "multiply", "divide"]),
        a: z.number(),
        b: z.number(),
      },
      async (args: any) => {
        let result: number;
        switch (args.operation) {
          case "add":
            result = args.a + args.b;
            break;
          case "subtract":
            result = args.a - args.b;
            break;
          case "multiply":
            result = args.a * args.b;
            break;
          case "divide":
            result = args.a / args.b;
            break;
          default:
            throw new Error("Unknown operation");
        }
        return {
          content: [{ type: "text", text: `Result: ${result}` }],
        };
      }
    );

    const messages: any[] = [];
    const messageIdToUpdates: Map<string, number> = new Map();

    for await (const message of wrappedSDK.query({
      prompt:
        "IMPORTANT: You MUST use the calculator tool to compute 42 + 17. Do not calculate yourself. Call the tool with operation='add', a=42, b=17, then report the result you get back.",
      options: {
        model: "haiku",
        maxTurns: 3,
        tools: [calculator] as any,
      },
    })) {
      // Track streaming updates per message ID
      if (message.type === "assistant") {
        const msg = message as any;
        const id = msg.message?.id;
        if (id) {
          const count = messageIdToUpdates.get(id) || 0;
          messageIdToUpdates.set(id, count + 1);

          console.log("Assistant streaming update:", {
            id,
            updateNumber: count + 1,
            model: msg.message?.model,
            outputTokens: msg.message?.usage?.output_tokens,
            stopReason: msg.message?.stop_reason,
          });
        }
      }

      if (message.type === "result") {
        console.log("Result:", {
          num_turns: message.num_turns,
          totalOutputTokens: message.usage?.output_tokens,
        });
      }

      messages.push(message);
    }

    console.log("\nMessage ID update counts:");
    for (const [id, count] of messageIdToUpdates) {
      console.log(`  ${id}: ${count} updates`);
    }

    // Get unique message IDs (should correspond to LLM spans created)
    const uniqueMessageIds = [...messageIdToUpdates.keys()];
    console.log(`\nUnique assistant message IDs: ${uniqueMessageIds.length}`);

    expect(messages.length).toBeGreaterThan(0);

    const resultMessage = messages.find((m) => m.type === "result");
    expect(resultMessage).toBeDefined();
    expect(resultMessage.usage.output_tokens).toBeGreaterThan(1); // Should be more than the initial streaming count of 1
  });

  test("tool failure creates errored tool trace", async () => {
    const { client, callSpy } = mockClient();
    const tracedSDK = wrapClaudeAgentSDK(claudeSDK, {
      client,
      tracingEnabled: true,
      name: "test.tool_failure",
    }) as typeof claudeSDK;

    const messages = await consumeQuery(
      tracedSDK.query({
        prompt:
          "Run this exact bash command: cat /tmp/__langsmith_test_nonexistent.txt",
        options: {
          model: "haiku",
          allowedTools: ["Bash"],
          permissionMode: "bypassPermissions",
          allowDangerouslySkipPermissions: true,
          maxTurns: 2,
        },
      })
    );

    const toolResultBlocks = messages.flatMap((message) =>
      message.type === "user" && Array.isArray(message.message?.content)
        ? message.message.content.filter(
            (block: any) => block.type === "tool_result"
          )
        : []
    );
    expect(toolResultBlocks.length).toBeGreaterThanOrEqual(1);
    expect(toolResultBlocks.some((block: any) => block.is_error === true)).toBe(
      true
    );

    const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
    const bashRuns = Object.values(tree.data).filter(
      (run) => run.name === "Bash" && run.run_type === "tool"
    );
    expect(bashRuns.length).toBeGreaterThanOrEqual(1);
    expect(bashRuns.some((run) => run.error != null)).toBe(true);
  });

  test("subagent trace includes transcript-reconciled LLM turns and tools", async () => {
    const { client, callSpy } = mockClient();
    const tracedSDK = wrapClaudeAgentSDK(claudeSDK, {
      client,
      tracingEnabled: true,
      name: "test.subagent",
    }) as typeof claudeSDK;

    await consumeQuery(
      tracedSDK.query({
        prompt: "Call foo.",
        options: {
          model: "haiku",
          systemPrompt: "You must always call the foo subagent.",
          allowedTools: ["Agent"],
          agents: {
            foo: {
              description: "Does foo things.",
              prompt:
                "You must first call the Bash tool with command 'echo hello', then call the Bash tool with command 'echo world', and then respond with exactly: 'done'",
              model: "haiku",
              tools: ["Bash"],
            },
          },
          permissionMode: "bypassPermissions",
          allowDangerouslySkipPermissions: true,
          maxTurns: 5,
        },
      })
    );

    const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
    const fooEntry = Object.entries(tree.data).find(
      ([, run]) => run.name === "foo" && run.run_type === "chain"
    );
    if (fooEntry == null) {
      throw new Error("Expected foo subagent chain run");
    }
    const [fooKey] = fooEntry;
    const parentToolKey = tree.edges.find(([, child]) => child === fooKey)?.[0];
    if (parentToolKey == null) {
      throw new Error("Expected foo subagent to be nested under a tool run");
    }
    expect(tree.data[parentToolKey]).toMatchObject({
      run_type: "tool",
      name: expect.stringMatching(/^(Agent|Task)$/),
    });

    const bashChildren = tree.edges.filter(([parent, child]) => {
      const childRun = tree.data[child];
      return (
        parent === fooKey &&
        childRun?.name === "Bash" &&
        childRun.run_type === "tool"
      );
    });
    expect(bashChildren.length).toBeGreaterThanOrEqual(2);

    const subagentLlmChildren = tree.edges.filter(([parent, child]) => {
      const childRun = tree.data[child];
      return (
        parent === fooKey &&
        childRun?.name === "claude.assistant.turn" &&
        childRun.run_type === "llm"
      );
    });
    expect(subagentLlmChildren.length).toBeGreaterThanOrEqual(2);

    for (const [, child] of subagentLlmChildren) {
      expect(tree.data[child].extra?.metadata?.usage_metadata).toBeDefined();
    }
  });

  test("resuming a session does not duplicate old LLM runs", async () => {
    const firstMessages = await consumeQuery(
      wrappedSDK.query({
        prompt: "Say hello.",
        options: {
          model: "haiku",
          systemPrompt: "Answer concisely.",
          maxTurns: 1,
        },
      })
    );
    const sessionId = firstMessages.find(
      (message) => message.session_id
    )?.session_id;
    expect(sessionId).toBeDefined();

    const { client, callSpy } = mockClient();
    const tracedSDK = wrapClaudeAgentSDK(claudeSDK, {
      client,
      tracingEnabled: true,
      name: "test.continue_session",
    }) as typeof claudeSDK;

    await consumeQuery(
      tracedSDK.query({
        prompt: "Say goodbye.",
        options: {
          model: "haiku",
          systemPrompt: "Answer concisely.",
          resume: sessionId,
          maxTurns: 1,
        },
      })
    );

    const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
    const llmRuns = Object.values(tree.data).filter(
      (run) => run.run_type === "llm"
    );
    expect(llmRuns.length).toBe(1);
  });

  test("custom MCP tool denied by default permissions is traced and closed", async () => {
    const { client, callSpy } = mockClient();
    const tracedSDK = wrapClaudeAgentSDK(claudeSDK, {
      client,
      tracingEnabled: true,
      name: "test.custom_tool_denied",
    }) as typeof claudeSDK;

    const getWeather = tracedSDK.tool(
      "get_weather",
      "Gets the current weather for a given city.",
      { city: z.string() },
      async (args: any) => ({
        content: [{ type: "text", text: `Foggy in ${args.city}` }],
      })
    );

    const server = tracedSDK.createSdkMcpServer({
      name: "weather",
      tools: [getWeather],
    });

    const messages = await consumeQuery(
      tracedSDK.query({
        prompt: "What's the weather in San Francisco?",
        options: {
          model: "haiku",
          systemPrompt: WEATHER_PROMPT,
          mcpServers: { weather: server },
          maxTurns: 3,
        },
      })
    );

    expect(
      toolUseNames(messages).some((name) => name.includes("get_weather"))
    ).toBe(true);

    const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
    const weatherRuns = Object.values(tree.data).filter(
      (run) => run.name.includes("get_weather") && run.run_type === "tool"
    );
    expect(weatherRuns.length).toBeGreaterThanOrEqual(1);
    expect(
      weatherRuns.every((run) => run.end_time != null || run.error != null)
    ).toBe(true);
  });

  test("custom MCP tool granted by canUseTool returns result and is traced", async () => {
    const { client, callSpy } = mockClient();
    const tracedSDK = wrapClaudeAgentSDK(claudeSDK, {
      client,
      tracingEnabled: true,
      name: "test.custom_tool_granted",
    }) as typeof claudeSDK;

    const getWeather = tracedSDK.tool(
      "get_weather",
      "Gets the current weather for a given city.",
      { city: z.string() },
      async (args: any) => ({
        content: [{ type: "text", text: `Foggy in ${args.city}` }],
      })
    );

    const server = tracedSDK.createSdkMcpServer({
      name: "weather",
      tools: [getWeather],
    });

    const messages = await consumeQuery(
      tracedSDK.query({
        prompt: "What's the weather in San Francisco?",
        options: {
          model: "haiku",
          systemPrompt: WEATHER_PROMPT,
          mcpServers: { weather: server },
          canUseTool: allowAllTools,
          maxTurns: 3,
        },
      })
    );

    expect(
      toolUseNames(messages).some((name) => name.includes("get_weather"))
    ).toBe(true);

    const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
    const weatherRuns = Object.values(tree.data).filter(
      (run) => run.name.includes("get_weather") && run.run_type === "tool"
    );
    expect(weatherRuns.length).toBeGreaterThanOrEqual(1);
    expect(weatherRuns.some((run) => run.outputs != null)).toBe(true);
    expect(
      [
        ...toolResultContents(messages),
        ...weatherRuns.map((run) => stringifyToolResultContent(run.outputs)),
      ].some((result) => result.includes("Foggy"))
    ).toBe(true);
  });

  test("traceable called from MCP tool handler nests under MCP tool run", async () => {
    const { client, callSpy } = mockClient();
    const tracedSDK = wrapClaudeAgentSDK(claudeSDK, {
      client,
      tracingEnabled: true,
      name: "test.custom_tool_nested_traceable",
    }) as typeof claudeSDK;

    const innerLookup = traceable(
      async (city: string) => `nested lookup for ${city}`,
      { name: "mcp_nested_lookup", client, tracingEnabled: true }
    );

    const getWeather = tracedSDK.tool(
      "get_weather",
      "Gets the current weather for a given city.",
      { city: z.string() },
      async (args: any) => {
        const lookup = await innerLookup(args.city);
        return {
          content: [{ type: "text", text: `Foggy in ${args.city}; ${lookup}` }],
        };
      }
    );

    const server = tracedSDK.createSdkMcpServer({
      name: "weather",
      tools: [getWeather],
    });

    await consumeQuery(
      tracedSDK.query({
        prompt: "What's the weather in San Francisco?",
        options: {
          model: "haiku",
          systemPrompt: WEATHER_PROMPT,
          mcpServers: { weather: server },
          canUseTool: allowAllTools,
          maxTurns: 3,
        },
      })
    );

    const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
    const weatherEntry = Object.entries(tree.data).find(
      ([, run]) => run.name.includes("get_weather") && run.run_type === "tool"
    );
    const nestedEntry = Object.entries(tree.data).find(
      ([, run]) => run.name === "mcp_nested_lookup"
    );

    if (weatherEntry == null) {
      throw new Error("Expected get_weather tool run");
    }
    if (nestedEntry == null) {
      throw new Error("Expected nested traceable run");
    }

    expect(tree.edges).toContainEqual([weatherEntry[0], nestedEntry[0]]);
  });

  test("concurrent SDK queries keep trace state isolated", async () => {
    const { client, callSpy } = mockClient();
    const tracedSDK = wrapClaudeAgentSDK(claudeSDK, {
      client,
      tracingEnabled: true,
      name: "test.concurrent_three_clients",
    }) as typeof claudeSDK;

    const runOne = async (label: string) => {
      const messages = await consumeQuery(
        tracedSDK.query({
          prompt: `Run the exact command: echo ${label}`,
          options: {
            model: "haiku",
            systemPrompt: `You must call the Bash tool exactly once with command 'echo ${label}', then stop.`,
            allowedTools: ["Bash"],
            permissionMode: "bypassPermissions",
            allowDangerouslySkipPermissions: true,
            maxTurns: 2,
          },
        })
      );
      return {
        label,
        messages,
        sessionIds: new Set(
          messages.map((message) => message.session_id).filter(Boolean)
        ),
      };
    };

    const results = await Promise.all([
      runOne("alpha"),
      runOne("beta"),
      runOne("gamma"),
    ]);

    for (const result of results) {
      expect(toolUseNames(result.messages)).toContain("Bash");
      expect(
        toolResultContents(result.messages).some((output) =>
          output.includes(result.label)
        )
      ).toBe(true);
      expect(result.sessionIds.size).toBeGreaterThanOrEqual(1);
    }

    const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
    const bashParentIds = new Set(
      tree.edges
        .filter(([, child]) => {
          const childRun = tree.data[child];
          return childRun?.name === "Bash" && childRun.run_type === "tool";
        })
        .map(([parent]) => parent)
    );
    expect(bashParentIds.size).toBe(3);
  });

  test("wrapping query preserves extra methods from generator", async () => {
    const query = wrappedSDK.query({
      prompt: "Write a haiku about programming.",
      options: {
        model: "haiku",
        maxTurns: 1,
      },
    });

    expect(query.supportedModels).toBeDefined();
    expect(query.supportedCommands).toBeDefined();

    await expect(() => query.supportedModels()).not.toThrow();
    await expect(() => query.supportedCommands()).not.toThrow();
  });

  test("streaming input", async () => {
    const query = wrappedSDK.query({
      prompt: (async function* () {
        yield {
          type: "user" as const,
          message: { role: "user" as const, content: "Hello" },
        } as unknown as claudeSDK.SDKUserMessage;

        yield {
          type: "user" as const,
          message: { role: "user" as const, content: "How are you?" },
        } as unknown as claudeSDK.SDKUserMessage;
      })(),
      options: {
        model: "haiku",
        maxTurns: 1,
      },
    });

    const messages: any[] = [];
    for await (const message of query) {
      messages.push(message);
    }

    expect(messages.length).toBeGreaterThan(0);
  });
});
