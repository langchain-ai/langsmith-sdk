/* eslint-disable no-process-env */
import {
  StringNodeRule,
  createAnonymizer,
  createSecretAnonymizer,
  DEFAULT_SECRET_RULES,
  SECRET_PLACEHOLDER,
  isLikelyBase64,
} from "../anonymizer/index.js";
import { v4 as uuid } from "../utils/uuid/src/index.js";
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
      }),
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
      "[email address]",
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
      }),
    ).toEqual({
      message: "Hello, this is my email: [email address]",
      metadata: "[uuid]",
    });
  });

  test("array", () => {
    expect(createAnonymizer(replacers)(["human", "hello@example.com"])).toEqual(
      ["human", "[email address]"],
    );
  });

  test("string", () => {
    expect(createAnonymizer(replacers)("hello@example.com")).toEqual(
      "[email address]",
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
      { name: "child" },
    );

    const evaluate = traceable(
      (values: Record<string, unknown>) => {
        const messages = [new SystemMessage(`UUID: ${id}`)];
        return child({ messages, values });
      },
      { client, name: "evaluate", tracingEnabled: true },
    );

    const result = await evaluate({ email: "hello@example.com" });

    expect(result).toEqual(
      [`UUID: ${id}`, `email: hello@example.com`].join("\n"),
    );

    expect(
      await getAssumedTreeFromCalls(callSpy.mock.calls, client),
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

describe("createSecretAnonymizer", () => {
  const redact = createSecretAnonymizer();

  // Sample secrets that match each rule (fake values, correct shapes).
  const SAMPLES: Record<string, string> = {
    anthropic: "sk-ant-api03-AbCdEf0123456789AbCdEf0123456789xyz",
    "openai-project": "sk-proj-abcdefghij1234567890ABCDEFGHIJ",
    "openai-legacy": `sk-${"a".repeat(48)}`,
    "langsmith-lsv2": `lsv2_pt_${"a".repeat(36)}_${"b".repeat(10)}`,
    "langsmith-legacy": `ls__${"a".repeat(24)}`,
    "github-pat": `ghp_${"A".repeat(36)}`,
    "github-fine-grained": `github_pat_${"A".repeat(82)}`,
    gitlab: `glpat-${"a".repeat(20)}`,
    aws: "AKIAIOSFODNN7EXAMPLE",
    "aws-a3t": `A3TX${"A".repeat(16)}`,
    "google-api": `AIza${"A".repeat(35)}`,
    "google-oauth": "ya29.A0ARrdaM-abcdefABCDEF1234567890_-",
    // Assembled at runtime so no literal secret-shaped string sits in source
    // (a repo secret-scanner would otherwise rewrite the fixture).
    "slack-token": ["xoxb", "ABCDEFGHIJ0123456789xy"].join("-"),
    "slack-app": `xapp-1-${"A".repeat(16)}`,
    "slack-webhook":
      "https://hooks.slack.com/services/T00000000/B00000000/abcdefABCDEF1234",
    stripe: `sk_live_${"a".repeat(24)}`,
    npm: `npm_${"a".repeat(36)}`,
    pypi: `pypi-AgEIcHlwaS${"A".repeat(50)}`,
    sendgrid: `SG.${"a".repeat(22)}.${"b".repeat(43)}`,
    jwt: "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NSJ9.SflKxwRJSMeKKF2QT4fwpMeJf36",
  };

  test.each(Object.entries(SAMPLES))("redacts %s", (_name, secret) => {
    const out = redact(`value is ${secret} end`) as string;
    expect(out).not.toContain(secret);
    expect(out).toContain(SECRET_PLACEHOLDER);
  });

  test("redacts PEM private key blocks", () => {
    // Assembled from fragments so no literal key block sits in source
    // (the repo secret-scanner rewrites contiguous PEM blocks).
    const begin = ["-----BEGIN", "RSA", "PRIVATE", "KEY-----"].join(" ");
    const end = ["-----END", "RSA", "PRIVATE", "KEY-----"].join(" ");
    const pem = [begin, "a".repeat(64), end].join("\n");
    const out = redact({ file: pem }) as { file: string };
    expect(out.file).toBe(SECRET_PLACEHOLDER);
  });

  describe("precision guards (must NOT be redacted)", () => {
    const SAFE = [
      "123e4567-e89b-12d3-a456-426614174000", // UUID
      "e83c5163316f89bfbde7d9ab23ca2e25604af290", // 40-char git SHA
      "const total = computeSum(items) + 42;", // ordinary code
      "The deployment finished successfully in 12 seconds.", // prose
      'tokenizer: "cl100k_base"', // no provider-key prefix
      "tokens_used: 123456", // no provider-key prefix
      "MY_SERVICE_TOKEN=abcdef1234567890", // structural rule removed
      '{"api_key": "abcdef1234567890"}', // structural rule removed
      "Authorization: Bearer aB3xY7zQ1234567890", // structural rule removed
      "postgres://user:sup3rs3cretpw@db.example.com:5432/app", // structural rule removed
    ];
    test.each(SAFE)("leaves %s untouched", (value) => {
      expect(redact(value)).toBe(value);
    });
  });

  test("redacts a multi-segment LangSmith v2 key including the tail", () => {
    const key = `lsv2_pt_${"a".repeat(36)}_${"b".repeat(10)}`;
    // Bare context (no assignment) so only the provider rule applies; exact
    // equality catches any tail left visible past the placeholder.
    expect(redact(`using ${key} now`)).toBe(`using ${SECRET_PLACEHOLDER} now`);
  });

  test("redacts a PGP private key block (KEY BLOCK armor)", () => {
    const begin = ["-----BEGIN", "PGP", "PRIVATE", "KEY", "BLOCK-----"].join(
      " ",
    );
    const end = ["-----END", "PGP", "PRIVATE", "KEY", "BLOCK-----"].join(" ");
    const block = [begin, "a".repeat(64), end].join("\n");
    expect((redact({ file: block }) as { file: string }).file).toBe(
      SECRET_PLACEHOLDER,
    );
  });

  test("redacts secrets nested deep in a payload", () => {
    const input = {
      messages: [
        {
          role: "assistant",
          content: [
            {
              type: "tool_call",
              args: { command: `export OPENAI_API_KEY=sk-${"a".repeat(48)}` },
            },
          ],
        },
      ],
    };
    const out = redact(input) as typeof input;
    const command = (
      out.messages[0].content[0] as { args: { command: string } }
    ).args.command;
    expect(command).toContain(SECRET_PLACEHOLDER);
    expect(command).not.toContain("aaaa");
  });

  test("extraRules are applied in addition to the defaults", () => {
    const redactExtra = createSecretAnonymizer({
      extraRules: [
        { pattern: /INTERNAL-[0-9]{6}/g, replace: SECRET_PLACEHOLDER },
      ],
    });
    expect(redactExtra("ticket INTERNAL-123456")).toBe(
      `ticket ${SECRET_PLACEHOLDER}`,
    );
    // Defaults still active.
    expect(redactExtra(`key sk-ant-${"a".repeat(24)}`)).toContain(
      SECRET_PLACEHOLDER,
    );
  });

  test("DEFAULT_SECRET_RULES all set an explicit replacement token", () => {
    for (const rule of DEFAULT_SECRET_RULES) {
      expect(rule.replace).toContain(SECRET_PLACEHOLDER);
    }
  });

  test("applies through the Client before upload", async () => {
    const anonymizer = createSecretAnonymizer();
    const { client, callSpy } = mockClient({ anonymizer });

    const fn = traceable(
      async (_input: Record<string, unknown>) => ({
        note: `leaked sk-ant-${"a".repeat(30)} here`,
      }),
      { client, name: "fn", tracingEnabled: true },
    );

    await fn({ apiKey: "AKIAIOSFODNN7EXAMPLE" });

    const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
    const data = tree.data["fn:0"] as {
      inputs: Record<string, unknown>;
      outputs: Record<string, unknown>;
    };
    expect(JSON.stringify(data.inputs)).toContain(SECRET_PLACEHOLDER);
    expect(JSON.stringify(data.inputs)).not.toContain("AKIAIOSFODNN7EXAMPLE");
    expect(JSON.stringify(data.outputs)).toContain(SECRET_PLACEHOLDER);
  });
});

// ── default-on secret redaction (no explicit anonymizer) ─────────────────────

describe("default secret redaction", () => {
  const AWS_KEY = "AKIAIOSFODNN7EXAMPLE";
  const ANTHROPIC_KEY = `sk-ant-api03-${"A".repeat(30)}`;

  test("redacts secrets by default with no explicit anonymizer", async () => {
    const { client, callSpy } = mockClient({});

    const fn = traceable(
      async (_apiKey: string) => ({
        note: `leaked ${ANTHROPIC_KEY} here`,
      }),
      { client, name: "fn", tracingEnabled: true },
    );

    await fn(AWS_KEY);

    const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
    const blob = JSON.stringify(tree);
    expect(blob).not.toContain(AWS_KEY);
    expect(blob).not.toContain(ANTHROPIC_KEY);
    expect(blob).toContain(SECRET_PLACEHOLDER);
  });

  test("redactSecrets: false opts out of default redaction", async () => {
    const { client, callSpy } = mockClient({ redactSecrets: false });

    const fn = traceable(
      async (_apiKey: string) => ({ note: "no secrets here" }),
      { client, name: "fn", tracingEnabled: true },
    );

    await fn(AWS_KEY);

    const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
    const blob = JSON.stringify(tree);
    // Without redaction, the key passes through untouched.
    expect(blob).toContain(AWS_KEY);
    expect(blob).not.toContain(SECRET_PLACEHOLDER);
  });

  test("custom anonymizer takes precedence over redactSecrets", async () => {
    const custom = createAnonymizer([
      { pattern: /REPLACE_ME/g, replace: "[done]" },
    ]);
    const { client, callSpy } = mockClient({ anonymizer: custom });

    const fn = traceable(
      async () => ({
        note: `leaked REPLACE_ME and ${ANTHROPIC_KEY}`,
      }),
      { client, name: "fn", tracingEnabled: true },
    );

    await fn();

    const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
    const blob = JSON.stringify(tree);
    // Custom anonymizer ran, but the secret was NOT redacted.
    expect(blob).toContain("[done]");
    expect(blob).toContain(ANTHROPIC_KEY);
  });

  test("default redaction also applies to metadata", async () => {
    const { client, callSpy } = mockClient({});

    const fn = traceable(async () => ({ ok: true }), {
      client,
      name: "fn",
      tracingEnabled: true,
      metadata: { config: `key=${ANTHROPIC_KEY}` },
    });

    await fn();

    const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
    const blob = JSON.stringify(tree);
    expect(blob).not.toContain(ANTHROPIC_KEY);
    expect(blob).toContain(SECRET_PLACEHOLDER);
  });

  test("LANGSMITH_REDACT_SECRETS=false disables default redaction", async () => {
    const original = process.env.LANGSMITH_REDACT_SECRETS;
    process.env.LANGSMITH_REDACT_SECRETS = "false";
    try {
      const { client, callSpy } = mockClient({});

      const fn = traceable(
        async (_apiKey: string) => ({ note: "no secrets here" }),
        { client, name: "fn", tracingEnabled: true },
      );

      await fn(AWS_KEY);

      const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
      const blob = JSON.stringify(tree);
      expect(blob).toContain(AWS_KEY);
      expect(blob).not.toContain(SECRET_PLACEHOLDER);
    } finally {
      if (original === undefined) {
        delete process.env.LANGSMITH_REDACT_SECRETS;
      } else {
        process.env.LANGSMITH_REDACT_SECRETS = original;
      }
    }
  });

  test("constructor redactSecrets: true overrides env var false", async () => {
    const original = process.env.LANGSMITH_REDACT_SECRETS;
    process.env.LANGSMITH_REDACT_SECRETS = "false";
    try {
      const { client, callSpy } = mockClient({ redactSecrets: true });

      const fn = traceable(
        async () => ({ note: `leaked ${ANTHROPIC_KEY} here` }),
        { client, name: "fn", tracingEnabled: true },
      );

      await fn();

      const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
      const blob = JSON.stringify(tree);
      expect(blob).not.toContain(ANTHROPIC_KEY);
      expect(blob).toContain(SECRET_PLACEHOLDER);
    } finally {
      if (original === undefined) {
        delete process.env.LANGSMITH_REDACT_SECRETS;
      } else {
        process.env.LANGSMITH_REDACT_SECRETS = original;
      }
    }
  });

  test("LANGSMITH_HIDE_INPUTS=true fully hides inputs instead of redacting", async () => {
    const original = process.env.LANGSMITH_HIDE_INPUTS;
    process.env.LANGSMITH_HIDE_INPUTS = "true";
    try {
      const { client, callSpy } = mockClient({});

      const fn = traceable(
        async (_params: Record<string, unknown>) => ({ note: "ok" }),
        {
          client,
          name: "fn",
          tracingEnabled: true,
        },
      );

      await fn({ password: "supersecret123", other: "visible" });

      const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
      const data = tree.data["fn:0"] as {
        inputs: Record<string, unknown>;
      };
      // With HIDE_INPUTS=true, inputs should be {} (fully hidden), not redacted.
      expect(data.inputs).toEqual({});
      // The raw value must not appear anywhere.
      expect(JSON.stringify(tree)).not.toContain("supersecret123");
    } finally {
      if (original === undefined) {
        delete process.env.LANGSMITH_HIDE_INPUTS;
      } else {
        process.env.LANGSMITH_HIDE_INPUTS = original;
      }
    }
  });

  test("does not throw when extra.metadata is undefined", async () => {
    const { client } = mockClient({});

    // Directly call createRun with extra.metadata present but undefined.
    // Before the fix, the default anonymizer would throw on
    // JSON.parse(JSON.stringify(undefined)).
    await expect(
      client.createRun({
        name: "test-undefined-metadata",
        inputs: { value: "ok" },
        run_type: "chain",
        extra: { metadata: undefined },
      }),
    ).resolves.not.toThrow();
  });
});

// ── base64 skip optimization ────────────────────────────────────────────────

describe("base64 skip optimization", () => {
  test("skips large base64 blobs but still redacts secrets in adjacent text", () => {
    const redact = createSecretAnonymizer();
    const blob = "A".repeat(5000); // long, pure base64 alphabet
    const anthropicKey = `sk-ant-api03-${"A".repeat(30)}`;
    const payload = {
      image_data: blob,
      text: `Here is a secret: ${anthropicKey}`,
    };
    const result = redact(payload) as Record<string, string>;
    // Base64 blob is untouched
    expect(result.image_data).toBe(blob);
    // Secret in text field is still redacted
    expect(result.text).toContain(SECRET_PLACEHOLDER);
    expect(result.text).not.toContain(anthropicKey);
  });

  test("short strings are never classified as base64", () => {
    expect(isLikelyBase64("short")).toBe(false);
    expect(isLikelyBase64("A".repeat(99))).toBe(false);
    expect(isLikelyBase64("A".repeat(100))).toBe(true);
  });

  test("base64 blobs with newlines are still skipped", () => {
    const blob = ("A".repeat(76) + "\n").repeat(10); // 760 chars + newlines
    expect(isLikelyBase64(blob)).toBe(true);
  });

  test("prose with spaces and punctuation is not flagged as base64", () => {
    const text = "The quick brown fox jumps over the lazy dog. ".repeat(20);
    expect(isLikelyBase64(text)).toBe(false);
  });
});
