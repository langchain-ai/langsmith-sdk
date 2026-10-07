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
import { Client } from "../index.js";
import {
  Agent,
  Evaluator,
  Experiment,
  type Address,
  EnvAddressError,
} from "../address.js";
import { RunTree } from "../run_trees.js";
import { traceable } from "../traceable.js";
import {
  applyToPayload,
  firstNamed,
  resolveFromEnv,
} from "../utils/addressing.js";
import { _resetWarnedMessages } from "../utils/warn.js";
import { mockClient } from "./utils/mock_client.js";

// What a JS caller can pass; the SDK validates it at runtime.
const jsCaller = (value: unknown) => value as Agent;

const SUPPORT_AGENT = new Agent("customer-support", "production");
const STAGING_AGENT = new Agent("customer-support", "staging");
const SUPPORT_STR = "lrn:agents/customer-support/environments/production";
const STAGING_STR = "lrn:agents/customer-support/environments/staging";
const SUPPORT_WIRE = {
  agent_id: "customer-support",
  agent_environment: "production",
};

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
    expect(address).toBe(SUPPORT_AGENT);
    expect(SUPPORT_AGENT.id).toBe("customer-support");
    expect(SUPPORT_AGENT.env).toBe("production");
    expect(new Agent("customer-support", "PRODUCTION")).toEqual(SUPPORT_AGENT);
    expect(() => {
      (SUPPORT_AGENT as any).env = "staging";
    }).toThrow();
  });

  test("the environment is lowercased", () => {
    expect(new Agent("a", "STAGING").env).toBe("staging");
    for (const env of ["local", "development", "staging", "production"]) {
      expect(new Agent("a", env).env).toBe(env);
    }
  });

  test("agent rejects invalid values", () => {
    for (const id of ["", "a".repeat(64), "Support", "1a", "a-", "a_b"]) {
      expect(() => new Agent(id, "production")).toThrow(/1 to 63 lowercase/);
    }
    for (const id of ["a", "a".repeat(63), "support-v2"]) {
      expect(new Agent(id, "production").id).toBe(id);
    }
    for (const env of ["", "prod", "e"]) {
      expect(() => new Agent("a", env)).toThrow(/must be one of/);
    }
    expect(() => new Agent("a", undefined as any)).toThrow();
  });

  test("toApiAddress names the agent with an uppercase environment", () => {
    expect(SUPPORT_AGENT.toApiAddress()).toEqual({
      kind: "AGENT",
      id: "customer-support",
      environment: "PRODUCTION",
    });
    expect(STAGING_AGENT.toApiAddress().environment).toBe("STAGING");
  });

  test("the LRN is not public", () => {
    // @ts-expect-error parse is internal
    expect(Agent.parse).toBeUndefined();
    const rendered: string = String(SUPPORT_AGENT);
    expect(rendered).not.toContain("lrn:");
    expect(Object.keys(SUPPORT_AGENT).sort()).toEqual(["env", "id"]);
    // @ts-expect-error the LRN is not part of Address
    expect((SUPPORT_AGENT as Address)._toLrn).toBeDefined();
    expect(JSON.stringify(SUPPORT_AGENT)).not.toContain("lrn");
    // Errors don't render an LRN either.
    expect(() => new RunTree({ name: "r", address: jsCaller("x") })).toThrow(
      /^(?!.*lrn:)/,
    );
  });
});

describe("Experiment and Evaluator", () => {
  const UUID = "0A1B2C3D-0000-4000-8000-ABCDEF012345";

  test("an Experiment is a frozen address with a lowercase id", () => {
    const experiment = new Experiment(UUID);
    expect(experiment.toApiAddress()).toEqual({
      kind: "EXPERIMENT",
      id: UUID.toLowerCase(),
    });
    expect(Object.isFrozen(experiment)).toBe(true);
    const address: Address = experiment;
    expect(address).toBe(experiment);
    expect(langsmith.Experiment).toBe(Experiment);
  });

  test("an Experiment rejects a non-UUID", () => {
    for (const bad of ["", "exp", "0a1b2c3d00004000800abcdef012345", 1, null]) {
      expect(() => new Experiment(bad as any)).toThrow(/must be a UUID/);
    }
  });

  test("an Evaluator is a frozen address without an id", () => {
    const evaluator = new Evaluator();
    expect(evaluator.toApiAddress()).toEqual({ kind: "EVALUATOR" });
    expect(Object.isFrozen(evaluator)).toBe(true);
    expect(langsmith.Evaluator).toBe(Evaluator);
  });
});

