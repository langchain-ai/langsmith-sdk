/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, test, expect, vi, it } from "vitest";
import * as fs from "node:fs";
import { wrapAnthropic } from "../wrappers/anthropic.js";
import { mockClient } from "./utils/vitest_mock_client.js";
import { asTree, getAssumedTreeFromCalls } from "./utils/tree.js";

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

async function createReplayableAnthropic(
  path: string,
  options?: {
    replaceTime?: boolean;
  },
): Promise<[anthropic: any, session: { id: string }]> {
  const input = await fs.promises.readFile(
    new URL(path, import.meta.url),
    "utf-8",
  );

  const reviver = (() => {
    const { replaceTime } = options ?? {};
    if (!replaceTime) return undefined;

    const testTime = new Date();
    let firstTime: Date | null = null;
    return (k: string, v: any) => {
      if (
        replaceTime &&
        ["processed_at", "created_at", "updated_at"].includes(k)
      ) {
        const parsedV = new Date(v);
        firstTime ??= parsedV;
        return new Date(
          testTime.getTime() + (parsedV.getTime() - firstTime.getTime()),
        ).toISOString();
      }
      return v;
    };
  })();

  const logEvents: [
    methodName:
      | "client.beta.sessions.create"
      | "client.beta.sessions.events.send"
      | "client.beta.sessions.events.stream",
    args: any,
  ][] = input
    .split("\n")
    .filter((line) => line.trim() !== "")
    .map((line) => JSON.parse(line, reviver));

  const streamEvents = logEvents
    .filter(
      ([methodName]) => methodName === "client.beta.sessions.events.stream",
    )
    .map(([, args]) => args);

  const sessionRetrieve = logEvents.find(
    ([methodName]) => methodName === "client.beta.sessions.create",
  )?.[1];

  return [
    {
      messages: { create: vi.fn(), stream: vi.fn() },
      beta: {
        sessions: {
          retrieve: vi.fn(async () => sessionRetrieve),
          events: {
            stream: vi.fn(async () => createAsyncIterable(streamEvents)),
            send: vi.fn(async () => ({})),
          },
        },
      },
    } as any,
    sessionRetrieve,
  ];
}

