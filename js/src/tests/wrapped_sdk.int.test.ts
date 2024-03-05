import { jest } from "@jest/globals";
import { Anthropic } from "@anthropic-ai/sdk";
import { wrapSDK } from "../wrappers.js";
import { Client } from "../client.js";

test.concurrent("chat.completions", async () => {
  const client = new Client();
  const callSpy = jest
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .spyOn((client as any).caller, "call")
    .mockResolvedValue({ ok: true, text: () => "" });

  const originalClient = new Anthropic();
  const patchedClient = wrapSDK(new Anthropic(), { client });

  // invoke
  const original = await originalClient.messages.create({
    messages: [
      {
        role: "user",
        content: `What is 1 + 1? Respond only with "2" and nothing else.`,
      },
    ],
    model: "claude-2.1",
    max_tokens: 1024,
  });

  const patched = await patchedClient.messages.create({
    messages: [
      {
        role: "user",
        content: `What is 1 + 1? Respond only with "2" and nothing else.`,
      },
    ],
    model: "claude-2.1",
    max_tokens: 1024,
  });

  expect(patched.content).toEqual(original.content);

  // stream
  const originalStream = await originalClient.messages.create({
    messages: [
      {
        role: "user",
        content: `What is 1 + 1? Respond only with "2" and nothing else.`,
      },
    ],
    model: "claude-2.1",
    max_tokens: 1024,
    stream: true,
  });

  const originalChunks = [];
  for await (const chunk of originalStream) {
    if (chunk.type === "message_delta") {
      originalChunks.push(chunk.delta);
    }
  }

  const patchedStream = await patchedClient.messages.create({
    messages: [
      {
        role: "user",
        content: `What is 1 + 1? Respond only with "2" and nothing else.`,
      },
    ],
    model: "claude-2.1",
    max_tokens: 1024,
    stream: true,
  });

  const patchedChunks = [];
  for await (const chunk of patchedStream) {
    if (chunk.type === "message_delta") {
      patchedChunks.push(chunk.delta);
    }
  }

  expect(patchedChunks).toEqual(originalChunks);
  for (const call of callSpy.mock.calls) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    expect((call[2] as any)["method"]).toBe("POST");
  }
});
