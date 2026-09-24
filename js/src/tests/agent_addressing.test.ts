/* eslint-disable no-process-env, @typescript-eslint/no-explicit-any */

import { jest } from "@jest/globals";
import { RunTree } from "../run_trees.js";
import { Client } from "../client.js";
import { traceable } from "../traceable.js";
import { mockClient } from "./utils/mock_client.js";
import { _resetWarnedMessages } from "../utils/warn.js";

const _DATE = 1620000000000;
Date.now = jest.fn(() => _DATE);

// The agent env vars have no `LANGCHAIN_` alias, and the client reads them
// once per construction, so every test starts from a clean slate.
function clearAgentEnv() {
  delete process.env.LANGSMITH_AGENT_ID;
  delete process.env.LANGSMITH_AGENT_ENVIRONMENT;
  delete process.env.LANGSMITH_PROJECT;
  delete process.env.LANGCHAIN_PROJECT;
  delete process.env.LANGCHAIN_SESSION;
}

// The client posts each run as a single JSON body when auto-batching is off
// (`mockClient`'s configuration); the body may arrive as a byte array.
function sentRunBodies(callSpy: jest.Mock): Record<string, any>[] {
  const bodies: Record<string, any>[] = [];
  for (const call of callSpy.mock.calls) {
    const url = call[0] as string;
    if (!url.endsWith("/runs") && !/\/runs\/[^/]+$/.test(url)) continue;
    const init = call[1] as RequestInit;
    const body = init.body;
    if (body == null) continue;
    let text: string;
    if (typeof body === "string") {
      text = body;
    } else if (body instanceof Uint8Array) {
      text = new TextDecoder().decode(body);
    } else if (Array.isArray(body)) {
      text = new TextDecoder().decode(new Uint8Array(body as number[]));
    } else if (
      // A Uint8Array from a different Jest realm fails `instanceof`.
      (body as { constructor?: { name?: string } }).constructor?.name ===
      "Uint8Array"
    ) {
      text = new TextDecoder().decode(body as Uint8Array);
    } else {
      continue;
    }
    try {
      bodies.push(JSON.parse(text));
    } catch (_e) {
      // Not a JSON run payload; ignore.
    }
  }
  return bodies;
}

function lastRunBody(callSpy: jest.Mock): Record<string, any> {
  const bodies = sentRunBodies(callSpy);
  expect(bodies.length).toBeGreaterThan(0);
  return bodies[bodies.length - 1];
}

beforeEach(() => {
  clearAgentEnv();
  _resetWarnedMessages();
});

afterEach(() => {
  clearAgentEnv();
});

describe("agent addressing env vars", () => {
  it("agent env replaces the default project", async () => {
    process.env.LANGSMITH_AGENT_ID = "my-agent";
    process.env.LANGSMITH_AGENT_ENVIRONMENT = "staging";
    const { client, callSpy } = mockClient();
    const runTree = new RunTree({ name: "test", client });
    await runTree.postRun();
    await client.flush().catch(() => {});
    const bodies = sentRunBodies(callSpy);
    expect(bodies.length).toBeGreaterThan(0);
    for (const body of bodies) {
      expect(body.agent_id).toBe("my-agent");
      expect(body.agent_environment).toBe("staging");
      expect(body.session_name).toBeUndefined();
    }
  });

  it("LANGCHAIN_ aliases are not read for the agent pair", () => {
    process.env.LANGCHAIN_AGENT_ID = "aliased";
    process.env.LANGCHAIN_AGENT_ENVIRONMENT = "aliased";
    const runTree = new RunTree({ name: "test" });
    expect(runTree.agent_id).toBeUndefined();
    expect(runTree.agent_environment).toBeUndefined();
  });

  it("explicit project wins over the agent env", async () => {
    process.env.LANGSMITH_AGENT_ID = "my-agent";
    process.env.LANGSMITH_AGENT_ENVIRONMENT = "staging";
    const { client, callSpy } = mockClient();
    const runTree = new RunTree({
      name: "test",
      client,
      project_name: "my-project",
    });
    await runTree.postRun();
    await client.flush().catch(() => {});
    const bodies = sentRunBodies(callSpy);
    expect(bodies.length).toBeGreaterThan(0);
    for (const body of bodies) {
      expect(body.session_name).toBe("my-project");
      expect(body.agent_id).toBeUndefined();
      expect(body.agent_environment).toBeUndefined();
    }
  });

  it("agent environment alone is forwarded, not defaulted away", async () => {
    process.env.LANGSMITH_AGENT_ENVIRONMENT = "production";
    const { client, callSpy } = mockClient();
    const runTree = new RunTree({ name: "test", client });
    await runTree.postRun();
    await client.flush().catch(() => {});
    const bodies = sentRunBodies(callSpy);
    expect(bodies.length).toBeGreaterThan(0);
    for (const body of bodies) {
      expect(body.agent_id).toBeUndefined();
      expect(body.agent_environment).toBe("production");
      expect(body.session_name).toBeUndefined();
    }
  });

  it("explicit agent half is completed from the env var", async () => {
    process.env.LANGSMITH_AGENT_ENVIRONMENT = "production";
    const { client, callSpy } = mockClient();
    const runTree = new RunTree({
      name: "test",
      client,
      agent_id: "explicit",
    } as never);
    await runTree.postRun();
    await client.flush().catch(() => {});
    const bodies = sentRunBodies(callSpy);
    expect(bodies.length).toBeGreaterThan(0);
    for (const body of bodies) {
      expect(body.agent_id).toBe("explicit");
      expect(body.agent_environment).toBe("production");
    }
  });
});

