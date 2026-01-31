/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable no-process-env */

import { GoogleGenAI } from "@google/genai";
import { wrapGemini } from "../wrappers/gemini.js";
import { mockClient } from "./utils/mock_client.js";

function parseRequestBody(body: any) {
  // eslint-disable-next-line no-instanceof/no-instanceof
  return body instanceof Uint8Array
    ? JSON.parse(new TextDecoder().decode(body))
    : JSON.parse(body);
}

test("wrapGemini should return type compatible with GoogleGenAI", async () => {
  const originalClient = new GoogleGenAI({
    apiKey: process.env.GEMINI_API_KEY || "test-key",
  });

  const wrappedClient = wrapGemini(originalClient);

  expect(wrappedClient).toBeDefined();
});

test("models.generateContent non-streaming", async () => {
  const { client, callSpy } = mockClient();

  const originalClient = new GoogleGenAI({
    apiKey: process.env.GEMINI_API_KEY || "test-key",
  });

  const patchedClient = wrapGemini(originalClient, {
    client,
    tracingEnabled: true,
  });

  const response = await patchedClient.models.generateContent({
    model: "gemini-2.5-flash",
    contents: "Say 'hello'",
  });

  await client.awaitPendingTraceBatches();

  // TypeScript knows response should have certain properties
  // Let's verify the basic response structure
  expect(response).toBeDefined();

  // Verify tracing was called
  expect(callSpy.mock.calls.length).toBeGreaterThanOrEqual(1);

  // Verify we made POST (create run) and PATCH (update run) calls
  for (const call of callSpy.mock.calls) {
    expect(["POST", "PATCH"]).toContain((call[1] as any)["method"]);
  }

  callSpy.mockClear();
});

test("models.generateContentStream streaming", async () => {
  const { client, callSpy } = mockClient();

  const originalClient = new GoogleGenAI({
    apiKey: process.env.GEMINI_API_KEY || "test-key",
  });

  const patchedClient = wrapGemini(originalClient, {
    client,
    tracingEnabled: true,
  });

  // generateContentStream returns an async iterable
  // Type: AsyncGenerator<Chunk> or AsyncIterable<Chunk>
  const stream = await patchedClient.models.generateContentStream({
    model: "gemini-2.5-flash",
    contents: "Count to 3",
  });

  // Collect chunks using for-await-of (async iteration)
  const chunks: any[] = [];
  for await (const chunk of stream) {
    chunks.push(chunk);
  }

  // Verify we got some chunks
  expect(chunks.length).toBeGreaterThan(0);

  await client.awaitPendingTraceBatches();

  // Verify tracing was called
  expect(callSpy.mock.calls.length).toBeGreaterThanOrEqual(1);

  callSpy.mockClear();
});

test("wrapping same instance should throw", async () => {
  const wrapped = wrapGemini(
    new GoogleGenAI({
      apiKey: process.env.GEMINI_API_KEY || "test-key",
    })
  );
  expect(() => wrapGemini(wrapped)).toThrowError(/already been wrapped/i);
});

test("should trace calls to langsmith", async () => {
  const { client, callSpy } = mockClient();

  const geminiClient = wrapGemini(
    new GoogleGenAI({
      apiKey: process.env.GEMINI_API_KEY || "test-key",
    }),
    {
      client,
      tracingEnabled: true,
    }
  );

  await geminiClient.models.generateContent({
    model: "gemini-2.5-flash",
    contents: "Say 'hello'",
  });

  await client.awaitPendingTraceBatches();

  expect(callSpy.mock.calls.length).toBeGreaterThan(0);

  const firstCall = callSpy.mock.calls[0];
  const request = firstCall[1] as any;
  const body = parseRequestBody(request.body);

  expect(body.name).toBeDefined();
  expect(body.inputs).toBeDefined();
  expect(body.run_type).toBe("llm");

  callSpy.mockClear();
});

