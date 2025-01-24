import { NodeTracerProvider } from "@opentelemetry/sdk-trace-node";
import { BatchSpanProcessor } from "@opentelemetry/sdk-trace-base";
import { context, trace } from "@opentelemetry/api";
import { v4 as uuidv4 } from "uuid";
import {
  generateText,
  streamText,
  generateObject,
  streamObject,
  tool,
  LanguageModelV1StreamPart,
} from "ai";

import { z } from "zod";
import { AISDKExporter } from "../vercel.js";
import { traceable } from "../traceable.js";
import { toArray } from "./utils.js";
import { mockClient } from "./utils/mock_client.js";
import { convertArrayToReadableStream, MockLanguageModelV1 } from "ai/test";
import { getAssumedTreeFromCalls } from "./utils/tree.js";

const { client, callSpy } = mockClient();
const provider = new NodeTracerProvider();
provider.addSpanProcessor(
  new BatchSpanProcessor(new AISDKExporter({ client }))
);
provider.register();

class ExecutionOrderSame {
  $$typeof = Symbol.for("jest.asymmetricMatcher");

  private expectedNs: string;
  private expectedDepth: number;

  constructor(depth: number, ns: string) {
    this.expectedDepth = depth;
    this.expectedNs = ns;
  }

  asymmetricMatch(other: unknown) {
    // eslint-disable-next-line no-instanceof/no-instanceof
    if (!(typeof other === "string" || other instanceof String)) {
      return false;
    }

    const segments = other.split(".");
    if (segments.length !== this.expectedDepth) return false;

    const last = segments.at(-1);
    if (!last) return false;

    const nanoseconds = last.split("Z").at(0)?.slice(-3);
    return nanoseconds === this.expectedNs;
  }

  toString() {
    return "ExecutionOrderSame";
  }

  getExpectedType() {
    return "string";
  }

  toAsymmetricMatcher() {
    return `ExecutionOrderSame<${this.expectedDepth}, ${this.expectedNs}>`;
  }
}

class MockMultiStepLanguageModelV1 extends MockLanguageModelV1 {
  generateStep = -1;
  streamStep = -1;

  constructor(...args: ConstructorParameters<typeof MockLanguageModelV1>) {
    super(...args);

    const oldDoGenerate = this.doGenerate;
    this.doGenerate = async (...args) => {
      this.generateStep += 1;
      return await oldDoGenerate(...args);
    };

    const oldDoStream = this.doStream;
    this.doStream = async (...args) => {
      this.streamStep += 1;
      return await oldDoStream(...args);
    };
  }
}

beforeEach(() => callSpy.mockClear());
afterAll(async () => await provider.shutdown());

test("generateText", async () => {
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

  await generateText({
    model,
    messages: [
      {
        role: "user",
        content: "What are my orders? My user ID is 123",
      },
    ],
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

  await provider.forceFlush();
  expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
    nodes: [
      "generateText:0",
      "mock-provider:1",
      "listOrders:2",
      "mock-provider:3",
    ],
    edges: [
      ["generateText:0", "mock-provider:1"],
      ["generateText:0", "listOrders:2"],
      ["generateText:0", "mock-provider:3"],
    ],
    data: {
      "generateText:0": {
        name: "generateText",
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
            token_usage: { completion_tokens: 20, prompt_tokens: 10 },
          },
        },
        extra: {
          metadata: {
            functionId: "functionId",
            userId: "123",
            language: "english",
          },
        },
        dotted_order: new ExecutionOrderSame(1, "000"),
      },
      "mock-provider:1": {
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
            token_usage: { completion_tokens: 20, prompt_tokens: 10 },
          },
        },
        dotted_order: new ExecutionOrderSame(2, "000"),
      },
      "listOrders:2": {
        inputs: { userId: "123" },
        outputs: { output: "User 123 has the following orders: 1" },
        dotted_order: new ExecutionOrderSame(2, "001"),
      },
      "mock-provider:3": {
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
            token_usage: { completion_tokens: 20, prompt_tokens: 10 },
          },
        },
        dotted_order: new ExecutionOrderSame(2, "002"),
      },
    },
  });
});

