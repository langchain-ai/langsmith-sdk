// import { generateText, stepCountIs, tool, wrapLanguageModel } from "ai";
import { openai } from "@ai-sdk/openai";
import * as ai from "ai";
import z from "zod";
import { v4 } from "uuid";
import * as fs from "fs/promises";
import { fileURLToPath } from "url";
import path from "path";

import { Client } from "../../../index.js";
import {
  createLangSmithProviderOptions,
  wrapAISDK,
} from "../../../experimental/vercel/index.js";
import { waitUntilRunFound } from "../../utils.js";
import { mockClient } from "../../utils/mock_client.js";

const { tool, stepCountIs } = ai;

const { generateText, streamText, generateObject, streamObject } =
  wrapAISDK(ai);

test("wrap generateText", async () => {
  const result = await generateText({
    model: openai("gpt-5-nano"),
    messages: [
      {
        role: "user",
        content: "What are my orders? My user ID is 123. Always use tools.",
      },
    ],
    tools: {
      listOrders: tool({
        description: "list all orders",
        inputSchema: z.object({ userId: z.string() }),
        execute: async ({ userId }) =>
          `User ${userId} has the following orders: 1`,
      }),
    },
    stopWhen: stepCountIs(10),
  });
  expect(result.text).toBeDefined();
  expect(result.text.length).toBeGreaterThan(0);
  expect(result.usage).toBeDefined();
  expect(result.providerMetadata).toBeDefined();
});

test("wrap generateText with tool class", async () => {
  class MyTool {
    inputSchema: z.ZodSchema;
    description: string;

    constructor(inputSchema: z.ZodSchema, description: string) {
      this.inputSchema = inputSchema;
      this.description = description;
    }

    async execute() {
      return this.helperMethod();
    }

    helperMethod() {
      return `User has the following orders: 1`;
    }
  }

  const result = await generateText({
    model: openai("gpt-5-nano"),
    messages: [
      {
        role: "user",
        content: "What are my orders? My user ID is 123. Always use tools.",
      },
    ],
    tools: {
      listOrders: new MyTool(
        z.object({ userId: z.string() }),
        "list all orders"
      ),
    },
    stopWhen: stepCountIs(10),
  });
  expect(result.text).toBeDefined();
  expect(result.text.length).toBeGreaterThan(0);
  expect(result.usage).toBeDefined();
  expect(result.providerMetadata).toBeDefined();
});

test("wrap generateText with flex service tier", async () => {
  const { client, callSpy } = mockClient();

  const result = await generateText({
    model: openai("gpt-5-mini"),
    messages: [
      {
        role: "user",
        content: "What color is the sky in one word?",
      },
    ],
    providerOptions: {
      openai: {
        serviceTier: "flex",
      },
      langsmith: createLangSmithProviderOptions({
        client,
      }),
    },
  });
  expect(result.text).toBeDefined();
  expect(result.text.length).toBeGreaterThan(0);
  expect(result.usage).toBeDefined();
  expect(result.providerMetadata).toBeDefined();
  await client.awaitPendingTraceBatches();
  const patchBodies = await Promise.all(
    callSpy.mock.calls
      .filter((call) => call[1]!.method === "PATCH")
      .map((call) => new Response(call[1]!.body).json())
  );
  const childRunPatchBodies = patchBodies.filter(
    (body) => body.parent_run_id != null
  );

  expect(childRunPatchBodies.length).toBeGreaterThanOrEqual(1);

  const llmChildRun = childRunPatchBodies.find(
    (body) => body.extra?.metadata?.usage_metadata
  );
  expect(llmChildRun).toBeDefined();

  const usageMetadata = llmChildRun!.extra.metadata.usage_metadata;
  expect(usageMetadata.input_token_details.flex).toBeGreaterThan(1);
  expect(usageMetadata.input_token_details.flex).toEqual(
    usageMetadata.input_tokens
  );
  expect(usageMetadata.output_token_details.flex).toBeGreaterThan(1);
  expect(
    usageMetadata.output_token_details.flex +
      usageMetadata.output_token_details.flex_reasoning
  ).toEqual(usageMetadata.output_tokens);
});

test("wrap streamText", async () => {
  const result = streamText({
    model: openai("gpt-5-nano"),
    messages: [
      {
        role: "user",
        content: "What are my orders? My user ID is 123. Always use tools.",
      },
    ],
    tools: {
      listOrders: tool({
        description: "list all orders",
        inputSchema: z.object({ userId: z.string() }),
        execute: async ({ userId }) =>
          `User ${userId} has the following orders: 1`,
      }),
    },
    stopWhen: stepCountIs(10),
  });
  let total = "";
  for await (const chunk of result.textStream) {
    total += chunk;
  }
  expect(total).toBeDefined();
  expect(total.length).toBeGreaterThan(0);
  expect(result.usage).toBeDefined();
  expect(result.providerMetadata).toBeDefined();
});