test("should extract usage metadata in outputs", async () => {
  const { client, callSpy } = mockClient();

  const geminiClient = wrapGemini(
    new GoogleGenAI({
      apiKey: process.env.GEMINI_API_KEY || "test-key",
    }),
    {
      client,
      tracingEnabled: true,
    }
  );

  await geminiClient.models.generateContent({
    model: "gemini-2.5-flash",
    contents: "Say hello world",
  });

  await client.awaitPendingTraceBatches();

  expect(callSpy.mock.calls.length).toBeGreaterThan(0);

  // Find any call with usage_metadata in outputs
  let usageMetadata;
  for (const call of callSpy.mock.calls) {
    const request = call[1] as any;
    const body = parseRequestBody(request.body);

    if (body.outputs && body.outputs.usage_metadata) {
      usageMetadata = body.outputs.usage_metadata;
      break;
    }
  }

  // Verify usage_metadata exists in outputs
  expect(usageMetadata).toBeDefined();
  expect(usageMetadata.input_tokens).toBeGreaterThan(0);
  expect(usageMetadata.output_tokens).toBeGreaterThan(0);
  expect(usageMetadata.total_tokens).toBeGreaterThan(0);

  callSpy.mockClear();
});

test("should extract usage metadata in extra.metadata.usage_metadata", async () => {
  const { client, callSpy } = mockClient();

  const geminiClient = wrapGemini(
    new GoogleGenAI({
      apiKey: process.env.GEMINI_API_KEY || "test-key",
    }),
    {
      client,
      tracingEnabled: true,
    }
  );

  await geminiClient.models.generateContent({
    model: "gemini-2.5-flash",
    contents: "Say hello world",
  });

  await client.awaitPendingTraceBatches();

  expect(callSpy.mock.calls.length).toBeGreaterThan(0);

  // Find any call with usage_metadata in extra.metadata.usage_metadata
  let usageMetadata;
  for (const call of callSpy.mock.calls) {
    const request = call[1] as any;
    const body = parseRequestBody(request.body);

    if (body.extra?.metadata?.usage_metadata) {
      usageMetadata = body.extra.metadata.usage_metadata;
      break;
    }
  }

  // Verify usage_metadata exists in extra.metadata
  expect(usageMetadata).toBeDefined();
  expect(usageMetadata.input_tokens).toBeGreaterThan(0);
  expect(usageMetadata.output_tokens).toBeGreaterThan(0);
  expect(usageMetadata.total_tokens).toBeGreaterThan(0);

  callSpy.mockClear();
});

test("should handle function calling", async () => {
  const { client, callSpy } = mockClient();

  const geminiClient = wrapGemini(
    new GoogleGenAI({
      apiKey: process.env.GEMINI_API_KEY || "test-key",
    }),
    {
      client,
      tracingEnabled: true,
    }
  );

  const toolDeclaration = {
    name: "get_weather",
    parametersJsonSchema: {
      type: "object",
      properties: {
        location: { type: "string" },
      },
      required: ["location"],
    },
  };

  const response = await geminiClient.models.generateContent({
    model: "gemini-2.5-flash",
    contents: "What's the weather in San Francisco?",
    config: {
      tools: [{ functionDeclarations: [toolDeclaration] }],
    },
  });

  expect(response).toBeDefined();

  await client.awaitPendingTraceBatches();
  expect(callSpy.mock.calls.length).toBeGreaterThan(0);

  // Find the PATCH call
  const patchCalls = callSpy.mock.calls.filter(
    (call) => (call[1] as any).method === "PATCH"
  );

  if (patchCalls.length > 0) {
    const lastPatchCall = patchCalls[patchCalls.length - 1];
    const requestBody = (lastPatchCall[1] as any).body;
    const body =
      typeof requestBody === "string" ? JSON.parse(requestBody) : requestBody;

    // If function was called, verify it's in outputs
    if (body.outputs?.tool_calls) {
      expect(Array.isArray(body.outputs.tool_calls)).toBe(true);
      expect(body.outputs.tool_calls.length).toBeGreaterThan(0);
    }
  }

  callSpy.mockClear();
});

