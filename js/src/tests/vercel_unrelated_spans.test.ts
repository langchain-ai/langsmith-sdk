import { context, trace } from "@opentelemetry/api";
import { v4 as uuidv4 } from "uuid";
import { NodeTracerProvider } from "@opentelemetry/sdk-trace-node";
import { BatchSpanProcessor } from "@opentelemetry/sdk-trace-base";
import { generateText, tool } from "ai";
import { MockLanguageModelV1 } from "ai/test";

import { z } from "zod";
import { AISDKExporter } from "../vercel.js";
import { mockClient } from "./utils/mock_client.js";
import { getAssumedTreeFromCalls } from "./utils/tree.js";

const { client, callSpy } = mockClient();
const exporter = new AISDKExporter({ client });
const provider = new NodeTracerProvider({
  spanProcessors: [new BatchSpanProcessor(exporter)],
});
provider.register();

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
  await provider.shutdown();

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
