/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable no-process-env */
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  jest,
  test,
} from "@jest/globals";
import * as langsmith from "../index.js";
import { Agent, type Address, type Lrn, EnvAddressError } from "../address.js";
import { RunTree } from "../run_trees.js";
import { traceable } from "../traceable.js";
import {
  applyToPayload,
  firstNamed,
  resolveFromEnv,
} from "../utils/agent_addressing.js";
import { _resetWarnedMessages } from "../utils/warn.js";
import { mockClient } from "./utils/mock_client.js";

// What a JS caller can pass; the SDK validates it at runtime.
const jsCaller = (value: string) => value as Lrn;

const SUPPORT_AGENT = new Agent("customer-support", "production");
const SUPPORT: Lrn = SUPPORT_AGENT.toLrn();
const SUPPORT_STR = "lrn:agents/customer-support/environments/production";
const STAGING_STR = "lrn:agents/customer-support/environments/staging";

const ENV_KEYS = [
  "LANGSMITH_AGENT_ID",
  "LANGSMITH_AGENT_ENVIRONMENT",
  "LANGSMITH_ADDRESS",
  "LANGSMITH_PROJECT",
  "LANGCHAIN_PROJECT",
  "LANGCHAIN_SESSION",
];
let savedEnv: Record<string, string | undefined>;

beforeEach(() => {
  savedEnv = Object.fromEntries(ENV_KEYS.map((k) => [k, process.env[k]]));
  ENV_KEYS.forEach((k) => delete process.env[k]);
  _resetWarnedMessages();
  jest.spyOn(console, "warn").mockImplementation(() => {});
});

afterEach(() => {
  for (const [key, value] of Object.entries(savedEnv)) {
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }
  jest.restoreAllMocks();
});

function bodyOf(init: any): any {
  return JSON.parse(
    typeof init.body === "string"
      ? init.body
      : new TextDecoder().decode(init.body),
  );
}

async function postedRuns(callSpy: any, client: any): Promise<any[]> {
  await client.awaitPendingTraceBatches();
  return callSpy.mock.calls
    .filter(
      ([url, init]: [string, any]) =>
        String(url).endsWith("/runs") && init?.method === "POST",
    )
    .map(([, init]: [string, any]) => bodyOf(init));
}

function headersWith(baggage: string) {
  const parent = new RunTree({ name: "p", project_name: "x" });
  return { "langsmith-trace": parent.dotted_order, baggage };
}

describe("address", () => {
  test("is exported from the package", () => {
    expect(langsmith.Agent).toBe(Agent);
  });

  test("an agent is an immutable address", () => {
    const address: Address = SUPPORT_AGENT;
    expect(address.toLrn()).toBe(SUPPORT_STR);
    expect(String(SUPPORT_AGENT)).toBe(SUPPORT_STR);
    expect(SUPPORT_AGENT.id).toBe("customer-support");
    expect(new Agent("customer-support", "PRODUCTION")).toEqual(SUPPORT_AGENT);
    expect(() => {
      (SUPPORT_AGENT as any).env = "staging";
    }).toThrow();
  });

  test("agent builds a lowercase string", () => {
    expect(SUPPORT).toBe(SUPPORT_STR);
    expect(new Agent("a", "STAGING").toLrn()).toBe(
      "lrn:agents/a/environments/staging",
    );
    for (const env of ["local", "development", "staging", "production"]) {
      expect(new Agent("a", env).toLrn()).toBe(
        `lrn:agents/a/environments/${env}`,
      );
    }
  });

  test("agent rejects invalid values", () => {
    for (const id of ["", "a".repeat(64), "Support", "1a", "a-", "a_b"]) {
      expect(() => new Agent(id, "production").toLrn()).toThrow(
        /1 to 63 lowercase/,
      );
    }
    for (const id of ["a", "a".repeat(63), "support-v2"]) {
      expect(new Agent(id, "production").toLrn()).toBe(
        `lrn:agents/${id}/environments/production`,
      );
    }
    for (const env of ["", "prod", "e"]) {
      expect(() => new Agent("a", env).toLrn()).toThrow(/must be one of/);
    }
    expect(() => new Agent("a", undefined as any)).toThrow();
  });

  test("parse validates and lowercases the environment", () => {
    expect(Agent.parse(SUPPORT_STR).toLrn()).toBe(SUPPORT_STR);
    expect(Agent.parse("lrn:agents/a/environments/Production").toLrn()).toBe(
      "lrn:agents/a/environments/production",
    );
    for (const bad of [
      "",
      "support",
      "lrn:agents/a",
      "lrn:agents/a/environments/",
      "lrn:agents//environments/production",
      "lrn:agents/a/environments/production/x",
      "lrn:agents/a/environments/production\n",
      "projects/a/environments/production",
      "agents/a/environments/production",
      "lrn:agents/Bad/environments/production",
      "lrn:agents/a/environments/prod",
    ]) {
      expect(() => Agent.parse(bad).toLrn()).toThrow();
    }
    expect(() => Agent.parse({} as any).toLrn()).toThrow(
      /must be an `Address` or a string/,
    );
  });

  test("round-trips through agent and parse", () => {
    const built = new Agent("a-b", "Local").toLrn();
    expect(Agent.parse(built).toLrn()).toBe(built);
  });
});