describe("agent addressing on run trees", () => {
  it("children inherit agent addressing", () => {
    const { client } = mockClient();
    const parent = new RunTree({
      name: "parent",
      client,
      project_name: undefined,
      agent_id: "my-agent",
      agent_environment: "staging",
    } as never);
    const child = parent.createChild({ name: "child" });
    expect(child.agent_id).toBe("my-agent");
    expect(child.agent_environment).toBe("staging");
    expect(child.project_name).toBeUndefined();
  });

  it("rejects a call that names both a project and an agent", () => {
    const { client } = mockClient();
    expect(
      () =>
        new RunTree({
          name: "test",
          client,
          project_name: "proj",
          agent_id: "ag",
          agent_environment: "staging",
        } as never),
    ).toThrow(/addressed by project/);
  });

  it("patches carry the same addressing as their post", async () => {
    process.env.LANGSMITH_AGENT_ID = "my-agent";
    process.env.LANGSMITH_AGENT_ENVIRONMENT = "staging";
    const { client, callSpy } = mockClient();
    const runTree = new RunTree({ name: "test", client });
    await runTree.postRun();
    await runTree.patchRun();
    await client.flush().catch(() => {});
    const patch = lastRunBody(callSpy);
    expect(patch?.agent_id).toBe("my-agent");
    expect(patch?.agent_environment).toBe("staging");
    expect(patch?.session_name).toBeUndefined();
  });
});

describe("agent addressing in baggage headers", () => {
  it("survives the hop", () => {
    const { client } = mockClient();
    const parent = new RunTree({
      name: "parent",
      client,
      agent_id: "my-agent",
      agent_environment: "staging",
    } as never);
    const headers = parent.toHeaders();
    const child = RunTree.fromHeaders(headers, { name: "child" });
    expect(child?.agent_id).toBe("my-agent");
    expect(child?.agent_environment).toBe("staging");
    expect(child?.project_name).toBeUndefined();
  });

  it("a baggage project is ignored when the caller named an agent", () => {
    const { client } = mockClient();
    const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});
    try {
      // A project-addressed parent, so its baggage carries a project.
      const parent = new RunTree({
        name: "parent",
        client,
        project_name: "parent-project",
      });
      const headers = parent.toHeaders();
      const child = RunTree.fromHeaders(headers, {
        name: "child",
        agent_id: "other-agent",
        agent_environment: "staging",
      } as never);
      expect(child?.agent_id).toBe("other-agent");
      expect(child?.project_name).toBeUndefined();
      expect(warnSpy).toHaveBeenCalled();
    } finally {
      warnSpy.mockRestore();
    }
  });

  it("half a pair in a header is ignored rather than raised on", () => {
    const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});
    try {
      const headers = {
        "langsmith-trace":
          "20230914T223155647Z1b64098b-4ab7-43f6-afee-992304f198d8",
        baggage: "langsmith-agent-id=half-pair",
      };
      const runTree = RunTree.fromHeaders(headers, { name: "child" });
      expect(runTree?.agent_id).toBeUndefined();
      expect(runTree?.agent_environment).toBeUndefined();
      expect(warnSpy).toHaveBeenCalled();
    } finally {
      warnSpy.mockRestore();
    }
  });
});

