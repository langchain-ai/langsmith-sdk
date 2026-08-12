/* eslint-disable @typescript-eslint/no-explicit-any */
import { wrapGemini } from "../wrappers/gemini.js";
import { SECRET_PLACEHOLDER } from "../anonymizer/index.js";
import { mockClient } from "./utils/mock_client.js";

const FAKE_TOKEN = "fake-token-for-tests-only";

const authHeaders = () => ({ Authorization: `Bearer ${FAKE_TOKEN}` });

function parseRequestBody(body: any) {
  // eslint-disable-next-line no-instanceof/no-instanceof
  return body instanceof Uint8Array
    ? JSON.parse(new TextDecoder().decode(body))
    : JSON.parse(body);
}

/** Stub provider, so input processing runs without a network call. */
function stubGemini(): any {
  const response = {
    candidates: [{ content: { role: "model", parts: [{ text: "hi" }] } }],
    usageMetadata: { promptTokenCount: 1, candidatesTokenCount: 1 },
  };
  return {
    models: {
      generateContent: async () => response,
      generateContentStream: async () => response,
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

async function traceGenerate(params: Record<string, unknown>) {
  const { client, callSpy } = mockClient();
  const patched: any = wrapGemini(stubGemini(), {
    client,
    tracingEnabled: true,
  });

  await patched.models.generateContent({
    model: "gemini-2.5-flash",
    contents: "hi",
    ...params,
  });

  const runs = uploadedRuns(callSpy);
  return { runs, wire: JSON.stringify(runs) };
}

describe("config credentials are masked before tracing", () => {
  test("httpOptions credentials never reach the uploaded run", async () => {
    const { runs, wire } = await traceGenerate({
      config: {
        temperature: 0.5,
        httpOptions: {
          headers: authHeaders(),
          baseUrl: "https://generativelanguage.googleapis.com",
          timeout: 30,
        },
      },
    });

    expect(wire).not.toContain(FAKE_TOKEN);
    const httpOptions = runs[0].inputs.config.httpOptions;
    expect(httpOptions.headers).toBe(SECRET_PLACEHOLDER);
    expect(httpOptions.baseUrl).toBe(
      "https://generativelanguage.googleapis.com",
    );
    expect(httpOptions.timeout).toBe(30);
    expect(runs[0].inputs.config.temperature).toBe(0.5);
  });

  test("httpOptions fields that are not explicitly allowed are masked", async () => {
    const { runs } = await traceGenerate({
      config: { httpOptions: { futureSecret: "s3cret" } },
    });

    expect(runs[0].inputs.config.httpOptions.futureSecret).toBe(
      SECRET_PLACEHOLDER,
    );
  });

  test("MCP server transport headers are masked, url survives", async () => {
    const { runs, wire } = await traceGenerate({
      config: {
        tools: [
          {
            mcpServers: [
              {
                name: "example",
                streamableHttpTransport: {
                  url: "https://mcp.example.com/mcp",
                  headers: authHeaders(),
                },
              },
            ],
          },
        ],
      },
    });

    expect(wire).not.toContain(FAKE_TOKEN);
    const transport =
      runs[0].inputs.config.tools[0].mcpServers[0].streamableHttpTransport;
    expect(transport.headers).toBe(SECRET_PLACEHOLDER);
    expect(transport.url).toBe("https://mcp.example.com/mcp");
  });

  test("transport fields that are not explicitly allowed are masked", async () => {
    const { runs } = await traceGenerate({
      config: {
        tools: [
          {
            mcpServers: [
              {
                streamableHttpTransport: { url: "u", futureSecret: "s3cret" },
              },
            ],
          },
        ],
      },
    });

    const transport =
      runs[0].inputs.config.tools[0].mcpServers[0].streamableHttpTransport;
    expect(transport.futureSecret).toBe(SECRET_PLACEHOLDER);
    expect(transport.url).toBe("u");
  });

  test("googleMaps authConfig is masked", async () => {
    const { runs, wire } = await traceGenerate({
      config: {
        tools: [
          {
            googleMaps: {
              authConfig: { apiKeyConfig: { apiKeyString: FAKE_TOKEN } },
              enableWidget: true,
            },
          },
        ],
      },
    });

    expect(wire).not.toContain(FAKE_TOKEN);
    const googleMaps = runs[0].inputs.config.tools[0].googleMaps;
    expect(googleMaps.authConfig).toEqual({
      apiKeyConfig: SECRET_PLACEHOLDER,
    });
    expect(googleMaps.enableWidget).toBe(true);
  });

  test.each(["apiAuth", "authConfig"])(
    "retrieval %s is masked",
    async (key) => {
      const { runs, wire } = await traceGenerate({
        config: {
          tools: [
            {
              retrieval: {
                externalApi: {
                  [key]: { apiKeyConfig: { apiKeyString: FAKE_TOKEN } },
                  apiSpec: "SIMPLE_SEARCH",
                },
              },
            },
          ],
        },
      });

      expect(wire).not.toContain(FAKE_TOKEN);
      const externalApi = runs[0].inputs.config.tools[0].retrieval.externalApi;
      expect(externalApi[key]).toEqual({ apiKeyConfig: SECRET_PLACEHOLDER });
      expect(externalApi.apiSpec).toBe("SIMPLE_SEARCH");
    },
  );

  test.each(["exaAiSearch", "parallelAiSearch"])(
    "%s apiKey is masked",
    async (tool) => {
      const { runs, wire } = await traceGenerate({
        config: {
          tools: [{ [tool]: { apiKey: FAKE_TOKEN, customConfigs: { a: 1 } } }],
        },
      });

      expect(wire).not.toContain(FAKE_TOKEN);
      expect(runs[0].inputs.config.tools[0][tool].apiKey).toBe(
        SECRET_PLACEHOLDER,
      );
      expect(runs[0].inputs.config.tools[0][tool].customConfigs).toEqual({
        a: 1,
      });
    },
  );

  test("functionDeclarations schemas are left intact", async () => {
    const tools = [
      {
        functionDeclarations: [
          {
            name: "send_request",
            parameters: {
              type: "object",
              properties: {
                url: { type: "string" },
                headers: { type: "object" },
                apiKey: { type: "string" },
              },
            },
          },
        ],
      },
    ];

    const { runs } = await traceGenerate({ config: { tools } });

    expect(runs[0].inputs.config.tools).toEqual(tools);
  });

  test.each(["responseSchema", "responseJsonSchema"])(
    "%s is left intact",
    async (key) => {
      const schema = {
        type: "object",
        properties: { headers: { type: "object" } },
      };

      const { runs } = await traceGenerate({ config: { [key]: schema } });

      expect(runs[0].inputs.config[key]).toEqual(schema);
    },
  );

  test("unknown tool variants are left intact", async () => {
    const tools = [
      { futureTool: { headers: { type: "object" }, apiKey: "shape" } },
    ];

    const { runs } = await traceGenerate({ config: { tools } });

    expect(runs[0].inputs.config.tools).toEqual(tools);
  });

  test("the caller's config is left intact for the API call", async () => {
    const headers = authHeaders();
    const config = { httpOptions: { headers } };

    await traceGenerate({ config });

    expect(headers.Authorization).toBe(`Bearer ${FAKE_TOKEN}`);
    expect(config.httpOptions.headers).toBe(headers);
  });

  test("non-secret config is preserved", async () => {
    const config = { temperature: 0.5, maxOutputTokens: 100, topK: 4 };
    const { runs } = await traceGenerate({ config });

    expect(runs[0].inputs.config).toEqual(config);
  });

  test("user content is not walked", async () => {
    const { wire } = await traceGenerate({
      contents: [
        {
          role: "user",
          parts: [{ text: "call it with headers: {'apiKey': 'abc'}" }],
        },
      ],
    });

    expect(wire).toContain("abc");
  });

  test.each([
    ["null", null],
    ["a string", "not-an-object"],
    ["a number", 42],
  ])("tolerates a config that is %s", async (_label, config) => {
    const { runs } = await traceGenerate({ config });

    if (config == null) {
      expect(runs[0].inputs.config ?? null).toBeNull();
    } else {
      expect(runs[0].inputs.config).toEqual(config);
    }
  });

  test("tolerates a non-array tools value", async () => {
    const { runs } = await traceGenerate({ config: { tools: "not-an-array" } });

    expect(runs[0].inputs.config.tools).toBe("not-an-array");
  });
});

describe("invocation params metadata stays clean", () => {
  test("config is not copied into ls_invocation_params", async () => {
    const { runs } = await traceGenerate({
      config: { httpOptions: { headers: authHeaders() } },
    });

    expect(JSON.stringify(runs[0].extra.metadata)).not.toContain(FAKE_TOKEN);
  });
});