describe("fromEnv", () => {
  test("is undefined when nothing is set", () => {
    expect(Agent.fromEnv()?.toLrn()).toBeUndefined();
  });

  test("half an address or an invalid value throws", () => {
    process.env.LANGSMITH_AGENT_ID = "a";
    expect(() => Agent.fromEnv()).toThrow(EnvAddressError);
    expect(() => Agent.fromEnv()).toThrow(/LANGSMITH_AGENT_ENVIRONMENT/);
    delete process.env.LANGSMITH_AGENT_ID;
    process.env.LANGSMITH_AGENT_ENVIRONMENT = "production";
    expect(() => Agent.fromEnv()).toThrow(/LANGSMITH_AGENT_ID/);
    process.env.LANGSMITH_AGENT_ID = "Bad";
    expect(() => Agent.fromEnv()).toThrow(EnvAddressError);
    process.env.LANGSMITH_AGENT_ID = "a";
    process.env.LANGSMITH_AGENT_ENVIRONMENT = "nope";
    expect(() => Agent.fromEnv()).toThrow(EnvAddressError);
  });

  test("reads both vars, case-insensitively for the environment", () => {
    process.env.LANGSMITH_AGENT_ID = "customer-support";
    process.env.LANGSMITH_AGENT_ENVIRONMENT = "Production";
    expect(Agent.fromEnv()?.toLrn()).toBe(SUPPORT_STR);
  });

  test("there is no LANGSMITH_ADDRESS env var", () => {
    process.env.LANGSMITH_ADDRESS = SUPPORT_STR;
    expect(Agent.fromEnv()?.toLrn()).toBeUndefined();
    expect(resolveFromEnv()).toEqual(["default", undefined]);
  });
});

describe("precedence", () => {
  test("the first level naming anything wins; both at one level throws", () => {
    expect(firstNamed([undefined, SUPPORT], ["p", undefined])).toEqual([
      undefined,
      SUPPORT,
    ]);
    expect(() => firstNamed(["p", SUPPORT])).toThrow(/not both/);
  });

  test("the env names an address, a project, or an error", () => {
    expect(resolveFromEnv()).toEqual(["default", undefined]);
    process.env.LANGSMITH_AGENT_ID = "a";
    expect(() => resolveFromEnv()).toThrow(EnvAddressError);
    process.env.LANGSMITH_AGENT_ENVIRONMENT = "staging";
    expect(resolveFromEnv()[1]).toBe("lrn:agents/a/environments/staging");
    process.env.LANGSMITH_PROJECT = "p";
    expect(() => resolveFromEnv()).toThrow(EnvAddressError);
  });
});

