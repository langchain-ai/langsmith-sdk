/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable no-process-env */
import { AzureOpenAI, OpenAI } from "openai";
import { wrapOpenAI } from "../wrappers/index.js";
import { mockClient } from "./utils/mock_client.js";
import { getAssumedTreeFromCalls } from "./utils/tree.js";
import { zodResponseFormat, zodTextFormat } from "openai/helpers/zod";
import { z } from "zod";
import { UsageMetadata } from "../schemas.js";
import fs from "fs";

function parseRequestBody(body: any) {
  // eslint-disable-next-line no-instanceof/no-instanceof
  return body instanceof Uint8Array
    ? JSON.parse(new TextDecoder().decode(body))
    : JSON.parse(body);
}

test("wrapOpenAI should return type compatible with OpenAI", async () => {
  let originalClient = new OpenAI();
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  originalClient = wrapOpenAI(originalClient);

  expect(true).toBe(true);
});

test("chat.completions", async () => {
  const { client, callSpy } = mockClient();

  const originalClient = new OpenAI();
  const patchedClient = wrapOpenAI(new OpenAI(), {
    client,
    tracingEnabled: true,
  });

  // invoke
  const original = await originalClient.chat.completions.create({
    messages: [{ role: "user", content: `Say 'foo'` }],
    temperature: 0,
    seed: 42,
    model: "gpt-4.1-nano",
  });

  const patched = await patchedClient.chat.completions.create({
    messages: [{ role: "user", content: `Say 'foo'` }],
    temperature: 0,
    seed: 42,
    model: "gpt-4.1-nano",
  });

  expect(patched.choices).toEqual(original.choices);

  const response = await patchedClient.chat.completions
    .create({
      messages: [{ role: "user", content: `Say 'foo'` }],
      temperature: 0,
      seed: 42,
      model: "gpt-4.1-nano",
    })
    .asResponse();

  expect(response.ok).toBe(true);

  // stream
  const originalStream = await originalClient.chat.completions.create({
    messages: [{ role: "user", content: `Say 'foo'` }],
    temperature: 0,
    seed: 42,
    model: "gpt-4.1-nano",
    stream: true,
  });

  const originalChoices: unknown[] = [];
  for await (const chunk of originalStream) {
    originalChoices.push(chunk.choices);
  }

  const patchedStream = await patchedClient.chat.completions.create({
    messages: [{ role: "user", content: `Say 'foo'` }],
    temperature: 0,
    seed: 42,
    model: "gpt-4.1-nano",
    stream: true,
  });

  const patchedChoices: unknown[] = [];
  for await (const chunk of patchedStream) {
    patchedChoices.push(chunk.choices);
    // @ts-expect-error Should type check streamed output
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const _test = chunk.invalidPrompt;
  }

  expect(patchedChoices).toEqual(originalChoices);

  expect(callSpy.mock.calls.length).toBeGreaterThanOrEqual(1);

  // Verify token events were logged
  const patchCalls = callSpy.mock.calls.filter(
    (call) => (call[1] as any).method === "PATCH"
  );
  const lastPatchCall = patchCalls[patchCalls.length - 1];
  const body = parseRequestBody((lastPatchCall[1] as any).body);

  expect(body.events).toBeDefined();
  const tokenEvents = body.events.filter(
    (event: any) => event.name === "new_token"
  );
  expect(tokenEvents.length).toBeGreaterThan(0);
  tokenEvents.forEach((event: any) => {
    expect(event.name).toBe("new_token");
    expect(event.kwargs).toBeDefined();
    expect(event.kwargs.token).toBeDefined();
    expect(event.time).toBeDefined();
  });

  for (const call of callSpy.mock.calls) {
    expect(["POST", "PATCH"]).toContain((call[1] as any)["method"]);
  }
  callSpy.mockClear();

  const patchedStreamToBreak = await patchedClient.chat.completions.create({
    messages: [{ role: "user", content: `Say 'hello world hello again'` }],
    temperature: 0,
    seed: 42,
    model: "gpt-4.1-nano",
    stream: true,
  });

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  for await (const _ of patchedStreamToBreak) {
    break;
  }

  expect(callSpy.mock.calls.length).toBeGreaterThanOrEqual(1);
  for (const call of callSpy.mock.calls) {
    expect(["POST", "PATCH"]).toContain((call[1] as any)["method"]);
  }
  callSpy.mockClear();

  const patchedStreamWithMetadata = await patchedClient.chat.completions.create(
    {
      messages: [{ role: "user", content: `Say 'foo'` }],
      temperature: 0,
      seed: 42,
      model: "gpt-4.1-nano",
      stream: true,
    },
    {
      langsmithExtra: {
        metadata: {
          thing1: "thing2",
        },
      },
    }
  );

  const patchedChoices2: unknown[] = [];
  for await (const chunk of patchedStreamWithMetadata) {
    patchedChoices2.push(chunk.choices);
    // @ts-expect-error Should type check streamed output
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const _test = chunk.invalidPrompt;
  }

  expect(patchedChoices2).toEqual(originalChoices);
  expect(callSpy.mock.calls.length).toBeGreaterThanOrEqual(1);
  for (const call of callSpy.mock.calls) {
    expect(["POST", "PATCH"]).toContain((call[1] as any)["method"]);
  }
  callSpy.mockClear();
});