describe("only an Agent can receive traces", () => {
  class Custom implements Address {
    toApiAddress() {
      return { kind: "EVALUATOR" as const };
    }
  }
  const others = (): any[] => [
    new Experiment("0a1b2c3d-0000-4000-8000-abcdef012345"),
    new Evaluator(),
    new Custom(),
  ];
  const ONLY = (name: string) =>
    new RegExp(`Only an Agent can receive traces, got ${name}\\.`);
  const RUN_ID = "00000000-0000-0000-0000-000000000001";

  test("RunTree and its replicas reject them", () => {
    for (const other of others()) {
      const name = other.constructor.name;
      expect(() => new RunTree({ name: "r", address: other })).toThrow(
        ONLY(name),
      );
      expect(
        () => new RunTree({ name: "r", replicas: [{ address: other }] }),
      ).toThrow(ONLY(name));
    }
  });

  test("traceable rejects them at wrap time and at call time", async () => {
    for (const other of others()) {
      const name = other.constructor.name;
      expect(() => traceable(async () => 1, { address: other })).toThrow(
        ONLY(name),
      );
      const { client } = mockClient();
      const fn = traceable(async (_input: string) => "ok", {
        client,
        tracingEnabled: true,
        argsConfigPath: [1],
      });
      await expect(async () =>
        (fn as any)("x", { address: other }),
      ).rejects.toThrow(ONLY(name));
    }
  });

  test("createRun, createFeedback and updateRun reject them", async () => {
    const { client } = mockClient();
    for (const other of others()) {
      const name = other.constructor.name;
      await expect(
        client.createRun({
          name: "r",
          inputs: {},
          run_type: "chain",
          address: other,
        }),
      ).rejects.toThrow(ONLY(name));
      await expect(
        client.createFeedback({ runId: RUN_ID, key: "k", address: other }),
      ).rejects.toThrow(ONLY(name));
      await expect(
        client.updateRun(RUN_ID, { address: other }),
      ).rejects.toThrow(ONLY(name));
    }
  });

  test("a plain object is rejected as not an Agent", () => {
    for (const bad of [{}, { _toLrn: () => "x" }]) {
      expect(() => new RunTree({ name: "r", address: bad as any })).toThrow(
        /address must be an Agent/,
      );
    }
  });

  test("the types reject them", () => {
    const rejected = (build: () => unknown) => expect(build).toBeDefined(); // never called; only type-checked
    rejected(() => {
      // @ts-expect-error an Experiment is not an Agent
      new RunTree({ name: "r", address: new Experiment(RUN_ID) });
      // @ts-expect-error an Evaluator is not an Agent
      traceable(async () => 1, { address: new Evaluator() });
      // @ts-expect-error a replica takes an Agent
      new RunTree({ name: "r", replicas: [{ address: new Evaluator() }] });
      const { client } = mockClient();
      const address = new Evaluator();
      // @ts-expect-error createRun takes an Agent
      client.createRun({ name: "r", run_type: "chain", address });
      // @ts-expect-error createFeedback takes an Agent
      client.createFeedback({ runId: "r", key: "k", address });
      // @ts-expect-error updateRun takes an Agent
      client.updateRun("r", { address });
    });
  });
});

describe("fromEnv", () => {
  test("is undefined when nothing is set", () => {
    expect(Agent.fromEnv()).toBeUndefined();
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
    expect(Agent.fromEnv()).toEqual(SUPPORT_AGENT);
  });

  test("there is no LANGSMITH_ADDRESS env var", () => {
    process.env.LANGSMITH_ADDRESS = SUPPORT_STR;
    expect(Agent.fromEnv()).toBeUndefined();
    expect(resolveFromEnv()).toEqual(["default", undefined]);
  });
});

describe("precedence", () => {
  test("the first level naming anything wins; both at one level throws", () => {
    expect(firstNamed([undefined, SUPPORT_AGENT], ["p", undefined])).toEqual([
      undefined,
      SUPPORT_AGENT,
    ]);
    expect(() => firstNamed(["p", SUPPORT_AGENT])).toThrow(/not both/);
  });

  test("the env names an address, a project, or an error", () => {
    expect(resolveFromEnv()).toEqual(["default", undefined]);
    process.env.LANGSMITH_AGENT_ID = "a";
    expect(() => resolveFromEnv()).toThrow(EnvAddressError);
    process.env.LANGSMITH_AGENT_ENVIRONMENT = "staging";
    expect(resolveFromEnv()[1]).toEqual(new Agent("a", "staging"));
    process.env.LANGSMITH_PROJECT = "p";
    expect(() => resolveFromEnv()).toThrow(EnvAddressError);
  });
});