describe("RunTree", () => {
  test("accepts and normalises a plain string", () => {
    const run = new RunTree({
      name: "r",
      address: jsCaller("lrn:agents/customer-support/environments/PRODUCTION"),
    });
    expect(run.address).toBe(SUPPORT_STR);
  });

  test("rejects a malformed or non-agent string", () => {
    expect(
      () => new RunTree({ name: "r", address: jsCaller("support") }),
    ).toThrow(/string like/);
    expect(
      () =>
        new RunTree({
          name: "r",
          address: jsCaller("projects/a/environments/staging"),
        }),
    ).toThrow();
  });

  test("naming both throws", () => {
    expect(
      () => new RunTree({ name: "r", address: SUPPORT, project_name: "p" }),
    ).toThrow(/not both/);
  });

  test("a child joins its parent's address", () => {
    const parent = new RunTree({ name: "p", address: SUPPORT_STR });
    const child = parent.createChild({ name: "c", project_name: "other" });
    expect(child.address).toBe(SUPPORT_STR);
    expect(child.project_name).toBeUndefined();
  });

  test("a bad env leaves the run untraced", () => {
    process.env.LANGSMITH_AGENT_ID = "a";
    expect(
      new RunTree({ name: "r", tracingEnabled: true }).tracingEnabled,
    ).toBe(false);
  });

  test("posts one lowercase address string without a project", async () => {
    const { client, callSpy } = mockClient();
    await new RunTree({
      name: "r",
      address: jsCaller("lrn:agents/customer-support/environments/Production"),
      client,
    }).postRun();
    const [body] = await postedRuns(callSpy, client);
    expect(body.address).toBe(SUPPORT_STR);
    expect(body).not.toHaveProperty("session_name");
    expect(body).not.toHaveProperty("agent_id");
    expect(body).not.toHaveProperty("agent_environment");
  });

  test("a replica equal to the run's address keeps its ids", async () => {
    const { client, callSpy } = mockClient();
    const run = new RunTree({
      name: "r",
      address: SUPPORT,
      client,
      replicas: [
        {
          address: jsCaller(
            "lrn:agents/customer-support/environments/PRODUCTION",
          ),
        },
      ],
    });
    await run.postRun();
    const [body] = await postedRuns(callSpy, client);
    expect(body.id).toBe(run.id);
  });

  test("an addressed replica gets its own ids, seeded by the address", async () => {
    const { client, callSpy } = mockClient();
    const run = new RunTree({
      name: "r",
      project_name: "p",
      client,
      replicas: [{ projectName: "p" }, { address: SUPPORT_STR }],
    });
    await run.postRun();
    const [toProject, toAddress] = await postedRuns(callSpy, client);
    expect(toProject.session_name).toBe("p");
    expect(toAddress.address).toBe(SUPPORT_STR);
    expect(toAddress.id).not.toBe(toProject.id);
    // Same ids as a replica seeded by the same string.
    const remapped = (run as any)._remapForProject({
      address: SUPPORT_STR,
      primary: false,
    });
    expect(remapped.id).toBe(toAddress.id);
    const other = (run as any)._remapForProject({
      address: STAGING_STR,
      primary: false,
    });
    expect(other.id).not.toBe(toAddress.id);
  });
});

describe("baggage", () => {
  test("round-trips the address as one langsmith-address entry", () => {
    const parent = new RunTree({ name: "p", address: SUPPORT });
    const { baggage } = parent.toHeaders();
    expect(baggage).toBe(
      `langsmith-address=${encodeURIComponent(SUPPORT_STR)}`,
    );
    const child = RunTree.fromHeaders(parent.toHeaders(), {
      project_name: "caller",
    })!;
    expect(child.address).toBe(SUPPORT_STR);
    expect(child.project_name).toBeUndefined();
  });

  test("a header naming both is rejected", () => {
    const { baggage } = new RunTree({
      name: "p",
      address: SUPPORT,
    }).toHeaders();
    expect(
      RunTree.fromHeaders(headersWith(`${baggage},langsmith-project=p`)),
    ).toBeUndefined();
  });

  test("a bad value is ignored without being logged", () => {
    const warn = console.warn as jest.Mock;
    for (const value of [
      "not-an-address",
      '{"agent_id":"a"}',
      "lrn:agents/a/environments/nope",
      "",
    ]) {
      warn.mockClear();
      const child = RunTree.fromHeaders(
        headersWith(`langsmith-address=${encodeURIComponent(value)}`),
      )!;
      expect(child.address).toBeUndefined();
      expect(JSON.stringify(warn.mock.calls)).not.toContain(value || "\0");
    }
  });

  test("a header address is normalised", () => {
    const child = RunTree.fromHeaders(
      headersWith(
        `langsmith-address=${encodeURIComponent(
          "lrn:agents/customer-support/environments/STAGING",
        )}`,
      ),
    )!;
    expect(child.address).toBe(STAGING_STR);
  });

  test("header replicas keep only safe fields; bad addresses are dropped", () => {
    const child = RunTree.fromHeaders(
      headersWith(
        `langsmith-replicas=${encodeURIComponent(
          JSON.stringify([
            { address: SUPPORT_STR, apiKey: "leak" },
            { address: "half" },
            { address: SUPPORT_STR, projectName: "p" },
          ]),
        )}`,
      ),
    )!;
    expect(child.replicas).toEqual([
      { address: SUPPORT_STR },
      { projectName: "p" },
    ]);
  });
});

