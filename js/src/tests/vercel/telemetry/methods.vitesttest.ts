/* eslint-disable @typescript-eslint/no-explicit-any */
import {
  generateText,
  isStepCount,
  registerTelemetry,
  simulateReadableStream,
  streamText,
  tool,
} from "ai";
import { MockLanguageModelV4 } from "ai/test";
import { z } from "zod";
import { describe, it, expect, vi } from "vitest";
import { LangSmithTelemetry } from "../../../experimental/vercel/telemetry.js";
import { traceable } from "../../../traceable.js";
import { Client } from "../../../index.js";
import { getAssumedTreeFromCalls } from "../../utils/tree.js";
import type {
  LanguageModelV4,
  LanguageModelV4GenerateResult,
  LanguageModelV4Usage,
} from "@ai-sdk/provider";

function usage({
  input,
  output,
  cacheRead = 0,
  cacheWrite = 0,
  reasoning = 0,
}: {
  input: number;
  output: number;
  cacheRead?: number;
  cacheWrite?: number;
  reasoning?: number;
}): LanguageModelV4Usage {
  return {
    inputTokens: {
      total: input,
      noCache: input - cacheRead - cacheWrite,
      cacheRead,
      cacheWrite,
    },
    outputTokens: {
      total: output,
      text: output - reasoning,
      reasoning,
    },
  };
}

function textResult(
  text: string,
  tokenUsage = usage({ input: 5, output: 3 }),
  finishReason = "stop",
): LanguageModelV4GenerateResult {
  return {
    content: [{ type: "text" as const, text }],
    finishReason: { unified: finishReason as "stop", raw: finishReason },
    usage: tokenUsage,
    warnings: [],
  };
}

function toolCallResult(
  {
    toolCallId,
    toolName,
    input,
  }: { toolCallId: string; toolName: string; input: Record<string, unknown> },
  tokenUsage = usage({ input: 10, output: 5 }),
): LanguageModelV4GenerateResult {
  return {
    content: [
      {
        type: "tool-call" as const,
        toolCallId,
        toolName,
        input: JSON.stringify(input),
      },
    ],
    finishReason: { unified: "tool-calls" as const, raw: "tool-calls" },
    usage: tokenUsage,
    warnings: [],
  };
}

function createModel({
  provider = "test-provider",
  modelId = "test-model",
  responses = [textResult("Hello world")],
  doGenerate,
}: {
  provider?: string;
  modelId?: string;
  responses?: LanguageModelV4GenerateResult[];
  doGenerate?: LanguageModelV4["doGenerate"];
} = {}) {
  return new MockLanguageModelV4({
    provider,
    modelId,
    doGenerate: doGenerate ?? responses,
    doStream: async () => ({
      stream: simulateReadableStream({
        chunks: [
          { type: "text-start", id: "text-1" },
          { type: "text-delta", id: "text-1", delta: "Hello" },
          { type: "text-delta", id: "text-1", delta: " world" },
          { type: "text-end", id: "text-1" },
          {
            type: "finish",
            finishReason: { unified: "stop" as const, raw: "stop" },
            usage: usage({ input: 5, output: 3 }),
          },
        ],
      }),
    }),
  });
}

