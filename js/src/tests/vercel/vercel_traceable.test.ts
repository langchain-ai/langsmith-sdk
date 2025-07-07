// Split out because .shutdown() seems to be the only reliable way to flush spans
import { NodeTracerProvider } from "@opentelemetry/sdk-trace-node";
import { BatchSpanProcessor } from "@opentelemetry/sdk-trace-base";
import { generateText, tool } from "ai";

import { z } from "zod";
import { AISDKExporter } from "../../vercel.js";
import { mockClient } from "../utils/mock_client.js";
import { getAssumedTreeFromCalls } from "../utils/tree.js";
import { MockMultiStepLanguageModelV1, ExecutionOrderSame } from "./utils.js";
import { traceable } from "../../traceable.js";

const { client, callSpy } = mockClient();
const exporter = new AISDKExporter({ client });
const provider = new NodeTracerProvider({
  spanProcessors: [new BatchSpanProcessor(exporter)],
});
provider.register();

test("traceable", async () => {
  const model = new MockMultiStepLanguageModelV1({
    doGenerate: async () => {
      if (model.generateStep === 0) {
        return {
          rawCall: { rawPrompt: null, rawSettings: {} },
          finishReason: "stop",
          usage: { promptTokens: 10, completionTokens: 20 },
          toolCalls: [
            {
              toolCallType: "function",
              toolName: "listOrders",
              toolCallId: "tool-id",
              args: JSON.stringify({ userId: "123" }),
            },
          ],
        };
      }

      return {
        rawCall: { rawPrompt: null, rawSettings: {} },
        finishReason: "stop",
        usage: { promptTokens: 10, completionTokens: 20 },
        text: `Hello, world!`,
      };
    },
  });

  const wrappedText = traceable(
    async (content: string) => {
      const { text } = await generateText({
        model,
        messages: [{ role: "user", content }],
        tools: {
          listOrders: tool({
            description: "list all orders",
            parameters: z.object({ userId: z.string() }),
            execute: async ({ userId }) =>
              `User ${userId} has the following orders: 1`,
          }),
        },
        experimental_telemetry: AISDKExporter.getSettings({
          isEnabled: true,
          runName: "generateText",
          functionId: "functionId",
          metadata: { userId: "123", language: "english" },
        }),
        maxSteps: 10,
      });

      return { text };
    },
    { name: "wrappedText", client, tracingEnabled: true }
  );

  await wrappedText("What are my orders? My user ID is 123");
  await provider.shutdown();

  const actual = getAssumedTreeFromCalls(callSpy.mock.calls);
  expect(actual).toMatchObject({
    nodes: [
      "wrappedText:0",
      "generateText:1",
      "mock-provider:2",
      "listOrders:3",
      "mock-provider:4",
    ],
    edges: [
      ["wrappedText:0", "generateText:1"],
      ["generateText:1", "mock-provider:2"],
      ["generateText:1", "listOrders:3"],
      ["generateText:1", "mock-provider:4"],
    ],
    data: {
      "wrappedText:0": {
        inputs: {
          input: "What are my orders? My user ID is 123",
        },
        outputs: {
          text: "Hello, world!",
        },
        dotted_order: new ExecutionOrderSame(1, "001"),
      },
      "generateText:1": {
        name: "generateText",
        extra: {
          metadata: {
            functionId: "functionId",
            userId: "123",
            language: "english",
            usage_metadata: {
              input_tokens: 10,
              output_tokens: 20,
              total_tokens: 30,
            },
          },
        },
        inputs: {
          messages: [
            {
              type: "human",
              data: { content: "What are my orders? My user ID is 123" },
            },
          ],
        },
        outputs: {
          llm_output: {
            type: "ai",
            data: { content: "Hello, world!" },
          },
        },
        dotted_order: new ExecutionOrderSame(2, "000"),
      },
      "mock-provider:2": {
        inputs: {
          messages: [
            {
              type: "human",
              data: {
                content: [
                  {
                    type: "text",
                    text: "What are my orders? My user ID is 123",
                  },
                ],
              },
            },
          ],
        },
        outputs: {
          llm_output: {
            type: "ai",
            data: {
              content: [
                {
                  type: "tool_use",
                  name: "listOrders",
                  id: "tool-id",
                  input: { userId: "123" },
                },
              ],
              additional_kwargs: {
                tool_calls: [
                  {
                    id: "tool-id",
                    type: "function",
                    function: {
                      name: "listOrders",
                      id: "tool-id",
                      arguments: '{"userId":"123"}',
                    },
                  },
                ],
              },
            },
          },
        },
        extra: {
          metadata: {
            usage_metadata: {
              input_tokens: 10,
              output_tokens: 20,
              total_tokens: 30,
            },
          },
        },
        dotted_order: new ExecutionOrderSame(3, "000"),
      },
      "listOrders:3": {
        inputs: { userId: "123" },
        outputs: { output: "User 123 has the following orders: 1" },
        dotted_order: new ExecutionOrderSame(3, "001"),
      },
      "mock-provider:4": {
        inputs: {
          messages: [
            {
              type: "human",
              data: {
                content: [
                  {
                    type: "text",
                    text: "What are my orders? My user ID is 123",
                  },
                ],
              },
            },
            {
              type: "ai",
              data: {
                content: [
                  {
                    type: "tool_use",
                    name: "listOrders",
                    id: "tool-id",
                    input: { userId: "123" },
                  },
                ],
                additional_kwargs: {
                  tool_calls: [
                    {
                      id: "tool-id",
                      type: "function",
                      function: {
                        name: "listOrders",
                        id: "tool-id",
                        arguments: '{"userId":"123"}',
                      },
                    },
                  ],
                },
              },
            },
            {
              type: "tool",
              data: {
                content: '"User 123 has the following orders: 1"',
                name: "listOrders",
                tool_call_id: "tool-id",
              },
            },
          ],
        },
        outputs: {
          llm_output: {
            type: "ai",
            data: { content: "Hello, world!" },
          },
        },
        extra: {
          metadata: {
            usage_metadata: {
              input_tokens: 10,
              output_tokens: 20,
              total_tokens: 30,
            },
          },
        },
        dotted_order: new ExecutionOrderSame(3, "002"),
      },
    },
  });
});
