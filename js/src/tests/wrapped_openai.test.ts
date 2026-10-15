import { jest } from "@jest/globals";
import { OpenAI } from "openai";
import { wrapOpenAI } from "../wrappers/openai.js";
import { mockClient } from "./utils/mock_client.js";
import { getAssumedTreeFromCalls } from "./utils/tree.js";

test.each([200, 404])(
  "responses.create is traced but retrieval with status %i is not",
  async (status) => {
    const response = {
      id: "resp_test",
      object: "response",
      status: "completed",
      model: "gpt-5-nano",
      output: [
        {
          id: "msg_test",
          type: "message",
          role: "assistant",
          status: "completed",
          content: [{ type: "output_text", text: "4", annotations: [] }],
        },
      ],
      usage: { input_tokens: 10, output_tokens: 2, total_tokens: 12 },
    };
    const error = {
      type: "invalid_request_error",
      message: "Response with id 'resp_test' not found.",
    };
    const openaiFetch = jest
      .fn<typeof fetch>()
      .mockResolvedValueOnce(Response.json(response))
      .mockResolvedValueOnce(
        Response.json(status === 200 ? response : { error }, { status }),
      );
    const { client, callSpy } = mockClient();
    const openai = wrapOpenAI(
      new OpenAI({
        apiKey: "MOCK",
        baseURL: "https://openai.example.test/v1",
        fetch: openaiFetch,
        maxRetries: 0,
      }),
      { client, tracingEnabled: true },
    );
    const params = {
      model: "gpt-5-nano",
      input: "What is 2+2?",
      store: true,
      metadata: { request_key: "request_value" },
    };

    const created = await openai.responses.create(params);
    expect(created).toMatchObject(response);
    const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
    expect(tree.nodes).toEqual(["ChatOpenAI:0"]);
    expect(tree.data["ChatOpenAI:0"]).toMatchObject({
      run_type: "llm",
      inputs: params,
      extra: {
        metadata: { request_key: "request_value", ls_model_name: params.model },
      },
      outputs: {
        id: response.id,
        usage_metadata: response.usage,
      },
    });
    const createCallCount = callSpy.mock.calls.length;

    const retrieved = openai.responses.retrieve(created.id);
    if (status === 200) {
      await expect(retrieved).resolves.toMatchObject(response);
    } else {
      await expect(retrieved).rejects.toMatchObject({ status, error });
    }
    await client.awaitPendingTraceBatches();
    expect(callSpy.mock.calls.length).toBe(createCallCount);
    expect(openaiFetch).toHaveBeenCalledTimes(2);
    expect(openaiFetch).toHaveBeenNthCalledWith(
      1,
      "https://openai.example.test/v1/responses",
      expect.objectContaining({ method: "POST", body: JSON.stringify(params) }),
    );
    expect(openaiFetch).toHaveBeenNthCalledWith(
      2,
      `https://openai.example.test/v1/responses/${created.id}`,
      expect.objectContaining({ method: "GET" }),
    );
  },
);

// OpenAI shut down its legacy `/v1/completions` models on 2026-09-28; this
// covers wrapping `completions.create` for OpenAI-compatible providers.
function completionsFetch() {
  const completion = {
    id: "cmpl-test",
    object: "text_completion",
    created: 1700000000,
    model: "gpt-3.5-turbo-instruct",
    choices: [
      {
        text: " Hi I'm ChatGPT",
        index: 0,
        logprobs: null,
        finish_reason: "stop",
      },
    ],
    usage: { prompt_tokens: 10, completion_tokens: 5, total_tokens: 15 },
  };
  const chunks = [" Hi", " I'm", " ChatGPT"].map((text, i) => ({
    ...completion,
    choices: [
      {
        text,
        index: 0,
        logprobs: null,
        finish_reason: i === 2 ? "stop" : null,
      },
    ],
    usage: undefined,
  }));
  const sse =
    chunks.map((c) => `data: ${JSON.stringify(c)}\n\n`).join("") +
    "data: [DONE]\n\n";
  return jest.fn<typeof fetch>().mockImplementation(async (_url, init) => {
    const body = JSON.parse(init?.body as string);
    return body.stream
      ? new Response(sse, {
          headers: { "content-type": "text/event-stream" },
        })
      : Response.json(completion);
  });
}

test("completions", async () => {
  const { client, callSpy } = mockClient();
  const openaiFetch = completionsFetch();
  const openaiParams = {
    apiKey: "MOCK",
    baseURL: "https://openai.example.test/v1",
    fetch: openaiFetch,
    maxRetries: 0,
  };
  const originalClient = new OpenAI(openaiParams);
  const patchedClient = wrapOpenAI(new OpenAI(openaiParams), {
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
  expect(patched.choices[0].text).toBe(" Hi I'm ChatGPT");

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
  expect(originalChoices).toHaveLength(3);

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
    },
  );

  const patchedChoices2: unknown[] = [];
  for await (const chunk of patchedStream2) {
    patchedChoices2.push(chunk.choices);
    // @ts-expect-error Should type check streamed output
    const _test = chunk.invalidPrompt;
  }

  expect(patchedChoices2).toEqual(originalChoices);
  expect(openaiFetch).toHaveBeenCalledTimes(5);
  for (const [url, init] of openaiFetch.mock.calls) {
    expect(url).toBe("https://openai.example.test/v1/completions");
    expect(init).toMatchObject({ method: "POST" });
  }

  await client.awaitPendingTraceBatches();
  const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
  expect(tree.nodes).toEqual(["OpenAI:0", "OpenAI:1", "OpenAI:2"]);
  expect(tree.data["OpenAI:0"]).toMatchObject({
    run_type: "llm",
    inputs: { prompt, model: "gpt-3.5-turbo-instruct" },
    outputs: { choices: original.choices },
  });
  expect(tree.data["OpenAI:2"]).toMatchObject({
    extra: { metadata: { thing1: "thing2" } },
  });
});