describe("agent-addressed replicas", () => {
  it("replica agent is used when it names no project", async () => {
    const { client, callSpy } = mockClient();
    const runTree = new RunTree({
      name: "test",
      client,
      replicas: [
        {
          agentId: "ag-remote",
          agentEnvironment: "staging",
        },
      ],
    } as never);
    await runTree.postRun();
    await client.flush().catch(() => {});
    const bodies = sentRunBodies(callSpy);
    expect(bodies.length).toBeGreaterThan(0);
    for (const body of bodies) {
      expect(body.agent_id).toBe("ag-remote");
      expect(body.agent_environment).toBe("staging");
      expect(body.session_name).toBeUndefined();
    }
  });

  it("agent-addressed replicas get distinct run ids", async () => {
    const { client, callSpy } = mockClient();
    const runTree = new RunTree({
      name: "test",
      client,
      replicas: [
        { projectName: "proj-a" },
        { agentId: "ag", agentEnvironment: "staging" },
      ],
    } as never);
    await runTree.postRun();
    await client.flush().catch(() => {});
    const bodies = sentRunBodies(callSpy);
    const ids = bodies.map((body) => body.id);
    expect(new Set(ids).size).toBe(2);
  });

  it("rejects a replica that names both a project and an agent", async () => {
    const { client } = mockClient();
    const runTree = new RunTree({
      name: "test",
      client,
      replicas: [
        { projectName: "proj", agentId: "ag", agentEnvironment: "staging" },
      ],
    } as never);
    await expect(runTree.postRun()).rejects.toThrow(/addressed by project/);
  });
});

describe("client-side addressing", () => {
  it("createRun forwards the agent pair and drops the project", async () => {
    process.env.LANGSMITH_AGENT_ID = "my-agent";
    process.env.LANGSMITH_AGENT_ENVIRONMENT = "staging";
    const { client, callSpy } = mockClient();
    await client.createRun({
      name: "test",
      inputs: { input: "foo" },
      run_type: "chain",
      id: "1b64098b-4ab7-43f6-afee-992304f198d8",
    });
    const bodies = sentRunBodies(callSpy);
    expect(bodies.length).toBeGreaterThan(0);
    for (const body of bodies) {
      expect(body.agent_id).toBe("my-agent");
      expect(body.agent_environment).toBe("staging");
      expect(body.session_name).toBeUndefined();
    }
  });

  it("agent env vars stay out of run metadata", async () => {
    // First-class run fields, not metadata: resolving them into the body
    // must not also echo them into every run's metadata.
    process.env.LANGSMITH_AGENT_ID = "my-agent";
    process.env.LANGSMITH_AGENT_ENVIRONMENT = "staging";
    const { client, callSpy } = mockClient();
    await client.createRun({
      name: "test",
      inputs: { input: "foo" },
      run_type: "chain",
      id: "1b64098b-4ab7-43f6-afee-992304f198d8",
    });
    const body = lastRunBody(callSpy);
    const metadata = body.extra?.metadata ?? {};
    expect(metadata.LANGSMITH_AGENT_ID).toBeUndefined();
    expect(metadata.LANGSMITH_AGENT_ENVIRONMENT).toBeUndefined();
  });

  it("explicit project on createRun beats the agent env", async () => {
    process.env.LANGSMITH_AGENT_ID = "my-agent";
    process.env.LANGSMITH_AGENT_ENVIRONMENT = "staging";
    const { client, callSpy } = mockClient();
    await client.createRun({
      name: "test",
      inputs: { input: "foo" },
      run_type: "chain",
      project_name: "my-project",
      id: "1b64098b-4ab7-43f6-afee-992304f198d8",
    });
    const bodies = sentRunBodies(callSpy);
    expect(bodies.length).toBeGreaterThan(0);
    for (const body of bodies) {
      expect(body.session_name).toBe("my-project");
      expect(body.agent_id).toBeUndefined();
    }
  });

  it("feedback travels to the agent it names", async () => {
    const { client, callSpy } = mockClient();
    await client.createFeedback({
      runId: "1b64098b-4ab7-43f6-afee-992304f198d8",
      key: "correctness",
      score: 1,
      agentId: "my-agent",
      agentEnvironment: "staging",
    });
    const body = JSON.parse(
      (callSpy.mock.calls[callSpy.mock.calls.length - 1][1] as RequestInit)
        .body as string,
    );
    expect(body.agent_id).toBe("my-agent");
    expect(body.agent_environment).toBe("staging");
  });
});

