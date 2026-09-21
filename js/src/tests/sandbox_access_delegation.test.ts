/* eslint-disable @typescript-eslint/no-explicit-any */
import { jest, describe, it, expect } from "@jest/globals";
import { SandboxClient } from "../sandbox/client.js";
import { Sandbox } from "../sandbox/sandbox.js";
import type { AccessDelegation } from "../sandbox/access_delegation.js";
import { LangSmithValidationError } from "../sandbox/errors.js";

const DATAPLANE = "https://sandbox-router.example.com/sb-123";

const jsonResponse = (body: unknown) =>
  new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });

const clientWithMock = () => {
  const mockFetch = jest
    .fn<(url: string, init?: RequestInit) => Promise<Response>>()
    .mockResolvedValue(
      jsonResponse({ name: "sb", status: "ready", dataplane_url: DATAPLANE }),
    );
  const client = new SandboxClient({
    apiEndpoint: "http://test-server:8080",
    apiKey: "test-key",
  });
  (client as any)._fetch = mockFetch;
  return { client, mockFetch };
};

const sentBody = (mockFetch: any) => {
  const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
  return JSON.parse(init.body as string);
};

describe("access delegation on create", () => {
  it("sends an INHERIT grant", async () => {
    const { client, mockFetch } = clientWithMock();
    await client.createSandbox("snap-1", {
      accessDelegation: { mode: "INHERIT" },
    });
    expect(sentBody(mockFetch).access_delegation).toEqual({ mode: "INHERIT" });
  });

  it("sends an EXPLICIT grant with its permissions", async () => {
    const { client, mockFetch } = clientWithMock();
    await client.createSandbox("snap-1", {
      accessDelegation: {
        mode: "EXPLICIT",
        permissions: ["datasets:read", "tracer_sessions:read"],
      },
    });
    expect(sentBody(mockFetch).access_delegation).toEqual({
      mode: "EXPLICIT",
      permissions: ["datasets:read", "tracer_sessions:read"],
    });
  });

  it("omits the field when no grant is requested", async () => {
    const { client, mockFetch } = clientWithMock();
    await client.createSandbox("snap-1");
    expect(sentBody(mockFetch)).not.toHaveProperty("access_delegation");
  });

  // Rejected client-side so the caller does not pay a round trip for a 422.
  it.each([
    [{ mode: "MAYBE" }, /"INHERIT" or "EXPLICIT"/],
    [{ mode: "INHERIT", permissions: ["a"] }, /not allowed with mode/],
    [{ mode: "EXPLICIT" }, /required with mode/],
    [{ mode: "EXPLICIT", permissions: "a" }, /array of strings/],
  ])("rejects %j", async (grant, message) => {
    const { client, mockFetch } = clientWithMock();
    await expect(
      client.createSandbox("snap-1", {
        accessDelegation: grant as unknown as AccessDelegation,
      }),
    ).rejects.toThrow(LangSmithValidationError);
    await expect(
      client.createSandbox("snap-1", {
        accessDelegation: grant as unknown as AccessDelegation,
      }),
    ).rejects.toThrow(message);
    expect(mockFetch).not.toHaveBeenCalled();
  });
});

describe("access delegation on the response", () => {
  it("is exposed when the sandbox has one", () => {
    const sandbox = new Sandbox(
      {
        name: "sb",
        dataplane_url: DATAPLANE,
        access_delegation: { mode: "EXPLICIT", permissions: ["datasets:read"] },
      },
      {} as unknown as SandboxClient,
    );
    expect(sandbox.access_delegation).toEqual({
      mode: "EXPLICIT",
      permissions: ["datasets:read"],
    });
  });

  it("is absent when it has none", () => {
    const sandbox = new Sandbox(
      { name: "sb", dataplane_url: DATAPLANE },
      {} as unknown as SandboxClient,
    );
    expect(sandbox.access_delegation).toBeUndefined();
  });
});