test("chat completions with tool calling", async () => {
  const { client, callSpy } = mockClient();

  const originalClient = new OpenAI();
  const patchedClient = wrapOpenAI(new OpenAI(), {
    client,
    tracingEnabled: true,
  });
  const removeToolCallId = (
    choices:
      | OpenAI.ChatCompletion.Choice[]
      | OpenAI.ChatCompletionChunk.Choice[][]
  ) => {
    if (Array.isArray(choices[0])) {
      return (choices as OpenAI.ChatCompletionChunk.Choice[][]).map(
        (choices) => {
          return choices.map((choice) => {
            choice.delta.tool_calls = choice.delta.tool_calls?.map(
              (toolCall) => {
                const { id, ...rest } = toolCall;
                return rest;
              }
            ) as any;
            return choice;
          });
        }
      );
    } else {
      return (choices as OpenAI.ChatCompletion.Choice[]).map((choice) => {
        choice.message.tool_calls = choice.message.tool_calls?.map(
          (toolCall) => {
            const { id, ...rest } = toolCall;
            return rest;
          }
        ) as any;
        return choice;
      });
    }
  };

  const toolDefinition = [
    {
      type: "function" as const,
      function: {
        name: "get_current_weather",
        description: "Get the current weather in a given location",
        parameters: {
          type: "object",
          properties: {
            location: {
              type: "string",
              description: "The city and only the city, e.g. San Francisco",
            },
          },
          required: ["location"],
        },
      },
    },
  ];

  // invoke
  const original = await originalClient.chat.completions.create({
    messages: [{ role: "user", content: `What is the current weather in SF?` }],
    temperature: 0,
    seed: 42,
    model: "gpt-4.1-nano",
    tools: toolDefinition,
    tool_choice: {
      type: "function",
      function: { name: "get_current_weather" },
    },
  });

  const patched = await patchedClient.chat.completions.create({
    messages: [{ role: "user", content: `What is the current weather in SF?` }],
    temperature: 0,
    seed: 42,
    model: "gpt-4.1-nano",
    tools: toolDefinition,
    tool_choice: {
      type: "function",
      function: { name: "get_current_weather" },
    },
  });

  expect(removeToolCallId(patched.choices)).toEqual(
    removeToolCallId(original.choices)
  );

  // stream
  const originalStream = await originalClient.chat.completions.create({
    messages: [{ role: "user", content: `What is the current weather in SF?` }],
    temperature: 0,
    seed: 42,
    model: "gpt-4.1-nano",
    tools: toolDefinition,
    tool_choice: {
      type: "function",
      function: { name: "get_current_weather" },
    },
    stream: true,
  });

  const originalChoices: any[] = [];
  for await (const chunk of originalStream) {
    originalChoices.push(chunk.choices);
  }

  const patchedStream = await patchedClient.chat.completions.create({
    messages: [{ role: "user", content: `What is the current weather in SF?` }],
    temperature: 0,
    seed: 42,
    model: "gpt-4.1-nano",
    tools: toolDefinition,
    tool_choice: {
      type: "function",
      function: { name: "get_current_weather" },
    },
    stream: true,
  });

  const patchedChoices: any[] = [];
  for await (const chunk of patchedStream) {
    patchedChoices.push(chunk.choices);
    // @ts-expect-error Should type check streamed output
    const _test = chunk.invalidPrompt;
  }

  expect(removeToolCallId(patchedChoices)).toEqual(
    removeToolCallId(originalChoices)
  );
  expect(callSpy.mock.calls.length).toBeGreaterThanOrEqual(1);

  // Verify token events were logged for tool calling stream
  const patchCalls = callSpy.mock.calls.filter(
    (call) => (call[1] as any).method === "PATCH"
  );
  const lastPatchCall = patchCalls[patchCalls.length - 1];
  const body = parseRequestBody((lastPatchCall[1] as any).body);

  expect(body.events).toBeDefined();
  const tokenEvents = body.events.filter(
    (event: any) => event.name === "new_token"
  );
  expect(tokenEvents.length).toBeGreaterThan(0);
  tokenEvents.forEach((event: any) => {
    expect(event.name).toBe("new_token");
    expect(event.kwargs).toBeDefined();
    expect(event.kwargs.token).toBeDefined();
    expect(event.time).toBeDefined();
  });

  for (const call of callSpy.mock.calls) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    expect(["POST", "PATCH"]).toContain((call[1] as any)["method"]);
  }
  callSpy.mockClear();

  const patchedStream2 = await patchedClient.chat.completions.create(
    {
      messages: [
        { role: "user", content: `What is the current weather in SF?` },
      ],
      temperature: 0,
      seed: 42,
      model: "gpt-4.1-nano",
      tools: toolDefinition,
      tool_choice: {
        type: "function",
        function: { name: "get_current_weather" },
      },
      stream: true,
    },
    {
      langsmithExtra: {
        metadata: {
          thing1: "thing2",
        },
      },
    }
  );

  const patchedChoices2: any[] = [];
  for await (const chunk of patchedStream2) {
    patchedChoices2.push(chunk.choices);
    // @ts-expect-error Should type check streamed output
    const _test = chunk.invalidPrompt;
  }

  expect(removeToolCallId(patchedChoices2)).toEqual(
    removeToolCallId(originalChoices)
  );
  expect(callSpy.mock.calls.length).toBeGreaterThanOrEqual(1);
  for (const call of callSpy.mock.calls) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    expect(["POST", "PATCH"]).toContain((call[1] as any)["method"]);
    const body = parseRequestBody((call[1] as any).body);
    expect(body.extra.metadata).toMatchObject({
      thing1: "thing2",
      ls_model_name: "gpt-4.1-nano",
      ls_model_type: "chat",
      ls_provider: "openai",
      ls_temperature: 0,
    });
  }
  callSpy.mockClear();
});