describe("agent-addressed replica reroot state", () => {
  beforeEach(clearAgentEnv);

  it("keeps each agent replica's rerooted trace root separate", () => {
    const { client } = mockClient();
    const root = new RunTree({
      name: "Root",
      inputs: {},
      client,
      project_name: "base",
    });
    const middle = root.createChild({ name: "Middle" });
    const leaf = middle.createChild({ name: "Leaf" });

    // Replica A reroots at `middle` -- the endpoint is shared with B.
    (middle as any)._remapForProject({
      agentId: "agent-a",
      agentEnvironment: "staging",
      reroot: true,
      excludeChildRuns: true,
    });

    // Replica B never rerooted, so the leaf keeps its full hierarchy there.
    const forB = (leaf as any)._remapForProject({
      agentId: "agent-b",
      agentEnvironment: "staging",
      excludeChildRuns: true,
    });
    expect(forB.dotted_order.split(".")).toHaveLength(3);

    // Replica A sees the leaf under the rerooted `middle`.
    const forA = (leaf as any)._remapForProject({
      agentId: "agent-a",
      agentEnvironment: "staging",
      excludeChildRuns: true,
    });
    expect(forA.dotted_order.split(".")).toHaveLength(2);
  });
});

describe("direct batch ingestion addressing", () => {
  const RUN_ID = "1b64098b-4ab7-43f6-afee-992304f198d8";
  const TRACE_ID = RUN_ID;
  const DOTTED_ORDER = `20210503T000000000001Z${RUN_ID}`;

  function makeCreate(extra: Record<string, unknown> = {}): any {
    return {
      id: RUN_ID,
      trace_id: TRACE_ID,
      dotted_order: DOTTED_ORDER,
      name: "test",
      inputs: { input: "foo" },
      run_type: "chain",
      start_time: _DATE,
      ...extra,
    };
  }

  function makeUpdate(extra: Record<string, unknown> = {}): any {
    return {
      id: "2c64098b-4ab7-43f6-afee-992304f198d9",
      trace_id: "2c64098b-4ab7-43f6-afee-992304f198d9",
      dotted_order:
        "20210503T000000000001Z2c64098b-4ab7-43f6-afee-992304f198d9",
      outputs: { output: "bar" },
      end_time: _DATE,
      ...extra,
    };
  }

  describe.each(["batchIngestRuns", "multipartIngestRuns"] as const)(
    "%s",
    (method) => {
      // Capture what reaches the transport-level implementation.
      function spyOnImpl(client: any) {
        return jest
          .spyOn(client, `_${method}`)
          .mockResolvedValue(undefined as never) as jest.Mock;
      }

      it("addresses creates from the agent env like createRun", async () => {
        process.env.LANGSMITH_AGENT_ID = "my-agent";
        process.env.LANGSMITH_AGENT_ENVIRONMENT = "staging";
        const { client } = mockClient();
        const impl = spyOnImpl(client);
        const create = makeCreate();
        await (client as any)[method]({ runCreates: [create] });
        const { runCreates } = impl.mock.calls[0][0] as any;
        expect(runCreates[0].agent_id).toBe("my-agent");
        expect(runCreates[0].agent_environment).toBe("staging");
        expect("session_name" in runCreates[0]).toBe(false);
        // The caller's object is left alone.
        expect(create.agent_id).toBeUndefined();
      });

      it("a create that names a project keeps it", async () => {
        process.env.LANGSMITH_AGENT_ID = "my-agent";
        process.env.LANGSMITH_AGENT_ENVIRONMENT = "staging";
        const { client } = mockClient();
        const impl = spyOnImpl(client);
        await (client as any)[method]({
          runCreates: [makeCreate({ session_name: "my-project" })],
        });
        const { runCreates } = impl.mock.calls[0][0] as any;
        expect(runCreates[0].session_name).toBe("my-project");
        expect(runCreates[0].agent_id).toBeUndefined();
      });

      it("standalone updates do not consult the env", async () => {
        process.env.LANGSMITH_AGENT_ID = "my-agent";
        process.env.LANGSMITH_AGENT_ENVIRONMENT = "staging";
        const { client } = mockClient();
        const impl = spyOnImpl(client);
        await (client as any)[method]({ runUpdates: [makeUpdate()] });
        const { runUpdates } = impl.mock.calls[0][0] as any;
        expect(runUpdates[0].agent_id).toBeUndefined();
        expect(runUpdates[0].agent_environment).toBeUndefined();
      });

      it("updates keep an agent they name explicitly", async () => {
        const { client } = mockClient();
        const impl = spyOnImpl(client);
        await (client as any)[method]({
          runUpdates: [
            makeUpdate({ agent_id: "my-agent", agent_environment: "staging" }),
          ],
        });
        const { runUpdates } = impl.mock.calls[0][0] as any;
        expect(runUpdates[0].agent_id).toBe("my-agent");
        expect(runUpdates[0].agent_environment).toBe("staging");
      });
    },
  );

  it("sends the agent pair on the wire via batchIngestRuns", async () => {
    process.env.LANGSMITH_AGENT_ID = "my-agent";
    process.env.LANGSMITH_AGENT_ENVIRONMENT = "staging";
    const { client, callSpy } = mockClient();
    await client.batchIngestRuns({ runCreates: [makeCreate()] });
    const call = callSpy.mock.calls.find((c: any) =>
      (c[0] as string).endsWith("/runs/batch"),
    );
    expect(call).toBeDefined();
    const init = call[1] as RequestInit;
    const raw = init.body;
    const text =
      typeof raw === "string"
        ? raw
        : new TextDecoder().decode(raw as Uint8Array);
    const body = JSON.parse(text);
    expect(body.post[0].agent_id).toBe("my-agent");
    expect(body.post[0].agent_environment).toBe("staging");
    expect(body.post[0].session_name).toBeUndefined();
  });
});

