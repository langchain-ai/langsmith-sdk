import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { traceable, withRunTree } from "../traceable.js";
import type { RunTree } from "../run_trees.js";
import { isTracingEnabled } from "../utils/guard.js";
import { mockClient } from "./utils/vitest_mock_client.js";

beforeEach(() => {
  vi.stubEnv("LANGCHAIN_TRACING", undefined);
  vi.stubEnv("LANGSMITH_TRACING", undefined);
  vi.stubEnv("LANGSMITH_TRACING_V2", undefined);
  vi.stubEnv("LANGCHAIN_TRACING_V2", undefined);
});

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("isTracingEnabled", () => {
  it("returns false without an active run tree or tracing env var", () => {
    expect(isTracingEnabled()).toBe(false);
  });

  it.each([
    "LANGCHAIN_TRACING",
    "LANGSMITH_TRACING",
    "LANGCHAIN_TRACING_V2",
    "LANGSMITH_TRACING_V2",
  ])("reads %s=true without an active run tree", (envVar) => {
    vi.stubEnv(envVar, "true");
    expect(isTracingEnabled()).toBe(true);
  });

  it("traceable without any env vars", async () => {
    const { client, callSpy } = mockClient();
    const traced = traceable(() => isTracingEnabled(), { client });

    await expect(traced()).resolves.toBe(false);
    expect(callSpy).toHaveBeenCalledTimes(0);
  });

  it("traceable with tracingEnabled=true override", async () => {
    vi.stubEnv("LANGSMITH_TRACING", "false");

    const { client, callSpy } = mockClient();
    const traced = traceable(() => isTracingEnabled(), {
      client,
      tracingEnabled: true,
    });

    await expect(traced()).resolves.toBe(true);
    expect(callSpy).toHaveBeenCalledTimes(1);
  });

  it("traceable with env + tracingEnabled=false", async () => {
    vi.stubEnv("LANGSMITH_TRACING", "true");

    const { client, callSpy } = mockClient();
    const traced = traceable(() => isTracingEnabled(), {
      client,
      tracingEnabled: false,
    });

    await expect(traced()).resolves.toBe(false);
    expect(callSpy).toHaveBeenCalledTimes(0);
  });

  it.each([
    ["LANGSMITH_TRACING", "true"],
    ["LANGSMITH_TRACING", "false"],
  ])("withRunTree from env var $1", async (_, value) => {
    vi.stubEnv("LANGSMITH_TRACING", value);

    await expect(
      withRunTree({} as RunTree, () => isTracingEnabled()),
    ).resolves.toBe(value === "true");
  });

  it("withRunTree explicit tracingEnabled", async () => {
    await expect(
      withRunTree({ tracingEnabled: false } as RunTree, () =>
        isTracingEnabled(),
      ),
    ).resolves.toBe(false);

    await expect(
      withRunTree({ tracingEnabled: true } as RunTree, () =>
        isTracingEnabled(),
      ),
    ).resolves.toBe(true);
  });
});
