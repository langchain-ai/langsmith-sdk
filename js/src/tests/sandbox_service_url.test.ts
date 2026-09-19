/* eslint-disable @typescript-eslint/no-explicit-any */
import { jest, describe, it, expect } from "@jest/globals";
import { SandboxClient } from "../sandbox/client.js";
import {
  ServiceLoginUrl,
  ServiceUrl,
  SERVICE_TOKEN_HEADER,
} from "../sandbox/service_url.js";
import { LangSmithValidationError } from "../sandbox/errors.js";

const jsonResponse = (body: unknown) =>
  new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });

const TOKEN_BODY = {
  browser_url: "https://box--8000.example.dev/_svc/auth?token=tok",
  service_url: "https://box--8000.example.dev/",
  token: "tok",
  expires_at: "2099-01-01T00:00:00Z",
};

const LOGIN_BODY = {
  browser_url: "https://l-abc.example.dev/",
  service_url: "https://l-abc.example.dev/",
  access: "workspace",
};

const clientWithMock = (body: unknown = TOKEN_BODY) => {
  const mockFetch = jest
    .fn<(url: string, init?: RequestInit) => Promise<Response>>()
    .mockImplementation(() => Promise.resolve(jsonResponse(body)));
  const client = new SandboxClient({
    apiEndpoint: "http://test-server:8080",
    apiKey: "test-key",
  });
  (client as any)._fetch = mockFetch;
  return { client, mockFetch };
};

const sentBody = (mockFetch: any, call = 0) => {
  const [, init] = mockFetch.mock.calls[call] as [string, RequestInit];
  return JSON.parse(init.body as string);
};

describe("serviceUrl token mode", () => {
  it("mints a token and sends only the port by default", async () => {
    const { client, mockFetch } = clientWithMock();
    const result = await client.serviceUrl("sb", { port: 8000 });
    expect(result).toBeInstanceOf(ServiceUrl);
    expect(sentBody(mockFetch)).toEqual({ port: 8000 });
    expect(await (result as ServiceUrl).token()).toBe("tok");
    expect(await (result as ServiceUrl).serviceUrl()).toBe(
      "https://box--8000.example.dev/",
    );
  });

  it("forwards expiresInSeconds", async () => {
    const { client, mockFetch } = clientWithMock();
    await client.serviceUrl("sb", { port: 8000, expiresInSeconds: 3600 });
    expect(sentBody(mockFetch)).toEqual({
      port: 8000,
      expires_in_seconds: 3600,
    });
  });

  it("injects the token header on fetch", async () => {
    const { client } = clientWithMock();
    const svc = (await client.serviceUrl("sb", { port: 8000 })) as ServiceUrl;
    const spy = jest
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response("ok", { status: 200 }));
    try {
      await svc.fetch("/api/data");
      const [url, init] = spy.mock.calls[0] as [string, RequestInit];
      expect(url).toBe("https://box--8000.example.dev/api/data");
      expect(new Headers(init.headers).get(SERVICE_TOKEN_HEADER)).toBe("tok");
    } finally {
      spy.mockRestore();
    }
  });

  it("refreshes a token that is past the margin", async () => {
    const stale = { ...TOKEN_BODY, token: "stale", expires_at: "2000-01-01T00:00:00Z" };
    const { client, mockFetch } = clientWithMock();
    (mockFetch as any)
      .mockImplementationOnce(() => Promise.resolve(jsonResponse(stale)))
      .mockImplementationOnce(() => Promise.resolve(jsonResponse(TOKEN_BODY)));
    const svc = (await client.serviceUrl("sb", { port: 8000 })) as ServiceUrl;
    expect(await svc.token()).toBe("tok");
    expect(mockFetch).toHaveBeenCalledTimes(2);
  });
});

describe("serviceUrl LangSmith login mode", () => {
  it.each(["restricted", "workspace"] as const)(
    "returns a login URL for access=%s",
    async (access) => {
      const { client, mockFetch } = clientWithMock({ ...LOGIN_BODY, access });
      const result = await client.serviceUrl("sb", { port: 8000, access });
      expect(result).toBeInstanceOf(ServiceLoginUrl);
      expect((result as ServiceLoginUrl).url).toBe("https://l-abc.example.dev/");
      expect((result as ServiceLoginUrl).access).toBe(access);
      expect(sentBody(mockFetch)).toEqual({ port: 8000, access });
    },
  );

  it("access=off stays token mode and revokes the grant", async () => {
    const { client, mockFetch } = clientWithMock();
    const result = await client.serviceUrl("sb", { port: 8000, access: "off" });
    expect(result).toBeInstanceOf(ServiceUrl);
    expect(sentBody(mockFetch)).toEqual({ port: 8000, access: "off" });
  });
});

describe("serviceUrl validation", () => {
  it.each([0, 70000, 1.5])("rejects port %p", async (port) => {
    const { client, mockFetch } = clientWithMock();
    await expect(client.serviceUrl("sb", { port })).rejects.toThrow(
      LangSmithValidationError,
    );
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("rejects an unknown access value", async () => {
    const { client, mockFetch } = clientWithMock();
    await expect(
      client.serviceUrl("sb", { port: 8000, access: "maybe" as any }),
    ).rejects.toThrow(/"restricted", "workspace", "off"/);
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("rejects expiresInSeconds with a login mode", async () => {
    const { client, mockFetch } = clientWithMock();
    await expect(
      client.serviceUrl("sb", {
        port: 8000,
        access: "workspace",
        expiresInSeconds: 600,
      }),
    ).rejects.toThrow(/does not expire/);
    expect(mockFetch).not.toHaveBeenCalled();
  });
});