describe("RunTree", () => {
  test("carries the Address it was given", () => {
    const run = new RunTree({
      name: "r",
      address: new Agent("customer-support", "PRODUCTION"),
    });
    expect(run.address).toEqual(SUPPORT_AGENT);
    expect(Object.isFrozen(run.address)).toBe(true);
  });

  test("rejects a string, even a valid LRN", () => {
    for (const bad of [SUPPORT_STR, "support"]) {
      expect(() => new RunTree({ name: "r", address: jsCaller(bad) })).toThrow(
        /address must be an Agent such as `new Agent\(id, env\)`/,
      );
    }
  });

  test("naming both throws", () => {
    expect(
      () =>
        new RunTree({ name: "r", address: SUPPORT_AGENT, project_name: "p" }),
    ).toThrow(/not both/);
  });

  test("a child joins its parent's address", () => {
    const parent = new RunTree({ name: "p", address: SUPPORT_AGENT });
    const child = parent.createChild({ name: "c", project_name: "other" });
    expect(child.address).toEqual(SUPPORT_AGENT);
    expect(child.project_name).toBeUndefined();
  });

  test("a bad env leaves the run untraced", () => {
    process.env.LANGSMITH_AGENT_ID = "a";
    expect(
      new RunTree({ name: "r", tracingEnabled: true }).tracingEnabled,
    ).toBe(false);
  });

  test("posts the LRN string on the wire without a project", async () => {
    const { client, callSpy } = mockClient();
    await new RunTree({
      name: "r",
      address: new Agent("customer-support", "Production"),
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
      address: SUPPORT_AGENT,
      client,
      replicas: [{ address: new Agent("customer-support", "PRODUCTION") }],
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
      replicas: [{ projectName: "p" }, { address: SUPPORT_AGENT }],
    });
    await run.postRun();
    const [toProject, toAddress] = await postedRuns(callSpy, client);
    expect(toProject.session_name).toBe("p");
    expect(toAddress.address).toBe(SUPPORT_STR);
    expect(toAddress.id).not.toBe(toProject.id);
    // Same ids as a replica seeded by the same address.
    const remapped = (run as any)._remapForProject({
      address: SUPPORT_AGENT,
      primary: false,
    });
    expect(remapped.id).toBe(toAddress.id);
    const other = (run as any)._remapForProject({
      address: STAGING_AGENT,
      primary: false,
    });
    expect(other.id).not.toBe(toAddress.id);
  });
});

describe("baggage", () => {
  test("round-trips the address as one entry", () => {
    const parent = new RunTree({ name: "p", address: SUPPORT_AGENT });
    const { baggage } = parent.toHeaders();
    expect(baggage).toBe(
      `langsmith-address=${encodeURIComponent(SUPPORT_STR)}`,
    );
    const child = RunTree.fromHeaders(parent.toHeaders(), {
      project_name: "caller",
    })!;
    expect(child.address).toEqual(SUPPORT_AGENT);
    expect(child.project_name).toBeUndefined();
  });

  test("a header naming both is rejected", () => {
    const { baggage } = new RunTree({
      name: "p",
      address: SUPPORT_AGENT,
    }).toHeaders();
    expect(
      RunTree.fromHeaders(headersWith(`${baggage},langsmith-project=p`)),
    ).toBeUndefined();
  });

  test("a bad value is ignored without being logged", () => {
    const warn = console.warn as jest.Mock;
    for (const bad of [
      "support",
      "",
      "lrn:agents/Bad/environments/production",
      "lrn:agents/a/environments/nope",
      "lrn:agents//environments/production",
      "lrn:agents/a/environments/",
      "lrn:agents/a/b/environments/local",
      "lrn:agents/a/environments/local/extra",
      "lrn:agents/a/environments/local\n",
    ]) {
      warn.mockClear();
      const child = RunTree.fromHeaders(
        headersWith(`langsmith-address=${encodeURIComponent(bad)}`),
      )!;
      expect(child.address).toBeUndefined();
      expect(warn).toHaveBeenCalledTimes(1);
      if (bad) {
        expect(JSON.stringify(warn.mock.calls)).not.toContain(bad);
      }
    }
  });

  test("the fields of an earlier format are not read", () => {
    const child = RunTree.fromHeaders(
      headersWith(
        "langsmith-agent-id=customer-support,langsmith-agent-environment=production",
      ),
    )!;
    expect(child.address).toBeUndefined();
  });

  test("a header address is normalised", () => {
    const child = RunTree.fromHeaders(
      headersWith(
        `langsmith-address=${encodeURIComponent(
          "lrn:agents/customer-support/environments/STAGING",
        )}`,
      ),
    )!;
    expect(child.address).toEqual(STAGING_AGENT);
  });

  test("header replicas keep only safe fields; bad addresses are dropped", () => {
    const child = RunTree.fromHeaders(
      headersWith(
        `langsmith-replicas=${encodeURIComponent(
          JSON.stringify([
            { address: SUPPORT_STR, apiKey: "leak" },
            { address: { agent_id: "a" } },
            // The fields of an earlier format are not read.
            { address: SUPPORT_WIRE },
            { address: SUPPORT_STR, projectName: "p" },
          ]),
        )}`,
      ),
    )!;
    expect(child.replicas).toEqual([
      { address: SUPPORT_AGENT },
      { projectName: "p" },
    ]);
  });
});