describe("inherited addressing carrying both modes", () => {
  // An env-only setup that names both a project and an agent: the SDK keeps
  // both so the endpoint refuses the run, and must not throw mid-trace.
  function setBothEnv() {
    process.env.LANGSMITH_PROJECT = "proj";
    process.env.LANGSMITH_AGENT_ID = "agent";
    process.env.LANGSMITH_AGENT_ENVIRONMENT = "staging";
  }

  it("createChild inherits the parent's addressing without throwing", () => {
    setBothEnv();
    const { client } = mockClient();
    const root = new RunTree({ name: "root", client });
    expect(root.project_name).toBe("proj");
    expect(root.agent_id).toBe("agent");
    const child = root.createChild({ name: "child" });
    expect(child.project_name).toBe("proj");
    expect(child.agent_id).toBe("agent");
    expect(child.agent_environment).toBe("staging");
    const grandchild = child.createChild({ name: "grandchild" });
    expect(grandchild.project_name).toBe("proj");
    expect(grandchild.agent_id).toBe("agent");
  });

  it("nested traceable calls still run", async () => {
    setBothEnv();
    const { client } = mockClient();
    const inner = traceable(async (x: string) => `${x}!`, {
      name: "inner",
      client,
      tracingEnabled: true,
    });
    const outer = traceable(async (x: string) => inner(x), {
      name: "outer",
      client,
      tracingEnabled: true,
    });
    await expect(outer("hi")).resolves.toBe("hi!");
  });

  it("a child follows its parent even when it names an agent", () => {
    // As in Python: the child's parent_run_id points into the parent's
    // destination, so addressing it elsewhere would split the trace.
    const { client } = mockClient();
    const root = new RunTree({ name: "root", client, project_name: "proj" });
    const child = root.createChild({
      name: "child",
      agent_id: "agent",
      agent_environment: "staging",
    });
    expect(child.project_name).toBe("proj");
    expect(child.agent_id).toBeUndefined();
    expect(child.agent_environment).toBeUndefined();
  });

  it("a child's own project and agent are both ignored", () => {
    const { client } = mockClient();
    const root = new RunTree({
      name: "root",
      client,
      agent_id: "agent",
      agent_environment: "staging",
    });
    const child = root.createChild({
      name: "child",
      project_name: "other",
      agent_id: "other-agent",
      agent_environment: "production",
    });
    expect(child.project_name).toBeUndefined();
    expect(child.agent_id).toBe("agent");
    expect(child.agent_environment).toBe("staging");
  });

  it("fromHeaders accepts baggage carrying both modes", () => {
    setBothEnv();
    const { client } = mockClient();
    const root = new RunTree({ name: "root", client });
    const headers = root.toHeaders();
    clearAgentEnv();
    const received = RunTree.fromHeaders(headers, { client });
    expect(received).toBeDefined();
    // As in Python, the header's project wins and its agent is dropped, so
    // the run is not sent to both.
    expect(received!.project_name).toBe("proj");
    expect(received!.agent_id).toBeUndefined();
    expect(received!.agent_environment).toBeUndefined();
    expect(() => received!.createChild({ name: "child" })).not.toThrow();
  });
});