test("completions", async () => {
  const { client, callSpy } = mockClient();
  const originalClient = new OpenAI();
  const patchedClient = wrapOpenAI(new OpenAI(), {
    client,
    tracingEnabled: true,
  });

  const prompt = `Say 'Hi I'm ChatGPT' then stop.`;

  // invoke
  const original = await originalClient.completions.create({
    prompt,
    temperature: 0,
    seed: 42,
    model: "gpt-3.5-turbo-instruct",
  });

  const patched = await patchedClient.completions.create({
    prompt,
    temperature: 0,
    seed: 42,
    model: "gpt-3.5-turbo-instruct",
  });

  expect(patched.choices).toEqual(original.choices);

  // stream
  const originalStream = await originalClient.completions.create({
    prompt,
    temperature: 0,
    seed: 42,
    model: "gpt-3.5-turbo-instruct",
    stream: true,
  });

  const originalChoices: unknown[] = [];
  for await (const chunk of originalStream) {
    originalChoices.push(chunk.choices);
    // @ts-expect-error Should type check streamed output
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const _test = chunk.invalidPrompt;
  }

  const patchedStream = await patchedClient.completions.create({
    prompt,
    temperature: 0,
    seed: 42,
    model: "gpt-3.5-turbo-instruct",
    stream: true,
  });

  const patchedChoices: unknown[] = [];
  for await (const chunk of patchedStream) {
    patchedChoices.push(chunk.choices);
    // @ts-expect-error Should type check streamed output
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const _test = chunk.invalidPrompt;
  }

  expect(patchedChoices).toEqual(originalChoices);
  expect(callSpy.mock.calls.length).toBeGreaterThanOrEqual(1);
  for (const call of callSpy.mock.calls) {
    expect(["POST", "PATCH"]).toContain((call[1] as any)["method"]);
  }

  const patchedStream2 = await patchedClient.completions.create(
    {
      prompt,
      temperature: 0,
      seed: 42,
      model: "gpt-3.5-turbo-instruct",
      stream: true,
    },
    {
      langsmithExtra: {
        metadata: {
          thing1: "thing2",
        },
      },
    }
  );

  const patchedChoices2: unknown[] = [];
  for await (const chunk of patchedStream2) {
    patchedChoices2.push(chunk.choices);
    // @ts-expect-error Should type check streamed output
    const _test = chunk.invalidPrompt;
  }

  expect(patchedChoices2).toEqual(originalChoices);
  expect(callSpy.mock.calls.length).toBeGreaterThanOrEqual(1);
  for (const call of callSpy.mock.calls) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    expect(["POST", "PATCH"]).toContain((call[1] as any)["method"]);
  }
});