test("wrap streamText with service tier", async () => {
  const { client, callSpy } = mockClient();

  const result = streamText({
    model: openai("gpt-5-mini"),
    messages: [
      {
        role: "user",
        content: "What color is the sky in one word?",
      },
    ],
    providerOptions: {
      openai: {
        serviceTier: "flex",
      },
      langsmith: createLangSmithProviderOptions({
        client,
      }),
    },
  });
  await result.consumeStream();
  const patchBodies = await Promise.all(
    callSpy.mock.calls
      .filter((call) => call[1]!.method === "PATCH")
      .map((call) => new Response(call[1]!.body).json())
  );
  const childRunPatchBodies = patchBodies.filter(
    (body) => body.parent_run_id != null
  );

  expect(childRunPatchBodies.length).toBeGreaterThanOrEqual(1);

  const llmChildRun = childRunPatchBodies.find(
    (body) => body.extra?.metadata?.usage_metadata
  );
  expect(llmChildRun).toBeDefined();

  const usageMetadata = llmChildRun!.extra.metadata.usage_metadata;
  expect(usageMetadata.input_token_details.flex).toBeGreaterThan(1);
  expect(usageMetadata.input_token_details.flex).toEqual(
    usageMetadata.input_tokens
  );
  expect(usageMetadata.output_token_details.flex).toBeGreaterThan(1);
  expect(
    usageMetadata.output_token_details.flex +
      usageMetadata.output_token_details.flex_reasoning
  ).toEqual(usageMetadata.output_tokens);
});

test("wrap generateObject", async () => {
  const schema = z.object({
    color: z.string(),
  });
  const result = await generateObject({
    model: openai("gpt-5-nano"),
    messages: [
      {
        role: "user",
        content: "What color is the sky in one word?",
      },
    ],
    schema,
  });
  expect(result.object).toBeDefined();
  expect(schema.parse(result.object)).toBeDefined();
  expect(result.usage).toBeDefined();
  expect(result.providerMetadata).toBeDefined();
});

test("wrap streamObject", async () => {
  const schema = z.object({
    color: z.string(),
  });
  const result = await streamObject({
    model: openai("gpt-5-nano"),
    messages: [
      {
        role: "user",
        content: "What color is the sky in one word?",
      },
    ],
    schema,
  });
  const chunks = [];
  for await (const chunk of result.partialObjectStream) {
    chunks.push(chunk);
  }
  expect(chunks.length).toBeGreaterThan(0);
  expect(schema.parse(chunks.at(-1))).toBeDefined();
  expect(result.usage).toBeDefined();
  expect(result.providerMetadata).toBeDefined();
});

test("can set run id", async () => {
  const runId = v4();
  const client = new Client();
  const { generateText } = wrapAISDK(ai, { id: runId });
  await generateText({
    model: openai("gpt-5-nano"),
    messages: [
      {
        role: "user",
        content: "What color is the sky in one word?",
      },
    ],
  });
  await waitUntilRunFound(client, runId);
  const run = await client.readRun(runId);
  expect(run.id).toBe(runId);
});

test("should reuse tool def without double wrapping tool traces", async () => {
  const toolDef = {
    listOrders: tool({
      description: "list all orders",
      inputSchema: z.object({ userId: z.string() }),
      execute: async ({ userId }) =>
        `User ${userId} has the following orders: 1`,
    }),
  };
  const result = await generateText({
    model: openai("gpt-5-nano"),
    messages: [
      {
        role: "user",
        content: "What are my orders? My user ID is 123. Always use tools.",
      },
    ],
    tools: toolDef,
    stopWhen: stepCountIs(10),
  });
  expect(result.text).toBeDefined();
  expect(result.text.length).toBeGreaterThan(0);
  expect(result.usage).toBeDefined();
  expect(result.providerMetadata).toBeDefined();
  const result2 = await generateText({
    model: openai("gpt-5-nano"),
    messages: [
      {
        role: "user",
        content: "What are my orders? My user ID is 123. Always use tools.",
      },
    ],
    tools: toolDef,
    stopWhen: stepCountIs(10),
  });
  expect(result2.text).toBeDefined();
  expect(result2.text.length).toBeGreaterThan(0);
  expect(result2.usage).toBeDefined();
  expect(result2.providerMetadata).toBeDefined();
});