describe("traceable", () => {
  test("a bad decorator address throws at wrap time", () => {
    expect(() =>
      traceable(async () => "ok", {
        address: SUPPORT_AGENT,
        project_name: "p",
      }),
    ).toThrow(/not both/);
  });

  test("a string address is rejected at wrap time", () => {
    expect(() =>
      traceable(async () => "ok", { address: jsCaller(SUPPORT_STR) }),
    ).toThrow(/address must be an Agent/);
  });

  test("an Address is posted as its LRN", async () => {
    const { client, callSpy } = mockClient();
    const fn = traceable(async () => "ok", {
      client,
      tracingEnabled: true,
      address: new Agent("customer-support", "Staging"),
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
      address: SUPPORT_AGENT,
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
    await (fn as any)("x", { address: new Agent("a", "LOCAL") });
    const [body] = await postedRuns(callSpy, client);
    expect(body.address).toBe("lrn:agents/a/environments/local");
  });

  test("a runtime string address is rejected", async () => {
    const { client } = mockClient();
    const fn = traceable(async (_input: string) => "ok", {
      client,
      tracingEnabled: true,
      argsConfigPath: [1],
    });
    await expect(async () =>
      (fn as any)("x", { address: "lrn:agents/a/environments/local" }),
    ).rejects.toThrow(/address must be an Agent/);
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

  test("createRun rejects a string address", async () => {
    const { client } = mockClient();
    for (const bad of [SUPPORT_STR, "nope"]) {
      await expect(
        client.createRun({
          name: "r",
          inputs: {},
          run_type: "chain",
          address: jsCaller(bad),
        }),
      ).rejects.toThrow(/address must be an Agent/);
    }
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
        address: SUPPORT_AGENT,
      } as Parameters<typeof client.createRun>[0]),
    ).rejects.toThrow(/not both/);
  });

  test("applyToPayload writes the LRN string and keeps it when applied again", () => {
    const payload: any = {
      address: new Agent("customer-support", "PRODUCTION"),
    };
    applyToPayload(payload);
    expect(payload).toEqual({ address: SUPPORT_STR });
    // A queued run is applied again when its batch is sent.
    applyToPayload(payload);
    expect(payload).toEqual({ address: SUPPORT_STR });
    expect(() => applyToPayload({ address: 42 } as any)).toThrow(
      /address must be an Agent/,
    );
  });

  test("a run with an address survives the auto-batch queue", async () => {
    const callSpy = jest.fn<typeof fetch>().mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      text: () => Promise.resolve(""),
      json: () => Promise.resolve({}),
    } as Response);
    const client = new Client({
      apiKey: "MOCK",
      autoBatchTracing: true,
      fetchImplementation: callSpy,
    });
    const run = new RunTree({ name: "r", address: SUPPORT_AGENT, client });
    await run.postRun();
    await run.end({ ok: true });
    await run.patchRun();
    await client.awaitPendingTraceBatches();
    const sent = (
      await Promise.all(
        callSpy.mock.calls.map(async ([, init]) =>
          init?.body == null
            ? ""
            : await new Response(init.body as BodyInit).text(),
        ),
      )
    ).join("\n");
    expect(sent).toContain(SUPPORT_STR);
  });

  test("batchIngestRuns sends the address to POST /runs/batch", async () => {
    const { client, callSpy } = mockClient();
    const run = new RunTree({ name: "r", address: SUPPORT_AGENT, client });
    await client.batchIngestRuns({ runCreates: [run.toJSON()] });
    const [, init] = callSpy.mock.calls.find(([url]: [string]) =>
      String(url).endsWith("/runs/batch"),
    );
    const { post } = bodyOf(init);
    expect(post).toHaveLength(1);
    expect(post[0].address).toBe(SUPPORT_STR);
    expect(post[0]).not.toHaveProperty("session_name");
  });

  test("createFeedback sends the Address as an LRN string", async () => {
    const { client, callSpy } = mockClient();
    await client.createFeedback({
      runId: "00000000-0000-0000-0000-000000000001",
      key: "k",
      address: new Agent("customer-support", "PRODUCTION"),
    });
    const [, init] = callSpy.mock.calls.find(([url]: [string]) =>
      String(url).endsWith("/feedback"),
    );
    const body = JSON.parse(init.body);
    expect(body.address).toBe(SUPPORT_STR);
    expect(body).not.toHaveProperty("agent_id");
  });

  test("createFeedback rejects a string address", async () => {
    const { client } = mockClient();
    for (const bad of [SUPPORT_STR, "nope"]) {
      await expect(
        client.createFeedback({
          runId: "00000000-0000-0000-0000-000000000001",
          key: "k",
          address: jsCaller(bad),
        }),
      ).rejects.toThrow(/address must be an Agent/);
    }
  });

  test("a direct updateRun sends the LRN string", async () => {
    const { client, callSpy } = mockClient();
    await client.updateRun("00000000-0000-0000-0000-000000000001", {
      address: new Agent("customer-support", "STAGING"),
    });
    const [, init] = callSpy.mock.calls.find(
      ([, init]: [string, any]) => init?.method === "PATCH",
    );
    const body = bodyOf(init);
    expect(body.address).toBe(STAGING_STR);
    expect(body).not.toHaveProperty("agent_id");
  });

  test("updateRun rejects a string address", async () => {
    const { client } = mockClient();
    await expect(
      client.updateRun("00000000-0000-0000-0000-000000000001", {
        address: jsCaller(SUPPORT_STR),
      }),
    ).rejects.toThrow(/address must be an Agent/);
  });
});