describe("traceable", () => {
  test("a bad decorator address throws at wrap time", () => {
    expect(() =>
      traceable(async () => "ok", { address: SUPPORT, project_name: "p" }),
    ).toThrow(/not both/);
    expect(() =>
      traceable(async () => "ok", {
        address: "lrn:agents/Bad/environments/production",
      }),
    ).toThrow(/1 to 63 lowercase/);
  });

  test("a plain string is accepted and posted", async () => {
    const { client, callSpy } = mockClient();
    const fn = traceable(async () => "ok", {
      client,
      tracingEnabled: true,
      address: jsCaller("lrn:agents/customer-support/environments/Staging"),
    });
    await fn();
    const [body] = await postedRuns(callSpy, client);
    expect(body.address).toBe(STAGING_STR);
  });

  test("a runtime project outranks a decorator address", async () => {
    const { client, callSpy } = mockClient();
    const fn = traceable(async (_input: string) => "ok", {
      client,
      tracingEnabled: true,
      address: SUPPORT,
      argsConfigPath: [1],
    });
    await (fn as any)("x", { project_name: "runtime" });
    const [body] = await postedRuns(callSpy, client);
    expect(body.session_name).toBe("runtime");
    expect(body).not.toHaveProperty("address");
  });

  test("a runtime address outranks a decorator project", async () => {
    const { client, callSpy } = mockClient();
    const fn = traceable(async (_input: string) => "ok", {
      client,
      tracingEnabled: true,
      project_name: "p",
      argsConfigPath: [1],
    });
    await (fn as any)("x", { address: "lrn:agents/a/environments/LOCAL" });
    const [body] = await postedRuns(callSpy, client);
    expect(body.address).toBe("lrn:agents/a/environments/local");
  });
});

describe("Client", () => {
  test("createRun drops the run for a bad env", async () => {
    process.env.LANGSMITH_AGENT_ID = "a";
    const { client, callSpy } = mockClient();
    await client.createRun({ name: "r", inputs: {}, run_type: "chain" });
    expect(await postedRuns(callSpy, client)).toHaveLength(0);
  });

  test("createRun takes the env address", async () => {
    process.env.LANGSMITH_AGENT_ID = "customer-support";
    process.env.LANGSMITH_AGENT_ENVIRONMENT = "production";
    const { client, callSpy } = mockClient();
    await client.createRun({ name: "r", inputs: {}, run_type: "chain" });
    const [body] = await postedRuns(callSpy, client);
    expect(body.address).toBe(SUPPORT_STR);
  });

  test("createRun rejects a malformed address", async () => {
    const { client } = mockClient();
    await expect(
      client.createRun({
        name: "r",
        inputs: {},
        run_type: "chain",
        address: jsCaller("nope"),
      }),
    ).rejects.toThrow(/string like/);
  });

  test("createRun rejects a session_name beside an address", async () => {
    const { client } = mockClient();
    await expect(
      // A built run body, as `RunTree.postRun` passes it.
      client.createRun({
        name: "r",
        inputs: {},
        run_type: "chain",
        session_name: "p",
        address: SUPPORT,
      } as Parameters<typeof client.createRun>[0]),
    ).rejects.toThrow(/not both/);
  });

  test("applying a payload twice is idempotent", () => {
    process.env.LANGSMITH_AGENT_ID = "a";
    process.env.LANGSMITH_AGENT_ENVIRONMENT = "local";
    const payload: any = {
      address: "lrn:agents/customer-support/environments/PRODUCTION",
    };
    applyToPayload(payload);
    applyToPayload(payload);
    expect(payload).toEqual({ address: SUPPORT_STR });
  });

  test("batchIngestRuns sends the address to POST /runs/batch", async () => {
    const { client, callSpy } = mockClient();
    const run = new RunTree({ name: "r", address: SUPPORT, client });
    await client.batchIngestRuns({ runCreates: [run.toJSON()] });
    const [, init] = callSpy.mock.calls.find(([url]: [string]) =>
      String(url).endsWith("/runs/batch"),
    );
    const { post } = bodyOf(init);
    expect(post).toHaveLength(1);
    expect(post[0].address).toBe(SUPPORT_STR);
    expect(post[0]).not.toHaveProperty("session_name");
  });

  test("createFeedback sends one lowercase address string", async () => {
    const { client, callSpy } = mockClient();
    await client.createFeedback({
      runId: "00000000-0000-0000-0000-000000000001",
      key: "k",
      address: jsCaller("lrn:agents/customer-support/environments/PRODUCTION"),
    });
    const [, init] = callSpy.mock.calls.find(([url]: [string]) =>
      String(url).endsWith("/feedback"),
    );
    const body = JSON.parse(init.body);
    expect(body.address).toBe(SUPPORT_STR);
    expect(body).not.toHaveProperty("agent_id");
  });

  test("createFeedback rejects a malformed address", async () => {
    const { client } = mockClient();
    await expect(
      client.createFeedback({
        runId: "00000000-0000-0000-0000-000000000001",
        key: "k",
        address: jsCaller("nope"),
      }),
    ).rejects.toThrow(/string like/);
  });

  test("a direct updateRun sends the address string", async () => {
    const { client, callSpy } = mockClient();
    await client.updateRun("00000000-0000-0000-0000-000000000001", {
      address: jsCaller("lrn:agents/customer-support/environments/STAGING"),
    });
    const [, init] = callSpy.mock.calls.find(
      ([, init]: [string, any]) => init?.method === "PATCH",
    );
    const body = bodyOf(init);
    expect(body.address).toBe(STAGING_STR);
    expect(body).not.toHaveProperty("agent_id");
  });
});

