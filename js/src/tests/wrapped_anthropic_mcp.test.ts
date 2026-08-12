/* eslint-disable @typescript-eslint/no-explicit-any */
import { wrapAnthropic } from "../wrappers/anthropic.js";
import { SECRET_PLACEHOLDER } from "../anonymizer/index.js";
import { mockClient } from "./utils/mock_client.js";

const FAKE_TOKEN = "fake-token-for-tests-only";

function parseRequestBody(body: any) {
  // eslint-disable-next-line no-instanceof/no-instanceof
  return body instanceof Uint8Array
    ? JSON.parse(new TextDecoder().decode(body))
    : JSON.parse(body);
}

/** Stub provider, so input processing runs without a network call. */
function stubAnthropic(): any {
  const message = {
    id: "msg_stub",
    type: "message",
    role: "assistant",
    model: "claude-haiku-4-5",
    content: [{ type: "text", text: "hi" }],
    stop_reason: "end_turn",
    usage: { input_tokens: 1, output_tokens: 1 },
  };
  return {
    messages: {
      create: async () => message,
      stream: async () => {
        throw new Error("not used by these tests");
      },
    },
  };
}

/** The runs the SDK would have uploaded. */
function uploadedRuns(callSpy: any): any[] {
  return (callSpy.mock.calls as any[])
    .map(([, init]: any) => {
      try {
        return parseRequestBody(init?.body);
      } catch {
        return undefined;
      }
    })
    .filter(Boolean)
    .flatMap((body: any) => body?.post ?? body?.patch ?? [body])
    .filter((run: any) => run?.inputs);
}

async function traceCreate(
  params: Record<string, unknown>,
  requestOptions?: Record<string, unknown>,
) {
  const { client, callSpy } = mockClient();
  const patched = wrapAnthropic(stubAnthropic(), {
    client,
    tracingEnabled: true,
  });

  const args: unknown[] = [
    {
      model: "claude-haiku-4-5",
      max_tokens: 16,
      messages: [{ role: "user", content: "hi" }],
      ...params,
    },
  ];
  if (requestOptions !== undefined) args.push(requestOptions);

  await (patched.messages.create as any)(...args);

  const runs = uploadedRuns(callSpy);
  return { runs, wire: JSON.stringify(runs) };
}

/**
 * The traced provider params. A multi-argument call is recorded as
 * `{ args: [params, requestOptions] }` rather than as the params object.
 */
function tracedParams(run: any): any {
  return Array.isArray(run.inputs.args) ? run.inputs.args[0] : run.inputs;
}

const mcpServers = (extra: Record<string, unknown> = {}) => [
  {
    type: "url",
    url: "https://mcp.example.com/sse",
    name: "example",
    authorization_token: FAKE_TOKEN,
    ...extra,
  },
];

describe("mcp_servers credentials are masked before tracing", () => {
  test("authorization_token never reaches the uploaded run", async () => {
    const { runs, wire } = await traceCreate({ mcp_servers: mcpServers() });

    expect(wire).not.toContain(FAKE_TOKEN);
    const server = runs[0].inputs.mcp_servers[0];
    expect(server.authorization_token).toBe(SECRET_PLACEHOLDER);
    expect(server).toMatchObject({
      type: "url",
      url: "https://mcp.example.com/sse",
      name: "example",
    });
  });

  test("fields that are not explicitly allowed are masked too", async () => {
    const { runs, wire } = await traceCreate({
      mcp_servers: mcpServers({ future_secret: "s3cret" }),
    });

    expect(wire).not.toContain("s3cret");
    expect(runs[0].inputs.mcp_servers[0].future_secret).toBe(
      SECRET_PLACEHOLDER,
    );
  });

  test("the caller's params are left intact for the API call", async () => {
    const servers = mcpServers();
    await traceCreate({ mcp_servers: servers });

    expect(servers[0].authorization_token).toBe(FAKE_TOKEN);
  });

  test("masking also applies when a system prompt is present", async () => {
    const { runs, wire } = await traceCreate({
      system: "be brief",
      mcp_servers: mcpServers(),
    });

    expect(wire).not.toContain(FAKE_TOKEN);
    expect(runs[0].inputs.mcp_servers[0].authorization_token).toBe(
      SECRET_PLACEHOLDER,
    );
    expect(runs[0].inputs.messages[0]).toEqual({
      role: "system",
      content: "be brief",
    });
    expect(runs[0].inputs.system).toBeUndefined();
  });

  test.each([
    ["a non-array value", "not-an-array"],
    ["null entries", [null]],
    ["nested arrays", [["nested"]]],
    ["an empty list", []],
  ])("tolerates %s", async (_label, servers) => {
    const { runs } = await traceCreate({ mcp_servers: servers });

    expect(runs[0].inputs.mcp_servers).toEqual(servers);
  });
});

describe("masking survives every argument shape", () => {
  // A second argument makes `traceable` record the call as
  // `{ args: [params, requestOptions] }`, which a top-level-key lookup misses.
  test.each([
    ["langsmithExtra only", { langsmithExtra: { metadata: { foo: "bar" } } }],
    ["an empty options object", {}],
    ["real request options", { timeout: 5000 }],
  ])("masks mcp_servers when called with %s", async (_label, options) => {
    const { runs, wire } = await traceCreate(
      { mcp_servers: mcpServers() },
      options,
    );

    expect(wire).not.toContain(FAKE_TOKEN);
    expect(tracedParams(runs[0]).mcp_servers[0].authorization_token).toBe(
      SECRET_PLACEHOLDER,
    );
  });

  test("masks credentials in the request options themselves", async () => {
    const { runs, wire } = await traceCreate(
      {},
      { headers: { Authorization: `Bearer ${FAKE_TOKEN}` } },
    );

    expect(wire).not.toContain(FAKE_TOKEN);
    expect(runs[0].inputs.args[1].headers).toEqual({
      Authorization: SECRET_PLACEHOLDER,
    });
  });

  test("the caller's arguments are left intact for the API call", async () => {
    const servers = mcpServers();
    const options = { headers: { Authorization: `Bearer ${FAKE_TOKEN}` } };

    await traceCreate({ mcp_servers: servers }, options);

    expect(servers[0].authorization_token).toBe(FAKE_TOKEN);
    expect(options.headers.Authorization).toBe(`Bearer ${FAKE_TOKEN}`);
  });
});

describe("per-request transport overrides are masked", () => {
  test.each(["extra_headers", "extra_body", "extra_query"])(
    "%s keeps its key names but not its values",
    async (key) => {
      const { runs, wire } = await traceCreate({
        [key]: { Authorization: `Bearer ${FAKE_TOKEN}` },
      });

      expect(wire).not.toContain(FAKE_TOKEN);
      expect(runs[0].inputs[key]).toEqual({
        Authorization: SECRET_PLACEHOLDER,
      });
    },
  );
});
