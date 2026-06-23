import {
  StringNodeRule,
  createAnonymizer,
  createSecretAnonymizer,
  DEFAULT_SECRET_RULES,
  SECRET_PLACEHOLDER,
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

  describe("structural rules", () => {
    test("redacts the value of a sensitive assignment, keeps the name", () => {
      const out = redact("MY_SERVICE_TOKEN=abcdef1234567890") as string;
      expect(out).toBe(`MY_SERVICE_TOKEN=${SECRET_PLACEHOLDER}`);
    });

    test("redacts a quoted JSON secret value", () => {
      const out = redact('{"api_key": "abcdef1234567890"}') as string;
      expect(out).toBe(`{"api_key": "${SECRET_PLACEHOLDER}"}`);
    });

    test("redacts bare Bearer tokens", () => {
      const out = redact("header: Bearer aB3xY7zQ1234567890") as string;
      expect(out).toBe(`header: Bearer ${SECRET_PLACEHOLDER}`);
    });

    test("redacts the password in a connection string", () => {
      const out = redact(
        "postgres://user:sup3rs3cretpw@db.example.com:5432/app",
      ) as string;
      expect(out).toBe(
        `postgres://user:${SECRET_PLACEHOLDER}@db.example.com:5432/app`,
      );
    });
  });

  describe("precision guards (must NOT be redacted)", () => {
    const SAFE = [
      "123e4567-e89b-12d3-a456-426614174000", // UUID
      "e83c5163316f89bfbde7d9ab23ca2e25604af290", // 40-char git SHA
      "const total = computeSum(items) + 42;", // ordinary code
      "The deployment finished successfully in 12 seconds.", // prose
      "count=5", // short, non-sensitive assignment
      'description="a reasonably long human description"', // non-sensitive name
      'tokenizer: "cl100k_base"', // "token" must not match mid-word
      "tokens_used: 123456", // keyword as a prefix of a longer word
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

  test("preserves the Bearer scheme in Authorization headers (parity)", () => {
    expect(redact("Authorization: Bearer aB3xY7zQ1234567890")).toBe(
      `Authorization: Bearer ${SECRET_PLACEHOLDER}`,
    );
  });

  test("redacts the credential after a scheme word in X-Api-Key", () => {
    // The structural api-key rule must not stop at "Bearer" and leave the token.
    const out = redact("X-Api-Key: Bearer tok_abcdefghij") as string;
    expect(out).not.toContain("tok_abcdefghij");
    expect(out).toBe(`X-Api-Key: ${SECRET_PLACEHOLDER}`);
  });

  test("stops the redacted value at query-string separators", () => {
    expect(redact("/api?api_key=ABCDEF123456&user=bob")).toBe(
      `/api?api_key=${SECRET_PLACEHOLDER}&user=bob`,
    );
  });

  test("redacts the password in a connection string with empty username", () => {
    expect(redact("redis://:sup3rs3cretpw@host:6379")).toBe(
      `redis://:${SECRET_PLACEHOLDER}@host:6379`,
    );
  });

  test("redacts a lowercase bare bearer token, preserving the scheme word", () => {
    expect(redact("sent bearer aB3xY7zQ1234567890 here")).toBe(
      `sent bearer ${SECRET_PLACEHOLDER} here`,
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

  describe("base64 skip", () => {
    test("skips any wholly-base64 string (blob or bare pure-base64 key)", () => {
      // Deliberate: a wholly-base64 value is treated as a blob and skipped, so
      // a standalone pure-base64 secret (e.g. a bare AWS key) is NOT redacted.
      expect(redact("AKIAIOSFODNN7EXAMPLE")).toBe("AKIAIOSFODNN7EXAMPLE");
      const png =
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ" + "A".repeat(40);
      expect(redact(png)).toBe(png);
    });

    test("skips data: URI blobs", () => {
      const blob = `data:image/png;base64,AKIAIOSFODNN7EXAMPLE${"A".repeat(60)}`;
      expect(redact(blob)).toBe(blob);
    });

    test("still redacts a pure-base64 key when it appears in context", () => {
      // The same AWS key in an assignment isn't wholly base64 → still scanned.
      const out = redact("AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE") as string;
      expect(out).toContain(SECRET_PLACEHOLDER);
      expect(out).not.toContain("AKIAIOSFODNN7EXAMPLE");
    });

    test("still scans non-base64 strings (separators/dots/spaces present)", () => {
      // sk-ant- (dash), JWT (dots) are not wholly base64 → still redacted.
      expect(redact(`sk-ant-${"a".repeat(30)}`)).toContain(SECRET_PLACEHOLDER);
    });
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

    await fn({ command: `export ANTHROPIC_API_KEY=sk-ant-${"a".repeat(30)}` });

    const tree = await getAssumedTreeFromCalls(callSpy.mock.calls, client);
    const data = tree.data["fn:0"] as {
      inputs: Record<string, unknown>;
      outputs: Record<string, unknown>;
    };
    expect(JSON.stringify(data.inputs)).toContain(SECRET_PLACEHOLDER);
    expect(JSON.stringify(data.inputs)).not.toContain("sk-ant-");
    expect(JSON.stringify(data.outputs)).toContain(SECRET_PLACEHOLDER);
  });
});
