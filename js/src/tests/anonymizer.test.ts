import { StringNodeRule, createAnonymizer } from "../anonymizer/index.js";
import { v4 as uuid } from "uuid";
import { traceable } from "../traceable.js";
import { BaseMessage, SystemMessage } from "@langchain/core/messages";
import { mockClient } from "./utils/mock_client.js";
import { getAssumedTreeFromCalls } from "./utils/tree.js";

const EMAIL_REGEX = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+.[a-zA-Z]{2,}/g;
const UUID_REGEX =
  /[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}/g;

describe("prototype pollution prevention", () => {
  test("blocks constructor.prototype path", () => {
    const anonymizer = createAnonymizer([
      { pattern: "secret", replace: "[REDACTED]" },
    ]);

    // Verify clean state
    expect(({} as Record<string, unknown>).isAdmin).toBeUndefined();

    // Malicious input with prototype pollution attempt
    const maliciousInput = {
      wrapper: {
        "constructor.prototype.isAdmin": "this-is-secret-data",
      },
    };

    anonymizer(maliciousInput);

    // Should NOT pollute Object.prototype
    expect(({} as Record<string, unknown>).isAdmin).toBeUndefined();
  });

  test("blocks __proto__ path", () => {
    const anonymizer = createAnonymizer([
      { pattern: "secret", replace: "[REDACTED]" },
    ]);

    expect(({} as Record<string, unknown>).polluted).toBeUndefined();

    const maliciousInput = {
      "__proto__.polluted": "secret-data",
    };

    anonymizer(maliciousInput);

    expect(({} as Record<string, unknown>).polluted).toBeUndefined();
  });

  test("blocks prototype path", () => {
    const anonymizer = createAnonymizer([
      { pattern: "secret", replace: "[REDACTED]" },
    ]);

    expect(({} as Record<string, unknown>).polluted).toBeUndefined();

    const maliciousInput = {
      prototype: {
        polluted: "secret-data",
      },
    };

    anonymizer(maliciousInput);

    expect(({} as Record<string, unknown>).polluted).toBeUndefined();
  });

  test("handles dotted keys distinctly from nested keys", () => {
    const anonymizer = createAnonymizer([
      { pattern: "secret", replace: "[REDACTED]" },
    ]);

    const input = {
      "a.b": "secret-1",
      a: { b: "secret-2" },
    };

    const output = anonymizer(input);

    expect(output["a.b"]).toBe("[REDACTED]-1");
    expect(output.a.b).toBe("[REDACTED]-2");
  });
});

describe("replacer", () => {
  const replacer = (text: string) =>
    text.replace(EMAIL_REGEX, "[email address]").replace(UUID_REGEX, "[uuid]");

  test("object", () => {
    expect(
      createAnonymizer(replacer)({
        message: "Hello, this is my email: hello@example.com",
        metadata: uuid(),
      })
    ).toEqual({
      message: "Hello, this is my email: [email address]",
      metadata: "[uuid]",
    });
  });

  test("array", () => {
    expect(createAnonymizer(replacer)(["human", "hello@example.com"])).toEqual([
      "human",
      "[email address]",
    ]);
  });

  test("string", () => {
    expect(createAnonymizer(replacer)("hello@example.com")).toEqual(
      "[email address]"
    );
  });
});

describe("declared", () => {
  const replacers: StringNodeRule[] = [
    { pattern: EMAIL_REGEX, replace: "[email address]" },
    { pattern: UUID_REGEX, replace: "[uuid]" },
  ];

  test("object", () => {
    expect(
      createAnonymizer(replacers)({
        message: "Hello, this is my email: hello@example.com",
        metadata: uuid(),
      })
    ).toEqual({
      message: "Hello, this is my email: [email address]",
      metadata: "[uuid]",
    });
  });

  test("array", () => {
    expect(createAnonymizer(replacers)(["human", "hello@example.com"])).toEqual(
      ["human", "[email address]"]
    );
  });

  test("string", () => {
    expect(createAnonymizer(replacers)("hello@example.com")).toEqual(
      "[email address]"
    );
  });
});

describe("client", () => {
  test("messages", async () => {
    const anonymizer = createAnonymizer([
      { pattern: EMAIL_REGEX, replace: "[email]" },
      { pattern: UUID_REGEX, replace: "[uuid]" },
    ]);

    const { client, callSpy } = mockClient({ anonymizer });

    const id = uuid();
    const child = traceable(
      (value: { messages: BaseMessage[]; values: Record<string, unknown> }) => {
        return [
          ...value.messages.map((message) => message.content.toString()),
          ...Object.entries(value.values).map((lst) => lst.join(": ")),
        ].join("\n");
      },
      { name: "child" }
    );

    const evaluate = traceable(
      (values: Record<string, unknown>) => {
        const messages = [new SystemMessage(`UUID: ${id}`)];
        return child({ messages, values });
      },
      { client, name: "evaluate", tracingEnabled: true }
    );

    const result = await evaluate({ email: "hello@example.com" });

    expect(result).toEqual(
      [`UUID: ${id}`, `email: hello@example.com`].join("\n")
    );

    expect(
      await getAssumedTreeFromCalls(callSpy.mock.calls, client)
    ).toMatchObject({
      nodes: ["evaluate:0", "child:1"],
      data: {
        "evaluate:0": {
          inputs: { email: "[email]" },
          outputs: { outputs: [`UUID: [uuid]`, `email: [email]`].join("\n") },
        },
        "child:1": {
          inputs: {
            messages: [
              {
                lc: 1,
                type: "constructor",
                id: ["langchain_core", "messages", "SystemMessage"],
                kwargs: { content: "UUID: [uuid]" },
              },
            ],
            values: { email: "[email]" },
          },
          outputs: { outputs: [`UUID: [uuid]`, `email: [email]`].join("\n") },
        },
      },
    });
  });
});
