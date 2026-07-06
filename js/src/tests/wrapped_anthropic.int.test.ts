/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable no-process-env */
import Anthropic, { toFile } from "@anthropic-ai/sdk";
import { wrapAnthropic } from "../wrappers/anthropic.js";
import { mockClient } from "./utils/mock_client.js";
import { getAssumedTreeFromCalls } from "./utils/tree.js";
import { UsageMetadata } from "../schemas.js";
import { generateLongContext } from "./utils.js";

function parseRequestBody(body: any) {
  // eslint-disable-next-line no-instanceof/no-instanceof
  return body instanceof Uint8Array
    ? JSON.parse(new TextDecoder().decode(body))
    : JSON.parse(body);
}

describe.skip("Requires Anthropic API key", () => {
  test("wrapAnthropic should return type compatible with Anthropic", async () => {
    let originalClient = new Anthropic();
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    originalClient = wrapAnthropic(originalClient);

    expect(true).toBe(true);
  });

  test("messages.create non-streaming", async () => {
    const { client, callSpy } = mockClient();

    const originalClient = new Anthropic();
    const patchedClient = wrapAnthropic(new Anthropic(), {
      client,
      tracingEnabled: true,
    });

    // invoke
    const original = await originalClient.messages.create({
      model: "claude-haiku-4-5",
      max_tokens: 100,
      messages: [{ role: "user", content: "Say 'foo'" }],
    });

    const patched = await patchedClient.messages.create({
      model: "claude-haiku-4-5",
      max_tokens: 100,
      messages: [{ role: "user", content: "Say 'foo'" }],
    });

    // Both should have content
    expect(patched.content).toBeDefined();
    expect(patched.role).toBe("assistant");
    expect(original.role).toBe("assistant");

    // Verify tracing calls were made
    expect(callSpy.mock.calls.length).toBeGreaterThanOrEqual(1);

    for (const call of callSpy.mock.calls) {
      expect(["POST", "PATCH"]).toContain((call[1] as any)["method"]);
    }

    // Verify metadata was set correctly
    const postCalls = callSpy.mock.calls.filter(
      (call: any) => (call[1] as any).method === "POST",
    );
    expect(postCalls.length).toBeGreaterThanOrEqual(1);

    const postBody = parseRequestBody((postCalls[0][1] as any).body);
    expect(postBody.extra.metadata).toMatchObject({
      ls_model_name: "claude-haiku-4-5",
      ls_model_type: "chat",
      ls_provider: "anthropic",
    });

    // Verify usage_metadata was captured
    const patchCalls = callSpy.mock.calls.filter(
      (call: any) => (call[1] as any).method === "PATCH",
    );
    expect(patchCalls.length).toBeGreaterThanOrEqual(1);

    const patchBody = parseRequestBody((patchCalls[0][1] as any).body);
    expect(patchBody.outputs).toBeDefined();
    expect(patchBody.outputs.usage_metadata).toBeDefined();
    expect(patchBody.outputs.usage_metadata.input_tokens).toBeGreaterThan(0);
    expect(patchBody.outputs.usage_metadata.output_tokens).toBeGreaterThan(0);
    expect(patchBody.outputs.usage_metadata.total_tokens).toBeGreaterThan(0);

    callSpy.mockClear();
  });

  test("messages.create streaming", async () => {
    const { client, callSpy } = mockClient();

    const originalClient = new Anthropic();
    const patchedClient = wrapAnthropic(new Anthropic(), {
      client,
      tracingEnabled: true,
    });

    // Stream with original client
    const originalStream = await originalClient.messages.create({
      model: "claude-haiku-4-5",
      max_tokens: 100,
      messages: [{ role: "user", content: "Say 'foo'" }],
      stream: true,
    });

    const originalEvents: any[] = [];
    for await (const event of originalStream) {
      originalEvents.push(event);
    }

    // Stream with patched client
    const patchedStream = await patchedClient.messages.create({
      model: "claude-haiku-4-5",
      max_tokens: 100,
      messages: [{ role: "user", content: "Say 'foo'" }],
      stream: true,
    });

    const patchedEvents: any[] = [];
    for await (const event of patchedStream) {
      patchedEvents.push(event);
    }

    // Both should have events
    expect(patchedEvents.length).toBeGreaterThan(0);
    expect(originalEvents.length).toBeGreaterThan(0);

    // Verify tracing calls were made
    expect(callSpy.mock.calls.length).toBeGreaterThanOrEqual(1);

    // Verify token events were logged
    const patchCalls = callSpy.mock.calls.filter(
      (call: any) => (call[1] as any).method === "PATCH",
    );
    expect(patchCalls.length).toBeGreaterThan(0);
    const lastPatchCall = patchCalls[patchCalls.length - 1];
    const body = parseRequestBody((lastPatchCall[1] as any).body);

    expect(body.events).toBeDefined();
    const tokenEvents = body.events.filter(
      (event: any) => event.name === "new_token",
    );
    expect(tokenEvents.length).toBeGreaterThan(0);
    tokenEvents.forEach((event: any) => {
      expect(event.name).toBe("new_token");
      expect(event.kwargs).toBeUndefined();
      expect(event.time).toBeDefined();
    });

    for (const call of callSpy.mock.calls) {
      expect(["POST", "PATCH"]).toContain((call[1] as any)["method"]);
    }

    // Verify metadata
    const postCalls = callSpy.mock.calls.filter(
      (call: any) => (call[1] as any).method === "POST",
    );
    const postBody = parseRequestBody((postCalls[0][1] as any).body);
    expect(postBody.extra.metadata).toMatchObject({
      ls_model_name: "claude-haiku-4-5",
      ls_model_type: "chat",
      ls_provider: "anthropic",
    });

    // Verify aggregated output has usage_metadata
    expect(body.outputs).toBeDefined();
    expect(body.outputs.usage_metadata).toBeDefined();
    expect(body.outputs.usage_metadata.input_tokens).toBeGreaterThan(0);
    expect(body.outputs.usage_metadata.output_tokens).toBeGreaterThan(0);

    callSpy.mockClear();
  });

  test("messages.create streaming break early", async () => {
    const { client, callSpy } = mockClient();

    const patchedClient = wrapAnthropic(new Anthropic(), {
      client,
      tracingEnabled: true,
    });

    const patchedStreamToBreak = await patchedClient.messages.create({
      model: "claude-haiku-4-5",
      max_tokens: 1024,
      messages: [{ role: "user", content: "Count from 1 to 100 slowly" }],
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
  });

  test("messages.create streaming with langsmithExtra", async () => {
    const { client, callSpy } = mockClient();

    const patchedClient = wrapAnthropic(new Anthropic(), {
      client,
      tracingEnabled: true,
    });

    const patchedStreamWithMetadata = await patchedClient.messages.create(
      {
        model: "claude-haiku-4-5",
        max_tokens: 100,
        messages: [{ role: "user", content: "Say 'foo'" }],
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

    const patchedChoices: unknown[] = [];
    for await (const chunk of patchedStreamWithMetadata) {
      patchedChoices.push(chunk);
    }

    expect(patchedChoices.length).toBeGreaterThan(0);
    expect(callSpy.mock.calls.length).toBeGreaterThanOrEqual(1);
    for (const call of callSpy.mock.calls) {
      expect(["POST", "PATCH"]).toContain((call[1] as any)["method"]);
      const body = parseRequestBody((call[1] as any).body);
      expect(body.extra.metadata).toMatchObject({
        thing1: "thing2",
        ls_model_name: "claude-haiku-4-5",
        ls_model_type: "chat",
        ls_provider: "anthropic",
      });
    }
    callSpy.mockClear();
  });

  test("messages.stream", async () => {
    const { client, callSpy } = mockClient();

    const originalClient = new Anthropic();
    const patchedClient = wrapAnthropic(new Anthropic(), {
      client,
      tracingEnabled: true,
    });

    // Use messages.stream with original client
    const originalStream = originalClient.messages.stream({
      model: "claude-haiku-4-5",
      max_tokens: 100,
      messages: [{ role: "user", content: "Say 'bar'" }],
    });

    const originalEvents: any[] = [];
    for await (const event of originalStream) {
      originalEvents.push(event);
    }

    // Use messages.stream with patched client
    const patchedStream = patchedClient.messages.stream({
      model: "claude-haiku-4-5",
      max_tokens: 100,
      messages: [{ role: "user", content: "Say 'bar'" }],
    });

    const patchedEvents: any[] = [];
    for await (const event of patchedStream) {
      patchedEvents.push(event);
    }

    // Both should have events and final messages
    expect(patchedEvents.length).toBeGreaterThan(0);
    expect(originalEvents.length).toBeGreaterThan(0);

    // Verify tracing calls were made
    expect(callSpy.mock.calls.length).toBeGreaterThanOrEqual(1);

    // Verify metadata
    const postCalls = callSpy.mock.calls.filter(
      (call: any) => (call[1] as any).method === "POST",
    );
    expect(postCalls.length).toBeGreaterThanOrEqual(1);

    const postBody = parseRequestBody((postCalls[0][1] as any).body);
    expect(postBody.extra.metadata).toMatchObject({
      ls_model_name: "claude-haiku-4-5",
      ls_model_type: "chat",
      ls_provider: "anthropic",
    });

    // Verify token events were logged
    const patchCalls = callSpy.mock.calls.filter(
      (call: any) => (call[1] as any).method === "PATCH",
    );
    expect(patchCalls.length).toBeGreaterThan(0);
    const lastPatchCall = patchCalls[patchCalls.length - 1];
    const body = parseRequestBody((lastPatchCall[1] as any).body);

    expect(body.events).toBeDefined();
    const tokenEvents = body.events.filter(
      (event: any) => event.name === "new_token",
    );
    expect(tokenEvents.length).toBeGreaterThan(0);

    callSpy.mockClear();
  });

  test("messages.stream with finalMessage", async () => {
    const { client, callSpy } = mockClient();

    const originalClient = new Anthropic();
    const patchedClient = wrapAnthropic(new Anthropic(), {
      client,
      tracingEnabled: true,
    });

    // Use messages.stream with original client
    const originalStream = originalClient.messages.stream({
      model: "claude-haiku-4-5",
      max_tokens: 100,
      messages: [{ role: "user", content: "Say 'bar'" }],
    });

    const originalFinalMessage = await originalStream.finalMessage();

    // Use messages.stream with patched client
    const patchedStream = patchedClient.messages.stream({
      model: "claude-haiku-4-5",
      max_tokens: 100,
      messages: [{ role: "user", content: "Say 'bar'" }],
    });

    const patchedFinalMessage = await patchedStream.finalMessage();

    // Both should have events and final messages
    expect(patchedFinalMessage.role).toBe("assistant");
    expect(originalFinalMessage.role).toBe("assistant");

    // Verify tracing calls were made
    expect(callSpy.mock.calls.length).toBeGreaterThanOrEqual(1);

    // Verify metadata
    const postCalls = callSpy.mock.calls.filter(
      (call: any) => (call[1] as any).method === "POST",
    );
    expect(postCalls.length).toBeGreaterThanOrEqual(1);

    const postBody = parseRequestBody((postCalls[0][1] as any).body);
    expect(postBody.extra.metadata).toMatchObject({
      ls_model_name: "claude-haiku-4-5",
      ls_model_type: "chat",
      ls_provider: "anthropic",
    });

    // Verify token events were logged
    const patchCalls = callSpy.mock.calls.filter(
      (call: any) => (call[1] as any).method === "PATCH",
    );
    expect(patchCalls.length).toBeGreaterThan(0);
    const lastPatchCall = patchCalls[patchCalls.length - 1];
    const body = parseRequestBody((lastPatchCall[1] as any).body);

    expect(body.events).toBeDefined();
    const tokenEvents = body.events.filter(
      (event: any) => event.name === "new_token",
    );
    expect(tokenEvents.length).toBeGreaterThan(0);

    callSpy.mockClear();
  });

  test("messages.stream with langsmithExtra", async () => {
    const { client, callSpy } = mockClient();

    const patchedClient = wrapAnthropic(new Anthropic(), {
      client,
      tracingEnabled: true,
    });

    const patchedStream = patchedClient.messages.stream(
      {
        model: "claude-haiku-4-5",
        max_tokens: 100,
        messages: [{ role: "user", content: "Say 'baz'" }],
      },
      {
        langsmithExtra: {
          name: "custom_stream_name",
          metadata: {
            customKey: "customValue",
          },
        },
      },
    );

    const events: any[] = [];
    for await (const event of patchedStream) {
      events.push(event);
    }

    expect(events.length).toBeGreaterThan(0);
    expect(callSpy.mock.calls.length).toBeGreaterThanOrEqual(1);

    for (const call of callSpy.mock.calls) {
      const body = parseRequestBody((call[1] as any).body);
      expect(body.name).toBe("custom_stream_name");
      expect(body.extra.metadata).toMatchObject({
        customKey: "customValue",
        ls_provider: "anthropic",
      });
    }

    callSpy.mockClear();
  });

  test("messages.create with tool calling", async () => {
    const { client, callSpy } = mockClient();

    const originalClient = new Anthropic();
    const patchedClient = wrapAnthropic(new Anthropic(), {
      client,
      tracingEnabled: true,
    });

    const toolDefinition: Anthropic.Tool[] = [
      {
        name: "get_weather",
        description: "Get the current weather in a given location",
        input_schema: {
          type: "object",
          properties: {
            location: {
              type: "string",
              description: "The city, e.g. San Francisco",
            },
          },
          required: ["location"],
        },
      },
    ];

    // Non-streaming tool call
    const original = await originalClient.messages.create({
      model: "claude-haiku-4-5",
      max_tokens: 1024,
      messages: [{ role: "user", content: "What's the weather in SF?" }],
      tools: toolDefinition,
      tool_choice: { type: "tool", name: "get_weather" },
    });

    const patched = await patchedClient.messages.create({
      model: "claude-haiku-4-5",
      max_tokens: 1024,
      messages: [{ role: "user", content: "What's the weather in SF?" }],
      tools: toolDefinition,
      tool_choice: { type: "tool", name: "get_weather" },
    });

    // Both should have tool_use content blocks
    expect(patched.content).toBeDefined();
    expect(patched.content.some((block) => block.type === "tool_use")).toBe(
      true,
    );
    expect(original.content.some((block) => block.type === "tool_use")).toBe(
      true,
    );

    // Verify tracing was done
    expect(callSpy.mock.calls.length).toBeGreaterThanOrEqual(1);

    const patchCalls = callSpy.mock.calls.filter(
      (call: any) => (call[1] as any).method === "PATCH",
    );
    const patchBody = parseRequestBody((patchCalls[0][1] as any).body);
    expect(patchBody.outputs).toBeDefined();
    expect(patchBody.outputs.content).toBeDefined();

    callSpy.mockClear();
  });

  test("messages.create streaming with tool calling", async () => {
    const { client, callSpy } = mockClient();

    const patchedClient = wrapAnthropic(new Anthropic(), {
      client,
      tracingEnabled: true,
    });

    const toolDefinition: Anthropic.Tool[] = [
      {
        name: "get_weather",
        description: "Get the current weather in a given location",
        input_schema: {
          type: "object",
          properties: {
            location: {
              type: "string",
              description: "The city, e.g. San Francisco",
            },
          },
          required: ["location"],
        },
      },
    ];

    const patchedStream = await patchedClient.messages.create({
      model: "claude-haiku-4-5",
      max_tokens: 1024,
      messages: [{ role: "user", content: "What's the weather in SF?" }],
      tools: toolDefinition,
      tool_choice: { type: "tool", name: "get_weather" },
      stream: true,
    });

    const events: any[] = [];
    for await (const event of patchedStream) {
      events.push(event);
    }

    expect(events.length).toBeGreaterThan(0);
    expect(callSpy.mock.calls.length).toBeGreaterThanOrEqual(1);

    // Verify the aggregated output contains tool_use
    const patchCalls = callSpy.mock.calls.filter(
      (call: any) => (call[1] as any).method === "PATCH",
    );
    const lastPatchCall = patchCalls[patchCalls.length - 1];
    const body = parseRequestBody((lastPatchCall[1] as any).body);

    expect(body.outputs).toBeDefined();
    expect(body.outputs.content).toBeDefined();
    expect(
      body.outputs.content.some((block: any) => block.type === "tool_use"),
    ).toBe(true);

    callSpy.mockClear();
  });

  test("wrapping same instance", async () => {
    const wrapped = wrapAnthropic(new Anthropic());
    expect(() => wrapAnthropic(wrapped)).toThrowError(
      "This instance of Anthropic client has been already wrapped once.",
    );
  });

  test("beta.messages.create", async () => {
    const { client, callSpy } = mockClient();

    const originalClient = new Anthropic();
    const patchedClient = wrapAnthropic(new Anthropic(), {
      client,
      tracingEnabled: true,
    });

    // Verify beta namespace exists
    expect(patchedClient.beta).toBeDefined();
    expect(patchedClient.beta.messages).toBeDefined();

    // Non-streaming beta call
    const original = await originalClient.beta.messages.create({
      model: "claude-haiku-4-5",
      max_tokens: 100,
      messages: [{ role: "user", content: "Say 'beta'" }],
      betas: ["computer-use-2025-01-24"],
    });

    const patched = await patchedClient.beta.messages.create({
      model: "claude-haiku-4-5",
      max_tokens: 100,
      messages: [{ role: "user", content: "Say 'beta'" }],
      betas: ["computer-use-2025-01-24"],
    });

    expect(patched.content).toBeDefined();
    expect(patched.role).toBe("assistant");
    expect(original.role).toBe("assistant");

    // Verify tracing calls were made
    expect(callSpy.mock.calls.length).toBeGreaterThanOrEqual(1);

    // Verify metadata was set correctly
    const postCalls = callSpy.mock.calls.filter(
      (call: any) => (call[1] as any).method === "POST",
    );
    expect(postCalls.length).toBeGreaterThanOrEqual(1);

    const postBody = parseRequestBody((postCalls[0][1] as any).body);
    expect(postBody.extra.metadata).toMatchObject({
      ls_model_name: "claude-haiku-4-5",
      ls_model_type: "chat",
      ls_provider: "anthropic",
    });

    callSpy.mockClear();
  });

  test("beta.messages.parse", async () => {
    const { client, callSpy } = mockClient();

    const originalClient = new Anthropic();
    const patchedClient = wrapAnthropic(new Anthropic(), {
      client,
      tracingEnabled: true,
    });

    expect(patchedClient.beta.messages.parse).toBeDefined();

    const original = await originalClient.beta.messages.parse({
      model: "claude-haiku-4-5",
      max_tokens: 1024,
      messages: [
        {
          role: "user",
          content: "Alice and Bob are going to a science fair on Friday.",
        },
      ],
    });

    const patched = await patchedClient.beta.messages.parse({
      model: "claude-haiku-4-5",
      max_tokens: 1024,
      messages: [
        {
          role: "user",
          content: "Alice and Bob are going to a science fair on Friday.",
        },
      ],
    });

    expect(patched.content).toBeDefined();
    expect(patched.role).toBe("assistant");
    expect(original.role).toBe("assistant");

    expect(callSpy.mock.calls.length).toBeGreaterThanOrEqual(1);

    const postCalls = callSpy.mock.calls.filter(
      (call: any) => (call[1] as any).method === "POST",
    );
    expect(postCalls.length).toBeGreaterThanOrEqual(1);

    const postBody = parseRequestBody((postCalls[0][1] as any).body);
    expect(postBody.extra.metadata).toMatchObject({
      ls_model_name: "claude-haiku-4-5",
      ls_model_type: "chat",
      ls_provider: "anthropic",
    });

    callSpy.mockClear();
  });

  test("beta.messages.create streaming", async () => {
    const { client, callSpy } = mockClient();

    const patchedClient = wrapAnthropic(new Anthropic(), {
      client,
      tracingEnabled: true,
    });

    const patchedStream = await patchedClient.beta.messages.create({
      model: "claude-haiku-4-5",
      max_tokens: 100,
      messages: [{ role: "user", content: "Say 'beta stream'" }],
      betas: ["computer-use-2025-01-24"],
      stream: true,
    });

    const events: any[] = [];
    for await (const event of patchedStream) {
      events.push(event);
    }

    expect(events.length).toBeGreaterThan(0);
    expect(callSpy.mock.calls.length).toBeGreaterThanOrEqual(1);

    // Verify metadata
    const postCalls = callSpy.mock.calls.filter(
      (call: any) => (call[1] as any).method === "POST",
    );
    const postBody = parseRequestBody((postCalls[0][1] as any).body);
    expect(postBody.extra.metadata).toMatchObject({
      ls_model_name: "claude-haiku-4-5",
      ls_model_type: "chat",
      ls_provider: "anthropic",
    });

    callSpy.mockClear();
  });

  test("beta.messages.stream", async () => {
    const { client, callSpy } = mockClient();

    const originalClient = new Anthropic();
    const patchedClient = wrapAnthropic(new Anthropic(), {
      client,
      tracingEnabled: true,
    });

    // Use beta.messages.stream with original client
    const originalStream = originalClient.beta.messages.stream({
      model: "claude-haiku-4-5",
      max_tokens: 100,
      messages: [{ role: "user", content: "Say 'beta stream method'" }],
      betas: ["computer-use-2025-01-24"],
    });

    const originalEvents: any[] = [];
    for await (const event of originalStream) {
      originalEvents.push(event);
    }

    // Use beta.messages.stream with patched client
    const patchedStream = patchedClient.beta.messages.stream({
      model: "claude-haiku-4-5",
      max_tokens: 100,
      messages: [{ role: "user", content: "Say 'beta stream method'" }],
      betas: ["computer-use-2025-01-24"],
    });

    const patchedEvents: any[] = [];
    for await (const event of patchedStream) {
      patchedEvents.push(event);
    }

    // Both should have events
    expect(patchedEvents.length).toBeGreaterThan(0);
    expect(originalEvents.length).toBeGreaterThan(0);

    // Verify tracing calls were made
    expect(callSpy.mock.calls.length).toBeGreaterThanOrEqual(1);

    // Verify metadata
    const postCalls = callSpy.mock.calls.filter(
      (call: any) => (call[1] as any).method === "POST",
    );
    expect(postCalls.length).toBeGreaterThanOrEqual(1);

    const postBody = parseRequestBody((postCalls[0][1] as any).body);
    expect(postBody.extra.metadata).toMatchObject({
      ls_model_name: "claude-haiku-4-5",
      ls_model_type: "chat",
      ls_provider: "anthropic",
    });

    // Verify token events were logged
    const patchCalls = callSpy.mock.calls.filter(
      (call: any) => (call[1] as any).method === "PATCH",
    );
    expect(patchCalls.length).toBeGreaterThan(0);
    const lastPatchCall = patchCalls[patchCalls.length - 1];
    const body = parseRequestBody((lastPatchCall[1] as any).body);

    expect(body.events).toBeDefined();
    const tokenEvents = body.events.filter(
      (event: any) => event.name === "new_token",
    );
    expect(tokenEvents.length).toBeGreaterThan(0);

    callSpy.mockClear();
  });

  test("beta.messages.stream with finalMessage", async () => {
    const { client, callSpy } = mockClient();

    const originalClient = new Anthropic();
    const patchedClient = wrapAnthropic(new Anthropic(), {
      client,
      tracingEnabled: true,
    });

    // Use beta.messages.stream with original client
    const originalStream = originalClient.beta.messages.stream({
      model: "claude-haiku-4-5",
      max_tokens: 100,
      messages: [{ role: "user", content: "Say 'beta final'" }],
      betas: ["computer-use-2025-01-24"],
    });

    const originalFinalMessage = await originalStream.finalMessage();

    // Use beta.messages.stream with patched client
    const patchedStream = patchedClient.beta.messages.stream({
      model: "claude-haiku-4-5",
      max_tokens: 100,
      messages: [{ role: "user", content: "Say 'beta final'" }],
      betas: ["computer-use-2025-01-24"],
    });

    const patchedFinalMessage = await patchedStream.finalMessage();

    // Both should have final messages
    expect(patchedFinalMessage.role).toBe("assistant");
    expect(originalFinalMessage.role).toBe("assistant");

    // Verify tracing calls were made
    expect(callSpy.mock.calls.length).toBeGreaterThanOrEqual(1);

    // Verify metadata
    const postCalls = callSpy.mock.calls.filter(
      (call: any) => (call[1] as any).method === "POST",
    );
    expect(postCalls.length).toBeGreaterThanOrEqual(1);

    const postBody = parseRequestBody((postCalls[0][1] as any).body);
    expect(postBody.extra.metadata).toMatchObject({
      ls_model_name: "claude-haiku-4-5",
      ls_model_type: "chat",
      ls_provider: "anthropic",
    });

    // Verify token events were logged
    const patchCalls = callSpy.mock.calls.filter(
      (call: any) => (call[1] as any).method === "PATCH",
    );
    expect(patchCalls.length).toBeGreaterThan(0);
    const lastPatchCall = patchCalls[patchCalls.length - 1];
    const body = parseRequestBody((lastPatchCall[1] as any).body);

    expect(body.events).toBeDefined();
    const tokenEvents = body.events.filter(
      (event: any) => event.name === "new_token",
    );
    expect(tokenEvents.length).toBeGreaterThan(0);

    callSpy.mockClear();
  });

  test("chat extra name", async () => {
    const { client, callSpy } = mockClient();

    const anthropic = wrapAnthropic(new Anthropic(), {
      client,
      tracingEnabled: true,
    });

    await anthropic.messages.create(
      {
        model: "claude-haiku-4-5",
        max_tokens: 100,
        messages: [{ role: "user", content: "Say 'red'" }],
      },
      { langsmithExtra: { name: "red", metadata: { customKey: "red" } } },
    );

    const stream = await anthropic.messages.create(
      {
        model: "claude-haiku-4-5",
        max_tokens: 100,
        messages: [{ role: "user", content: "Say 'green'" }],
        stream: true,
      },
      { langsmithExtra: { name: "green", metadata: { customKey: "green" } } },
    );

    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    for await (const _ of stream) {
      // pass
    }

    expect(
      await getAssumedTreeFromCalls(callSpy.mock.calls, client),
    ).toMatchObject({
      nodes: ["red:0", "green:1"],
      edges: [],
      data: {
        "red:0": {
          name: "red",
          extra: { metadata: { customKey: "red" } },
          outputs: {
            content: expect.any(Array),
            role: "assistant",
          },
        },
        "green:1": {
          name: "green",
          extra: { metadata: { customKey: "green" } },
          outputs: {
            content: expect.any(Array),
            role: "assistant",
          },
        },
      },
    });
  });

  const usageMetadataTestCases = [
    {
      description: "stream with usage",
      params: {
        model: "claude-haiku-4-5",
        max_tokens: 100,
        messages: [{ role: "user", content: "howdy" }],
        stream: true,
      },
      expectUsageMetadata: true,
    },
    {
      description: "default",
      params: {
        model: "claude-haiku-4-5",
        max_tokens: 100,
        messages: [{ role: "user", content: "howdy" }],
      },
      expectUsageMetadata: true,
    },
  ];

  // Token intensive test, so skipping by default
  describe.skip("Anthropic Prompt Caching Tests", () => {
    test("5-minute ephemeral cache", async () => {
      const patchedClient = wrapAnthropic(new Anthropic(), {
        tracingEnabled: true,
      });

      const longContext = generateLongContext();

      // First call - creates 5-minute cache
      const response1 = await patchedClient.beta.messages.create({
        model: "claude-sonnet-4-5",
        max_tokens: 1024,
        betas: ["prompt-caching-2024-07-31"],
        system: [
          {
            type: "text",
            text: "You are a helpful assistant that analyzes error logs.",
          },
          {
            type: "text",
            text: longContext,
            cache_control: { type: "ephemeral", ttl: "5m" },
          },
        ],
        messages: [
          { role: "user", content: "Summarize the main error briefly." },
        ],
      });

      expect(
        response1.usage.cache_creation?.ephemeral_5m_input_tokens,
      ).toBeGreaterThan(0);

      // Second call - should read from 5-minute cache
      const response2 = await patchedClient.beta.messages.create({
        model: "claude-sonnet-4-5",
        max_tokens: 1024,
        betas: ["prompt-caching-2024-07-31"],
        system: [
          {
            type: "text",
            text: "You are a helpful assistant that analyzes error logs.",
          },
          {
            type: "text",
            text: longContext,
            cache_control: { type: "ephemeral", ttl: "5m" },
          },
        ],
        messages: [
          { role: "user", content: "What are the recommended fixes?" },
        ],
      });

      expect(response2.usage).toBeDefined();
      expect(response2.usage.cache_read_input_tokens).toBeGreaterThan(0);
    });

    test("1-hour extended cache", async () => {
      const patchedClient = wrapAnthropic(new Anthropic(), {
        tracingEnabled: true,
      });

      const longContext = generateLongContext();

      // First call - creates 1-hour extended cache
      const response1 = await patchedClient.beta.messages.create({
        model: "claude-sonnet-4-5",
        max_tokens: 1024,
        betas: ["prompt-caching-2024-07-31"],
        system: [
          {
            type: "text",
            text: "You are a helpful assistant that analyzes error logs.",
          },
          {
            type: "text",
            text: longContext,
            cache_control: { type: "ephemeral", ttl: "1h" },
          },
        ],
        messages: [
          { role: "user", content: "What is the primary error message?" },
        ],
      });

      expect(
        response1.usage.cache_creation?.ephemeral_1h_input_tokens,
      ).toBeGreaterThan(0);

      // Second call - should read from 1-hour extended cache
      const response2 = await patchedClient.beta.messages.create({
        model: "claude-sonnet-4-5",
        max_tokens: 1024,
        betas: ["prompt-caching-2024-07-31"],
        system: [
          {
            type: "text",
            text: "You are a helpful assistant that analyzes error logs.",
          },
          {
            type: "text",
            text: longContext,
            cache_control: { type: "ephemeral", ttl: "1h" },
          },
        ],
        messages: [
          {
            role: "user",
            content: "What services are mentioned in the stack?",
          },
        ],
      });

      expect(response2.usage).toBeDefined();
      expect(response2.usage.cache_read_input_tokens).toBeGreaterThan(0);
    });

    test("5-minute ephemeral cache with streaming and finalMessage", async () => {
      const patchedClient = wrapAnthropic(new Anthropic(), {
        tracingEnabled: true,
      });

      const longContext = generateLongContext();

      // First call - creates 5-minute cache
      const stream1 = await patchedClient.beta.messages.create({
        model: "claude-sonnet-4-5",
        max_tokens: 100,
        betas: ["prompt-caching-2024-07-31"],
        system: [
          {
            type: "text",
            text: "You are a helpful assistant that analyzes error logs.",
          },
          {
            type: "text",
            text: longContext,
            cache_control: { type: "ephemeral", ttl: "5m" },
          },
        ],
        messages: [
          { role: "user", content: "Summarize the main error briefly." },
        ],
        stream: true,
      });

      const events1: any[] = [];
      for await (const event of stream1) {
        events1.push(event);
      }

      expect(events1.length).toBeGreaterThan(0);

      // Second call - should read from 5-minute cache using finalMessage
      const stream2 = patchedClient.beta.messages.stream({
        model: "claude-sonnet-4-5",
        max_tokens: 100,
        betas: ["prompt-caching-2024-07-31"],
        system: [
          {
            type: "text",
            text: "You are a helpful assistant that analyzes error logs.",
          },
          {
            type: "text",
            text: longContext,
            cache_control: { type: "ephemeral", ttl: "5m" },
          },
        ],
        messages: [
          { role: "user", content: "What are the recommended fixes?" },
        ],
      });

      const finalMessage = await stream2.finalMessage();

      expect(finalMessage.role).toBe("assistant");
      expect(finalMessage.usage).toBeDefined();
      expect(finalMessage.usage.cache_read_input_tokens).toBeGreaterThan(0);
    });

    test("1-hour extended cache with streaming and finalMessage", async () => {
      const patchedClient = wrapAnthropic(new Anthropic(), {
        tracingEnabled: true,
      });

      const longContext = generateLongContext();

      // First call - creates 1-hour cache
      const stream1 = await patchedClient.beta.messages.create({
        model: "claude-sonnet-4-5",
        max_tokens: 100,
        betas: ["prompt-caching-2024-07-31"],
        system: [
          {
            type: "text",
            text: "You are a helpful assistant that analyzes error logs.",
          },
          {
            type: "text",
            text: longContext,
            cache_control: { type: "ephemeral", ttl: "1h" },
          },
        ],
        messages: [
          { role: "user", content: "What is the primary error message?" },
        ],
        stream: true,
      });

      const events1: any[] = [];
      for await (const event of stream1) {
        events1.push(event);
      }

      expect(events1.length).toBeGreaterThan(0);

      // Second call - should read from 1-hour cache using finalMessage
      const stream2 = patchedClient.beta.messages.stream({
        model: "claude-sonnet-4-5",
        max_tokens: 100,
        betas: ["prompt-caching-2024-07-31"],
        system: [
          {
            type: "text",
            text: "You are a helpful assistant that analyzes error logs.",
          },
          {
            type: "text",
            text: longContext,
            cache_control: { type: "ephemeral", ttl: "1h" },
          },
        ],
        messages: [
          {
            role: "user",
            content: "What services are mentioned in the stack?",
          },
        ],
      });

      const finalMessage = await stream2.finalMessage();

      expect(finalMessage.role).toBe("assistant");
      expect(finalMessage.usage).toBeDefined();
      expect(finalMessage.usage.cache_read_input_tokens).toBeGreaterThan(0);
    });
  });

  describe("Usage Metadata Tests", () => {
    usageMetadataTestCases.forEach(
      ({ description, params, expectUsageMetadata }) => {
        it(`should handle ${description}`, async () => {
          const { client, callSpy } = mockClient();
          const anthropic = wrapAnthropic(new Anthropic(), {
            tracingEnabled: true,
            client,
          });

          const requestParams = { ...params } as Anthropic.MessageCreateParams;

          let anthropicUsage: Anthropic.Usage | undefined;
          if ((requestParams as any).stream) {
            const stream = await anthropic.messages.create(
              requestParams as Anthropic.MessageCreateParamsStreaming,
            );
            for await (const event of stream) {
              if (event.type === "message_start" && event.message?.usage) {
                anthropicUsage = event.message.usage;
              }
              if (event.type === "message_delta" && event.usage) {
                anthropicUsage = {
                  ...anthropicUsage,
                  output_tokens: event.usage.output_tokens,
                } as Anthropic.Usage;
              }
            }
          } else {
            const res = await anthropic.messages.create(
              requestParams as Anthropic.MessageCreateParamsNonStreaming,
            );
            anthropicUsage = res.usage;
          }

          let usageMetadata: UsageMetadata | undefined;
          for (const call of callSpy.mock.calls) {
            const request = call[1] as any;
            const requestBody = parseRequestBody(request.body);
            if (requestBody.outputs && requestBody.outputs.usage_metadata) {
              usageMetadata = requestBody.outputs.usage_metadata;
              break;
            }
          }

          if (expectUsageMetadata) {
            expect(usageMetadata).not.toBeUndefined();
            expect(usageMetadata).not.toBeNull();
            expect(anthropicUsage).not.toBeUndefined();
            expect(anthropicUsage).not.toBeNull();
            expect(usageMetadata!.input_tokens).toEqual(
              anthropicUsage!.input_tokens,
            );
            expect(usageMetadata!.output_tokens).toEqual(
              anthropicUsage!.output_tokens,
            );
            expect(usageMetadata!.total_tokens).toEqual(
              anthropicUsage!.input_tokens + anthropicUsage!.output_tokens,
            );
          } else {
            expect(usageMetadata).toBeUndefined();
            expect(anthropicUsage).toBeUndefined();
          }

          callSpy.mockClear();
        });
      },
    );
  });
});

describe("Claude Managed Agents - requires Anthropic API key", () => {
  test("creates agent, environment, session, and streams traced events", async () => {
    const suffix = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const anthropic = wrapAnthropic(new Anthropic(), {
      tracingEnabled: true,
      tags: ["managed-agents", "anthropic", "integration-test"],
      metadata: {
        test: "langsmith-managed-agents-wrapper",
        test_run_id: suffix,
      },
    });

    console.log(`LangSmith managed agents test_run_id: ${suffix}`);
    let agentID: string | undefined;
    let environmentID: string | undefined;
    let sessionID: string | undefined;

    try {
      const agent = await anthropic.beta.agents.create({
        name: `LangSmith Managed Agents Test ${suffix}`,
        model: process.env.ANTHROPIC_MANAGED_AGENTS_MODEL ?? "claude-opus-4-8",
        system:
          "You are a concise test agent. Use the bash tool when the user asks you to run a command, then report the result exactly.",
        tools: [
          {
            type: "agent_toolset_20260401",
            configs: [
              {
                name: "bash",
                enabled: true,
                permission_policy: { type: "always_allow" },
              },
              { name: "edit", enabled: false },
              { name: "glob", enabled: false },
              { name: "grep", enabled: false },
              { name: "read", enabled: false },
              { name: "web_fetch", enabled: false },
              { name: "web_search", enabled: false },
              { name: "write", enabled: false },
            ],
          },
        ],
        metadata: { test: "langsmith-managed-agents-wrapper" },
      });
      agentID = agent.id;
      expect(agent.version).toBeGreaterThanOrEqual(1);

      const environment = await anthropic.beta.environments.create({
        name: `langsmith-managed-agents-test-${suffix}`,
        config: {
          type: "cloud",
          networking: { type: "unrestricted" },
        },
        metadata: { test: "langsmith-managed-agents-wrapper" },
      });
      environmentID = environment.id;

      const session = await anthropic.beta.sessions.create({
        agent: agent.id,
        environment_id: environment.id,
        title: "LangSmith managed agents wrapper integration test",
      });
      sessionID = session.id;

      const stream = await anthropic.beta.sessions.events.stream(session.id);
      await anthropic.beta.sessions.events.send(session.id, {
        events: [
          {
            type: "user.message",
            content: [
              {
                type: "text",
                text: "Use the bash tool to run: printf 'LangSmith managed agent tool tracing works'. Then reply with exactly the command output and no extra text.",
              },
            ],
          },
        ],
      });

      const streamedEvents: any[] = [];
      const toolUseEvents: any[] = [];
      const toolResultEvents: any[] = [];
      let assistantText = "";
      for await (const event of stream) {
        streamedEvents.push(event);
        if (event.type === "agent.tool_use") {
          toolUseEvents.push(event);
        } else if (event.type === "agent.tool_result") {
          toolResultEvents.push(event);
        }
        if (event.type === "agent.message") {
          assistantText += event.content.map((block) => block.text).join("");
        } else if (event.type === "session.error") {
          throw new Error(
            `Managed agent session error: ${event.error?.message ?? "unknown"}`,
          );
        } else if (event.type === "session.status_idle") {
          break;
        }
      }

      await new Promise((resolve) => setTimeout(resolve, 1000));

      expect(streamedEvents.length).toBeGreaterThan(0);
      expect(
        streamedEvents.some((event) => event.type === "agent.message"),
      ).toBe(true);
      expect(toolUseEvents.length).toBeGreaterThan(0);
      expect(toolUseEvents.some((event) => event.name === "bash")).toBe(true);
      expect(toolResultEvents.length).toBeGreaterThan(0);
      expect(assistantText).toContain(
        "LangSmith managed agent tool tracing works",
      );

      const retrievedSession = await anthropic.beta.sessions.retrieve(
        session.id,
      );
      expect(retrievedSession.id).toBe(session.id);
      expect(retrievedSession.usage).toBeDefined();
    } finally {
      if (sessionID) {
        await anthropic.beta.sessions.delete(sessionID).catch(() => undefined);
      }
      if (environmentID) {
        await anthropic.beta.environments
          .delete(environmentID)
          .catch(() => undefined);
      }
      if (agentID) {
        await anthropic.beta.agents.archive(agentID).catch(() => undefined);
      }
    }
  });

  test("streams web search tool events", async () => {
    const suffix = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const anthropic = wrapAnthropic(new Anthropic(), {
      tracingEnabled: true,
      tags: ["managed-agents", "anthropic", "integration-test", "web-search"],
      metadata: {
        test: "langsmith-managed-agents-web-search-wrapper",
        test_run_id: suffix,
      },
    });

    console.log(`LangSmith managed agents web search test_run_id: ${suffix}`);
    let agentID: string | undefined;
    let environmentID: string | undefined;
    let sessionID: string | undefined;

    try {
      const agent = await anthropic.beta.agents.create({
        name: `LangSmith Managed Agents Web Search Test ${suffix}`,
        model: process.env.ANTHROPIC_MANAGED_AGENTS_MODEL ?? "claude-opus-4-8",
        system:
          "You are a concise test agent. Use the web_search tool when the user asks you to search, then answer using the result.",
        tools: [
          {
            type: "agent_toolset_20260401",
            configs: [
              { name: "bash", enabled: false },
              { name: "edit", enabled: false },
              { name: "glob", enabled: false },
              { name: "grep", enabled: false },
              { name: "read", enabled: false },
              { name: "web_fetch", enabled: false },
              {
                name: "web_search",
                enabled: true,
                permission_policy: { type: "always_allow" },
              },
              { name: "write", enabled: false },
            ],
          },
        ],
        metadata: { test: "langsmith-managed-agents-web-search-wrapper" },
      });
      agentID = agent.id;

      const environment = await anthropic.beta.environments.create({
        name: `langsmith-managed-agents-web-search-test-${suffix}`,
        config: {
          type: "cloud",
          networking: { type: "unrestricted" },
        },
        metadata: { test: "langsmith-managed-agents-web-search-wrapper" },
      });
      environmentID = environment.id;

      const session = await anthropic.beta.sessions.create({
        agent: agent.id,
        environment_id: environment.id,
        title: "LangSmith managed agents web search wrapper integration test",
      });
      sessionID = session.id;

      const stream = await anthropic.beta.sessions.events.stream(session.id);
      await anthropic.beta.sessions.events.send(session.id, {
        events: [
          {
            type: "user.message",
            content: [
              {
                type: "text",
                text:
                  process.env.ANTHROPIC_MANAGED_AGENTS_WEB_SEARCH_PROMPT ??
                  "Use web_search to search for the official LangSmith product page, then answer with the page title or product name only.",
              },
            ],
          },
        ],
      });

      const streamedEvents: any[] = [];
      const webSearchToolUseEvents: any[] = [];
      const webSearchToolResultEvents: any[] = [];
      let assistantText = "";
      for await (const event of stream) {
        streamedEvents.push(event);
        if (event.type === "agent.tool_use" && event.name === "web_search") {
          webSearchToolUseEvents.push(event);
        } else if (
          event.type === "agent.tool_result" &&
          webSearchToolUseEvents.some(
            (toolUse) => toolUse.id === event.tool_use_id,
          )
        ) {
          webSearchToolResultEvents.push(event);
        } else if (event.type === "agent.message") {
          assistantText += event.content.map((block) => block.text).join("");
        } else if (event.type === "session.error") {
          throw new Error(
            `Managed agent web search session error: ${event.error?.message ?? "unknown"}`,
          );
        } else if (event.type === "session.status_idle") {
          break;
        }
      }

      await new Promise((resolve) => setTimeout(resolve, 1000));

      expect(streamedEvents.length).toBeGreaterThan(0);
      expect(webSearchToolUseEvents.length).toBeGreaterThan(0);
      expect(webSearchToolResultEvents.length).toBeGreaterThan(0);
      expect(assistantText.length).toBeGreaterThan(0);

      const retrievedSession = await anthropic.beta.sessions.retrieve(
        session.id,
      );
      expect(retrievedSession.id).toBe(session.id);
      expect(retrievedSession.usage).toBeDefined();
    } finally {
      if (sessionID) {
        await anthropic.beta.sessions.delete(sessionID).catch(() => undefined);
      }
      if (environmentID) {
        await anthropic.beta.environments
          .delete(environmentID)
          .catch(() => undefined);
      }
      if (agentID) {
        await anthropic.beta.agents.archive(agentID).catch(() => undefined);
      }
    }
  });

  test("streams MCP server tool events", async () => {
    const mcpServerUrl = process.env.ANTHROPIC_MANAGED_AGENTS_MCP_SERVER_URL;
    const mcpPrompt = process.env.ANTHROPIC_MANAGED_AGENTS_MCP_PROMPT;
    const expectedToolName = process.env.ANTHROPIC_MANAGED_AGENTS_MCP_TOOL_NAME;
    if (!mcpServerUrl || !mcpPrompt) {
      console.warn(
        "Skipping MCP managed agents integration test. Set ANTHROPIC_MANAGED_AGENTS_MCP_SERVER_URL and ANTHROPIC_MANAGED_AGENTS_MCP_PROMPT to run it.",
      );
      return;
    }

    const suffix = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const mcpServerName = `test_mcp_${suffix.replace(/[^a-zA-Z0-9_-]/g, "_")}`;
    const anthropic = wrapAnthropic(new Anthropic(), {
      tracingEnabled: true,
      tags: ["managed-agents", "anthropic", "integration-test", "mcp"],
      metadata: {
        test: "langsmith-managed-agents-mcp-wrapper",
        test_run_id: suffix,
      },
    });

    console.log(`LangSmith managed agents MCP test_run_id: ${suffix}`);
    let agentID: string | undefined;
    let environmentID: string | undefined;
    let sessionID: string | undefined;

    try {
      const mcpToolset: any = {
        type: "mcp_toolset",
        mcp_server_name: mcpServerName,
        default_config: {
          enabled: true,
          permission_policy: { type: "always_allow" },
        },
      };
      if (expectedToolName) {
        mcpToolset.configs = [
          {
            name: expectedToolName,
            enabled: true,
            permission_policy: { type: "always_allow" },
          },
        ];
      }

      const agent = await anthropic.beta.agents.create({
        name: `LangSmith Managed Agents MCP Test ${suffix}`,
        model: process.env.ANTHROPIC_MANAGED_AGENTS_MODEL ?? "claude-opus-4-8",
        system:
          "You are a concise test agent. Use the available MCP tool when the user asks, then report the result.",
        mcp_servers: [
          {
            name: mcpServerName,
            type: "url",
            url: mcpServerUrl,
          },
        ],
        tools: [mcpToolset],
        metadata: { test: "langsmith-managed-agents-mcp-wrapper" },
      });
      agentID = agent.id;

      const environment = await anthropic.beta.environments.create({
        name: `langsmith-managed-agents-mcp-test-${suffix}`,
        config: {
          type: "cloud",
          networking: { type: "unrestricted" },
        },
        metadata: { test: "langsmith-managed-agents-mcp-wrapper" },
      });
      environmentID = environment.id;

      const session = await anthropic.beta.sessions.create({
        agent: agent.id,
        environment_id: environment.id,
        title: "LangSmith managed agents MCP wrapper integration test",
      });
      sessionID = session.id;

      const stream = await anthropic.beta.sessions.events.stream(session.id);
      await anthropic.beta.sessions.events.send(session.id, {
        events: [
          {
            type: "user.message",
            content: [{ type: "text", text: mcpPrompt }],
          },
        ],
      });

      const streamedEvents: any[] = [];
      const mcpToolUseEvents: any[] = [];
      const mcpToolResultEvents: any[] = [];
      let assistantText = "";
      for await (const event of stream) {
        streamedEvents.push(event);
        if (event.type === "agent.mcp_tool_use") {
          mcpToolUseEvents.push(event);
        } else if (event.type === "agent.mcp_tool_result") {
          mcpToolResultEvents.push(event);
        } else if (event.type === "agent.message") {
          assistantText += event.content.map((block) => block.text).join("");
        } else if (event.type === "session.error") {
          throw new Error(
            `Managed agent MCP session error: ${event.error?.message ?? "unknown"}`,
          );
        } else if (event.type === "session.status_idle") {
          break;
        }
      }

      await new Promise((resolve) => setTimeout(resolve, 1000));

      expect(streamedEvents.length).toBeGreaterThan(0);
      expect(mcpToolUseEvents.length).toBeGreaterThan(0);
      expect(mcpToolResultEvents.length).toBeGreaterThan(0);
      expect(
        mcpToolUseEvents.every(
          (event) => event.mcp_server_name === mcpServerName,
        ),
      ).toBe(true);
      if (expectedToolName) {
        expect(
          mcpToolUseEvents.some((event) => event.name === expectedToolName),
        ).toBe(true);
      }
      expect(assistantText.length).toBeGreaterThan(0);

      const retrievedSession = await anthropic.beta.sessions.retrieve(
        session.id,
      );
      expect(retrievedSession.id).toBe(session.id);
      expect(retrievedSession.usage).toBeDefined();
    } finally {
      if (sessionID) {
        await anthropic.beta.sessions.delete(sessionID).catch(() => undefined);
      }
      if (environmentID) {
        await anthropic.beta.environments
          .delete(environmentID)
          .catch(() => undefined);
      }
      if (agentID) {
        await anthropic.beta.agents.archive(agentID).catch(() => undefined);
      }
    }
  });

  describe("additional managed agent scenarios", () => {
    async function createManagedAgentFixture(
      anthropic: any,
      suffix: string,
      agentParams: any,
    ) {
      const agent = await anthropic.beta.agents.create({
        name: `LangSmith Managed Agents Scenario Test ${suffix}`,
        model: process.env.ANTHROPIC_MANAGED_AGENTS_MODEL ?? "claude-opus-4-8",
        metadata: { test: "langsmith-managed-agents-scenario-wrapper" },
        ...agentParams,
      });
      const environment = await anthropic.beta.environments.create({
        name: `langsmith-managed-agents-scenario-test-${suffix}`,
        config: {
          type: "cloud",
          networking: { type: "unrestricted" },
        },
        metadata: { test: "langsmith-managed-agents-scenario-wrapper" },
      });
      const session = await anthropic.beta.sessions.create({
        agent: agent.id,
        environment_id: environment.id,
        title: "LangSmith managed agents skipped scenario integration test",
      });
      return {
        agent,
        environment,
        session,
        cleanup: async () => {
          await anthropic.beta.sessions
            .delete(session.id)
            .catch(() => undefined);
          await anthropic.beta.environments
            .delete(environment.id)
            .catch(() => undefined);
          await anthropic.beta.agents.archive(agent.id).catch(() => undefined);
        },
      };
    }

    test("handles user.interrupt", async () => {
      const suffix = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
      const anthropic = wrapAnthropic(new Anthropic(), {
        tracingEnabled: true,
        tags: ["managed-agents", "interrupt", "integration-test"],
        metadata: { test_run_id: suffix },
      });
      const fixture = await createManagedAgentFixture(anthropic, suffix, {
        system: "You are a test agent. Use bash for long-running commands.",
        tools: [
          {
            type: "agent_toolset_20260401",
            configs: [
              {
                name: "bash",
                enabled: true,
                permission_policy: { type: "always_allow" },
              },
            ],
          },
        ],
      });
      try {
        const stream = await anthropic.beta.sessions.events.stream(
          fixture.session.id,
        );
        await anthropic.beta.sessions.events.send(fixture.session.id, {
          events: [
            {
              type: "user.message",
              content: [
                {
                  type: "text",
                  text: "Run a long bash loop, then report completion.",
                },
              ],
            },
          ],
        });
        await anthropic.beta.sessions.events.send(fixture.session.id, {
          events: [{ type: "user.interrupt" }],
        });
        const events: any[] = [];
        for await (const event of stream) {
          events.push(event);
          if (event.type === "session.status_idle") break;
        }
        expect(events.some((event) => event.type === "user.interrupt")).toBe(
          true,
        );
      } finally {
        await fixture.cleanup();
      }
    });

    test("handles tool confirmation with user.tool_confirmation", async () => {
      const suffix = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
      const anthropic = wrapAnthropic(new Anthropic(), {
        tracingEnabled: true,
        tags: ["managed-agents", "tool-confirmation", "integration-test"],
        metadata: { test_run_id: suffix },
      });
      const fixture = await createManagedAgentFixture(anthropic, suffix, {
        system: "You are a test agent. Use bash when asked.",
        tools: [
          {
            type: "agent_toolset_20260401",
            configs: [
              {
                name: "bash",
                enabled: true,
                permission_policy: { type: "always_ask" },
              },
            ],
          },
        ],
      });
      try {
        const stream = await anthropic.beta.sessions.events.stream(
          fixture.session.id,
        );
        await anthropic.beta.sessions.events.send(fixture.session.id, {
          events: [
            {
              type: "user.message",
              content: [{ type: "text", text: "Use bash to echo hello." }],
            },
          ],
        });
        const eventsById = new Map<string, any>();
        for await (const event of stream) {
          if (event.id) eventsById.set(event.id, event);
          if (event.type === "session.status_idle") {
            if (event.stop_reason?.type === "requires_action") {
              await anthropic.beta.sessions.events.send(fixture.session.id, {
                events: event.stop_reason.event_ids.map((eventId: string) => ({
                  type: "user.tool_confirmation",
                  tool_use_id: eventId,
                  result: "allow",
                })),
              });
              continue;
            }
            break;
          }
        }
        expect(
          [...eventsById.values()].some(
            (event) => event.type === "agent.tool_use",
          ),
        ).toBe(true);
      } finally {
        await fixture.cleanup();
      }
    });

    test("handles custom tool result via user.custom_tool_result", async () => {
      const suffix = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
      const anthropic = wrapAnthropic(new Anthropic(), {
        tracingEnabled: true,
        tags: ["managed-agents", "custom-tool-result", "integration-test"],
        metadata: { test_run_id: suffix },
      });
      const fixture = await createManagedAgentFixture(anthropic, suffix, {
        system: "You are a test agent. Use the custom tool when asked.",
        tools: [
          {
            type: "custom",
            name: "lookup_test_value",
            description: "Returns a deterministic test value.",
            input_schema: {
              type: "object",
              properties: { key: { type: "string" } },
              required: ["key"],
            },
          },
        ],
      });
      try {
        const stream = await anthropic.beta.sessions.events.stream(
          fixture.session.id,
        );
        await anthropic.beta.sessions.events.send(fixture.session.id, {
          events: [
            {
              type: "user.message",
              content: [
                { type: "text", text: "Use lookup_test_value for key foo." },
              ],
            },
          ],
        });
        const customToolUses = new Map<string, any>();
        for await (const event of stream) {
          if (event.type === "agent.custom_tool_use") {
            customToolUses.set(event.id, event);
          }
          if (event.type === "session.status_idle") {
            if (event.stop_reason?.type === "requires_action") {
              await anthropic.beta.sessions.events.send(fixture.session.id, {
                events: event.stop_reason.event_ids.map((eventId: string) => ({
                  type: "user.custom_tool_result",
                  custom_tool_use_id: eventId,
                  content: [{ type: "text", text: "bar" }],
                })),
              });
              continue;
            }
            break;
          }
        }
        expect(customToolUses.size).toBeGreaterThan(0);
      } finally {
        await fixture.cleanup();
      }
    });

    test("handles user.define_outcome when supported by the SDK/API", async () => {
      const anthropic = wrapAnthropic(new Anthropic(), {
        tracingEnabled: true,
      });
      const sessionID = process.env.ANTHROPIC_MANAGED_AGENTS_SESSION_ID;
      expect(sessionID).toBeDefined();
      await anthropic.beta.sessions.events.send(sessionID!, {
        events: [
          {
            type: "user.define_outcome",
            outcome: { type: "success", description: "Test outcome" },
          } as any,
        ],
      } as any);
    });

    // TODO: figure out how to support this properly
    test.skip("streams subagent/thread status events", async () => {
      const suffix = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
      const anthropic = wrapAnthropic(new Anthropic(), {
        tracingEnabled: true,
        tags: ["managed-agents", "subagents", "integration-test"],
        metadata: { test_run_id: suffix },
      });
      const fixture = await createManagedAgentFixture(anthropic, suffix, {
        system:
          "You are a coordinator agent. Delegate work to a subagent/session thread when asked.",
        multiagent: {
          type: "coordinator",
          agents: [{ type: "self" }],
        },
      });
      try {
        const stream = await anthropic.beta.sessions.events.stream(
          fixture.session.id,
        );
        await anthropic.beta.sessions.events.send(fixture.session.id, {
          events: [
            {
              type: "user.message",
              content: [
                {
                  type: "text",
                  text: "Delegate a small task, like writing a haiku.",
                },
              ],
            },
          ],
        });
        const events: any[] = [];
        for await (const event of stream) {
          events.push(event);
          if (event.type === "session.status_idle") break;
        }
        expect(
          events.some((event) =>
            String(event.type).startsWith("session.thread_status_"),
          ),
        ).toBe(true);
      } finally {
        await fixture.cleanup();
      }
    });

    test.skip("handles file resources and skills", async () => {
      const suffix = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
      const anthropic = wrapAnthropic(new Anthropic(), {
        tracingEnabled: true,
        tags: ["managed-agents", "files", "skills", "integration-test"],
        metadata: { test_run_id: suffix },
      });
      const file = await toFile(
        new TextEncoder().encode(
          "city,weather,temperature\nPrague,sunny,23C\nParis,cloudy,18C\n",
        ),
        `langsmith-managed-agents-test-${suffix}.csv`,
        { type: "text/csv" },
      );
      const uploadedFile = await anthropic.beta.files.upload({ file });
      const fixture = await createManagedAgentFixture(anthropic, suffix, {
        system: "Use the attached file and skill to answer.",
        skills: [{ type: "anthropic", skill_id: "xlsx" }],
        tools: [
          {
            type: "agent_toolset_20260401",
            configs: [
              {
                name: "read",
                enabled: true,
                permission_policy: { type: "always_allow" },
              },
            ],
          },
        ],
      });
      let resourceID: string | undefined;
      try {
        const resource = await anthropic.beta.sessions.resources.add(
          fixture.session.id,
          {
            type: "file",
            file_id: uploadedFile.id,
          },
        );
        resourceID = resource.id;
        const stream = await anthropic.beta.sessions.events.stream(
          fixture.session.id,
        );
        await anthropic.beta.sessions.events.send(fixture.session.id, {
          events: [
            {
              type: "user.message",
              content: [{ type: "text", text: "Summarize the attached file." }],
            },
          ],
        });
        const events: any[] = [];
        for await (const event of stream) {
          events.push(event);
          if (event.type === "session.status_idle") break;
        }
        expect(events.some((event) => event.type === "agent.message")).toBe(
          true,
        );
      } finally {
        if (resourceID) {
          await anthropic.beta.sessions.resources
            .delete(resourceID, { session_id: fixture.session.id })
            .catch(() => undefined);
        }
        await fixture.cleanup();
        await anthropic.beta.files
          .delete(uploadedFile.id)
          .catch(() => undefined);
      }
    });

    test("handles image attachments in user messages", async () => {
      const suffix = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
      const anthropic = wrapAnthropic(new Anthropic(), {
        tracingEnabled: true,
        tags: ["managed-agents", "image", "integration-test"],
        metadata: { test_run_id: suffix },
      });
      const imageUrl = "https://smith.langchain.com/og_image.png";
      const fixture = await createManagedAgentFixture(anthropic, suffix, {
        system: "Describe images concisely.",
      });
      try {
        const stream = await anthropic.beta.sessions.events.stream(
          fixture.session.id,
        );
        await anthropic.beta.sessions.events.send(fixture.session.id, {
          events: [
            {
              type: "user.message",
              content: [
                { type: "text", text: "Describe this image in one sentence." },
                {
                  type: "image",
                  source: { type: "url", url: imageUrl },
                },
              ],
            },
          ],
        } as any);
        const events: any[] = [];
        for await (const event of stream) {
          events.push(event);
          if (event.type === "session.status_idle") break;
        }
        expect(events.some((event) => event.type === "agent.message")).toBe(
          true,
        );
      } finally {
        await fixture.cleanup();
      }
    });
  });
});

test("prepopulated invocation params are merged and runtime params override", async () => {
  const { client, callSpy } = mockClient();

  const wrappedClient = wrapAnthropic(new Anthropic(), {
    client,
    tracingEnabled: true,
    metadata: {
      ls_invocation_params: { top_k: 100, env: "test", team: "qa" },
      custom_key: "custom_value",
      version: "1.0.0",
    },
  });

  await wrappedClient.messages.create({
    messages: [{ role: "user", content: "Say 'hello'" }],
    model: "claude-haiku-4-5",
    top_k: 40, // Should override prepopulated top_k=100
    max_tokens: 10,
  });

  await new Promise((resolve) => setTimeout(resolve, 1000));

  const postCalls = callSpy.mock.calls.filter(
    (call: any) => (call[1] as any).method === "POST",
  );

  expect(postCalls.length).toBeGreaterThan(0);

  // Get the POST call with run data (should have extra.metadata)
  const postBody = parseRequestBody((postCalls[0][1] as any).body);

  // ls_invocation_params is in metadata, not in extra.invocation_params
  const metadata = postBody.extra?.metadata;
  const lsInvocationParams = metadata?.ls_invocation_params;

  // Runtime top_k should override prepopulated top_k
  expect(lsInvocationParams?.top_k).toBe(40);
  // Prepopulated params without conflicts should still be there
  expect(lsInvocationParams?.env).toBe("test");
  expect(lsInvocationParams?.team).toBe("qa");

  // Check that other metadata keys are preserved
  expect(metadata?.custom_key).toBe("custom_value");
  expect(metadata?.version).toBe("1.0.0");

  callSpy.mockClear();
});