test("should handle image input", async () => {
  const { client, callSpy } = mockClient();
  const geminiClient = wrapGemini(
    new GoogleGenAI({
      apiKey: process.env.GEMINI_API_KEY || "test-key",
    }),
    {
      client,
      tracingEnabled: true,
    }
  );

  // Simple 1x1 red pixel PNG in base64
  const redPixelBase64 =
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg==";

  const response = await geminiClient.models.generateContent({
    model: "gemini-2.5-flash-image",
    contents: [
      {
        role: "user",
        parts: [
          {
            text: "What do you see in this image? Just say 'red pixel' if you see it.",
          },
          {
            inlineData: {
              mimeType: "image/png",
              data: redPixelBase64,
            },
          },
        ],
      },
    ],
  });

  await client.awaitPendingTraceBatches();

  expect(callSpy.mock.calls.length).toBeGreaterThan(0);
  expect(response).toBeDefined();
  expect(response.text).toBeDefined();

  // Verify the image was included in the traced inputs
  let foundImageInput = false;
  for (const call of callSpy.mock.calls) {
    const request = call[1] as any;
    const body = parseRequestBody(request.body);

    if (body.inputs) {
      const inputStr = JSON.stringify(body.inputs);
      if (inputStr.includes("inlineData") || inputStr.includes("image/png")) {
        foundImageInput = true;
        break;
      }
    }
  }

  expect(foundImageInput).toBe(true);

  callSpy.mockClear();
});

test("should handle image generation output", async () => {
  const { client, callSpy } = mockClient();
  const geminiClient = wrapGemini(
    new GoogleGenAI({
      apiKey: process.env.GEMINI_API_KEY || "test-key",
    }),
    {
      client,
      tracingEnabled: true,
    }
  );

  // Use gemini-2.5-flash-image model which supports image generation
  const response = await geminiClient.models.generateContent({
    model: "gemini-2.5-flash-image",
    contents: [
      {
        role: "user",
        parts: [{ text: "Generate a simple red square" }],
      },
    ],
    config: {
      responseModalities: ["Image"],
    },
  });

  await client.awaitPendingTraceBatches();

  expect(callSpy.mock.calls.length).toBeGreaterThan(0);
  expect(response).toBeDefined();

  // Check if response contains image data
  if (response.candidates?.[0]?.content?.parts) {
    const parts = response.candidates[0].content.parts;
    const hasImage = parts.some(
      (part: any) =>
        part.inlineData?.mimeType?.startsWith("image/") ||
        part.fileData?.mimeType?.startsWith("image/")
    );
    expect(hasImage).toBe(true);
  }

  // Verify the image output is traced
  let foundImageOutput = false;
  for (const call of callSpy.mock.calls) {
    const request = call[1] as any;
    const body = parseRequestBody(request.body);

    if (body.outputs) {
      const outputStr = JSON.stringify(body.outputs);
      if (outputStr.includes("inlineData") || outputStr.includes("image/")) {
        foundImageOutput = true;
        break;
      }
    }
  }

  expect(foundImageOutput).toBe(true);

  callSpy.mockClear();
});

test("prepopulated invocation params are passed through", async () => {
  const { client, callSpy } = mockClient();

  const wrappedClient = wrapGemini(
    new GoogleGenAI({
      apiKey: process.env.GEMINI_API_KEY || "test-key",
    }),
    {
      client,
      tracingEnabled: true,
      metadata: {
        ls_invocation_params: { env: "test", team: "qa" },
        custom_key: "custom_value",
        version: "1.0.0",
      },
    }
  );

  await wrappedClient.models.generateContent({
    model: "gemini-2.5-flash",
    contents: "Say 'hello'",
  });

  await new Promise((resolve) => setTimeout(resolve, 1000));

  const postCalls = callSpy.mock.calls.filter(
    (call) => (call[1] as any).method === "POST"
  );

  expect(postCalls.length).toBeGreaterThan(0);

  // Get the POST call with run data (should have extra.metadata)
  const postBody = parseRequestBody((postCalls[0][1] as any).body);

  // ls_invocation_params is in metadata, not in extra.invocation_params
  const metadata = postBody.extra?.metadata;
  const lsInvocationParams = metadata?.ls_invocation_params;

  // Should have prepopulated params (Gemini doesn't extract runtime params)
  expect(lsInvocationParams?.env).toBe("test");
  expect(lsInvocationParams?.team).toBe("qa");

  // Check that other metadata keys are preserved
  expect(metadata?.custom_key).toBe("custom_value");
  expect(metadata?.version).toBe("1.0.0");

  callSpy.mockClear();
});
