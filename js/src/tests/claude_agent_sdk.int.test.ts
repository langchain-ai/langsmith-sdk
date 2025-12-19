/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable no-process-env */
/* eslint-disable import/no-extraneous-dependencies */
import { describe, beforeAll, test, expect } from "@jest/globals";
import * as claudeSDK from "@anthropic-ai/claude-agent-sdk";
import { wrapClaudeAgentSDK } from "../experimental/anthropic/index.js";

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
  });

  beforeAll(() => {
    if (!process.env.ANTHROPIC_API_KEY) {
      throw new Error("ANTHROPIC_API_KEY environment variable is required");
    }
  });

  test.only("query with simple prompt", async () => {
    const messages: any[] = [];

    for await (const message of wrappedSDK.query({
      prompt: "Say 'Hello from LangSmith!' and nothing else.",
      options: {
        model: "claude-3-5-haiku-20241022",
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

  test("query with tool usage", async () => {
    const calculator = wrappedSDK.tool(
      "calculator",
      "Performs basic arithmetic operations",
      {
        type: "object",
        properties: {
          operation: {
            type: "string",
            enum: ["add", "subtract", "multiply", "divide"],
          },
          a: { type: "number" },
          b: { type: "number" },
        },
        required: ["operation", "a", "b"],
      } as any,
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

    for await (const message of wrappedSDK.query({
      prompt:
        "Use the calculator tool to compute 42 + 17. Just give me the result.",
      options: {
        model: "claude-3-5-haiku-20241022",
        maxTurns: 3,
        tools: [calculator] as any,
      },
    })) {
      messages.push(message);
    }

    expect(messages.length).toBeGreaterThan(0);

    // Should have tool use in the messages
    const hasToolUse = messages.some(
      (m) =>
        m.type === "assistant" &&
        Array.isArray(m.message?.content) &&
        m.message.content.some((c: any) => c.type === "tool_use")
    );
    expect(hasToolUse).toBe(true);

    const resultMessage = messages.find((m) => m.type === "result");
    expect(resultMessage).toBeDefined();
    expect(resultMessage.usage).toBeDefined();
  });

  test("query with multiple turns", async () => {
    const messages: any[] = [];

    for await (const message of wrappedSDK.query({
      prompt: "Count from 1 to 3, one number per turn. Use exactly 3 turns.",
      options: {
        model: "claude-3-5-haiku-20241022",
        maxTurns: 5,
      },
    })) {
      messages.push(message);
    }

    expect(messages.length).toBeGreaterThan(0);

    const assistantMessages = messages.filter((m) => m.type === "assistant");
    expect(assistantMessages.length).toBeGreaterThan(0);

    const resultMessage = messages.find((m) => m.type === "result");
    expect(resultMessage).toBeDefined();
    expect(resultMessage.num_turns).toBeDefined();
    expect(resultMessage.num_turns).toBeGreaterThan(0);
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
        model: "claude-3-5-haiku-20241022",
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
    let messageIdChanges = 0;

    for await (const message of wrappedSDK.query({
      prompt: "Write a haiku about programming.",
      options: {
        model: "claude-3-5-haiku-20241022",
        maxTurns: 1,
      },
    })) {
      messages.push(message);

      if (message.type === "assistant" && message.message?.id) {
        if (lastMessageId && lastMessageId !== message.message.id) {
          messageIdChanges++;
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
        model: "claude-3-5-haiku-20241022",
        maxTurns: 1,
      },
    })) {
      messages.push(message);
    }

    expect(messages.length).toBeGreaterThan(0);
  });

  test("tool with error handling", async () => {
    const errorTool = wrappedSDK.tool(
      "error-tool",
      "A tool that always errors",
      {
        type: "object",
        properties: {},
      } as any,
      async () => {
        return {
          content: [{ type: "text", text: "Error occurred" }],
          isError: true,
        };
      }
    );

    const messages: any[] = [];

    for await (const message of wrappedSDK.query({
      prompt: "Try to use the error-tool.",
      options: {
        model: "claude-3-5-haiku-20241022",
        maxTurns: 2,
        tools: [errorTool] as any,
      },
    })) {
      messages.push(message);
    }

    expect(messages.length).toBeGreaterThan(0);
    const resultMessage = messages.find((m) => m.type === "result");
    expect(resultMessage).toBeDefined();
  });

  test("query with tool usage traces correctly", async () => {
    // This test verifies that streaming messages are properly grouped by ID
    // and that the final token counts are used (not the initial streaming count of 1)
    const calculator = wrappedSDK.tool(
      "calculator",
      "Performs basic arithmetic operations",
      {
        type: "object",
        properties: {
          operation: {
            type: "string",
            enum: ["add", "subtract", "multiply", "divide"],
          },
          a: { type: "number" },
          b: { type: "number" },
        },
        required: ["operation", "a", "b"],
      } as any,
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
      prompt: "Use the calculator tool to compute 42 + 17. Report the result.",
      options: {
        model: "claude-3-5-haiku-20241022",
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
});