test.skip("with initialization time config", async () => {
  const patchedClient = wrapOpenAI(new OpenAI(), {
    project_name: "alternate_project",
    metadata: {
      customKey: "customVal",
    },
  });
  const patchedStream = await patchedClient.chat.completions.create({
    messages: [{ role: "user", content: `What is the current weather in SF?` }],
    temperature: 0,
    seed: 42,
    model: "gpt-4.1-nano",
    stream: true,
  });

  const patchedChoices: unknown[] = [];
  for await (const chunk of patchedStream) {
    patchedChoices.push(chunk.choices);
    // @ts-expect-error Should type check streamed output
    const _test = chunk.invalidPrompt;
  }
});

test.skip("no tracing with env var unset", async () => {
  process.env.LANGCHAIN_TRACING_V2 = undefined;
  process.env.LANGSMITH_TRACING_V2 = undefined;
  const patchedClient = wrapOpenAI(new OpenAI());
  const patched = await patchedClient.chat.completions.create({
    messages: [{ role: "user", content: `Say 'bazqux'` }],
    temperature: 0,
    seed: 42,
    model: "gpt-4.1-nano",
  });
  expect(patched).toBeDefined();
});

test("wrapping same instance", async () => {
  const wrapped = wrapOpenAI(new OpenAI());
  expect(() => wrapOpenAI(wrapped)).toThrowError(
    "This instance of OpenAI client has been already wrapped once."
  );
});

test("chat extra name", async () => {
  const { client, callSpy } = mockClient();

  const openai = wrapOpenAI(new OpenAI(), {
    client,
    tracingEnabled: true,
  });

  await openai.chat.completions.create(
    {
      messages: [{ role: "user", content: `Say 'red'` }],
      temperature: 0,
      seed: 42,
      model: "gpt-4.1-nano",
    },
    { langsmithExtra: { name: "red", metadata: { customKey: "red" } } }
  );

  const stream = await openai.chat.completions.create(
    {
      messages: [{ role: "user", content: `Say 'green'` }],
      temperature: 0,
      seed: 42,
      model: "gpt-4.1-nano",
      stream: true,
    },
    { langsmithExtra: { name: "green", metadata: { customKey: "green" } } }
  );

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  for await (const _ of stream) {
    // pass
  }

  expect(
    await getAssumedTreeFromCalls(callSpy.mock.calls, client)
  ).toMatchObject({
    nodes: ["red:0", "green:1"],
    edges: [],
    data: {
      "red:0": {
        name: "red",
        extra: { metadata: { customKey: "red" } },
        outputs: {
          choices: [
            {
              index: 0,
              message: { role: "assistant", content: expect.any(String) },
            },
          ],
        },
      },
      "green:1": {
        name: "green",
        extra: { metadata: { customKey: "green" } },
        outputs: {
          choices: [
            {
              index: 0,
              message: { role: "assistant", content: expect.any(String) },
            },
          ],
        },
      },
    },
  });
});

test("chat.completions.parse", async () => {
  const { client, callSpy } = mockClient();

  const openai = wrapOpenAI(new OpenAI(), {
    client,
    tracingEnabled: true,
  });

  await openai.chat.completions.parse({
    model: "gpt-4.1-nano",
    temperature: 0,
    messages: [
      {
        role: "user",
        content: "I am Jacob",
      },
    ],
    response_format: zodResponseFormat(
      z.object({
        name: z.string(),
      }),
      "name"
    ),
  });

  for (const call of callSpy.mock.calls) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    expect(["POST", "PATCH"]).toContain((call[1] as any)["method"]);
    const body = parseRequestBody((call[1] as any).body);
    expect(body.extra.metadata).toMatchObject({
      ls_model_name: "gpt-4.1-nano",
      ls_model_type: "chat",
      ls_provider: "openai",
      ls_temperature: 0,
    });
  }
  callSpy.mockClear();
});

