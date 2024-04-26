import { jest } from "@jest/globals";
import { OpenAI } from "openai";
import { wrapOpenAI } from "../wrappers/index.js";
import { Client } from "../client.js";

test.concurrent("chat.completions", async () => {
  const client = new Client();
  const callSpy = jest
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .spyOn((client as any).caller, "call")
    .mockResolvedValue({ ok: true, text: () => "" });

  const originalClient = new OpenAI();
  const patchedClient = wrapOpenAI(new OpenAI(), { client });

  // invoke
  const original = await originalClient.chat.completions.create({
    messages: [{ role: "user", content: `Say 'foo'` }],
    temperature: 0,
    seed: 42,
    model: "gpt-3.5-turbo",
  });

  const patched = await patchedClient.chat.completions.create({
    messages: [{ role: "user", content: `Say 'foo'` }],
    temperature: 0,
    seed: 42,
    model: "gpt-3.5-turbo",
  });

  expect(patched.choices).toEqual(original.choices);

  // stream
  const originalStream = await originalClient.chat.completions.create({
    messages: [{ role: "user", content: `Say 'foo'` }],
    temperature: 0,
    seed: 42,
    model: "gpt-3.5-turbo",
    stream: true,
  });

  const originalChoices = [];
  for await (const chunk of originalStream) {
    originalChoices.push(chunk.choices);
  }

  const patchedStream = await patchedClient.chat.completions.create({
    messages: [{ role: "user", content: `Say 'foo'` }],
    temperature: 0,
    seed: 42,
    model: "gpt-3.5-turbo",
    stream: true,
  });

  const patchedChoices = [];
  for await (const chunk of patchedStream) {
    patchedChoices.push(chunk.choices);
    // @ts-expect-error Should type check streamed output
    const _test = chunk.invalidPrompt;
  }

  expect(patchedChoices).toEqual(originalChoices);
  for (const call of callSpy.mock.calls) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    expect((call[2] as any)["method"]).toBe("POST");
  }

  const patchedStream2 = await patchedClient.chat.completions.create(
    {
      messages: [{ role: "user", content: `Say 'foo'` }],
      temperature: 0,
      seed: 42,
      model: "gpt-3.5-turbo",
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

  const patchedChoices2 = [];
  for await (const chunk of patchedStream2) {
    patchedChoices2.push(chunk.choices);
    // @ts-expect-error Should type check streamed output
    const _test = chunk.invalidPrompt;
  }

  expect(patchedChoices2).toEqual(originalChoices);
  for (const call of callSpy.mock.calls) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    expect((call[2] as any)["method"]).toBe("POST");
  }
});

test.concurrent("chat completions with tool calling", async () => {
  const client = new Client();
  const callSpy = jest
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .spyOn((client as any).caller, "call")
    .mockResolvedValue({ ok: true, text: () => "" });

  const originalClient = new OpenAI();
  const patchedClient = wrapOpenAI(new OpenAI(), { client });
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
    model: "gpt-3.5-turbo",
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
    model: "gpt-3.5-turbo",
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
    model: "gpt-3.5-turbo",
    tools: toolDefinition,
    tool_choice: {
      type: "function",
      function: { name: "get_current_weather" },
    },
    stream: true,
  });

  const originalChoices = [];
  for await (const chunk of originalStream) {
    originalChoices.push(chunk.choices);
  }

  const patchedStream = await patchedClient.chat.completions.create({
    messages: [{ role: "user", content: `What is the current weather in SF?` }],
    temperature: 0,
    seed: 42,
    model: "gpt-3.5-turbo",
    tools: toolDefinition,
    tool_choice: {
      type: "function",
      function: { name: "get_current_weather" },
    },
    stream: true,
  });

  const patchedChoices = [];
  for await (const chunk of patchedStream) {
    patchedChoices.push(chunk.choices);
    // @ts-expect-error Should type check streamed output
    const _test = chunk.invalidPrompt;
  }

  expect(removeToolCallId(patchedChoices)).toEqual(
    removeToolCallId(originalChoices)
  );
  for (const call of callSpy.mock.calls) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    expect((call[2] as any)["method"]).toBe("POST");
  }

  const patchedStream2 = await patchedClient.chat.completions.create(
    {
      messages: [
        { role: "user", content: `What is the current weather in SF?` },
      ],
      temperature: 0,
      seed: 42,
      model: "gpt-3.5-turbo",
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

  const patchedChoices2 = [];
  for await (const chunk of patchedStream2) {
    patchedChoices2.push(chunk.choices);
    // @ts-expect-error Should type check streamed output
    const _test = chunk.invalidPrompt;
  }

  expect(removeToolCallId(patchedChoices2)).toEqual(
    removeToolCallId(originalChoices)
  );
  for (const call of callSpy.mock.calls) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    expect((call[2] as any)["method"]).toBe("POST");
  }
});

test.concurrent("completions", async () => {
  const client = new Client();
  const callSpy = jest
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .spyOn((client as any).caller, "call")
    .mockResolvedValue({ ok: true, text: () => "" });

  const originalClient = new OpenAI();
  const patchedClient = wrapOpenAI(new OpenAI(), { client });

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

  const originalChoices = [];
  for await (const chunk of originalStream) {
    originalChoices.push(chunk.choices);
    // @ts-expect-error Should type check streamed output
    const _test = chunk.invalidPrompt;
  }

  const patchedStream = await patchedClient.completions.create({
    prompt,
    temperature: 0,
    seed: 42,
    model: "gpt-3.5-turbo-instruct",
    stream: true,
  });

  const patchedChoices = [];
  for await (const chunk of patchedStream) {
    patchedChoices.push(chunk.choices);
    // @ts-expect-error Should type check streamed output
    const _test = chunk.invalidPrompt;
  }

  expect(patchedChoices).toEqual(originalChoices);
  for (const call of callSpy.mock.calls) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    expect((call[2] as any)["method"]).toBe("POST");
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

  const patchedChoices2 = [];
  for await (const chunk of patchedStream2) {
    patchedChoices2.push(chunk.choices);
    // @ts-expect-error Should type check streamed output
    const _test = chunk.invalidPrompt;
  }

  expect(patchedChoices2).toEqual(originalChoices);
  for (const call of callSpy.mock.calls) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    expect((call[2] as any)["method"]).toBe("POST");
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
    model: "gpt-3.5-turbo",
    stream: true,
  });

  const patchedChoices = [];
  for await (const chunk of patchedStream) {
    patchedChoices.push(chunk.choices);
    // @ts-expect-error Should type check streamed output
    const _test = chunk.invalidPrompt;
  }

  console.log(patchedChoices);
});