describe("fromHeaders addressing", () => {
  function agentHeaders() {
    const { client } = mockClient();
    const root = new RunTree({
      name: "root",
      client,
      agent_id: "agent",
      agent_environment: "staging",
    });
    return root.toHeaders();
  }

  it("applies the header's agent when nothing names a project", () => {
    const { client } = mockClient();
    const received = RunTree.fromHeaders(agentHeaders(), { client });
    expect(received!.agent_id).toBe("agent");
    expect(received!.agent_environment).toBe("staging");
    expect(received!.project_name).toBeUndefined();
  });

  it("a caller-named project drops the header's agent", () => {
    const { client } = mockClient();
    const received = RunTree.fromHeaders(agentHeaders(), {
      client,
      project_name: "mine",
    });
    expect(received!.project_name).toBe("mine");
    expect(received!.agent_id).toBeUndefined();
    expect(received!.agent_environment).toBeUndefined();
  });

  it("a caller naming both a project and an agent is still rejected", () => {
    const { client } = mockClient();
    expect(() =>
      RunTree.fromHeaders(agentHeaders(), {
        client,
        project_name: "mine",
        agent_id: "agent",
        agent_environment: "staging",
      }),
    ).toThrow(/not both/);
  });
});

describe("createRun conflict", () => {
  it("rejects a project and an agent in the same call", async () => {
    const { client, callSpy } = mockClient();
    await expect(
      client.createRun({
        name: "test",
        inputs: {},
        run_type: "chain",
        project_name: "proj",
        agent_id: "agent",
        agent_environment: "staging",
      }),
    ).rejects.toThrow(/not both/);
    expect(sentRunBodies(callSpy)).toHaveLength(0);
  });

  it("a project with null agent fields is not a conflict", async () => {
    const { client, callSpy } = mockClient();
    await client.createRun({
      name: "test",
      inputs: {},
      run_type: "chain",
      project_name: "proj",
      agent_id: null,
      agent_environment: null,
    });
    const body = lastRunBody(callSpy);
    expect(body.session_name).toBe("proj");
    expect("agent_id" in body).toBe(false);
  });
});