// Compile-time checks: `tsc` fails if a `@ts-expect-error` stops erroring.
describe("address types", () => {
  test("an Address is accepted", () => {
    const run = new RunTree({ name: "r", address: SUPPORT_AGENT });
    expect(run.address).toEqual(SUPPORT_AGENT);
    const traced = traceable(async () => 1, { address: SUPPORT_AGENT });
    expect(typeof traced).toBe("function");
  });

  test("a string is rejected", () => {
    const dynamic: string = SUPPORT_STR;
    const rejected = (build: () => unknown) => expect(build).toBeDefined(); // never called; only type-checked
    rejected(() => {
      // @ts-expect-error an LRN literal is not an Address
      traceable(async () => 1, { address: "lrn:agents/x/environments/local" });
      // @ts-expect-error a dynamic string is not an Address
      traceable(async () => 1, { address: dynamic });
      // @ts-expect-error an LRN literal is not an Address
      new RunTree({ name: "r", address: "lrn:agents/x/environments/local" });
      // @ts-expect-error a dynamic string is not an Address
      new RunTree({ name: "r", address: dynamic });
      // @ts-expect-error a replica takes an Address
      new RunTree({ name: "r", replicas: [{ address: dynamic }] });
      const { client } = mockClient();
      // @ts-expect-error createRun takes an Address
      client.createRun({ name: "r", run_type: "chain", address: dynamic });
      // @ts-expect-error createFeedback takes an Address
      client.createFeedback({ runId: "r", key: "k", address: dynamic });
      // @ts-expect-error updateRun takes an Address
      client.updateRun("r", { address: dynamic });
    });
  });

  test("Lrn is not exported from the package", () => {
    // @ts-expect-error Lrn is internal
    type _NoLrn = langsmith.Lrn;
    expect("Lrn" in langsmith).toBe(false);
  });
});
