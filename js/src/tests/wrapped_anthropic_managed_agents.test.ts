/* eslint-disable @typescript-eslint/no-explicit-any */
import { jest } from "@jest/globals";
import { wrapAnthropic } from "../wrappers/anthropic.js";
import { mockClient } from "./utils/mock_client.js";

function parseRequestBody(body: any) {
  return body instanceof Uint8Array
    ? JSON.parse(new TextDecoder().decode(body))
    : JSON.parse(body);
}

function createAsyncIterable<T>(items: T[]): AsyncIterable<T> {
  return {
    async *[Symbol.asyncIterator]() {
      for (const item of items) {
        yield item;
      }
    },
  };
}

async function flushPromises() {
  await new Promise((resolve) => setTimeout(resolve, 0));
}

describe("wrapAnthropic Claude Managed Agents", () => {
  function createFakeAnthropic(events: any[]) {
    const fakeEvents = {
      stream: jest.fn(async () => createAsyncIterable(events)),
      send: jest.fn(async (_sessionID: string, params: any) => ({
        data: params.events.map((event: any, index: number) => ({
          id: `sent_${index}`,
          ...event,
        })),
      })),
    };

    return {
      messages: {
        create: jest.fn(),
        stream: jest.fn(),
      },
      beta: {
        sessions: {
          retrieve: jest.fn(async (sessionID: string) => ({
            id: sessionID,
            agent: {
              model: { id: "claude-opus-4-8", speed: "standard" },
            },
          })),
          events: fakeEvents,
        },
      },
    } as any;
  }

  test("traces streamed managed agent events and aggregates outputs", async () => {
    const { client, callSpy } = mockClient();
    const fakeAnthropic = createFakeAnthropic([
      {
        id: "sevt_running",
        type: "session.status_running",
        processed_at: "2026-04-01T00:00:00Z",
      },
      {
        id: "sevt_span_start",
        type: "span.model_request_start",
        processed_at: "2026-04-01T00:00:00.500Z",
      },
      {
        id: "sevt_msg",
        type: "agent.message",
        content: [{ type: "text", text: "Created fibonacci.txt" }],
        processed_at: "2026-04-01T00:00:01Z",
      },
      {
        id: "sevt_tool",
        type: "agent.tool_use",
        name: "bash",
        input: { command: "python fibonacci.py" },
        processed_at: "2026-04-01T00:00:02Z",
      },
      {
        id: "sevt_tool_result",
        type: "agent.tool_result",
        tool_use_id: "sevt_tool",
        content: [{ type: "text", text: "ran script" }],
        is_error: false,
        processed_at: "2026-04-01T00:00:02.500Z",
      },
      {
        id: "sevt_span_end",
        type: "span.model_request_end",
        is_error: false,
        model_request_start_id: "sevt_span_start",
        model_usage: {
          input_tokens: 10,
          output_tokens: 5,
          cache_creation_input_tokens: 2,
          cache_read_input_tokens: 3,
        },
        processed_at: "2026-04-01T00:00:03Z",
      },
      {
        id: "sevt_idle",
        type: "session.status_idle",
        stop_reason: { type: "end_turn" },
        processed_at: "2026-04-01T00:00:04Z",
      },
    ]);
    const anthropic = wrapAnthropic(fakeAnthropic, {
      client,
      tracingEnabled: true,
    });

    const stream = await anthropic.beta.sessions.events.stream("sesn_123");
    const seenEvents = [];
    for await (const event of stream) {
      seenEvents.push(event);
      if (event.type === "session.status_idle") break;
    }
    await flushPromises();

    expect(seenEvents).toHaveLength(7);
    expect(fakeAnthropic.beta.sessions.events.stream).toHaveBeenCalledWith(
      "sesn_123",
    );

    const postBodies = callSpy.mock.calls
      .filter((call: any) => (call[1] as any).method === "POST")
      .map((call: any) => parseRequestBody((call[1] as any).body));
    expect(postBodies).toHaveLength(3);
    const postBody = postBodies.find(
      (body: any) => body.name === "ClaudeManagedAgent",
    );
    expect(postBody).toBeDefined();
    expect(postBody.run_type).toBe("chain");
    expect(postBody.inputs).toEqual({ session_id: "sesn_123" });
    expect(postBody.extra.metadata).toMatchObject({
      ls_provider: "anthropic",
      ls_model_type: "chat",
      thread_id: "sesn_123",
    });
    expect(
      postBodies.find(
        (body: any) => body.name === "ClaudeManagedAgentModelRequest",
      )?.run_type,
    ).toBe("llm");
    expect(postBodies.find((body: any) => body.name === "bash")?.run_type).toBe(
      "tool",
    );

    const patchBodies = postBodies;
    expect(
      callSpy.mock.calls.filter(
        (call: any) => (call[1] as any).method === "PATCH",
      ),
    ).toHaveLength(0);
    const patchBody = patchBodies.find(
      (body: any) => body.name === "ClaudeManagedAgent",
    );
    expect(patchBody.error).toBeUndefined();
    expect(patchBody.outputs.text).toBe("Created fibonacci.txt");
    expect(patchBody.outputs.messages).toHaveLength(1);
    expect(patchBody.outputs.tool_calls).toMatchObject([
      { type: "agent.tool_use", name: "bash" },
    ]);
    expect(patchBody.outputs.chat.messages).toEqual(
      expect.arrayContaining([
        { role: "assistant", content: "Created fibonacci.txt" },
        {
          role: "assistant",
          content: [
            {
              type: "tool_use",
              id: "sevt_tool",
              name: "bash",
              input: { command: "python fibonacci.py" },
            },
          ],
        },
        {
          role: "user",
          content: [
            {
              type: "tool_result",
              tool_use_id: "sevt_tool",
              content: "ran script",
              is_error: false,
            },
          ],
        },
      ]),
    );
    expect(patchBody.outputs.status).toBe("session.status_idle");
    expect(patchBody.outputs.stop_reason).toEqual({ type: "end_turn" });
    expect(patchBody.outputs.usage_metadata).toBeUndefined();
    expect(patchBody.extra.metadata.usage_metadata).toBeUndefined();

    const llmPatchBody = patchBodies.find(
      (body: any) => body.name === "ClaudeManagedAgentModelRequest",
    );
    expect(llmPatchBody?.extra.metadata).toMatchObject({
      ls_provider: "anthropic",
      ls_model_name: "claude-opus-4-8",
      ls_model_type: "chat",
      ls_invocation_params: {
        session_id: "sesn_123",
        model_config: { id: "claude-opus-4-8", speed: "standard" },
      },
    });
    expect(llmPatchBody?.outputs.tool_calls).toMatchObject([
      { type: "agent.tool_use", name: "bash" },
    ]);
    expect(llmPatchBody?.outputs.chat.messages).toEqual(
      expect.arrayContaining([
        { role: "assistant", content: "Created fibonacci.txt" },
        {
          role: "assistant",
          content: [
            {
              type: "tool_use",
              id: "sevt_tool",
              name: "bash",
              input: { command: "python fibonacci.py" },
            },
          ],
        },
      ]),
    );
    expect(llmPatchBody?.outputs.usage_metadata).toMatchObject({
      input_tokens: 15,
      output_tokens: 5,
      total_tokens: 20,
      input_token_details: {
        ephemeral_5m_input_tokens: 2,
        cache_read: 3,
      },
    });
    const toolPatchBody = patchBodies.find((body: any) => body.name === "bash");
    expect(toolPatchBody?.outputs.event).toMatchObject({
      type: "agent.tool_result",
      tool_use_id: "sevt_tool",
    });
  });

  test("traces web search tool use events as LLM tool calls and tool child runs", async () => {
    const { client, callSpy } = mockClient();
    const fakeAnthropic = createFakeAnthropic([
      {
        id: "sevt_user",
        type: "user.message",
        content: [{ type: "text", text: "Use web search" }],
        processed_at: "2026-04-01T00:00:00Z",
      },
      {
        id: "sevt_span_start",
        type: "span.model_request_start",
        processed_at: "2026-04-01T00:00:00.500Z",
      },
      {
        id: "sevt_web_search",
        type: "agent.tool_use",
        name: "web_search",
        input: { query: "LangSmith tracing" },
        processed_at: "2026-04-01T00:00:01Z",
      },
      {
        id: "sevt_span_end",
        type: "span.model_request_end",
        is_error: false,
        model_request_start_id: "sevt_span_start",
        model_usage: {
          input_tokens: 12,
          output_tokens: 6,
          cache_creation_input_tokens: 0,
          cache_read_input_tokens: 0,
        },
        processed_at: "2026-04-01T00:00:01.500Z",
      },
      {
        id: "sevt_web_search_result",
        type: "agent.tool_result",
        tool_use_id: "sevt_web_search",
        content: [{ type: "text", text: "Web search result" }],
        is_error: false,
        processed_at: "2026-04-01T00:00:02Z",
      },
      {
        id: "sevt_idle",
        type: "session.status_idle",
        stop_reason: { type: "end_turn" },
        processed_at: "2026-04-01T00:00:03Z",
      },
    ]);
    const anthropic = wrapAnthropic(fakeAnthropic, {
      client,
      tracingEnabled: true,
    });

    const stream =
      await anthropic.beta.sessions.events.stream("sesn_web_search");
    for await (const event of stream) {
      if (event.type === "session.status_idle") break;
    }
    await flushPromises();

    const postBodies = callSpy.mock.calls
      .filter((call: any) => (call[1] as any).method === "POST")
      .map((call: any) => parseRequestBody((call[1] as any).body));
    expect(
      postBodies.find(
        (body: any) => body.name === "ClaudeManagedAgentModelRequest",
      )?.run_type,
    ).toBe("llm");
    expect(
      postBodies.find((body: any) => body.name === "web_search")?.run_type,
    ).toBe("tool");

    const patchBodies = postBodies;
    expect(
      callSpy.mock.calls.filter(
        (call: any) => (call[1] as any).method === "PATCH",
      ),
    ).toHaveLength(0);
    const llmPatchBody = patchBodies.find(
      (body: any) => body.name === "ClaudeManagedAgentModelRequest",
    );
    expect(llmPatchBody?.outputs.tool_calls).toMatchObject([
      {
        type: "agent.tool_use",
        name: "web_search",
      },
    ]);
    const toolPatchBody = patchBodies.find(
      (body: any) => body.name === "web_search",
    );
    expect(toolPatchBody?.outputs.event).toMatchObject({
      type: "agent.tool_result",
      tool_use_id: "sevt_web_search",
    });
  });

  test("traces MCP tool use events as LLM tool calls and tool child runs", async () => {
    const { client, callSpy } = mockClient();
    const fakeAnthropic = createFakeAnthropic([
      {
        id: "sevt_user",
        type: "user.message",
        content: [{ type: "text", text: "Use the MCP tool" }],
        processed_at: "2026-04-01T00:00:00Z",
      },
      {
        id: "sevt_span_start",
        type: "span.model_request_start",
        processed_at: "2026-04-01T00:00:00.500Z",
      },
      {
        id: "sevt_mcp_tool",
        type: "agent.mcp_tool_use",
        mcp_server_name: "test_mcp",
        name: "search_docs",
        input: { query: "LangSmith" },
        processed_at: "2026-04-01T00:00:01Z",
      },
      {
        id: "sevt_span_end",
        type: "span.model_request_end",
        is_error: false,
        model_request_start_id: "sevt_span_start",
        model_usage: {
          input_tokens: 8,
          output_tokens: 4,
          cache_creation_input_tokens: 0,
          cache_read_input_tokens: 0,
        },
        processed_at: "2026-04-01T00:00:01.500Z",
      },
      {
        id: "sevt_mcp_result",
        type: "agent.mcp_tool_result",
        mcp_tool_use_id: "sevt_mcp_tool",
        content: [{ type: "text", text: "MCP result" }],
        is_error: false,
        processed_at: "2026-04-01T00:00:02Z",
      },
      {
        id: "sevt_idle",
        type: "session.status_idle",
        stop_reason: { type: "end_turn" },
        processed_at: "2026-04-01T00:00:03Z",
      },
    ]);
    const anthropic = wrapAnthropic(fakeAnthropic, {
      client,
      tracingEnabled: true,
    });

    const stream = await anthropic.beta.sessions.events.stream("sesn_mcp");
    for await (const event of stream) {
      if (event.type === "session.status_idle") break;
    }
    await flushPromises();

    const postBodies = callSpy.mock.calls
      .filter((call: any) => (call[1] as any).method === "POST")
      .map((call: any) => parseRequestBody((call[1] as any).body));
    expect(
      postBodies.find(
        (body: any) => body.name === "ClaudeManagedAgentModelRequest",
      )?.run_type,
    ).toBe("llm");
    expect(
      postBodies.find((body: any) => body.name === "search_docs")?.run_type,
    ).toBe("tool");

    const patchBodies = postBodies;
    expect(
      callSpy.mock.calls.filter(
        (call: any) => (call[1] as any).method === "PATCH",
      ),
    ).toHaveLength(0);
    const llmPatchBody = patchBodies.find(
      (body: any) => body.name === "ClaudeManagedAgentModelRequest",
    );
    expect(llmPatchBody?.outputs.tool_calls).toMatchObject([
      {
        type: "agent.mcp_tool_use",
        mcp_server_name: "test_mcp",
        name: "search_docs",
      },
    ]);
    const toolPatchBody = patchBodies.find(
      (body: any) => body.name === "search_docs",
    );
    expect(toolPatchBody?.outputs.event).toMatchObject({
      type: "agent.mcp_tool_result",
      mcp_tool_use_id: "sevt_mcp_tool",
    });
  });

  test("records sent user events on an active managed agent stream run", async () => {
    const { client, callSpy } = mockClient();
    const fakeAnthropic = createFakeAnthropic([
      {
        id: "sevt_user",
        type: "user.message",
        content: [{ type: "text", text: "Create fibonacci.txt" }],
        processed_at: "2026-04-01T00:00:00Z",
      },
      {
        id: "sevt_msg",
        type: "agent.message",
        content: [{ type: "text", text: "Done" }],
        processed_at: "2026-04-01T00:00:01Z",
      },
      {
        id: "sevt_idle",
        type: "session.status_idle",
        stop_reason: { type: "end_turn" },
        processed_at: "2026-04-01T00:00:02Z",
      },
    ]);
    const anthropic = wrapAnthropic(fakeAnthropic, {
      client,
      tracingEnabled: true,
    });

    const stream = await anthropic.beta.sessions.events.stream("sesn_456");
    await anthropic.beta.sessions.events.send("sesn_456", {
      events: [
        {
          type: "user.message",
          content: [{ type: "text", text: "Create fibonacci.txt" }],
        },
      ],
    });

    for await (const _event of stream) {
      // consume stream to finish the trace
    }
    await flushPromises();

    expect(
      callSpy.mock.calls.filter(
        (call: any) => (call[1] as any).method === "PATCH",
      ),
    ).toHaveLength(0);
    const streamPostCalls = callSpy.mock.calls.filter((call: any) => {
      if ((call[1] as any).method !== "POST") return false;
      const body = parseRequestBody((call[1] as any).body);
      return body.name === "ClaudeManagedAgent";
    });
    expect(streamPostCalls).toHaveLength(1);
    const postBody = parseRequestBody((streamPostCalls[0][1] as any).body);
    expect(postBody.inputs.events).toMatchObject([
      {
        type: "user.message",
        content: [{ type: "text", text: "Create fibonacci.txt" }],
      },
    ]);
    expect(postBody.inputs.chat).toEqual({
      messages: [{ role: "user", content: "Create fibonacci.txt" }],
    });
    const sendPostCalls = callSpy.mock.calls.filter((call: any) => {
      if ((call[1] as any).method !== "POST") return false;
      const body = parseRequestBody((call[1] as any).body);
      return body.name === "ClaudeManagedAgentSendEvents";
    });
    expect(sendPostCalls).toHaveLength(0);
  });
});