// Compile-time checks: `tsc` fails if a `@ts-expect-error` stops erroring.
describe("address types", () => {
  test("literals, parse and agent results are accepted", () => {
    const dynamic: string = SUPPORT_STR;
    const literal = new RunTree({
      name: "r",
      address: "lrn:agents/support-bot/environments/production",
    });
    const parsed = new RunTree({
      name: "r",
      address: Agent.parse(dynamic).toLrn(),
    });
    const built = new RunTree({
      name: "r",
      address: new Agent("support-bot", dynamic.slice(-10)).toLrn(),
    });
    expect(literal.address).toBe(
      "lrn:agents/support-bot/environments/production",
    );
    expect(parsed.address).toBe(SUPPORT_STR);
    expect(built.address).toBe(
      "lrn:agents/support-bot/environments/production",
    );
    const traced = traceable(async () => 1, { address: SUPPORT });
    expect(typeof traced).toBe("function");
  });

  test("a wrong environment, collection or dynamic string is rejected", () => {
    const dynamic: string = SUPPORT_STR;
    const rejected = (build: () => unknown) => expect(build).toBeDefined(); // never called; only type-checked
    rejected(() => {
      // @ts-expect-error unknown environment
      traceable(async () => 1, { address: "lrn:agents/x/environments/prod" });
      // @ts-expect-error wrong collection
      traceable(async () => 1, { address: "projects/x" });
      // @ts-expect-error a dynamic string must go through Agent.parse
      traceable(async () => 1, { address: dynamic });
      // @ts-expect-error unknown environment
      new RunTree({ name: "r", address: "lrn:agents/x/environments/prod" });
      // @ts-expect-error wrong collection
      new RunTree({ name: "r", address: "projects/x" });
      // @ts-expect-error a dynamic string must go through Agent.parse
      new RunTree({ name: "r", address: dynamic });
      // @ts-expect-error a replica takes an Address or LRN too
      new RunTree({ name: "r", replicas: [{ address: dynamic }] });
      const { client } = mockClient();
      // @ts-expect-error createRun takes an Address or LRN
      client.createRun({ name: "r", run_type: "chain", address: dynamic });
      // @ts-expect-error createFeedback takes an Address or LRN
      client.createFeedback({ runId: "r", key: "k", address: dynamic });
    });
  });
});

describe("Address objects", () => {
  class Custom implements Address {
    constructor(private readonly lrn: string) {}
    toLrn(): Lrn {
      return this.lrn as Lrn;
    }
  }

  test("a run tree carries the LRN of an Address", () => {
    expect(new RunTree({ name: "r", address: SUPPORT_AGENT }).address).toBe(
      SUPPORT_STR,
    );
  });

  test("any implementation is accepted and normalized", () => {
    const custom = new Custom(
      "lrn:agents/customer-support/environments/STAGING",
    );
    expect(new RunTree({ name: "r", address: custom }).address).toBe(
      STAGING_STR,
    );
  });

  test("an implementation must render a valid LRN", () => {
    expect(
      () => new RunTree({ name: "r", address: new Custom("experiments/e") }),
    ).toThrow(/string like/);
    expect(() => new RunTree({ name: "r", address: {} as any })).toThrow(
      /string like/,
    );
  });

  test("replicas take an Address", () => {
    const tree = new RunTree({
      name: "r",
      replicas: [{ address: SUPPORT_AGENT }],
    });
    expect(tree.replicas?.[0]).toMatchObject({ address: SUPPORT_STR });
  });

  test("createFeedback sends the LRN string of an Address", async () => {
    const { client, callSpy } = mockClient();
    await client.createFeedback({
      runId: "00000000-0000-0000-0000-000000000001",
      key: "k",
      address: SUPPORT_AGENT,
    });
    const [, init] = callSpy.mock.calls.find(([url]: [string]) =>
      String(url).endsWith("/feedback"),
    );
    expect(JSON.parse(init.body).address).toBe(SUPPORT_STR);
  });
});