test("responses.create and retrieve workflow", async () => {
  const { client, callSpy } = mockClient();

  const openai = wrapOpenAI(new OpenAI(), {
    client,
    tracingEnabled: true,
  });

  // Create a response (this should be traced)
  const createResponse = await openai.responses.create({
    model: "gpt-4.1-nano",
    input: [
      {
        role: "user",
        content: [{ type: "input_text", text: "What is 2+2?" }],
      },
    ],
  });

  expect(createResponse).toBeDefined();
  expect(createResponse.id).toBeDefined();

  // Verify that create was traced
  const createCalls = callSpy.mock.calls.filter(
    (call) => (call[1] as any).method === "POST"
  );
  expect(createCalls.length).toBeGreaterThanOrEqual(1);

  const createCallCount = callSpy.mock.calls.length;

  // Retrieve the response (this should NOT be traced)
  const retrieveResponse = await openai.responses.retrieve(createResponse.id);

  expect(retrieveResponse).toBeDefined();
  expect(retrieveResponse.id).toBe(createResponse.id);

  // Verify that retrieve did NOT add any new tracing calls
  expect(callSpy.mock.calls.length).toBe(createCallCount);

  // Verify the create call had proper metadata
  for (const call of createCalls) {
    const body = parseRequestBody((call[1] as any).body);
    expect(body.extra.metadata).toMatchObject({
      ls_model_name: "gpt-4.1-nano",
      ls_model_type: "chat",
      ls_provider: "openai",
    });
  }
  const updateCalls = callSpy.mock.calls.filter(
    (call) => (call[1] as any).method === "PATCH"
  );
  for (const call of updateCalls) {
    const body = parseRequestBody((call[1] as any).body);
    expect(body.outputs.usage_metadata).toBeDefined();
    expect(body.outputs.usage_metadata.input_tokens).toBeGreaterThan(0);
    expect(body.outputs.usage_metadata.output_tokens).toBeGreaterThan(0);
    expect(body.outputs.usage_metadata.total_tokens).toBeGreaterThan(0);
  }

  callSpy.mockClear();
});

test("responses.create streaming", async () => {
  const { client, callSpy } = mockClient();

  const openai = wrapOpenAI(new OpenAI(), {
    client,
    tracingEnabled: true,
  });

  const stream = await openai.responses.create({
    model: "gpt-4.1-nano",
    input: [
      {
        role: "user",
        content: [{ type: "input_text", text: "Say hello" }],
      },
    ],
    stream: true,
  });

  const chunks: unknown[] = [];
  for await (const chunk of stream) {
    chunks.push(chunk);
  }

  expect(chunks.length).toBeGreaterThan(0);
  expect(callSpy.mock.calls.length).toBeGreaterThanOrEqual(1);

  // Verify token events were logged
  const patchCalls = callSpy.mock.calls.filter(
    (call) => (call[1] as any).method === "PATCH"
  );
  const lastPatchCall = patchCalls[patchCalls.length - 1];
  const body = parseRequestBody((lastPatchCall[1] as any).body);

  expect(body.events).toBeDefined();
  const tokenEvents = body.events.filter(
    (event: any) => event.name === "new_token"
  );
  expect(tokenEvents.length).toBeGreaterThan(0);

  for (const call of callSpy.mock.calls) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    expect(["POST", "PATCH"]).toContain((call[1] as any)["method"]);
    const body = parseRequestBody((call[1] as any).body);
    expect(body.extra.metadata).toMatchObject({
      ls_model_name: "gpt-4.1-nano",
      ls_model_type: "chat",
      ls_provider: "openai",
    });
  }
  for (const call of patchCalls) {
    const body = parseRequestBody((call[1] as any).body);
    expect(body.outputs.usage_metadata).toBeDefined();
    expect(body.outputs.usage_metadata.input_tokens).toBeGreaterThan(0);
    expect(body.outputs.usage_metadata.output_tokens).toBeGreaterThan(0);
    expect(body.outputs.usage_metadata.total_tokens).toBeGreaterThan(0);
  }
  callSpy.mockClear();
});

