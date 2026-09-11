/* eslint-disable @typescript-eslint/no-explicit-any */
import { jest, describe, it, expect } from "@jest/globals";
import { SandboxClient } from "../sandbox/client.js";
import { Sandbox } from "../sandbox/sandbox.js";
import { LangSmithValidationError } from "../sandbox/errors.js";
import {
  validateCommandRunConfig,
  validateRunConfig,
} from "../sandbox/helpers.js";
import type { SandboxRunConfig } from "../sandbox/types.js";

const RUN_CONFIG: SandboxRunConfig = {
  user: "app",
  work_dir: "/srv",
  env_vars: { LANG: "C" },
};

const createClientWithMock = (mockFetch: any) => {
  const client = new SandboxClient({
    apiEndpoint: "https://api.example.com/v2/sandboxes",
    apiKey: "test-key",
  });
  (client as any)._caller = { call: (fn: any) => fn() };
  (client as any)._fetchImpl = mockFetch;
  return client;
};

const jsonResponse = (body: any) =>
  jest.fn<typeof fetch>().mockResolvedValue({
    ok: true,
    json: async () => body,
  } as Response);

const requestBody = (mockFetch: any, call = 0) => {
  const [, init] = mockFetch.mock.calls[call] as [string, RequestInit];
  return JSON.parse(init.body as string);
};

describe("run config validation", () => {
  it("accepts a full config", () => {
    expect(() => validateRunConfig(RUN_CONFIG)).not.toThrow();
  });

  it("accepts undefined", () => {
    expect(() => validateRunConfig(undefined)).not.toThrow();
  });

  it.each([
    [{ workdir: "/srv" } as SandboxRunConfig, "unsupported keys: workdir"],
    [{ user: "" }, "user must be a non-empty string"],
    [{ work_dir: "srv" }, "work_dir must be an absolute path"],
    [
      { env_vars: ["LANG=C"] } as unknown as SandboxRunConfig,
      "must be an object",
    ],
    [
      { env_vars: { PORT: 8080 } } as unknown as SandboxRunConfig,
      "must be a string",
    ],
  ])("rejects %p", (runConfig, message) => {
    expect(() => validateRunConfig(runConfig)).toThrow(message);
    expect(() => validateRunConfig(runConfig)).toThrow(
      LangSmithValidationError,
    );
  });

  it.each([
    [{ LANG: "C" }, undefined],
    [undefined, "/srv"],
    [{ LANG: "C" }, "/srv"],
  ])("rejects the deprecated env/cwd alongside runConfig", (env, cwd) => {
    expect(() => validateCommandRunConfig(RUN_CONFIG, env, cwd)).toThrow(
      "cannot be combined with",
    );
  });

  it("allows the deprecated env/cwd on their own", () => {
    expect(() =>
      validateCommandRunConfig(undefined, { LANG: "C" }, "/srv"),
    ).not.toThrow();
  });
});

describe("client forwards run config", () => {
  it("sends run_config on create", async () => {
    const mockFetch = jsonResponse({ name: "test-sb", status: "ready" });
    const client = createClientWithMock(mockFetch);

    await client.createSandbox("snap-123", { runConfig: RUN_CONFIG });

    expect(requestBody(mockFetch).run_config).toEqual(RUN_CONFIG);
  });

  it("sends run_config on update and surfaces the stored value", async () => {
    const mockFetch = jsonResponse({
      name: "test-sb",
      status: "ready",
      run_config: RUN_CONFIG,
    });
    const client = createClientWithMock(mockFetch);

    const sandbox = await client.updateSandbox("test-sb", {
      runConfig: RUN_CONFIG,
    });

    expect(requestBody(mockFetch).run_config).toEqual(RUN_CONFIG);
    expect(sandbox.run_config).toEqual(RUN_CONFIG);
  });

  it("sends run_config on snapshot build", async () => {
    const mockFetch = jsonResponse({
      id: "snap-1",
      name: "snap",
      status: "ready",
      run_config: RUN_CONFIG,
    });
    const client = createClientWithMock(mockFetch);

    const snapshot = await client.createSnapshot(
      "snap",
      "python:3.12-slim",
      1024,
      {
        runConfig: RUN_CONFIG,
      },
    );

    expect(requestBody(mockFetch).run_config).toEqual(RUN_CONFIG);
    expect(snapshot.run_config).toEqual(RUN_CONFIG);
  });

  it("sends run_config on capture", async () => {
    const mockFetch = jsonResponse({
      id: "snap-1",
      name: "snap",
      status: "ready",
    });
    const client = createClientWithMock(mockFetch);

    await client.captureSnapshot("test-sb", "snap", { runConfig: RUN_CONFIG });

    expect(requestBody(mockFetch).run_config).toEqual(RUN_CONFIG);
  });

  it("rejects a bad run config before calling the API", async () => {
    const mockFetch = jest.fn<typeof fetch>();
    const client = createClientWithMock(mockFetch);

    await expect(
      client.createSandbox("snap-123", { runConfig: { work_dir: "srv" } }),
    ).rejects.toThrow("work_dir must be an absolute path");
    expect(mockFetch).not.toHaveBeenCalled();
  });
});

describe("per-command run config", () => {
  const makeSandbox = (mockFetch: any) => {
    const sandbox = new Sandbox(
      { name: "test-sb", dataplane_url: "https://router.example.com/sb-123" },
      createClientWithMock(mockFetch),
    );
    jest.spyOn(sandbox as any, "_wsAvailable").mockResolvedValue(false);
    return sandbox;
  };

  it("sends run_config on the execute request", async () => {
    const mockFetch = jsonResponse({ stdout: "", stderr: "", exit_code: 0 });
    const sandbox = makeSandbox(mockFetch);

    await sandbox.run("id", { runConfig: RUN_CONFIG });

    const body = requestBody(mockFetch);
    expect(body.run_config).toEqual(RUN_CONFIG);
    expect(body.cwd).toBeUndefined();
    expect(body.env).toBeUndefined();
  });

  it("rejects runConfig combined with the deprecated cwd", async () => {
    const mockFetch = jest.fn<typeof fetch>();
    const sandbox = makeSandbox(mockFetch);

    await expect(
      sandbox.run("pwd", { cwd: "/tmp", runConfig: RUN_CONFIG }),
    ).rejects.toThrow("cannot be combined with cwd");
    expect(mockFetch).not.toHaveBeenCalled();
  });
});
