/* eslint-disable no-process-env, @typescript-eslint/no-explicit-any */

import { jest } from "@jest/globals";
import { RunTree } from "../run_trees.js";
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