function createTrace(config?: Parameters<typeof LangSmithTelemetry>[0]) {
  const callSpy = vi.fn(
    async () =>
      new Response("{}", {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
  );
  const client = new Client({
    autoBatchTracing: false,
    fetchImplementation: callSpy,
  });

  const integration = LangSmithTelemetry({
    tracingEnabled: true,
    client,
    ...config,
  });
  return { callSpy, client, integration };
}

async function expectTree({
  callSpy,
  client,
}: {
  callSpy: ReturnType<typeof vi.fn>;
  client: Client;
}) {
  return getAssumedTreeFromCalls(callSpy.mock.calls, client);
}

describe("basic tracing", () => {
  it("should create root and step spans for a simple generateText", async () => {
    const trace = createTrace();

    await generateText({
      model: createModel({
        responses: [
          textResult("Test response", usage({ input: 5, output: 3 })),
        ],
      }),
      prompt: "Test prompt",
      telemetry: { integrations: [trace.integration] },
    });

    await expect(expectTree(trace)).resolves.toMatchObject({
      edges: [["test-provider:0", "test-provider:1"]],
      data: {
        "test-provider:0": {
          run_type: "chain",
          inputs: { messages: [{ role: "user", content: "Test prompt" }] },
          extra: { metadata: { ls_integration: "vercel-ai-sdk-telemetry" } },
          outputs: { role: "assistant", content: "Test response" },
        },
        "test-provider:1": {
          run_type: "llm",
          inputs: { messages: [{ role: "user", content: "Test prompt" }] },
          outputs: {
            role: "assistant",
            content: [{ type: "text", text: "Test response" }],
          },
        },
      },
    });
  });

  it("should use the provider as default run name and store the AI SDK operation id", async () => {
    const trace = createTrace();

    await generateText({
      model: createModel({ provider: "openai", modelId: "gpt-4o" }),
      prompt: "Hello",
      telemetry: { integrations: [trace.integration] },
    });

    await expect(expectTree(trace)).resolves.toMatchObject({
      edges: [["openai:0", "openai:1"]],
      data: {
        "openai:0": {
          name: "openai",
          extra: {
            metadata: {
              ai_sdk_method: "ai.generateText",
              ls_model_name: "gpt-4o",
              ls_provider: "openai",
            },
          },
        },
      },
    });
  });

  it("should use the AI SDK function id as the default run name when present", async () => {
    const trace = createTrace();

    await generateText({
      model: createModel(),
      prompt: "Hello",
      telemetry: {
        integrations: [trace.integration],
        functionId: "summarize-endpoint",
      },
    });

    await expect(expectTree(trace)).resolves.toMatchObject({
      edges: [["summarize-endpoint:0", "test-provider:1"]],
      data: {
        "summarize-endpoint:0": {
          name: "summarize-endpoint",
          run_type: "chain",
          extra: {
            metadata: {
              ai_sdk_method: "ai.generateText",
              ls_model_name: "test-model",
              ls_provider: "test-provider",
            },
          },
        },
      },
    });
  });

  it("should allow custom name override", async () => {
    const trace = createTrace({ name: "my-agent" });
    await generateText({
      model: createModel(),
      prompt: "Hello",
      telemetry: { integrations: [trace.integration] },
    });

    await expect(expectTree(trace)).resolves.toMatchObject({
      edges: [["my-agent:0", "test-provider:1"]],
      data: { "my-agent:0": { name: "my-agent", run_type: "chain" } },
    });
  });

  it("should apply custom metadata and tags", async () => {
    const trace = createTrace({
      metadata: { customField: "test-value", version: "2.0" },
      tags: ["test-tag", "v2"],
    });

    await generateText({
      model: createModel(),
      prompt: "Test with metadata",
      telemetry: { integrations: [trace.integration] },
    });

    await expect(expectTree(trace)).resolves.toMatchObject({
      data: {
        "test-provider:0": {
          tags: ["test-tag", "v2"],
          extra: {
            metadata: {
              customField: "test-value",
              version: "2.0",
              ls_integration: "vercel-ai-sdk-telemetry",
            },
          },
        },
      },
    });
  });
});

describe("metadata", () => {
  it("should set ai_sdk_method and root ls_agent_type on top-level runs", async () => {
    const trace = createTrace();

    await generateText({
      model: createModel(),
      prompt: "Metadata test",
      telemetry: { integrations: [trace.integration] },
    });

    const tree = await expectTree(trace);
    const rootRun = Object.values(tree.data).find(
      (run) =>
        run.run_type === "chain" &&
        run.extra?.metadata?.ai_sdk_method === "ai.generateText",
    );

    expect(rootRun?.extra?.metadata).toMatchObject({
      ai_sdk_method: "ai.generateText",
      ls_agent_type: "root",
    });
  });

  it("should set ls_agent_type to subagent for telemetry runs inside tools", async () => {
    const trace = createTrace();

    await generateText({
      model: createModel({
        responses: [
          toolCallResult({
            toolCallId: "tc-research-1",
            toolName: "research",
            input: { topic: "AI" },
          }),
          textResult("Research complete.", usage({ input: 20, output: 8 })),
        ],
      }),
      prompt: "Use a tool with sub-agent",
      tools: {
        research: tool({
          inputSchema: z.object({ topic: z.string() }),
          execute: async () => {
            const result = await generateText({
              model: createModel({
                provider: "inner-provider",
                modelId: "inner-model",
                responses: [textResult("Inner result")],
              }),
              prompt: "Inner prompt",
              telemetry: { integrations: [trace.integration] },
            });
            return result.text;
          },
        }),
      },
      stopWhen: isStepCount(10),
      telemetry: { integrations: [trace.integration] },
    });

    await expect(expectTree(trace)).resolves.toMatchObject({
      edges: [
        ["test-provider:0", "test-provider:1"],
        ["test-provider:1", "research:2"],
        ["research:2", "inner-provider:3"],
        ["inner-provider:3", "inner-provider:4"],
        ["test-provider:0", "test-provider:5"],
      ],
      data: {
        "test-provider:0": {
          run_type: "chain",
          extra: {
            metadata: {
              ai_sdk_method: "ai.generateText",
              ls_agent_type: "root",
            },
          },
        },
        "test-provider:1": {
          run_type: "llm",
          extra: { metadata: { ls_agent_type: "root" } },
        },
        "research:2": {
          run_type: "tool",
          extra: { metadata: { ls_agent_type: "root" } },
        },
        "inner-provider:3": {
          run_type: "chain",
          extra: {
            metadata: {
              ai_sdk_method: "ai.generateText",
              ls_agent_type: "subagent",
            },
          },
        },
        "inner-provider:4": {
          run_type: "llm",
          extra: { metadata: { ls_agent_type: "subagent" } },
        },
        "test-provider:5": {
          run_type: "llm",
          extra: { metadata: { ls_agent_type: "root" } },
        },
      },
    });
  });
});

describe("global telemetry registration", () => {
  it("should trace globally registered telemetry and allow local child name override", async () => {
    const trace = createTrace();
    const previousGlobalIntegrations = globalThis.AI_SDK_TELEMETRY_INTEGRATIONS;

    try {
      registerTelemetry(trace.integration);

      await generateText({
        model: createModel({
          responses: [
            toolCallResult({
              toolCallId: "tc-delegate-1",
              toolName: "delegate",
              input: { task: "summarize" },
            }),
            textResult("Delegation complete.", usage({ input: 20, output: 8 })),
          ],
        }),
        prompt: "Delegate this task",
        tools: {
          delegate: tool({
            inputSchema: z.object({ task: z.string() }),
            execute: async () => {
              const result = await generateText({
                model: createModel({
                  provider: "child-provider",
                  modelId: "child-model",
                  responses: [textResult("Child answer")],
                }),
                prompt: "Child prompt",
                telemetry: {
                  integrations: [
                    LangSmithTelemetry({
                      client: trace.client,
                      name: "child-agent",
                      tracingEnabled: true,
                    }),
                  ],
                },
              });
              return result.text;
            },
          }),
        },
        stopWhen: isStepCount(10),
      });

      await expect(expectTree(trace)).resolves.toMatchObject({
        edges: [
          ["test-provider:0", "test-provider:1"],
          ["test-provider:1", "delegate:2"],
          ["delegate:2", "child-agent:3"],
          ["child-agent:3", "child-provider:4"],
          ["test-provider:0", "test-provider:5"],
        ],
        data: {
          "test-provider:0": {
            run_type: "chain",
            inputs: {
              messages: [{ role: "user", content: "Delegate this task" }],
              tools: ["delegate"],
            },
            extra: {
              metadata: {
                ai_sdk_method: "ai.generateText",
                ls_agent_type: "root",
              },
            },
          },
          "delegate:2": {
            run_type: "tool",
            inputs: { task: "summarize" },
            outputs: { output: "Child answer" },
          },
          "child-agent:3": {
            name: "child-agent",
            run_type: "chain",
            inputs: {
              messages: [{ role: "user", content: "Child prompt" }],
            },
            outputs: { content: "Child answer" },
            extra: {
              metadata: {
                ai_sdk_method: "ai.generateText",
                ls_agent_type: "subagent",
              },
            },
          },
          "child-provider:4": {
            run_type: "llm",
            extra: { metadata: { ls_agent_type: "subagent" } },
          },
        },
      });
    } finally {
      globalThis.AI_SDK_TELEMETRY_INTEGRATIONS = previousGlobalIntegrations;
    }
  });
});

describe("error handling", () => {
  it("should capture errors on the root span", async () => {
    const trace = createTrace();
    await expect(
      generateText({
        model: createModel({
          doGenerate: async () => {
            throw new Error("TOTALLY EXPECTED MOCK ERROR");
          },
        }),
        prompt: "This should fail",
        telemetry: { integrations: [trace.integration] },
      }),
    ).rejects.toThrow("TOTALLY EXPECTED MOCK ERROR");

    await expect(expectTree(trace)).resolves.toMatchObject({
      edges: [["test-provider:0", "test-provider:1"]],
      data: {
        "test-provider:0": {
          error: expect.stringContaining("TOTALLY EXPECTED MOCK ERROR"),
        },
      },
    });
  });

  it("should close open step runs on error", async () => {
    const trace = createTrace();

    await expect(
      generateText({
        model: createModel({
          doGenerate: async () => {
            throw new Error("Mid-step error");
          },
        }),
        prompt: "Test",
        telemetry: { integrations: [trace.integration] },
      }),
    ).rejects.toThrow("Mid-step error");

    await expect(expectTree(trace)).resolves.toMatchObject({
      edges: [["test-provider:0", "test-provider:1"]],
      data: {
        "test-provider:0": {
          error: expect.stringContaining("Mid-step error"),
        },
        "test-provider:1": {
          error: expect.stringContaining("Mid-step error"),
        },
      },
    });
  });
});

describe("multi-step tracing", () => {
  it("should create separate LLM spans for each step", async () => {
    const trace = createTrace();

    await generateText({
      model: createModel({
        responses: [
          toolCallResult(
            {
              toolCallId: "tc-1",
              toolName: "search",
              input: { query: "weather" },
            },
            usage({ input: 10, output: 5 }),
          ),
          textResult(
            "The weather is sunny and 72F.",
            usage({ input: 20, output: 8 }),
          ),
        ],
      }),
      prompt: "Multi-step test",
      tools: {
        search: tool({
          inputSchema: z.object({ query: z.string() }),
          execute: async () => "Sunny, 72F",
        }),
      },
      stopWhen: isStepCount(10),
      telemetry: { integrations: [trace.integration] },
    });

    const tree = await expectTree(trace);
    expect(tree).toMatchObject({
      edges: [
        ["test-provider:0", "test-provider:1"],
        ["test-provider:1", "search:2"],
        ["test-provider:0", "test-provider:3"],
      ],
      data: {
        "test-provider:0": {
          inputs: {
            messages: [{ role: "user", content: "Multi-step test" }],
            tools: ["search"],
          },
        },
        "test-provider:1": {
          run_type: "llm",
          extra: {
            metadata: { step_number: 0 },
            invocation_params: {
              tools: [
                expect.objectContaining({
                  name: "search",
                  input_schema: expect.objectContaining({
                    type: "object",
                    properties: {
                      query: expect.objectContaining({ type: "string" }),
                    },
                  }),
                }),
              ],
            },
          },
          outputs: {
            content: expect.arrayContaining([
              expect.objectContaining({
                type: "tool-call",
                toolName: "search",
                input: { query: "weather" },
              }),
            ]),
            tool_calls: expect.arrayContaining([
              expect.objectContaining({
                type: "function",
                function: expect.objectContaining({ name: "search" }),
              }),
            ]),
          },
        },
        "search:2": {
          run_type: "tool",
          inputs: { query: "weather" },
          outputs: { output: "Sunny, 72F" },
        },
        "test-provider:3": {
          run_type: "llm",
          extra: { metadata: { step_number: 1 } },
          outputs: {
            content: [{ type: "text", text: "The weather is sunny and 72F." }],
          },
        },
      },
    });

    expect(
      tree.data["test-provider:1"].extra?.invocation_params?.tools?.[0],
    ).not.toHaveProperty("inputSchema");
  });
});

describe("tool tracing via executeTool", () => {
  it("should create tool spans and record outputs on onToolExecutionEnd", async () => {
    const trace = createTrace();

    await generateText({
      model: createModel({
        responses: [
          toolCallResult({
            toolCallId: "tc-calc-1",
            toolName: "calculator",
            input: { expression: "2+2" },
          }),
          textResult("2+2 = 4", usage({ input: 15, output: 5 })),
        ],
      }),
      prompt: "Use a tool",
      tools: {
        calculator: tool({
          inputSchema: z.object({ expression: z.string() }),
          execute: async () => 4,
        }),
      },
      stopWhen: isStepCount(10),
      telemetry: { integrations: [trace.integration] },
    });

    await expect(expectTree(trace)).resolves.toMatchObject({
      edges: [
        ["test-provider:0", "test-provider:1"],
        ["test-provider:1", "calculator:2"],
        ["test-provider:0", "test-provider:3"],
      ],
      data: {
        "calculator:2": {
          run_type: "tool",
          inputs: { expression: "2+2" },
          outputs: { output: 4 },
        },
      },
    });
  });

  it("should nest sub-agent calls inside tool spans", async () => {
    const trace = createTrace();
    const innerTraceable = traceable(
      async (input: string) => `Processed: ${input}`,
      {
        name: "inner-agent-call",
        run_type: "chain",
        client: trace.client,
        tracingEnabled: true,
      },
    );

    await generateText({
      model: createModel({
        responses: [
          toolCallResult({
            toolCallId: "tc-research-1",
            toolName: "research",
            input: { topic: "AI" },
          }),
          textResult("Research complete.", usage({ input: 20, output: 8 })),
        ],
      }),
      prompt: "Use a tool with sub-agent",
      tools: {
        research: tool({
          inputSchema: z.object({ topic: z.string() }),
          execute: async () => innerTraceable("AI research"),
        }),
      },
      stopWhen: isStepCount(10),
      telemetry: { integrations: [trace.integration] },
    });

    await expect(expectTree(trace)).resolves.toMatchObject({
      edges: [
        ["test-provider:0", "test-provider:1"],
        ["test-provider:1", "research:2"],
        ["research:2", "inner-agent-call:3"],
        ["test-provider:0", "test-provider:4"],
      ],
      data: {
        "research:2": {
          run_type: "tool",
          inputs: { topic: "AI" },
          outputs: { output: "Processed: AI research" },
        },
        "inner-agent-call:3": {
          run_type: "chain",
          inputs: { input: "AI research" },
          outputs: { outputs: "Processed: AI research" },
        },
      },
    });
  });
});

describe("usage metadata tracking", () => {
  it("should track AI SDK 6 token usage on step runs", async () => {
    const trace = createTrace();

    await generateText({
      model: createModel({
        responses: [
          textResult(
            "Response",
            usage({
              input: 100,
              output: 25,
              cacheRead: 30,
              cacheWrite: 20,
              reasoning: 10,
            }),
          ),
        ],
      }),
      prompt: "Token test",
      telemetry: { integrations: [trace.integration] },
    });

    await expect(expectTree(trace)).resolves.toMatchObject({
      data: {
        "test-provider:1": {
          extra: {
            metadata: {
              usage_metadata: {
                input_tokens: 100,
                output_tokens: 25,
                total_tokens: 125,
                input_token_details: {
                  cache_read: 30,
                  cache_creation: 20,
                },
                output_token_details: { reasoning: 10 },
              },
            },
          },
        },
      },
    });
  });

  it("should track aggregated usage on the root span", async () => {
    const trace = createTrace();

    await generateText({
      model: createModel({
        responses: [
          textResult("Step response", usage({ input: 30, output: 15 })),
        ],
      }),
      prompt: "Aggregate test",
      telemetry: { integrations: [trace.integration] },
    });

    await expect(expectTree(trace)).resolves.toMatchObject({
      data: {
        "test-provider:0": {
          extra: {
            metadata: {
              usage_metadata: {
                input_tokens: 30,
                output_tokens: 15,
                total_tokens: 45,
              },
            },
          },
        },
      },
    });
  });
});

describe("invocation params", () => {
  it("should record language model call params on step spans", async () => {
    const trace = createTrace();

    await generateText({
      model: createModel(),
      prompt: "Call settings test",
      maxOutputTokens: 25,
      temperature: 0.2,
      topP: 0.9,
      seed: 42,
      telemetry: {
        integrations: [trace.integration],
        functionId: "settings-endpoint",
        recordInputs: false,
        recordOutputs: false,
      },
    });

    const tree = await expectTree(trace);
    expect(tree).toMatchObject({
      edges: [["settings-endpoint:0", "test-provider:1"]],
      data: {
        "test-provider:1": {
          run_type: "llm",
          extra: {
            invocation_params: {
              callId: expect.any(String),
              functionId: "settings-endpoint",
              maxOutputTokens: 25,
              temperature: 0.2,
              topP: 0.9,
              seed: 42,
            },
          },
        },
      },
    });

    const invocationParams =
      tree.data["test-provider:1"].extra?.invocation_params;
    expect(invocationParams).not.toHaveProperty("messages");
    expect(invocationParams).not.toHaveProperty("provider");
    expect(invocationParams).not.toHaveProperty("modelId");
    expect(invocationParams).not.toHaveProperty("recordInputs");
    expect(invocationParams).not.toHaveProperty("recordOutputs");
  });
});

describe("runtime and tool context", () => {
  it("should trace telemetry-filtered runtime and tool context", async () => {
    const trace = createTrace();

    await generateText({
      model: createModel({
        responses: [
          toolCallResult({
            toolCallId: "tc-weather-1",
            toolName: "weather",
            input: { location: "Prague" },
          }),
          textResult("It is 21 degrees.", usage({ input: 20, output: 6 })),
        ],
      }),
      prompt: "Check the weather",
      runtimeContext: {
        requestId: "req-123",
        userId: "user-secret",
      },
      tools: {
        weather: tool({
          inputSchema: z.object({ location: z.string() }),
          contextSchema: z.object({
            defaultUnit: z.enum(["celsius", "fahrenheit"]),
            apiKey: z.string(),
          }),
          execute: async ({ location }, { context }) => ({
            location,
            unit: context.defaultUnit,
          }),
        }),
      },
      toolsContext: {
        weather: {
          defaultUnit: "celsius",
          apiKey: "weather-secret",
        },
      },
      stopWhen: isStepCount(10),
      telemetry: {
        integrations: [trace.integration],
        includeRuntimeContext: {
          requestId: true,
        },
        includeToolsContext: {
          weather: {
            defaultUnit: true,
          },
        },
      },
    });

    const tree = await expectTree(trace);
    expect(tree).toMatchObject({
      edges: [
        ["test-provider:0", "test-provider:1"],
        ["test-provider:1", "weather:2"],
        ["test-provider:0", "test-provider:3"],
      ],
      data: {
        "test-provider:0": {
          inputs: {
            runtimeContext: { requestId: "req-123" },
            toolsContext: {
              weather: { defaultUnit: "celsius" },
            },
          },
        },
        "test-provider:1": {
          inputs: {
            runtimeContext: { requestId: "req-123" },
            toolsContext: {
              weather: { defaultUnit: "celsius" },
            },
          },
        },
        "weather:2": {
          run_type: "tool",
          inputs: {
            location: "Prague",
            toolContext: { defaultUnit: "celsius" },
          },
          outputs: {
            output: { location: "Prague", unit: "celsius" },
          },
        },
      },
    });

    const serializedTree = JSON.stringify(tree);
    expect(serializedTree).not.toContain("user-secret");
    expect(serializedTree).not.toContain("weather-secret");
  });
});

describe("processInputs / processOutputs", () => {
  it("should apply processInputs to the root span", async () => {
    const trace = createTrace({
      processInputs: (inputs) => ({
        ...inputs,
        messages: (inputs.messages ?? []).map((m: any) => ({
          ...m,
          content: "REDACTED",
        })),
      }),
    });

    await generateText({
      model: createModel(),
      prompt: "Secret prompt",
      telemetry: { integrations: [trace.integration] },
    });

    await expect(expectTree(trace)).resolves.toMatchObject({
      data: {
        "test-provider:0": {
          inputs: { messages: [{ role: "user", content: "REDACTED" }] },
        },
      },
    });
  });

  it("should apply processOutputs to the root span", async () => {
    const trace = createTrace({
      processOutputs: (outputs) => ({
        ...outputs,
        content: "REDACTED",
      }),
    });

    await generateText({
      model: createModel({
        responses: [textResult("Secret response")],
      }),
      prompt: "Test",
      telemetry: { integrations: [trace.integration] },
    });

    await expect(expectTree(trace)).resolves.toMatchObject({
      data: {
        "test-provider:0": { outputs: { content: "REDACTED" } },
      },
    });
  });

  it("should apply processChildLLMRunInputs to step spans", async () => {
    const trace = createTrace({
      processChildLLMRunInputs: (inputs) => ({
        messages: (inputs.messages ?? []).map((m: any) => ({
          ...m,
          content: "REDACTED_CHILD_INPUT",
        })),
      }),
    });

    await generateText({
      model: createModel(),
      prompt: "Test",
      telemetry: { integrations: [trace.integration] },
    });

    await expect(expectTree(trace)).resolves.toMatchObject({
      data: {
        "test-provider:1": {
          inputs: {
            messages: [{ role: "user", content: "REDACTED_CHILD_INPUT" }],
          },
        },
      },
    });
  });

  it("should apply processChildLLMRunOutputs to step spans", async () => {
    const trace = createTrace({
      processChildLLMRunOutputs: (outputs) => ({
        ...outputs,
        content: "REDACTED_CHILD_OUTPUT",
        role: "assistant",
      }),
    });

    await generateText({
      model: createModel({
        responses: [textResult("Secret step output")],
      }),
      prompt: "Test",
      telemetry: { integrations: [trace.integration] },
    });

    await expect(expectTree(trace)).resolves.toMatchObject({
      data: {
        "test-provider:1": {
          outputs: {
            role: "assistant",
            content: "REDACTED_CHILD_OUTPUT",
          },
        },
      },
    });
  });
});

describe("dotted order and trace hierarchy", () => {
  it("should maintain correct parent-child dotted order", async () => {
    const trace = createTrace();

    await generateText({
      model: createModel(),
      prompt: "Hierarchy test",
      telemetry: { integrations: [trace.integration] },
    });

    const tree = await expectTree(trace);
    expect(tree).toMatchObject({
      edges: [["test-provider:0", "test-provider:1"]],
    });

    const root = tree.data["test-provider:0"];
    const step = tree.data["test-provider:1"];
    expect(step.trace_id).toBe(root.trace_id);
    const rootDottedOrder = root.dotted_order;
    const stepDottedOrder = step.dotted_order;
    expect(rootDottedOrder).toEqual(expect.any(String));
    expect(stepDottedOrder).toEqual(expect.any(String));
    if (
      typeof rootDottedOrder !== "string" ||
      typeof stepDottedOrder !== "string"
    ) {
      throw new Error("Expected dotted order to be set on root and step runs");
    }
    expect(stepDottedOrder.startsWith(rootDottedOrder)).toBe(true);
    expect(stepDottedOrder.split(".").length).toBe(
      rootDottedOrder.split(".").length + 1,
    );
  });

  it("should nest under an existing traceable context", async () => {
    const trace = createTrace();
    const outerFn = traceable(
      async () => {
        await generateText({
          model: createModel(),
          prompt: "Nested test",
          telemetry: { integrations: [trace.integration] },
        });
      },
      {
        name: "outer-traceable",
        client: trace.client,
        tracingEnabled: true,
      },
    );

    await outerFn();

    await expect(expectTree(trace)).resolves.toMatchObject({
      edges: [
        ["outer-traceable:0", "test-provider:1"],
        ["test-provider:1", "test-provider:2"],
      ],
      data: {
        "outer-traceable:0": { name: "outer-traceable" },
        "test-provider:1": {
          run_type: "chain",
          extra: {
            metadata: {
              ls_integration: "vercel-ai-sdk-telemetry",
            },
          },
        },
        "test-provider:2": { run_type: "llm" },
      },
    });
  });
});

describe("traceResponseMetadata", () => {
  it("should include steps in output when traceResponseMetadata is true", async () => {
    const trace = createTrace({
      traceResponseMetadata: true,
    });

    await generateText({
      model: createModel({
        responses: [textResult("Step 1")],
      }),
      prompt: "Response metadata test",
      telemetry: { integrations: [trace.integration] },
    });

    await expect(expectTree(trace)).resolves.toMatchObject({
      data: {
        "test-provider:0": {
          outputs: {
            steps: [
              expect.objectContaining({
                step_number: 0,
                content: [{ type: "text", text: "Step 1" }],
              }),
            ],
          },
        },
      },
    });
  });

  it("should not include steps when traceResponseMetadata is false", async () => {
    const trace = createTrace();

    await generateText({
      model: createModel(),
      prompt: "No metadata test",
      telemetry: { integrations: [trace.integration] },
    });

    const tree = await expectTree(trace);
    expect(tree.data["test-provider:0"].outputs?.steps).toBeUndefined();
  });
});

describe("streaming (onChunk)", () => {
  it("should handle onChunk as a no-op without errors", async () => {
    const trace = createTrace();

    const result = streamText({
      model: createModel(),
      prompt: "Stream test",
      telemetry: { integrations: [trace.integration] },
    });

    await expect(result.text).resolves.toBe("Hello world");
    await expect(expectTree(trace)).resolves.toMatchObject({
      edges: [["test-provider:0", "test-provider:1"]],
      data: {
        "test-provider:0": {
          run_type: "chain",
          outputs: {
            role: "assistant",
            content: "Hello world",
            finish_reason: "stop",
          },
        },
        "test-provider:1": {
          run_type: "llm",
          outputs: {
            role: "assistant",
            content: [{ type: "text", text: "Hello world" }],
          },
        },
      },
    });
  });
});

describe("tracing disabled", () => {
  it("should not create runs when tracing is disabled", async () => {
    const trace = createTrace({ tracingEnabled: false });

    await generateText({
      model: createModel(),
      prompt: "Should not trace",
      telemetry: { integrations: [trace.integration] },
    });
    await trace.client.awaitPendingTraceBatches();
    expect(trace.callSpy).not.toHaveBeenCalled();
  });
});

describe("project name configuration", () => {
  it("should use custom project name", async () => {
    const trace = createTrace({
      projectName: "my-custom-project",
    });

    await generateText({
      model: createModel(),
      prompt: "Project test",
      telemetry: { integrations: [trace.integration] },
    });

    await expect(expectTree(trace)).resolves.toMatchObject({
      data: {
        "test-provider:0": { session_name: "my-custom-project" },
      },
    });
  });
});

describe("integration reuse", () => {
  it("should create separate traces when reusing the same integration sequentially", async () => {
    const trace = createTrace();

    await generateText({
      model: createModel({
        responses: [textResult("First response")],
      }),
      prompt: "First call",
      telemetry: { integrations: [trace.integration] },
    });

    const firstTree = await expectTree(trace);
    expect(firstTree).toMatchObject({
      edges: [["test-provider:0", "test-provider:1"]],
      data: {
        "test-provider:0": {
          inputs: { messages: [{ role: "user", content: "First call" }] },
          outputs: { content: "First response" },
        },
      },
    });
    const firstRoot = firstTree.data["test-provider:0"];

    trace.callSpy.mockClear();

    await generateText({
      model: createModel({
        responses: [
          textResult("Second response", usage({ input: 7, output: 4 })),
        ],
      }),
      prompt: "Second call",
      telemetry: { integrations: [trace.integration] },
    });

    const secondTree = await expectTree(trace);
    expect(secondTree).toMatchObject({
      edges: [["test-provider:0", "test-provider:1"]],
      data: {
        "test-provider:0": {
          inputs: { messages: [{ role: "user", content: "Second call" }] },
          outputs: { content: "Second response" },
        },
      },
    });
    const secondRoot = secondTree.data["test-provider:0"];
    expect(secondRoot.id).not.toBe(firstRoot.id);
    expect(secondRoot.trace_id).not.toBe(firstRoot.trace_id);
  });

  it("should not leak state between sequential invocations after error", async () => {
    const trace = createTrace();

    await expect(
      generateText({
        model: createModel({
          doGenerate: async () => {
            throw new Error("TOTALLY EXPECTED MOCK ERROR");
          },
        }),
        prompt: "Error call",
        telemetry: { integrations: [trace.integration] },
      }),
    ).rejects.toThrow("TOTALLY EXPECTED MOCK ERROR");

    await expect(expectTree(trace)).resolves.toMatchObject({
      data: {
        "test-provider:0": {
          error: expect.stringContaining("TOTALLY EXPECTED MOCK ERROR"),
        },
      },
    });
    trace.callSpy.mockClear();

    await generateText({
      model: createModel({
        responses: [textResult("Recovered")],
      }),
      prompt: "Recovery call",
      telemetry: { integrations: [trace.integration] },
    });

    await expect(expectTree(trace)).resolves.toMatchObject({
      edges: [["test-provider:0", "test-provider:1"]],
      data: {
        "test-provider:0": {
          inputs: { messages: [{ role: "user", content: "Recovery call" }] },
          outputs: { content: "Recovered" },
        },
      },
    });
  });

  it("should handle reuse with tools across invocations", async () => {
    const trace = createTrace();

    await generateText({
      model: createModel({
        responses: [
          toolCallResult({
            toolCallId: "tc-1",
            toolName: "search",
            input: { query: "first" },
          }),
          textResult("First answer", usage({ input: 20, output: 8 })),
        ],
      }),
      prompt: "First tool call",
      tools: {
        search: tool({
          inputSchema: z.object({ query: z.string() }),
          execute: async () => "first result",
        }),
      },
      stopWhen: isStepCount(10),
      telemetry: { integrations: [trace.integration] },
    });

    const firstTree = await expectTree(trace);
    const firstTraceId = firstTree.data["test-provider:0"].trace_id;
    trace.callSpy.mockClear();

    await generateText({
      model: createModel({
        responses: [
          toolCallResult({
            toolCallId: "tc-2",
            toolName: "calculator",
            input: { expression: "1+1" },
          }),
          textResult("1+1 = 2", usage({ input: 15, output: 5 })),
        ],
      }),
      prompt: "Second tool call",
      tools: {
        calculator: tool({
          inputSchema: z.object({ expression: z.string() }),
          execute: async () => 2,
        }),
      },
      stopWhen: isStepCount(10),
      telemetry: { integrations: [trace.integration] },
    });

    const secondTree = await expectTree(trace);
    expect(secondTree).toMatchObject({
      edges: [
        ["test-provider:0", "test-provider:1"],
        ["test-provider:1", "calculator:2"],
        ["test-provider:0", "test-provider:3"],
      ],
      data: {
        "calculator:2": {
          run_type: "tool",
          inputs: { expression: "1+1" },
          outputs: { output: 2 },
        },
      },
    });
    expect(secondTree.data["test-provider:0"].trace_id).not.toBe(firstTraceId);
  });
});