test("responses.parse", async () => {
  const { client, callSpy } = mockClient();
  const openai = wrapOpenAI(new OpenAI(), {
    client,
    tracingEnabled: true,
  });

  const response = await openai.responses.parse({
    model: "gpt-4.1-nano",
    input: [
      {
        role: "user",
        content: [{ type: "input_text", text: "Say hello" }],
      },
    ],
    text: {
      format: zodTextFormat(
        z.object({
          response: z.string(),
        }),
        "response"
      ),
    },
  });
  expect(response).toBeDefined();
  expect(response.output_parsed).toBeDefined();
  expect(typeof response.output_parsed?.response).toBe("string");
  expect(callSpy.mock.calls.length).toBeGreaterThan(0);
  for (const call of callSpy.mock.calls) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    expect(["POST", "PATCH"]).toContain((call[1] as any)["method"]);
    const body = parseRequestBody((call[1] as any).body);
    expect(body.extra.metadata).toMatchObject({
      ls_model_name: "gpt-4.1-nano",
      ls_model_type: "chat",
      ls_provider: "openai",
    });
  }
  callSpy.mockClear();
});

test("responses.parse streaming", async () => {
  const { client, callSpy } = mockClient();
  const openai = wrapOpenAI(new OpenAI(), {
    client,
    tracingEnabled: true,
  });

  const stream = openai.responses.stream({
    model: "gpt-4.1-nano",
    input: [
      {
        role: "user",
        content: [{ type: "input_text", text: "Say hello" }],
      },
    ],
    text: {
      format: zodTextFormat(
        z.object({
          response: z.string(),
        }),
        "response"
      ),
    },
  });
  const chunks: unknown[] = [];
  for await (const chunk of stream) {
    chunks.push(chunk);
  }
  expect(chunks.length).toBeGreaterThan(0);
  expect(callSpy.mock.calls.length).toBeGreaterThan(0);
  for (const call of callSpy.mock.calls) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    expect(["POST", "PATCH"]).toContain((call[1] as any)["method"]);
    const body = parseRequestBody((call[1] as any).body);
    expect(body.extra.metadata).toMatchObject({
      ls_model_name: "gpt-4.1-nano",
      ls_model_type: "chat",
      ls_provider: "openai",
    });
  }
  callSpy.mockClear();
});

test("responses other methods (untraced)", async () => {
  const { client, callSpy } = mockClient();

  const openai = wrapOpenAI(new OpenAI(), {
    client,
  });

  // Test that other responses methods exist and are preserved
  expect(openai.responses.inputItems).toBeDefined();
  expect(typeof openai.responses.create).toBe("function");
  expect(typeof openai.responses.retrieve).toBe("function");
  expect(typeof openai.responses.delete).toBe("function");
  expect(typeof openai.responses.parse).toBe("function");
  expect(typeof openai.responses.stream).toBe("function");
  expect(typeof openai.responses.cancel).toBe("function");

  // Verify that non-create methods don't generate tracing calls
  const initialCallCount = callSpy.mock.calls.length;

  // These should exist and be accessible without generating tracing calls
  expect(openai.responses.inputItems).toBeDefined();
  expect(callSpy.mock.calls.length).toBe(initialCallCount);

  callSpy.mockClear();
});

test("chat.completions other methods (untraced)", async () => {
  const { client, callSpy } = mockClient();

  const openai = wrapOpenAI(new OpenAI(), {
    client,
    tracingEnabled: true,
  });

  // Test that all chat.completions methods exist and are preserved
  expect(typeof openai.chat.completions.create).toBe("function");
  expect(typeof openai.chat.completions.parse).toBe("function");
  expect(typeof openai.chat.completions.retrieve).toBe("function");
  expect(typeof openai.chat.completions.update).toBe("function");
  expect(typeof openai.chat.completions.list).toBe("function");
  expect(typeof openai.chat.completions.delete).toBe("function");
  expect(typeof openai.chat.completions.runTools).toBe("function");
  expect(typeof openai.chat.completions.stream).toBe("function");

  // Verify that non-traced methods don't generate tracing calls
  const initialCallCount = callSpy.mock.calls.length;

  // These methods should exist and be accessible without generating tracing calls
  expect(typeof openai.chat.completions.retrieve).toBe("function");
  expect(typeof openai.chat.completions.list).toBe("function");
  expect(callSpy.mock.calls.length).toBe(initialCallCount);

  callSpy.mockClear();
});

test("beta methods preserved", async () => {
  const { client, callSpy } = mockClient();

  const openai = wrapOpenAI(new OpenAI(), {
    client,
    tracingEnabled: true,
  });

  // Test that beta namespace is preserved
  expect(openai.beta).toBeDefined();

  // Test that all beta methods are accessible (they may not all exist depending on OpenAI SDK version)
  if (openai.beta.assistants) {
    expect(openai.beta.assistants).toBeDefined();
  }

  if (openai.beta.threads) {
    expect(openai.beta.threads).toBeDefined();
  }

  // Verify that beta methods don't generate unexpected tracing calls
  const initialCallCount = callSpy.mock.calls.length;

  // Accessing beta should not generate tracing calls
  expect(openai.beta).toBeDefined();
  expect(callSpy.mock.calls.length).toBe(initialCallCount);

  callSpy.mockClear();
});

