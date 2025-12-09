/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable no-process-env */
import Anthropic from "@anthropic-ai/sdk";
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
      (call) => (call[1] as any).method === "POST"
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
      (call) => (call[1] as any).method === "PATCH"
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
      (call) => (call[1] as any).method === "PATCH"
    );
    expect(patchCalls.length).toBeGreaterThan(0);
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

    // Verify metadata
    const postCalls = callSpy.mock.calls.filter(
      (call) => (call[1] as any).method === "POST"
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
      }
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
      (call) => (call[1] as any).method === "POST"
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
      (call) => (call[1] as any).method === "PATCH"
    );
    expect(patchCalls.length).toBeGreaterThan(0);
    const lastPatchCall = patchCalls[patchCalls.length - 1];
    const body = parseRequestBody((lastPatchCall[1] as any).body);

    expect(body.events).toBeDefined();
    const tokenEvents = body.events.filter(
      (event: any) => event.name === "new_token"
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
      (call) => (call[1] as any).method === "POST"
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
      (call) => (call[1] as any).method === "PATCH"
    );
    expect(patchCalls.length).toBeGreaterThan(0);
    const lastPatchCall = patchCalls[patchCalls.length - 1];
    const body = parseRequestBody((lastPatchCall[1] as any).body);

    expect(body.events).toBeDefined();
    const tokenEvents = body.events.filter(
      (event: any) => event.name === "new_token"
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
      }
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
      true
    );
    expect(original.content.some((block) => block.type === "tool_use")).toBe(
      true
    );

    // Verify tracing was done
    expect(callSpy.mock.calls.length).toBeGreaterThanOrEqual(1);

    const patchCalls = callSpy.mock.calls.filter(
      (call) => (call[1] as any).method === "PATCH"
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
      (call) => (call[1] as any).method === "PATCH"
    );
    const lastPatchCall = patchCalls[patchCalls.length - 1];
    const body = parseRequestBody((lastPatchCall[1] as any).body);

    expect(body.outputs).toBeDefined();
    expect(body.outputs.content).toBeDefined();
    expect(
      body.outputs.content.some((block: any) => block.type === "tool_use")
    ).toBe(true);

    callSpy.mockClear();
  });

  test("wrapping same instance", async () => {
    const wrapped = wrapAnthropic(new Anthropic());
    expect(() => wrapAnthropic(wrapped)).toThrowError(
      "This instance of Anthropic client has been already wrapped once."
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
      (call) => (call[1] as any).method === "POST"
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
      (call) => (call[1] as any).method === "POST"
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
      (call) => (call[1] as any).method === "POST"
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
      (call) => (call[1] as any).method === "PATCH"
    );
    expect(patchCalls.length).toBeGreaterThan(0);
    const lastPatchCall = patchCalls[patchCalls.length - 1];
    const body = parseRequestBody((lastPatchCall[1] as any).body);

    expect(body.events).toBeDefined();
    const tokenEvents = body.events.filter(
      (event: any) => event.name === "new_token"
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
      (call) => (call[1] as any).method === "POST"
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
      (call) => (call[1] as any).method === "PATCH"
    );
    expect(patchCalls.length).toBeGreaterThan(0);
    const lastPatchCall = patchCalls[patchCalls.length - 1];
    const body = parseRequestBody((lastPatchCall[1] as any).body);

    expect(body.events).toBeDefined();
    const tokenEvents = body.events.filter(
      (event: any) => event.name === "new_token"
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
      { langsmithExtra: { name: "red", metadata: { customKey: "red" } } }
    );

    const stream = await anthropic.messages.create(
      {
        model: "claude-haiku-4-5",
        max_tokens: 100,
        messages: [{ role: "user", content: "Say 'green'" }],
        stream: true,
      },
      { langsmithExtra: { name: "green", metadata: { customKey: "green" } } }
    );

    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    for await (const _ of stream) {
      // pass
    }

    expect(getAssumedTreeFromCalls(callSpy.mock.calls)).toMatchObject({
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
        response1.usage.cache_creation?.ephemeral_5m_input_tokens
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
        response1.usage.cache_creation?.ephemeral_1h_input_tokens
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
              requestParams as Anthropic.MessageCreateParamsStreaming
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
              requestParams as Anthropic.MessageCreateParamsNonStreaming
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
              anthropicUsage!.input_tokens
            );
            expect(usageMetadata!.output_tokens).toEqual(
              anthropicUsage!.output_tokens
            );
            expect(usageMetadata!.total_tokens).toEqual(
              anthropicUsage!.input_tokens + anthropicUsage!.output_tokens
            );
          } else {
            expect(usageMetadata).toBeUndefined();
            expect(anthropicUsage).toBeUndefined();
          }

          callSpy.mockClear();
        });
      }
    );
  });
});