describe("null agent values count as unset", () => {
  it("a create with null agent fields keeps its project", async () => {
    const { client, callSpy } = mockClient();
    await client.batchIngestRuns({
      runCreates: [
        {
          id: "1b64098b-4ab7-43f6-afee-992304f198d8",
          trace_id: "1b64098b-4ab7-43f6-afee-992304f198d8",
          dotted_order:
            "20210503T000000000001Z1b64098b-4ab7-43f6-afee-992304f198d8",
          name: "test",
          inputs: {},
          run_type: "chain",
          start_time: _DATE,
          session_name: "proj",
          agent_id: null,
          agent_environment: null,
        } as any,
      ],
    });
    const call = callSpy.mock.calls.find((c: any) =>
      (c[0] as string).endsWith("/runs/batch"),
    );
    const raw = (call[1] as RequestInit).body;
    const text =
      typeof raw === "string" ? raw : new TextDecoder().decode(raw as any);
    const body = JSON.parse(text);
    expect(body.post[0].session_name).toBe("proj");
    expect("agent_id" in body.post[0]).toBe(false);
    expect("agent_environment" in body.post[0]).toBe(false);
  });

  it("a create with null agent fields and no project falls to the env", async () => {
    process.env.LANGSMITH_AGENT_ID = "env-agent";
    process.env.LANGSMITH_AGENT_ENVIRONMENT = "staging";
    const { client, callSpy } = mockClient();
    await client.createRun({
      name: "test",
      inputs: {},
      run_type: "chain",
      agent_id: null,
      agent_environment: null,
    });
    const body = lastRunBody(callSpy);
    expect(body.agent_id).toBe("env-agent");
    expect(body.agent_environment).toBe("staging");
  });

  it("a run tree with null agent fields resolves like one naming none", () => {
    process.env.LANGSMITH_AGENT_ID = "env-agent";
    process.env.LANGSMITH_AGENT_ENVIRONMENT = "staging";
    const { client } = mockClient();
    const run = new RunTree({
      name: "root",
      client,
      agent_id: null as any,
      agent_environment: null as any,
    });
    expect(run.agent_id).toBe("env-agent");
    expect(run.agent_environment).toBe("staging");
  });
});

describe("reviewed hunks", () => {
  it("updateRun queues the addressed payload under auto-batching", async () => {
    const client = new Client({
      apiKey: "MOCK",
      autoBatchTracing: true,
      fetchImplementation: jest
        .fn<typeof fetch>()
        .mockResolvedValue(new Response("{}")),
    });
    const queued = jest
      .spyOn(client as any, "processRunOperation")
      .mockResolvedValue(undefined as never) as jest.Mock;
    const id = "1b64098b-4ab7-43f6-afee-992304f198d8";
    await client.updateRun(id, {
      trace_id: id,
      dotted_order: `20210503T000000000001Z${id}`,
      end_time: _DATE,
      session_name: "proj",
      agent_id: null,
      agent_environment: null,
    } as any);
    const item = (queued.mock.calls[0][0] as any).item;
    expect(item.session_name).toBe("proj");
    expect("agent_id" in item).toBe(false);
    expect("agent_environment" in item).toBe(false);
  });

  it("fromRunnableConfig keeps an agent-addressed parent's addressing", () => {
    const { client } = mockClient();
    const parent = new RunTree({
      name: "parent",
      client,
      agent_id: "agent",
      agent_environment: "staging",
    });
    const child = RunTree.fromRunnableConfig(
      {
        callbacks: {
          getParentRunId: () => parent.id,
          handlers: [
            {
              name: "langchain_tracer",
              getRun: () => parent,
              projectName: "default",
              client,
            },
          ],
        },
      } as any,
      { name: "child" },
    );
    expect(child.agent_id).toBe("agent");
    expect(child.agent_environment).toBe("staging");
    expect(child.project_name).toBeUndefined();
  });

  it("a header without agent fields does not warn about an incomplete pair", () => {
    const { client } = mockClient();
    const id = "1b64098b-4ab7-43f6-afee-992304f198d8";
    // No project and no agent: only this shape reaches the agent branch.
    const headers = {
      "langsmith-trace": `20210503T000000000001Z${id}`,
      baggage: "langsmith-tags=a",
    };
    const warn = jest.spyOn(console, "warn").mockImplementation(() => {});
    try {
      RunTree.fromHeaders(headers, { client });
      expect(
        warn.mock.calls.some((c) => String(c[0]).includes("incomplete")),
      ).toBe(false);
    } finally {
      warn.mockRestore();
    }
  });
});
