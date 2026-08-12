/* eslint-disable @typescript-eslint/no-explicit-any */
import { wrapOpenAI } from "../wrappers/openai.js";
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
function stubOpenAI(): any {
  const response = { id: "resp_stub", output: [], usage: {} };
  return {
    responses: {
      create: async () => response,
      parse: async () => response,
    },
    chat: { completions: { create: async () => ({ id: "cc_stub" }) } },
    completions: { create: async () => ({ id: "c_stub" }) },
    beta: { chat: { completions: {} } },
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

async function traceResponse(
  params: Record<string, unknown>,
  requestOptions?: Record<string, unknown>,
) {
  const { client, callSpy } = mockClient();
  const patched: any = wrapOpenAI(stubOpenAI(), {
    client,
    tracingEnabled: true,
  });

  const args: unknown[] = [{ model: "gpt-5", input: "hi", ...params }];
  if (requestOptions !== undefined) args.push(requestOptions);

  await patched.responses.create(...args);

  const runs = uploadedRuns(callSpy);
  return { runs, wire: JSON.stringify(runs) };
}

/** Traced provider params; a multi-argument call is recorded as `{ args: [...] }`. */
function tracedParams(run: any): any {
  return Array.isArray(run.inputs.args) ? run.inputs.args[0] : run.inputs;
}

const mcpTool = (extra: Record<string, unknown> = {}) => [
  {
    type: "mcp",
    server_label: "example",
    server_url: "https://mcp.example.com/sse",
    authorization: FAKE_TOKEN,
    headers: { Authorization: `Bearer ${FAKE_TOKEN}` },
    ...extra,
  },
];

describe("hosted MCP tool credentials are masked before tracing", () => {
  test("authorization and headers never reach the uploaded run", async () => {
    const { runs, wire } = await traceResponse({ tools: mcpTool() });

    expect(wire).not.toContain(FAKE_TOKEN);
    const tool = runs[0].inputs.tools[0];
    expect(tool.authorization).toBe(SECRET_PLACEHOLDER);
    expect(tool.headers).toBe(SECRET_PLACEHOLDER);
    expect(tool).toMatchObject({
      type: "mcp",
      server_label: "example",
      server_url: "https://mcp.example.com/sse",
    });
  });

  test("fields that are not explicitly allowed are masked too", async () => {
    const { runs, wire } = await traceResponse({
      tools: mcpTool({ future_secret: "s3cret" }),
    });

    expect(wire).not.toContain("s3cret");
    expect(runs[0].inputs.tools[0].future_secret).toBe(SECRET_PLACEHOLDER);
  });

  test("the caller's params are left intact for the API call", async () => {
    const tools = mcpTool();
    await traceResponse({ tools });

    expect(tools[0].authorization).toBe(FAKE_TOKEN);
    expect(tools[0].headers).toEqual({
      Authorization: `Bearer ${FAKE_TOKEN}`,
    });
  });

  test("function tools keep their schema", async () => {
    const tools = [
      {
        type: "function",
        name: "get_weather",
        parameters: {
          type: "object",
          properties: { city: { type: "string" } },
        },
      },
    ];
    const { runs } = await traceResponse({ tools });

    expect(runs[0].inputs.tools[0]).toEqual(tools[0]);
  });

  test("masking survives a second argument", async () => {
    const { runs, wire } = await traceResponse(
      { tools: mcpTool() },
      { langsmithExtra: { metadata: { foo: "bar" } } },
    );

    expect(wire).not.toContain(FAKE_TOKEN);
    expect(tracedParams(runs[0]).tools[0].authorization).toBe(
      SECRET_PLACEHOLDER,
    );
  });

  test("credentials in the request options are masked", async () => {
    const { runs, wire } = await traceResponse(
      {},
      { headers: { Authorization: `Bearer ${FAKE_TOKEN}` } },
    );

    expect(wire).not.toContain(FAKE_TOKEN);
    expect(runs[0].inputs.args[1].headers).toEqual({
      Authorization: SECRET_PLACEHOLDER,
    });
  });

  test.each([
    ["a non-array value", "not-an-array"],
    ["null entries", [null]],
    ["nested arrays", [["nested"]]],
    ["an empty list", []],
  ])("tolerates %s", async (_label, tools) => {
    const { runs } = await traceResponse({ tools });

    expect(runs[0].inputs.tools).toEqual(tools);
  });
});

describe("per-request transport overrides are masked", () => {
  test.each(["extra_headers", "extra_body", "extra_query"])(
    "%s keeps its key names but not its values",
    async (key) => {
      const { runs, wire } = await traceResponse({
        [key]: { Authorization: `Bearer ${FAKE_TOKEN}` },
      });

      expect(wire).not.toContain(FAKE_TOKEN);
      expect(runs[0].inputs[key]).toEqual({
        Authorization: SECRET_PLACEHOLDER,
      });
    },
  );
});

describe("invocation params metadata stays clean", () => {
  test("tools are not copied into ls_invocation_params", async () => {
    const { runs } = await traceResponse({ tools: mcpTool() });

    const metadata = runs[0].extra.metadata;
    expect(JSON.stringify(metadata)).not.toContain(FAKE_TOKEN);
    expect(metadata.ls_invocation_params.tools).toBeUndefined();
  });
});
