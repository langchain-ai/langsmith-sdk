import { afterEach, describe, expect, it, jest } from "@jest/globals";
import { RunTree } from "../run_trees.js";
import { traceable, withRunTree } from "../traceable.js";
import { SandboxClient } from "../sandbox/client.js";
import { Sandbox } from "../sandbox/sandbox.js";
import { CommandHandle } from "../sandbox/command_handle.js";
import { ServiceUrl } from "../sandbox/service_url.js";
import { addSandboxMetadata } from "../sandbox/tracing.js";
import type { WsMessage } from "../sandbox/types.js";

const sandboxId = "01980000-0000-7000-8000-000000000001";
const otherId = "01980000-0000-7000-8000-000000000002";
const data = {
  id: sandboxId,
  name: "sandbox-name",
  dataplane_url: "https://sandbox.example.test",
  status: "ready",
};

function makeRun() {
  return new RunTree({ name: "sandbox-operation", metadata: { keep: true } });
}

function makeClient(body: unknown = data) {
  const client = new SandboxClient({ apiKey: "test-key", maxRetries: 0 });
  const request = jest
    .spyOn(client, "_fetch")
    .mockImplementation(async () => Response.json(body));
  return { client, request };
}

class HttpSandbox extends Sandbox {
  protected async _wsAvailable(): Promise<boolean> {
    return false;
  }
}

afterEach(() => {
  jest.restoreAllMocks();
});