test("image and file data normalization", async () => {
  const pathname = path.join(
    path.dirname(fileURLToPath(import.meta.url)),
    "..",
    "..",
    "test_data",
    "parrot-icon.png"
  );
  const imgBuffer = await fs.readFile(pathname);
  const imgArrayBuffer = imgBuffer.buffer.slice(
    imgBuffer.byteOffset,
    imgBuffer.byteOffset + imgBuffer.byteLength
  );
  const imgBase64 = imgBuffer.toString("base64");
  const imgUrl = "https://picsum.photos/200/300";
  const imgDataUrl = `data:image/png;base64,${imgBase64}`;
  const imgUrlObject = new URL("https://picsum.photos/200/300");

  const result = await generateText({
    model: openai("gpt-5-nano"),
    messages: [
      {
        role: "user",
        content: [
          { type: "text", text: "Analyze all these images and files:" },
          { type: "image", image: imgBuffer }, // Node.js Buffer
          { type: "image", image: imgArrayBuffer }, // ArrayBuffer
          { type: "image", image: imgBase64 }, // Base64 string
          { type: "image", image: imgUrl }, // HTTP URL string
          { type: "image", image: imgDataUrl }, // Existing data URL
          { type: "image", image: imgUrlObject }, // URL object
          {
            type: "file",
            data: imgBuffer,
            mediaType: "image/png",
            filename: "test.png",
          }, // File with Buffer data
        ],
      },
    ],
  });
  expect(result.text).toBeDefined();
  expect(result.text.length).toBeGreaterThan(0);
  expect(result.usage).toBeDefined();
  expect(result.providerMetadata).toBeDefined();
});

test("process inputs and outputs", async () => {
  const lsConfig = createLangSmithProviderOptions<typeof ai.generateText>({
    processInputs: (inputs) => {
      const { messages } = inputs;
      return {
        messages: messages?.map((message) => ({
          providerMetadata: message.providerOptions,
          role: "assistant",
          content: "REDACTED",
        })),
        prompt: "REDACTED",
      };
    },
    processOutputs: (outputs) => {
      return {
        providerMetadata: outputs.outputs.providerMetadata,
        role: "assistant",
        content: "REDACTED",
      };
    },
    processChildLLMRunInputs: (inputs) => {
      const { prompt } = inputs;
      return {
        messages: prompt.map((message) => ({
          ...message,
          content: "REDACTED CHILD INPUTS",
        })),
      };
    },
    processChildLLMRunOutputs: (outputs) => {
      return {
        ...outputs,
        content: "REDACTED CHILD OUTPUTS",
        role: "assistant",
      };
    },
  });
  const { text } = await generateText({
    model: openai("gpt-5-nano"),
    prompt: "What is the capital of France?",
    providerOptions: {
      langsmith: lsConfig,
    },
  });
  expect(text).not.toContain("REDACTED");
});

test("generateText with experimental_output should display as structured object in LangSmith", async () => {
  const outputSchema = z.object({
    city: z.string(),
    temperature: z.number().nullable(),
    unit: z.enum(["celsius", "fahrenheit"]),
    conditions: z.string(),
  });

  const { generateText: wrappedGenerateText } = wrapAISDK(ai);

  const result = await wrappedGenerateText({
    model: openai("gpt-5-nano"),
    prompt: "What's the weather in Prague? Return a structured response.",
    experimental_output: ai.Output.object({
      schema: outputSchema,
    }),
  });

  // Verify the output is returned correctly and can be parsed
  expect(result.experimental_output).toBeDefined();
  const parsedOutput = outputSchema.parse(result.experimental_output);
  expect(parsedOutput.city).toBeDefined();
  expect(parsedOutput.temperature).toBeDefined();
  expect(parsedOutput.unit).toBeDefined();
  expect(parsedOutput.conditions).toBeDefined();
});

test("streamText with experimental_output should display as structured object in LangSmith", async () => {
  const outputSchema = z.object({
    city: z.string(),
    temperature: z.number().nullable(),
    unit: z.enum(["celsius", "fahrenheit"]),
    conditions: z.string(),
  });

  const { streamText: wrappedStreamText } = wrapAISDK(ai);

  const result = wrappedStreamText({
    model: openai("gpt-5-nano"),
    prompt: "What's the weather in Paris? Return a structured response.",
    experimental_output: ai.Output.object({
      schema: outputSchema,
    }),
  });

  const chunks = [];
  // Consume the stream
  for await (const chunk of result.experimental_partialOutputStream) {
    chunks.push(chunk);
  }
  expect(chunks.length).toBeGreaterThan(0);
  expect(outputSchema.parse(chunks.at(-1))).toBeDefined();
});