describe("wrapAnthropic Claude Managed Agents", () => {
  function createFakeAnthropic(events: any[]) {
    const fakeEvents = {
      stream: vi.fn(async () => createAsyncIterable(events)),
      send: vi.fn(async (_sessionID: string, params: any) => ({
        data: params.events.map((event: any, index: number) => ({
          id: `sent_${index}`,
          ...event,
        })),
      })),
    };

    return {
      messages: {
        create: vi.fn(),
        stream: vi.fn(),
      },
      beta: {
        sessions: {
          retrieve: vi.fn(async (sessionID: string) => ({
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
        id: "sevt_user",
        type: "user.message",
        content: [{ type: "text", text: "Create fibonacci.txt" }],
        processed_at: "2026-04-01T00:00:00.250Z",
      },
      {
        id: "sevt_span_start",
        type: "span.model_request_start",
        processed_at: "2026-04-01T00:00:00.500Z",
      },
      {
        id: "sevt_tool",
        type: "agent.tool_use",
        name: "bash",
        input: { command: "python fibonacci.py" },
        processed_at: "2026-04-01T00:00:01Z",
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
        processed_at: "2026-04-01T00:00:01.500Z",
      },
      {
        id: "sevt_tool_result",
        type: "agent.tool_result",
        tool_use_id: "sevt_tool",
        content: [{ type: "text", text: "ran script" }],
        is_error: false,
        processed_at: "2026-04-01T00:00:02Z",
      },
      {
        id: "sevt_span_start_2",
        type: "span.model_request_start",
        processed_at: "2026-04-01T00:00:02.500Z",
      },
      {
        id: "sevt_msg",
        type: "agent.message",
        content: [{ type: "text", text: "Created fibonacci.txt" }],
        processed_at: "2026-04-01T00:00:03Z",
      },
      {
        id: "sevt_span_end_2",
        type: "span.model_request_end",
        is_error: false,
        model_request_start_id: "sevt_span_start_2",
        model_usage: {
          input_tokens: 20,
          output_tokens: 7,
          cache_creation_input_tokens: 0,
          cache_read_input_tokens: 3,
        },
        processed_at: "2026-04-01T00:00:03.500Z",
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

    await client.awaitPendingTraceBatches();

    expect(seenEvents).toHaveLength(10);
    expect(fakeAnthropic.beta.sessions.events.stream).toHaveBeenCalledWith(
      "sesn_123",
    );

    const postBodies = callSpy.mock.calls
      .filter((call: any) => (call[1] as any).method === "POST")
      .map((call: any) => parseRequestBody((call[1] as any).body));
    expect(postBodies).toHaveLength(4);
    const postBody = postBodies.find(
      (body: any) => body.name === "ClaudeManagedAgent",
    );
    expect(postBody).toBeDefined();
    expect(postBody.run_type).toBe("chain");
    expect(postBody.inputs).toMatchObject({
      session_id: "sesn_123",
      messages: [{ role: "user", content: "Create fibonacci.txt" }],
    });
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
    expect(patchBody.outputs.text).toBeUndefined();
    expect(patchBody.outputs.messages).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          role: "assistant",
          content: "Created fibonacci.txt",
        }),
        {
          id: "sevt_tool",
          role: "assistant",
          content: [
            {
              type: "tool_use",
              id: "sevt_tool",
              name: "bash",
              input: { command: "python fibonacci.py" },
            },
          ],
          processed_at: "2026-04-01T00:00:01Z",
        },
      ]),
    );
    expect(patchBody.outputs.tool_calls).toMatchObject([
      { type: "agent.tool_use", name: "bash" },
    ]);
    expect(patchBody.outputs.status).toBe("session.status_idle");
    expect(patchBody.outputs.stop_reason).toEqual({ type: "end_turn" });
    expect(patchBody.outputs.usage_metadata).toBeUndefined();
    expect(patchBody.extra.metadata.usage_metadata).toBeUndefined();

    const llmPatchBodies = patchBodies.filter(
      (body: any) => body.name === "ClaudeManagedAgentModelRequest",
    );
    expect(llmPatchBodies).toHaveLength(2);
    const llmPatchBody = llmPatchBodies[0];
    const finalLlmPatchBody = llmPatchBodies[1];
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
    expect(llmPatchBody?.outputs.messages).toEqual(
      expect.arrayContaining([
        {
          id: "sevt_tool",
          role: "assistant",
          content: [
            {
              type: "tool_use",
              id: "sevt_tool",
              name: "bash",
              input: { command: "python fibonacci.py" },
            },
          ],
          processed_at: "2026-04-01T00:00:01Z",
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
    expect(finalLlmPatchBody?.inputs.messages).toEqual(
      expect.arrayContaining([
        { role: "user", content: "Create fibonacci.txt" },
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
          role: "tool",
          tool_call_id: "sevt_tool",
          content: [{ type: "text", text: "ran script" }],
          is_error: false,
        },
      ]),
    );
    expect(finalLlmPatchBody?.outputs.messages).toMatchObject([
      { role: "assistant", content: "Created fibonacci.txt" },
    ]);
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
    await client.awaitPendingTraceBatches();

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
    await client.awaitPendingTraceBatches();

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
    await client.awaitPendingTraceBatches();

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
    expect(postBody.inputs.messages).toEqual([
      { role: "user", content: "Create fibonacci.txt" },
    ]);
    const sendPostCalls = callSpy.mock.calls.filter((call: any) => {
      if ((call[1] as any).method !== "POST") return false;
      const body = parseRequestBody((call[1] as any).body);
      return body.name === "ClaudeManagedAgentSendEvents";
    });
    expect(sendPostCalls).toHaveLength(0);
  });

  it("custom tools", async () => {
    const { client, callSpy } = mockClient();
    const [anthropic, session] = await createReplayableAnthropic(
      "./test_data/anthropic_managed_custom_tools.jsonl",
    );

    const wrappedClient = wrapAnthropic(anthropic, {
      client,
      tracingEnabled: true,
    });

    const stream = await wrappedClient.beta.sessions.events.stream(session.id);
    // consume stream
    for await (const _ of stream) {
      // noop
    }

    await client.awaitPendingTraceBatches();
    const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);

    const expected = asTree((run) => {
      run`ClaudeManagedAgent:3`(
        {
          run_type: "chain",
          inputs: {
            session_id: session.id,
            messages: [
              { role: "user", content: "What's the weather in Prague?" },
            ],
          },
          outputs: {
            messages: [
              {
                role: "assistant",
                content:
                  "It's currently **23°C and sunny** in Prague — a nice, warm day overall!",
              },
            ],
          },
        },
        run`ClaudeManagedAgentModelRequest:0`({
          run_type: "llm",
          inputs: {
            system:
              "You are a helpful coding assistant. Write clean, well-documented code.",
            messages: [
              { role: "user", content: "What's the weather in Prague?" },
            ],
          },
          outputs: {
            messages: [
              {
                role: "assistant",
                content: [
                  {
                    type: "tool_use",
                    name: "get_weather",
                    input: { location: "Prague" },
                  },
                ],
              },
            ],
          },
        }),
        run`get_weather:1`({
          run_type: "tool",
          inputs: {
            name: "get_weather",
            input: { location: "Prague" },
          },
          outputs: {
            content: [{ text: "It's 23°C and sunny in Prague.", type: "text" }],
          },
        }),
        run`ClaudeManagedAgentModelRequest:2`({
          run_type: "llm",
          inputs: {
            system:
              "You are a helpful coding assistant. Write clean, well-documented code.",
            messages: [
              { role: "user", content: "What's the weather in Prague?" },
              {
                role: "assistant",
                content: [
                  {
                    type: "tool_use",
                    name: "get_weather",
                    input: { location: "Prague" },
                  },
                ],
              },
              {
                role: "tool",
                content: [
                  { text: "It's 23°C and sunny in Prague.", type: "text" },
                ],
                is_error: false,
              },
            ],
          },
          outputs: {
            messages: [
              {
                role: "assistant",
                content:
                  "It's currently **23°C and sunny** in Prague — a nice, warm day overall!",
              },
            ],
          },
        }),
      );
    });

    expect(tree.nodes).toEqual(expect.arrayContaining(expected.nodes));
    expect(tree.edges).toEqual(expected.edges);
    expect(tree.data).toMatchObject(expected.data);
  });

  it("builtin tools", async () => {
    const { client, callSpy } = mockClient();
    const [anthropic, session] = await createReplayableAnthropic(
      "./test_data/anthropic_managed_builtin_tools.jsonl",
    );

    const wrappedClient = wrapAnthropic(anthropic, {
      client,
      tracingEnabled: true,
    });

    const stream = await wrappedClient.beta.sessions.events.stream(session.id);
    // consume stream
    for await (const _ of stream) {
      // noop
    }

    await client.awaitPendingTraceBatches();
    const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);

    const expected = asTree((run) => {
      run`ClaudeManagedAgent:3`(
        {
          run_type: "chain",
          inputs: {
            session_id: session.id,
            messages: [
              {
                role: "user",
                content: "Call 'date' to get the current date time",
              },
            ],
          },
          outputs: {
            messages: [
              {
                role: "assistant",
                content: [
                  {
                    type: "tool_use",
                    name: "bash",
                    input: { command: "date" },
                  },
                ],
              },
              {
                role: "assistant",
                content:
                  "The current date and time is:\n\n**Monday, July 6, 2026, 16:26:37 UTC**",
              },
            ],
          },
        },
        run`ClaudeManagedAgentModelRequest:0`({
          run_type: "llm",
          inputs: {
            system:
              "You are a helpful coding assistant. Write clean, well-documented code.",
            messages: [
              {
                role: "user",
                content: "Call 'date' to get the current date time",
              },
            ],
          },
          outputs: {
            messages: [
              {
                role: "assistant",
                content: [
                  {
                    type: "tool_use",
                    name: "bash",
                    input: { command: "date" },
                  },
                ],
              },
            ],
          },
        }),
        run`bash:1`({
          run_type: "tool",
          inputs: {
            name: "bash",
            input: { command: "date" },
          },
          outputs: {
            content: [{ text: "Mon Jul  6 16:26:37 UTC 2026\n", type: "text" }],
          },
        }),
        run`ClaudeManagedAgentModelRequest:2`({
          run_type: "llm",
          inputs: {
            system:
              "You are a helpful coding assistant. Write clean, well-documented code.",
            messages: [
              {
                role: "user",
                content: "Call 'date' to get the current date time",
              },
              {
                role: "assistant",
                content: [
                  {
                    type: "tool_use",
                    name: "bash",
                    input: { command: "date" },
                  },
                ],
              },
              {
                role: "tool",
                content: [
                  { text: "Mon Jul  6 16:26:37 UTC 2026\n", type: "text" },
                ],
                is_error: false,
              },
            ],
          },
          outputs: {
            messages: [
              {
                role: "assistant",
                content:
                  "The current date and time is:\n\n**Monday, July 6, 2026, 16:26:37 UTC**",
              },
            ],
          },
        }),
      );
    });

    expect(tree.nodes).toEqual(expect.arrayContaining(expected.nodes));
    expect(tree.edges).toEqual(expected.edges);
    expect(tree.data).toMatchObject(expected.data);
  });
});