describe("sandbox tracing metadata", () => {
  it("preserves metadata and does not create child runs", async () => {
    const run = makeRun();
    const { client, request } = makeClient();
    const sandbox = new HttpSandbox(data, client);
    await withRunTree(run, async () => {
      await sandbox.run("true");
      await sandbox.read("/tmp/file");
      await sandbox.ls("/tmp");
    });
    expect(run.metadata).toEqual({ keep: true, sandbox_id: sandboxId });
    expect(run.child_runs).toEqual([]);
    expect(request).toHaveBeenCalledTimes(3);
  });

  it.each(["create", "get", "update"])(
    "annotates %s responses with their ID",
    async (operation) => {
      const run = makeRun();
      const { client, request } = makeClient();
      await withRunTree(run, async () => {
        if (operation === "create") await client.createSandbox();
        if (operation === "get") await client.getSandbox(data.name);
        if (operation === "update")
          await client.updateSandbox(data.name, "renamed");
      });
      expect(run.metadata.sandbox_id).toBe(sandboxId);
      expect(request).toHaveBeenCalledTimes(1);
    },
  );

  it.each(["stop", "status", "download", "capture", "delete"])(
    "uses cached IDs for %s without extra requests",
    async (operation) => {
      const { client, request } = makeClient();
      await client.getSandbox(data.name);
      request.mockClear();
      jest
        .spyOn(client, "waitForSnapshot")
        .mockResolvedValue({ id: "snapshot-id" } as never);
      const run = makeRun();
      await withRunTree(run, async () => {
        if (operation === "stop") await client.stopSandbox(data.name);
        if (operation === "status") await client.getSandboxStatus(data.name);
        if (operation === "download")
          await client.generateDownloadURL(data.name, "/file");
        if (operation === "capture")
          await client.captureSnapshot(data.name, "snapshot");
        if (operation === "delete") await client.deleteSandbox(data.name);
      });
      expect(run.metadata.sandbox_id).toBe(sandboxId);
      expect(request).toHaveBeenCalledTimes(1);
    },
  );

  it("annotates UUID references and failed calls", async () => {
    const { client, request } = makeClient();
    request.mockRejectedValue(new Error("network failure"));
    const run = makeRun();
    await withRunTree(run, async () => {
      await expect(client.stopSandbox(sandboxId)).rejects.toThrow(
        "network failure",
      );
    });
    expect(run.metadata.sandbox_id).toBe(sandboxId);
    expect(request).toHaveBeenCalledTimes(1);
  });

  it("omits unknown IDs rather than recording names or looking them up", async () => {
    const { client, request } = makeClient({ name: data.name });
    const sandbox = new HttpSandbox({ ...data, id: undefined }, client);
    const run = makeRun();
    await withRunTree(run, async () => {
      await client.getSandbox(data.name);
      await client.stopSandbox(data.name);
      await sandbox.run("true");
    });
    expect(run.metadata).toEqual({ keep: true });
    expect(request).toHaveBeenCalledTimes(3);
  });

  it("does not annotate a listing but annotates later use of a listed handle", async () => {
    const { client } = makeClient({ sandboxes: [data] });
    const run = makeRun();
    await withRunTree(run, async () => {
      const [sandbox] = await client.listSandboxes();
      expect(run.metadata).toEqual({ keep: true });
      await sandbox.stop();
    });
    expect(run.metadata.sandbox_id).toBe(sandboxId);
  });

  it.each([data.name, sandboxId])(
    "forgets a deleted sandbox when addressed by %s",
    async (reference) => {
      const { client } = makeClient();
      await client.getSandbox(data.name);
      await client.deleteSandbox(reference);
      const run = makeRun();
      await withRunTree(run, () => client.stopSandbox(data.name));
      expect(run.metadata).toEqual({ keep: true });
    },
  );

  it("forgets old names after a rename", async () => {
    const { client, request } = makeClient();
    await client.getSandbox(data.name);
    request.mockImplementation(async () =>
      Response.json({ ...data, name: "renamed" }),
    );
    await client.updateSandbox(sandboxId, "renamed");
    const oldRun = makeRun();
    await withRunTree(oldRun, () => client.stopSandbox(data.name));
    expect(oldRun.metadata).toEqual({ keep: true });
    const newRun = makeRun();
    await withRunTree(newRun, () => client.stopSandbox("renamed"));
    expect(newRun.metadata.sandbox_id).toBe(sandboxId);
  });

  it("isolates concurrent contexts and records the most recently used sandbox", async () => {
    const { client } = makeClient();
    const first = new HttpSandbox(data, client);
    const second = new HttpSandbox({ ...data, id: otherId }, client);
    const firstRun = makeRun();
    const secondRun = makeRun();
    await Promise.all([
      withRunTree(firstRun, () => first.read("/file")),
      withRunTree(secondRun, () => second.read("/file")),
    ]);
    expect(firstRun.metadata.sandbox_id).toBe(sandboxId);
    expect(secondRun.metadata.sandbox_id).toBe(otherId);
    await withRunTree(firstRun, () => second.read("/file"));
    expect(firstRun.metadata.sandbox_id).toBe(otherId);
  });

  it("annotates only the active run and allows subsequent children to inherit metadata", async () => {
    const parent = makeRun();
    const child = parent.createChild({ name: "child" });
    await withRunTree(child, () => addSandboxMetadata(sandboxId));
    expect(parent.metadata).toEqual({ keep: true });
    expect(child.metadata.sandbox_id).toBe(sandboxId);
    expect(child.createChild({ name: "nested" }).metadata.sandbox_id).toBe(
      sandboxId,
    );
  });

  it("does nothing outside tracing or inside a disabled traceable context", async () => {
    expect(() => addSandboxMetadata(sandboxId)).not.toThrow();
    const fn = traceable(async () => addSandboxMetadata(sandboxId), {
      tracingEnabled: false,
    });
    await expect(fn()).resolves.toBeUndefined();
  });

  it.each(["result", "iterate", "kill", "input", "close"])(
    "annotates command handle %s in its caller's context",
    async (operation) => {
      const { client } = makeClient();
      const sandbox = new Sandbox(data, client);
      const stream = (async function* (): AsyncIterableIterator<WsMessage> {
        yield { type: "exit", exit_code: 0 };
      })();
      const handle = new CommandHandle(stream, null, sandbox, {
        commandId: "command-id",
      });
      const run = makeRun();
      await withRunTree(run, async () => {
        if (operation === "result") await handle.result;
        if (operation === "iterate")
          await handle[Symbol.asyncIterator]().next();
        if (operation === "kill") handle.kill();
        if (operation === "input") handle.sendInput("data");
        if (operation === "close") handle.closeInput();
      });
      expect(run.metadata.sandbox_id).toBe(sandboxId);
    },
  );

  it("annotates each resumed command stream read in its caller's context", async () => {
    const { client } = makeClient();
    const sandbox = new Sandbox(data, client);
    const makeIterator = () => {
      const stream = (async function* (): AsyncIterableIterator<WsMessage> {
        yield { type: "stdout", data: "a", offset: 0 };
        yield { type: "stdout", data: "b", offset: 1 };
        yield { type: "exit", exit_code: 0 };
      })();
      return new CommandHandle(stream, null, sandbox, {
        commandId: "command-id",
      })[Symbol.asyncIterator]();
    };

    // First chunk read outside tracing, the next inside a traced run.
    const later = makeIterator();
    await later.next();
    const laterRun = makeRun();
    await withRunTree(laterRun, () => later.next());
    expect(laterRun.metadata.sandbox_id).toBe(sandboxId);

    // Using another sandbox mid-stream, then resuming, records this sandbox.
    const interleaved = makeIterator();
    const run = makeRun();
    await withRunTree(run, async () => {
      await interleaved.next();
      addSandboxMetadata(otherId);
      expect(run.metadata.sandbox_id).toBe(otherId);
      await interleaved.next();
    });
    expect(run.metadata.sandbox_id).toBe(sandboxId);
  });

  it("annotates service requests when the URL was created outside the active run", async () => {
    const { client, request } = makeClient();
    await client.getSandbox(data.name);
    request.mockImplementation(async () =>
      Response.json({
        service_url: "https://service.example.test",
        token: "service-token",
        expires_at: "2099-01-01T00:00:00Z",
      }),
    );
    const service = await client.serviceUrl(data.name, { port: 8080 });
    expect(service).toBeInstanceOf(ServiceUrl);
    const fetchMock = jest
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response("ok"));
    const run = makeRun();
    await withRunTree(run, () => (service as ServiceUrl).fetch("/health"));
    expect(run.metadata.sandbox_id).toBe(sandboxId);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(request).toHaveBeenCalledTimes(2);
  });
});