const usageMetadataTestCases = [
  {
    description: "stream",
    params: {
      model: "gpt-4o-mini",
      messages: [{ role: "user", content: "howdy" }],
      stream: true,
      stream_options: { include_usage: true },
    },
    expectUsageMetadata: true,
  },
  {
    description: "stream no usage",
    params: {
      model: "gpt-4o-mini",
      messages: [{ role: "user", content: "howdy" }],
      stream: true,
    },
    expectUsageMetadata: false,
  },
  {
    description: "default",
    params: {
      model: "gpt-4o-mini",
      messages: [{ role: "user", content: "howdy" }],
    },
    expectUsageMetadata: true,
  },
  {
    description: "reasoning",
    params: {
      model: "o1",
      messages: [
        {
          role: "user",
          content:
            "Write a bash script that takes a matrix represented as a string with format '[1,2],[3,4],[5,6]' and prints the transpose in the same format.",
        },
      ],
    },
    expectUsageMetadata: true,
    checkReasoningTokens: true,
  },
  // just test flex as priority can randomly downgrade
  {
    description: "flex service tier",
    params: {
      model: "gpt-5-nano",
      messages: [{ role: "user", content: "howdy" }],
      service_tier: "flex",
    },
    expectUsageMetadata: true,
    checkServiceTier: "flex",
  },
];

test("Azure OpenAI provider detection", async () => {
  if (!process.env.AZURE_OPENAI_API_KEY) {
    return;
  }
  const { client, callSpy } = mockClient();

  const azureClient = new AzureOpenAI({
    apiKey: process.env.AZURE_OPENAI_API_KEY,
    apiVersion: process.env.AZURE_OPENAI_API_VERSION,
    endpoint: process.env.AZURE_OPENAI_ENDPOINT,
  });

  const patchedClient = wrapOpenAI(azureClient, {
    client,
    tracingEnabled: true,
  });

  await patchedClient.chat.completions.create({
    messages: [{ role: "user", content: "Say 'hello'" }],
    temperature: 0,
    seed: 42,
    model: "gpt-4o-mini",
  });

  expect(callSpy.mock.calls.length).toBeGreaterThanOrEqual(1);

  // Check that the provider is set to "azure_openai" in the request
  for (const call of callSpy.mock.calls) {
    const body = parseRequestBody((call[1] as any).body);
    if (body.extra && body.extra.metadata) {
      expect(body.extra.metadata.ls_provider).toBe("azure");
    }
  }

  callSpy.mockClear();
});

