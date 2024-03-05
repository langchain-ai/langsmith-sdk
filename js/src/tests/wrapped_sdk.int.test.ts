import { jest } from "@jest/globals";
import { OpenAI } from "openai";
import { wrapSDK } from "../wrappers.js";
import { Client } from "../client.js";

test.concurrent("chat.completions", async () => {
  const client = new Client();
  const callSpy = jest
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .spyOn((client as any).caller, "call")
    .mockResolvedValue({ ok: true, text: () => "" });

  const originalClient = new OpenAI();
  const patchedClient = wrapSDK(new OpenAI(), { client });

  // invoke
  const original = await originalClient.chat.completions.create({
    messages: [{ role: "user", content: `Say 'foo'` }],
    temperature: 0,
    seed: 42,
    model: "gpt-3.5-turbo",
  });

  const patched = await patchedClient.chat.completions.create({
    messages: [{ role: "user", content: `Say 'foo'` }],
    temperature: 0,
    seed: 42,
    model: "gpt-3.5-turbo",
  });

  expect(patched.choices).toEqual(original.choices);

  // stream
  const originalStream = await originalClient.chat.completions.create({
    messages: [{ role: "user", content: `Say 'foo'` }],
    temperature: 0,
    seed: 42,
    model: "gpt-3.5-turbo",
    stream: true,
  });

  const originalChoices = [];
  for await (const chunk of originalStream) {
    originalChoices.push(chunk.choices);
  }

  const patchedStream = await patchedClient.chat.completions.create({
    messages: [{ role: "user", content: `Say 'foo'` }],
    temperature: 0,
    seed: 42,
    model: "gpt-3.5-turbo",
    stream: true,
  });

  const patchedChoices = [];
  for await (const chunk of patchedStream) {
    patchedChoices.push(chunk.choices);
  }

  expect(patchedChoices).toEqual(originalChoices);
  for (const call of callSpy.mock.calls) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    expect((call[2] as any)["method"]).toBe("POST");
  }
});