test("streamText", async () => {
  const model = new MockMultiStepLanguageModelV1({
    doStream: async () => {
      if (model.streamStep === 0) {
        return {
          stream: convertArrayToReadableStream([
            {
              type: "tool-call",
              toolCallType: "function",
              toolName: "listOrders",
              toolCallId: "tool-id",
              args: JSON.stringify({ userId: "123" }),
            },
            {
              type: "finish",
              finishReason: "stop",
              logprobs: undefined,
              usage: { completionTokens: 10, promptTokens: 3 },
            },
          ] satisfies LanguageModelV1StreamPart[]),
          rawCall: { rawPrompt: null, rawSettings: {} },
        };
      }

      return {
        stream: convertArrayToReadableStream([
          { type: "text-delta", textDelta: "Hello" },
          { type: "text-delta", textDelta: ", " },
          { type: "text-delta", textDelta: `world!` },
          {
            type: "finish",
            finishReason: "stop",
            logprobs: undefined,
            usage: { completionTokens: 10, promptTokens: 3 },
          },
        ]),
        rawCall: { rawPrompt: null, rawSettings: {} },
      };
    },
  });

  const result = await streamText({
    model,
    messages: [
      {
        role: "user",
        content: "What are my orders? My user ID is 123",
      },
    ],
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
      functionId: "functionId",
      metadata: { userId: "123", language: "english" },
    }),
    maxSteps: 10,
  });

  await toArray(result.fullStream);
  await provider.forceFlush();

  const actual = getAssumedTreeFromCalls(callSpy.mock.calls);
  expect(actual).toMatchObject({
    nodes: [
      "mock-provider:0",
      "mock-provider:1",
      "listOrders:2",
      "mock-provider:3",
    ],
    edges: [
      ["mock-provider:0", "mock-provider:1"],
      ["mock-provider:0", "listOrders:2"],
      ["mock-provider:0", "mock-provider:3"],
    ],
    data: {
      "mock-provider:0": {
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
            token_usage: { completion_tokens: 20, prompt_tokens: 6 },
          },
        },
        extra: {
          metadata: {
            functionId: "functionId",
            userId: "123",
            language: "english",
          },
        },
        dotted_order: new ExecutionOrderSame(1, "000"),
      },
      "mock-provider:1": {
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
            token_usage: { completion_tokens: 10, prompt_tokens: 3 },
          },
        },
        dotted_order: new ExecutionOrderSame(2, "000"),
      },
      "listOrders:2": {
        inputs: { userId: "123" },
        outputs: { output: "User 123 has the following orders: 1" },
        dotted_order: new ExecutionOrderSame(2, "001"),
      },
      "mock-provider:3": {
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
            token_usage: { completion_tokens: 10, prompt_tokens: 3 },
          },
        },
        dotted_order: new ExecutionOrderSame(2, "002"),
      },
    },
  });
});

test("generateObject", async () => {
  const model = new MockMultiStepLanguageModelV1({
    doGenerate: async () => ({
      rawCall: { rawPrompt: null, rawSettings: {} },
      finishReason: "stop",
      usage: { promptTokens: 10, completionTokens: 20 },
      toolCalls: [
        {
          toolCallType: "function",
          toolName: "json",
          toolCallId: "tool-id",
          args: JSON.stringify({
            weather: { city: "Prague", unit: "celsius" },
          }),
        },
      ],
    }),
    defaultObjectGenerationMode: "tool",
  });

  await generateObject({
    model,
    schema: z.object({
      weather: z.object({
        city: z.string(),
        unit: z.union([z.literal("celsius"), z.literal("fahrenheit")]),
      }),
    }),
    prompt: "What's the weather in Prague?",
    experimental_telemetry: AISDKExporter.getSettings({
      isEnabled: true,
      functionId: "functionId",
      metadata: { userId: "123", language: "english" },
    }),
  });

  await provider.forceFlush();
  const actual = getAssumedTreeFromCalls(callSpy.mock.calls);

  expect(actual).toMatchObject({
    nodes: ["mock-provider:0", "mock-provider:1"],
    edges: [["mock-provider:0", "mock-provider:1"]],
    data: {
      "mock-provider:0": {
        inputs: {
          input: { prompt: "What's the weather in Prague?" },
        },
        outputs: {
          output: { weather: { city: "Prague", unit: "celsius" } },
          llm_output: {
            token_usage: { completion_tokens: 20, prompt_tokens: 10 },
          },
        },
        dotted_order: new ExecutionOrderSame(1, "000"),
      },
      "mock-provider:1": {
        inputs: {
          messages: [
            {
              type: "human",
              data: {
                content: [
                  { type: "text", text: "What's the weather in Prague?" },
                ],
              },
            },
          ],
        },
        outputs: {
          output: { weather: { city: "Prague", unit: "celsius" } },
          llm_output: {
            token_usage: { completion_tokens: 20, prompt_tokens: 10 },
          },
        },
        extra: {
          metadata: {
            functionId: "functionId",
            userId: "123",
            language: "english",
          },
        },
        dotted_order: new ExecutionOrderSame(2, "000"),
      },
    },
  });
});

