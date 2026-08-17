/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, test, expect } from "@jest/globals";
import { wrapClaudeAgentSDK } from "../experimental/anthropic/index.js";
import { SECRET_PLACEHOLDER } from "../anonymizer/index.js";
import { mockClient } from "./utils/mock_client.js";

const FAKE_TOKEN = "fake-token-for-tests-only";

function parseRequestBody(body: any) {
  // eslint-disable-next-line no-instanceof/no-instanceof
  return body instanceof Uint8Array
    ? JSON.parse(new TextDecoder().decode(body))
    : JSON.parse(body);
}

/** Stub Claude Agent SDK, so input processing runs without a subprocess. */
function stubSDK(): any {
  return {
    query: (_params: any) =>
      (async function* () {
        yield { type: "system", session_id: "session_1" };
        yield {
          type: "assistant",
          message: { role: "assistant", content: "hi" },
        };
        yield { type: "result", num_turns: 1 };
      })(),
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

async function traceQuery(options: Record<string, unknown>) {
  const { client, callSpy } = mockClient();
  const wrapped: any = wrapClaudeAgentSDK(stubSDK(), {
    client,
    tracingEnabled: true,
  });

  for await (const _ of wrapped.query({ prompt: "hi", options })) {
    // drain
  }

  const runs = uploadedRuns(callSpy);
  return { runs, wire: JSON.stringify(runs) };
}

describe("Claude Agent SDK option credentials are masked before tracing", () => {
  test("env never reaches the uploaded run", async () => {
    const { runs, wire } = await traceQuery({
      model: "claude-sonnet-4-5",
      env: { ANTHROPIC_API_KEY: FAKE_TOKEN, PATH: "/usr/bin" },
    });

    expect(wire).not.toContain(FAKE_TOKEN);
    const options = runs[0].inputs.options;
    expect(options.env).toEqual({
      ANTHROPIC_API_KEY: SECRET_PLACEHOLDER,
      PATH: SECRET_PLACEHOLDER,
    });
    expect(options.model).toBe("claude-sonnet-4-5");
  });

  test("extraArgs is masked", async () => {
    const { runs, wire } = await traceQuery({
      extraArgs: { "some-flag": FAKE_TOKEN },
    });

    expect(wire).not.toContain(FAKE_TOKEN);
    expect(runs[0].inputs.options.extraArgs).toEqual({
      "some-flag": SECRET_PLACEHOLDER,
    });
  });

  test("mcpServers are still reduced to name and type", async () => {
    const { runs, wire } = await traceQuery({
      mcpServers: {
        example: {
          type: "http",
          name: "example",
          url: "https://mcp.example.com/mcp",
          headers: { Authorization: `Bearer ${FAKE_TOKEN}` },
        },
      },
    });

    expect(wire).not.toContain(FAKE_TOKEN);
    expect(runs[0].inputs.options.mcpServers.example).toEqual({
      name: "example",
      type: "http",
    });
  });

  test("the caller's options are left intact for the SDK call", async () => {
    const env = { ANTHROPIC_API_KEY: FAKE_TOKEN };
    const options = { model: "claude-sonnet-4-5", env };

    await traceQuery(options);

    expect(env.ANTHROPIC_API_KEY).toBe(FAKE_TOKEN);
    expect(options.env).toBe(env);
  });

  test("non-secret options are preserved", async () => {
    const { runs } = await traceQuery({
      model: "claude-sonnet-4-5",
      maxTurns: 3,
      allowedTools: ["Read", "Grep"],
    });

    const options = runs[0].inputs.options;
    expect(options.model).toBe("claude-sonnet-4-5");
    expect(options.maxTurns).toBe(3);
    expect(options.allowedTools).toEqual(["Read", "Grep"]);
  });

  test("tolerates absent options", async () => {
    const { client, callSpy } = mockClient();
    const wrapped: any = wrapClaudeAgentSDK(stubSDK(), {
      client,
      tracingEnabled: true,
    });

    for await (const _ of wrapped.query({ prompt: "hi" })) {
      // drain
    }

    expect(uploadedRuns(callSpy).length).toBeGreaterThan(0);
  });
});
