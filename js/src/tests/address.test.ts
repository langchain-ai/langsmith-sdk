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
import {
  type Address,
  EnvAddressError,
  fromWire,
  normalizeAddress,
} from "../address.js";
import { RunTree } from "../run_trees.js";
import { traceable } from "../traceable.js";
import {
  applyToPayload,
  firstNamed,
  resolveFromEnv,
} from "../utils/agent_addressing.js";
import { _resetWarnedMessages } from "../utils/warn.js";
import { mockClient } from "./utils/mock_client.js";

const SUPPORT: Address = {
  agentId: "customer-support",
  agentEnvironment: "production",
};
const SUPPORT_WIRE = {
  agent_id: "customer-support",
  agent_environment: "production",
};

const ENV_KEYS = [
  "LANGSMITH_AGENT_ID",
  "LANGSMITH_AGENT_ENVIRONMENT",
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

async function postedRuns(callSpy: any, client: any): Promise<any[]> {
  await client.awaitPendingTraceBatches();
  return callSpy.mock.calls
    .filter(
      ([url, init]: [string, any]) =>
        String(url).endsWith("/runs") && init?.method === "POST",
    )
    .map(([, init]: [string, any]) =>
      JSON.parse(
        typeof init.body === "string"
          ? init.body
          : new TextDecoder().decode(init.body),
      ),
    );
}

function headersWith(baggage: string) {
  const parent = new RunTree({ name: "p", project_name: "x" });
  return { "langsmith-trace": parent.dotted_order, baggage };
}

describe("Address", () => {
  test("validates its fields", () => {
    const check = (value: unknown) => () => normalizeAddress(value);
    expect(check({ agentId: "", agentEnvironment: "e" })).toThrow();
    expect(check({ agentId: "a" })).toThrow(/agentEnvironment/);
    expect(check("support")).toThrow(/must be an object/);
    expect(check({ ...SUPPORT, agentRegion: "eu" })).toThrow(/agentRegion/);
    for (const agentId of ["a".repeat(64), "Support", "1a", "a-", "a_b"]) {
      expect(check({ agentId, agentEnvironment: "e" })).toThrow(
        /1 to 63 lowercase/,
      );
    }
    for (const agentId of ["a", "a".repeat(63), "support-v2"]) {
      expect(normalizeAddress({ agentId, agentEnvironment: "e" }).agentId).toBe(
        agentId,
      );
    }
    expect(() => fromWire({ agent_id: "a" })).toThrow(/agent_environment/);
  });

  test("the SDK keeps a frozen copy", () => {
    const mine = { ...SUPPORT };
    const run = new RunTree({ name: "r", address: mine });
    mine.agentEnvironment = "staging";
    expect(run.address).toEqual(SUPPORT);
    expect(Object.isFrozen(run.address)).toBe(true);
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
    process.env.LANGSMITH_AGENT_ENVIRONMENT = "e";
    expect(resolveFromEnv()[1]).toEqual({
      agentId: "a",
      agentEnvironment: "e",
    });
    process.env.LANGSMITH_PROJECT = "p";
    expect(() => resolveFromEnv()).toThrow(EnvAddressError);
  });
});

describe("RunTree", () => {
  test("naming both throws", () => {
    expect(
      () => new RunTree({ name: "r", address: SUPPORT, project_name: "p" }),
    ).toThrow(/not both/);
  });

  test("a child joins its parent's address", () => {
    const parent = new RunTree({ name: "p", address: SUPPORT });
    const child = parent.createChild({ name: "c", project_name: "other" });
    expect(child.address).toEqual(SUPPORT);
    expect(child.project_name).toBeUndefined();
  });

  test("a bad env leaves the run untraced", () => {
    process.env.LANGSMITH_AGENT_ID = "a";
    expect(
      new RunTree({ name: "r", tracingEnabled: true }).tracingEnabled,
    ).toBe(false);
  });

  test("posts wire fields without a project", async () => {
    const { client, callSpy } = mockClient();
    await new RunTree({ name: "r", address: SUPPORT, client }).postRun();
    const [body] = await postedRuns(callSpy, client);
    expect(body).toMatchObject(SUPPORT_WIRE);
    expect(body).not.toHaveProperty("session_name");
  });

  test("a replica equal to the run's address keeps its ids", async () => {
    const { client, callSpy } = mockClient();
    const run = new RunTree({
      name: "r",
      address: SUPPORT,
      client,
      replicas: [{ address: { ...SUPPORT } }],
    });
    await run.postRun();
    const [body] = await postedRuns(callSpy, client);
    expect(body.id).toBe(run.id);
  });

  test("an addressed replica gets its own ids", async () => {
    const { client, callSpy } = mockClient();
    await new RunTree({
      name: "r",
      project_name: "p",
      client,
      replicas: [{ projectName: "p" }, { address: SUPPORT }],
    }).postRun();
    const [toProject, toAddress] = await postedRuns(callSpy, client);
    expect(toProject.session_name).toBe("p");
    expect(toAddress).toMatchObject(SUPPORT_WIRE);
    expect(toAddress.id).not.toBe(toProject.id);
  });
});

describe("baggage", () => {
  test("round-trips the address, and it beats the caller's project", () => {
    const parent = new RunTree({ name: "p", address: SUPPORT });
    const child = RunTree.fromHeaders(parent.toHeaders(), {
      project_name: "caller",
    })!;
    expect(child.address).toEqual(SUPPORT);
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

  test("untrusted values are allowlisted and never throw", () => {
    for (const value of ["not-json", "[1]", '{"agent_id":"a"}']) {
      const child = RunTree.fromHeaders(
        headersWith(`langsmith-address=${encodeURIComponent(value)}`),
      )!;
      expect(child.address).toBeUndefined();
    }
    const child = RunTree.fromHeaders(
      headersWith(
        `langsmith-replicas=${encodeURIComponent(
          JSON.stringify([
            { ...SUPPORT_WIRE, apiKey: "leak" },
            { agent_id: "half" },
          ]),
        )}`,
      ),
    )!;
    expect(child.replicas).toEqual([{ address: SUPPORT }]);
  });
});

describe("traceable", () => {
  test("a bad decorator address throws at wrap time", () => {
    expect(() =>
      traceable(async () => "ok", { address: SUPPORT, project_name: "p" }),
    ).toThrow(/not both/);
    expect(() =>
      traceable(async () => "ok", {
        address: { agentId: "Bad", agentEnvironment: "e" },
      }),
    ).toThrow(/1 to 63 lowercase/);
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
    expect(body).not.toHaveProperty("agent_id");
  });
});

describe("Client", () => {
  test("createRun drops the run for a bad env", async () => {
    process.env.LANGSMITH_AGENT_ID = "a";
    const { client, callSpy } = mockClient();
    await client.createRun({ name: "r", inputs: {}, run_type: "chain" });
    expect(await postedRuns(callSpy, client)).toHaveLength(0);
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

  test("a rendered payload is not re-addressed from the env", () => {
    process.env.LANGSMITH_AGENT_ID = "a";
    process.env.LANGSMITH_AGENT_ENVIRONMENT = "e";
    const payload: any = { address: SUPPORT };
    applyToPayload(payload);
    applyToPayload(payload);
    expect(payload).toEqual(SUPPORT_WIRE);
  });

  test("batchIngestRuns sends the address to POST /runs/batch", async () => {
    const { client, callSpy } = mockClient();
    const run = new RunTree({ name: "r", address: SUPPORT, client });
    await client.batchIngestRuns({ runCreates: [run.toJSON()] });
    const [, init] = callSpy.mock.calls.find(([url]: [string]) =>
      String(url).endsWith("/runs/batch"),
    );
    const { post } = JSON.parse(
      typeof init.body === "string"
        ? init.body
        : new TextDecoder().decode(init.body),
    );
    expect(post).toHaveLength(1);
    expect(post[0]).toMatchObject(SUPPORT_WIRE);
    expect(post[0]).not.toHaveProperty("session_name");
  });

  test("createFeedback sends the address", async () => {
    const { client, callSpy } = mockClient();
    await client.createFeedback({
      runId: "00000000-0000-0000-0000-000000000001",
      key: "k",
      address: SUPPORT,
    });
    const [, init] = callSpy.mock.calls.find(([url]: [string]) =>
      String(url).endsWith("/feedback"),
    );
    expect(JSON.parse(init.body)).toMatchObject(SUPPORT_WIRE);
  });
});

test("a direct updateRun sends the address as wire fields", async () => {
  const { client, callSpy } = mockClient();
  await client.updateRun("00000000-0000-0000-0000-000000000001", {
    address: SUPPORT,
  });
  const [, init] = callSpy.mock.calls.find(
    ([, init]: [string, any]) => init?.method === "PATCH",
  );
  const body = JSON.parse(
    typeof init.body === "string"
      ? init.body
      : new TextDecoder().decode(init.body),
  );
  expect(body).toMatchObject(SUPPORT_WIRE);
  expect(body).not.toHaveProperty("address");
});