test("streamObject", async () => {
  const model = new MockMultiStepLanguageModelV1({
    doGenerate: async () => ({
      rawCall: { rawPrompt: null, rawSettings: {} },
      finishReason: "stop",
      usage: { promptTokens: 10, completionTokens: 20 },
      toolCalls: [
        {
          toolCallType: "function",
          toolName: "json",
          toolCallId: "tool-id",
          args: JSON.stringify({
            weather: { city: "Prague", unit: "celsius" },
          }),
        },
      ],
    }),

    doStream: async () => {
      return {
        stream: convertArrayToReadableStream([
          {
            type: "tool-call-delta",
            toolCallType: "function",
            toolName: "json",
            toolCallId: "tool-id",
            argsTextDelta: JSON.stringify({
              weather: { city: "Prague", unit: "celsius" },
            }),
          },
          {
            type: "finish",
            finishReason: "stop",
            logprobs: undefined,
            usage: { completionTokens: 10, promptTokens: 3 },
          },
        ] satisfies LanguageModelV1StreamPart[]),
        rawCall: { rawPrompt: null, rawSettings: {} },
      };
    },
    defaultObjectGenerationMode: "tool",
  });

  const result = await streamObject({
    model,
    schema: z.object({
      weather: z.object({
        city: z.string(),
        unit: z.union([z.literal("celsius"), z.literal("fahrenheit")]),
      }),
    }),
    prompt: "What's the weather in Prague?",
    experimental_telemetry: AISDKExporter.getSettings({
      isEnabled: true,
      functionId: "functionId",
      metadata: { userId: "123", language: "english" },
    }),
  });

  await toArray(result.partialObjectStream);
  await provider.forceFlush();

  const actual = getAssumedTreeFromCalls(callSpy.mock.calls);
  expect(actual).toMatchObject({
    nodes: ["mock-provider:0", "mock-provider:1"],
    edges: [["mock-provider:0", "mock-provider:1"]],
    data: {
      "mock-provider:0": {
        inputs: {
          input: { prompt: "What's the weather in Prague?" },
        },
        outputs: {
          output: { weather: { city: "Prague", unit: "celsius" } },
          llm_output: {
            token_usage: { completion_tokens: 10, prompt_tokens: 3 },
          },
        },
        extra: {
          metadata: {
            functionId: "functionId",
            userId: "123",
            language: "english",
          },
        },
        dotted_order: new ExecutionOrderSame(1, "000"),
      },
      "mock-provider:1": {
        inputs: {
          messages: [
            {
              type: "human",
              data: {
                content: [
                  { type: "text", text: "What's the weather in Prague?" },
                ],
              },
            },
          ],
        },
        outputs: {
          output: { weather: { city: "Prague", unit: "celsius" } },
          llm_output: {
            token_usage: { completion_tokens: 10, prompt_tokens: 3 },
          },
        },
        dotted_order: new ExecutionOrderSame(2, "000"),
      },
    },
  });
});

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
  await provider.forceFlush();

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
            token_usage: { completion_tokens: 20, prompt_tokens: 10 },
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
            token_usage: { completion_tokens: 20, prompt_tokens: 10 },
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
            token_usage: { completion_tokens: 20, prompt_tokens: 10 },
          },
        },
        dotted_order: new ExecutionOrderSame(3, "002"),
      },
    },
  });
});

test("unrelated spans around", async () => {
  const tracer = provider.getTracer("test");

  const inner = async () => {
    const span = tracer.startSpan("inner-unrelated");
    const ctx = trace.setSpan(context.active(), span);

    await context.with(ctx, async () => {
      await generateText({
        model: new MockMultiStepLanguageModelV1({
          provider: "inner-model",
          doGenerate: async () => {
            return {
              rawCall: { rawPrompt: null, rawSettings: {} },
              finishReason: "stop",
              usage: { promptTokens: 10, completionTokens: 20 },
              text: `Hello, world!`,
            };
          },
        }),
        messages: [{ role: "user", content: "Hello" }],
        experimental_telemetry: AISDKExporter.getSettings({
          isEnabled: true,
          metadata: { userId: "123" },
        }),
      });
    });

    span.end();
  };

  const rootRunId = uuidv4();

  const outer = async () => {
    const span = tracer.startSpan("outer-unrelated");
    const ctx = trace.setSpan(context.active(), span);

    const model = new MockMultiStepLanguageModelV1({
      provider: "outer-model",
      doGenerate: async () => {
        if (model.generateStep === 0) {
          return {
            rawCall: { rawPrompt: null, rawSettings: {} },
            finishReason: "stop",
            usage: { promptTokens: 10, completionTokens: 20 },
            toolCalls: [
              {
                toolCallType: "function",
                toolName: "callInner",
                toolCallId: "tool-id",
                args: JSON.stringify({}),
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

    await context.with(ctx, async () => {
      await generateText({
        model,
        tools: {
          callInner: tool({
            description: "call inner",
            parameters: z.object({}),
            execute: inner,
          }),
        },
        messages: [{ role: "user", content: "Nested call" }],
        experimental_telemetry: AISDKExporter.getSettings({
          isEnabled: true,
          runName: "outer",
          runId: rootRunId,
        }),
        maxSteps: 10,
      });
    });

    span.end();
  };

  await outer();
  await provider.forceFlush();

  const actual = getAssumedTreeFromCalls(callSpy.mock.calls);
  expect(actual).toMatchObject({
    nodes: [
      "outer:0",
      "outer-model:1",
      "callInner:2",
      "outer-model:3",
      "inner-model:4",
      "inner-model:5",
    ],
    edges: [
      ["outer:0", "outer-model:1"],
      ["outer:0", "callInner:2"],
      ["outer:0", "outer-model:3"],
      ["callInner:2", "inner-model:4"],
      ["inner-model:4", "inner-model:5"],
    ],
    data: {
      "outer:0": { id: rootRunId },
    },
  });
});