describe("Usage Metadata Tests", () => {
  usageMetadataTestCases.forEach(
    ({
      description,
      params,
      expectUsageMetadata,
      checkReasoningTokens,
      checkServiceTier,
    }) => {
      it(`should handle ${description}`, async () => {
        const { client, callSpy } = mockClient();
        const openai = wrapOpenAI(new OpenAI(), {
          tracingEnabled: true,
          client,
        });

        const requestParams = { ...params };

        let oaiUsage: OpenAI.CompletionUsage | undefined;
        if (requestParams.stream) {
          const stream = await openai.chat.completions.create(
            requestParams as OpenAI.ChatCompletionCreateParamsStreaming
          );
          for await (const chunk of stream) {
            if (expectUsageMetadata && chunk.usage) {
              oaiUsage = chunk.usage;
            }
          }
        } else {
          const res = await openai.chat.completions.create(
            requestParams as OpenAI.ChatCompletionCreateParams
          );
          oaiUsage = (res as OpenAI.ChatCompletion).usage;
        }

        let usageMetadata: UsageMetadata | undefined;
        const requestBodies: any = {};
        for (const call of callSpy.mock.calls) {
          const request = call[1] as any;
          const requestBody = parseRequestBody(request.body);
          if (request.method === "POST") {
            requestBodies["post"] = [requestBody];
          }
          if (request.method === "PATCH") {
            requestBodies["patch"] = [requestBody];
          }
          if (requestBody.outputs && requestBody.outputs.usage_metadata) {
            usageMetadata = requestBody.outputs.usage_metadata;
            break;
          }
        }

        if (expectUsageMetadata) {
          expect(usageMetadata).not.toBeUndefined();
          expect(usageMetadata).not.toBeNull();
          expect(oaiUsage).not.toBeUndefined();
          expect(oaiUsage).not.toBeNull();
          expect(usageMetadata!.input_tokens).toEqual(oaiUsage!.prompt_tokens);
          expect(usageMetadata!.output_tokens).toEqual(
            oaiUsage!.completion_tokens
          );
          expect(usageMetadata!.total_tokens).toEqual(oaiUsage!.total_tokens);

          if (checkReasoningTokens) {
            expect(usageMetadata!.output_token_details).not.toBeUndefined();
            expect(
              usageMetadata!.output_token_details!.reasoning
            ).not.toBeUndefined();
            expect(usageMetadata!.output_token_details!.reasoning).toEqual(
              oaiUsage!.completion_tokens_details?.reasoning_tokens
            );
          }

          if (checkServiceTier) {
            expect(usageMetadata!.input_token_details).not.toBeUndefined();
            expect(usageMetadata!.output_token_details).not.toBeUndefined();
            expect(
              usageMetadata?.input_token_details?.[checkServiceTier]
            ).not.toBeUndefined();
            expect(
              usageMetadata?.output_token_details?.[checkServiceTier]
            ).not.toBeUndefined();
            expect(
              usageMetadata?.input_token_details?.[checkServiceTier]
            ).toBeGreaterThan(0);
            expect(
              usageMetadata?.output_token_details?.[checkServiceTier]
            ).toBeGreaterThan(0);
          }
        } else {
          expect(usageMetadata).toBeUndefined();
          expect(oaiUsage).toBeUndefined();
        }

        if (process.env.WRITE_TOKEN_COUNTING_TEST_DATA === "1") {
          fs.writeFileSync(
            `${__dirname}/test_data/langsmith_js_wrap_openai_${description.replace(
              " ",
              "_"
            )}.json`,
            JSON.stringify(requestBodies, null, 2)
          );
        }

        callSpy.mockClear();
      });
    }
  );
});

test("chat.completions.stream with finalChatCompletion", async () => {
  const { client, callSpy } = mockClient();
  const openai = wrapOpenAI(new OpenAI(), {
    client,
    tracingEnabled: true,
  });

  const stream = openai.chat.completions.stream({
    model: "gpt-4o-mini",
    messages: [{ role: "user", content: "Say 'hello'" }],
  });

  const completion = await stream.finalChatCompletion();

  expect(completion.choices[0].message.role).toBe("assistant");
  expect(callSpy.mock.calls.length).toBeGreaterThanOrEqual(1);

  // Verify tracing calls were made
  const patchCalls = callSpy.mock.calls.filter(
    (call) => (call[1] as any).method === "PATCH"
  );
  expect(patchCalls.length).toBeGreaterThan(0);

  callSpy.mockClear();
});

test("chat.completions.stream with finalMessage", async () => {
  const { client, callSpy } = mockClient();
  const openai = wrapOpenAI(new OpenAI(), {
    client,
    tracingEnabled: true,
  });

  const stream = openai.chat.completions.stream({
    model: "gpt-4o-mini",
    messages: [{ role: "user", content: "Say 'hello'" }],
  });

  const message = await stream.finalMessage();

  expect(message.role).toBe("assistant");
  expect(callSpy.mock.calls.length).toBeGreaterThanOrEqual(1);

  // Verify tracing calls were made
  const patchCalls = callSpy.mock.calls.filter(
    (call) => (call[1] as any).method === "PATCH"
  );
  expect(patchCalls.length).toBeGreaterThan(0);

  callSpy.mockClear();
});

test("responses.stream with finalResponse", async () => {
  const { client, callSpy } = mockClient();
  const openai = wrapOpenAI(new OpenAI(), {
    client,
    tracingEnabled: true,
  });

  const stream = openai.responses.stream({
    model: "gpt-4.1-nano",
    input: [
      {
        role: "user",
        content: [{ type: "input_text", text: "Say hello" }],
      },
    ],
  });

  const response = await stream.finalResponse();

  expect(response).toBeDefined();
  expect(callSpy.mock.calls.length).toBeGreaterThanOrEqual(1);

  // Verify tracing calls were made
  const patchCalls = callSpy.mock.calls.filter(
    (call) => (call[1] as any).method === "PATCH"
  );
  expect(patchCalls.length).toBeGreaterThan(0);

  callSpy.mockClear();
});
