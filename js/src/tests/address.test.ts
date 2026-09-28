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
import { Address, address, EnvAddressError } from "../address.js";
import { RunTree } from "../run_trees.js";
import { traceable } from "../traceable.js";
import { applyToPayload, resolve } from "../utils/agent_addressing.js";
import { _resetWarnedMessages } from "../utils/warn.js";
import { mockClient } from "./utils/mock_client.js";

const SUPPORT = address({
  agentId: "customer-support",
  agentEnvironment: "production",
});

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
  for (const key of ENV_KEYS) {
    delete process.env[key];
  }
  _resetWarnedMessages();
  jest.spyOn(console, "warn").mockImplementation(() => {});
});

afterEach(() => {
  for (const [key, value] of Object.entries(savedEnv)) {
    if (value === undefined) {
      delete process.env[key];
    } else {
      process.env[key] = value;
    }
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

describe("the handle", () => {
  test("renders to its wire fields", () => {
    expect(SUPPORT.toWire()).toEqual({
      agent_id: "customer-support",
      agent_environment: "production",
    });
    expect(Address.wireKeys()).toEqual(["agent_id", "agent_environment"]);
  });

  test("is immutable", () => {
    expect(() => {
      (SUPPORT as any).agentId = "other";
    }).toThrow();
  });

  test("rejects empty and missing fields", () => {
    expect(() => address({ agentId: "", agentEnvironment: "prod" })).toThrow(
      /agentId/,
    );
    expect(() => address({ agentId: "a" } as any)).toThrow(/agentEnvironment/);
  });

  test("caps the agent id length", () => {
    expect(() =>
      address({ agentId: "a".repeat(256), agentEnvironment: "prod" }),
    ).toThrow(/at most 255/);
  });

  test("withAgentEnvironment keeps the agent", () => {
    const staging = SUPPORT.withAgentEnvironment("staging");
    expect(staging.agentId).toBe("customer-support");
    expect(staging.agentEnvironment).toBe("staging");
    expect(staging.equals(SUPPORT)).toBe(false);
    expect(SUPPORT.equals(address(SUPPORT))).toBe(true);
  });

  test("fromWire needs every required field", () => {
    expect(Address.fromWire({})).toBeUndefined();
    expect(() => Address.fromWire({ agent_id: "a" })).toThrow(
      /agent_environment/,
    );
  });
});

describe("precedence", () => {
  test("the first level naming anything wins, whichever mode", () => {
    expect(resolve([undefined, SUPPORT], ["p", undefined])).toEqual([
      undefined,
      SUPPORT,
    ]);
    expect(resolve(["p", undefined], [undefined, SUPPORT])).toEqual([
      "p",
      undefined,
    ]);
  });

  test("both at one level throws", () => {
    expect(() => resolve(["p", SUPPORT])).toThrow(/neither outranks/);
  });

  test("falls back to the env address", () => {
    process.env.LANGSMITH_AGENT_ID = "env-agent";
    process.env.LANGSMITH_AGENT_ENVIRONMENT = "prod";
    const [project, addr] = resolve();
    expect(project).toBeUndefined();
    expect(addr?.toWire()).toEqual({
      agent_id: "env-agent",
      agent_environment: "prod",
    });
  });

  test("falls back to the env project, then default", () => {
    expect(resolve()).toEqual(["default", undefined]);
    process.env.LANGSMITH_PROJECT = "env-project";
    expect(resolve()).toEqual(["env-project", undefined]);
  });

  test("half an env address is an EnvAddressError", () => {
    process.env.LANGSMITH_AGENT_ID = "env-agent";
    expect(() => resolve()).toThrow(EnvAddressError);
  });

  test("env address beside env project is an EnvAddressError", () => {
    process.env.LANGSMITH_AGENT_ID = "env-agent";
    process.env.LANGSMITH_AGENT_ENVIRONMENT = "prod";
    process.env.LANGSMITH_PROJECT = "env-project";
    expect(() => resolve()).toThrow(EnvAddressError);
  });

  test("a code-level project skips a bad env", () => {
    process.env.LANGSMITH_AGENT_ID = "env-agent";
    expect(resolve(["p", undefined])).toEqual(["p", undefined]);
  });
});

describe("RunTree", () => {
  test("an addressed run has no project", () => {
    const run = new RunTree({ name: "r", address: SUPPORT });
    expect(run.address).toBe(SUPPORT);
    expect(run.project_name).toBeUndefined();
  });

  test("naming both throws", () => {
    expect(
      () => new RunTree({ name: "r", address: SUPPORT, project_name: "p" }),
    ).toThrow(/not both/);
  });

  test("rejects a non-Address", () => {
    expect(
      () => new RunTree({ name: "r", address: { agentId: "a" } as any }),
    ).toThrow(/must be a langsmith `Address`/);
  });

  test("a child joins its parent's address", () => {
    const parent = new RunTree({ name: "p", address: SUPPORT });
    const child = parent.createChild({ name: "c", project_name: "other" });
    expect(child.address).toBe(SUPPORT);
    expect(child.project_name).toBeUndefined();
  });

  test("a bad env leaves the run untraced instead of throwing", () => {
    process.env.LANGSMITH_AGENT_ID = "env-agent";
    const run = new RunTree({ name: "r", tracingEnabled: true });
    expect(run.tracingEnabled).toBe(false);
    expect(console.warn).toHaveBeenCalledWith(
      expect.stringContaining("not tracing this call"),
    );
  });

  test("posts the address as wire fields, without a project", async () => {
    const { client, callSpy } = mockClient();
    const run = new RunTree({ name: "r", address: SUPPORT, client });
    await run.postRun();
    const [body] = await postedRuns(callSpy, client);
    expect(body.agent_id).toBe("customer-support");
    expect(body.agent_environment).toBe("production");
    expect(body).not.toHaveProperty("session_name");
    expect(body).not.toHaveProperty("address");
  });

  test("a project run is left alone", async () => {
    process.env.LANGSMITH_AGENT_ID = "env-agent";
    process.env.LANGSMITH_AGENT_ENVIRONMENT = "prod";
    const { client, callSpy } = mockClient();
    const run = new RunTree({ name: "r", project_name: "p", client });
    await run.postRun();
    const [body] = await postedRuns(callSpy, client);
    expect(body.session_name).toBe("p");
    expect(body).not.toHaveProperty("agent_id");
  });
});

describe("replicas", () => {
  test("a bare Address replica gets its own ids", async () => {
    const { client, callSpy } = mockClient();
    const run = new RunTree({
      name: "r",
      project_name: "p",
      client,
      replicas: [{ projectName: "p" }, SUPPORT],
    });
    await run.postRun();
    const bodies = await postedRuns(callSpy, client);
    expect(bodies).toHaveLength(2);
    const [toProject, toAddress] = bodies;
    expect(toProject.session_name).toBe("p");
    expect(toAddress.agent_id).toBe("customer-support");
    expect(toAddress).not.toHaveProperty("session_name");
    expect(toAddress.id).not.toBe(toProject.id);
  });

  test("a replica naming both throws", () => {
    const run = new RunTree({
      name: "r",
      project_name: "p",
      replicas: [{ projectName: "q", address: SUPPORT }],
    });
    expect(() => (run as any)._replicaAddressing(run.replicas![0])).toThrow(
      /not both/,
    );
  });

  test("Address.replica builds a WriteReplica", () => {
    expect(SUPPORT.replica({ primary: true })).toEqual({
      primary: true,
      address: SUPPORT,
    });
    expect(() => SUPPORT.replica({ projectName: "p" } as any)).toThrow();
  });
});

describe("distributed tracing", () => {
  test("round-trips the address through baggage", () => {
    const parent = new RunTree({ name: "p", address: SUPPORT });
    const headers = parent.toHeaders();
    expect(headers.baggage).toContain("langsmith-address=");
    const child = RunTree.fromHeaders(headers)!;
    expect(child.address?.equals(SUPPORT)).toBe(true);
    expect(child.project_name).toBeUndefined();
  });

  test("the header's destination beats the caller's", () => {
    const parent = new RunTree({ name: "p", address: SUPPORT });
    const child = RunTree.fromHeaders(parent.toHeaders(), {
      project_name: "caller",
    })!;
    expect(child.address?.equals(SUPPORT)).toBe(true);
    expect(child.project_name).toBeUndefined();
  });

  test("the caller's destination applies when the header names none", () => {
    const parent = new RunTree({ name: "p", project_name: "x" });
    const headers = {
      "langsmith-trace": parent.dotted_order,
      baggage: "",
    };
    const child = RunTree.fromHeaders(headers, { address: SUPPORT })!;
    expect(child.address).toBe(SUPPORT);
  });

  test("a header naming both is rejected", () => {
    const parent = new RunTree({ name: "p", address: SUPPORT });
    const { baggage } = parent.toHeaders();
    const headers = {
      "langsmith-trace": parent.dotted_order,
      baggage: `${baggage},langsmith-project=p`,
    };
    expect(RunTree.fromHeaders(headers)).toBeUndefined();
  });

  test("a malformed header address is ignored, not thrown", () => {
    const parent = new RunTree({ name: "p", project_name: "x" });
    for (const value of ["not-json", '{"agent_id":"a"}', "[1]"]) {
      const child = RunTree.fromHeaders({
        "langsmith-trace": parent.dotted_order,
        baggage: `langsmith-address=${encodeURIComponent(value)}`,
      })!;
      expect(child.address).toBeUndefined();
    }
  });

  test("only wire keys are read from a header address", () => {
    const parent = new RunTree({ name: "p", project_name: "x" });
    const child = RunTree.fromHeaders({
      "langsmith-trace": parent.dotted_order,
      baggage: `langsmith-address=${encodeURIComponent(
        JSON.stringify({
          agent_id: "a",
          agent_environment: "e",
          apiKey: "leak",
        }),
      )}`,
    })!;
    expect(child.address?.toWire()).toEqual({
      agent_id: "a",
      agent_environment: "e",
    });
  });

  test("header replicas can carry an address", () => {
    const parent = new RunTree({ name: "p", project_name: "x" });
    const child = RunTree.fromHeaders({
      "langsmith-trace": parent.dotted_order,
      baggage: `langsmith-replicas=${encodeURIComponent(
        JSON.stringify([
          { agent_id: "a", agent_environment: "e", apiKey: "leak" },
          { agent_id: "half" },
        ]),
      )}`,
    })!;
    expect(child.replicas).toHaveLength(1);
    expect(child.replicas![0].address?.toWire()).toEqual({
      agent_id: "a",
      agent_environment: "e",
    });
    expect(child.replicas![0]).not.toHaveProperty("apiKey");
  });
});

describe("traceable", () => {
  test("sends the run to the decorator's address", async () => {
    const { client, callSpy } = mockClient();
    const fn = traceable(async () => "ok", {
      client,
      tracingEnabled: true,
      address: SUPPORT,
    });
    await fn();
    const [body] = await postedRuns(callSpy, client);
    expect(body.agent_id).toBe("customer-support");
    expect(body).not.toHaveProperty("session_name");
  });

  test("a decorator naming both throws at wrap time", () => {
    expect(() =>
      traceable(async () => "ok", { address: SUPPORT, project_name: "p" }),
    ).toThrow(/not both/);
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

  test("nested runs join the parent's address", async () => {
    const { client, callSpy } = mockClient();
    const child = traceable(async () => "child", {
      name: "child",
      client,
      tracingEnabled: true,
      project_name: "ignored",
    });
    const parent = traceable(async () => child(), {
      name: "parent",
      client,
      tracingEnabled: true,
      address: SUPPORT,
    });
    await parent();
    const bodies = await postedRuns(callSpy, client);
    expect(bodies).toHaveLength(2);
    for (const body of bodies) {
      expect(body.agent_id).toBe("customer-support");
      expect(body).not.toHaveProperty("session_name");
    }
  });

  test("a bad env runs the function untraced", async () => {
    process.env.LANGSMITH_AGENT_ID = "env-agent";
    const { client, callSpy } = mockClient();
    const fn = traceable(async () => "ok", { client, tracingEnabled: true });
    expect(await fn()).toBe("ok");
    expect(await postedRuns(callSpy, client)).toHaveLength(0);
  });
});

describe("client", () => {
  test("createRun picks up the env address", async () => {
    process.env.LANGSMITH_AGENT_ID = "env-agent";
    process.env.LANGSMITH_AGENT_ENVIRONMENT = "prod";
    const { client, callSpy } = mockClient();
    await client.createRun({ name: "r", inputs: {}, run_type: "chain" });
    const [body] = await postedRuns(callSpy, client);
    expect(body.agent_id).toBe("env-agent");
  });

  test("createRun drops the run for a bad env", async () => {
    process.env.LANGSMITH_AGENT_ID = "env-agent";
    const { client, callSpy } = mockClient();
    await client.createRun({ name: "r", inputs: {}, run_type: "chain" });
    expect(await postedRuns(callSpy, client)).toHaveLength(0);
  });

  test("createRun rejects a project beside an address", async () => {
    const { client } = mockClient();
    await expect(
      client.createRun({
        name: "r",
        inputs: {},
        run_type: "chain",
        project_name: "p",
        address: SUPPORT,
      }),
    ).rejects.toThrow(/not both/);
  });

  test("an update never consults the env", () => {
    process.env.LANGSMITH_AGENT_ID = "env-agent";
    const payload: any = { id: "x" };
    applyToPayload(payload, { update: true });
    expect(payload).toEqual({ id: "x" });
  });

  test("a rendered payload is not re-addressed from the env", () => {
    process.env.LANGSMITH_AGENT_ID = "env-agent";
    process.env.LANGSMITH_AGENT_ENVIRONMENT = "prod";
    const payload: any = { address: SUPPORT };
    applyToPayload(payload);
    applyToPayload(payload);
    expect(payload.agent_id).toBe("customer-support");
  });

  test("createFeedback sends the address", async () => {
    const { client, callSpy } = mockClient();
    await client.createFeedback({
      runId: "00000000-0000-0000-0000-000000000001",
      key: "k",
      address: SUPPORT,
    });
    const call = callSpy.mock.calls.find(([url]: [string]) =>
      String(url).endsWith("/feedback"),
    );
    const body = JSON.parse(call[1].body);
    expect(body.agent_id).toBe("customer-support");
    expect(body.agent_environment).toBe("production");
  });

  test("getRunUrl refuses an addressed run", async () => {
    const { client } = mockClient();
    await expect(
      client.getRunUrl({ run: { id: "x", address: SUPPORT } as any }),
    ).rejects.toThrow(/No run URL/);
  });
});
