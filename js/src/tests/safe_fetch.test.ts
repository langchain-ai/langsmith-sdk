import { jest, describe, it, expect } from "@jest/globals";
import { _wrapFetchWithSafeRedirects } from "../utils/safe_fetch.js";

const makeResponse = (
  status: number,
  headers: Record<string, string> = {}
): Response =>
  ({
    status,
    ok: status >= 200 && status < 300,
    headers: new Headers(headers),
    text: () => Promise.resolve(""),
    json: () => Promise.resolve({}),
  } as Response);

const getHeader = (
  init: RequestInit | undefined,
  name: string
): string | null => {
  if (!init?.headers) return null;
  const hdrs = init.headers as Headers | Record<string, string>;
  if (typeof (hdrs as Headers).get === "function") {
    return (hdrs as Headers).get(name);
  }
  const obj = hdrs as Record<string, string>;
  const key = Object.keys(obj).find(
    (k) => k.toLowerCase() === name.toLowerCase()
  );
  return key ? obj[key] : null;
};

describe("_wrapFetchWithSafeRedirects", () => {
  it("passes through non-redirect responses without touching headers", async () => {
    const inner = jest
      .fn<(url: string, init?: RequestInit) => Promise<Response>>()
      .mockResolvedValue(makeResponse(200));
    const wrapped = _wrapFetchWithSafeRedirects(inner);
    const headers = {
      "x-api-key": "secret",
      "Content-Type": "application/json",
    };
    const res = await wrapped("https://api.example.com/foo", {
      method: "POST",
      headers,
      body: "payload",
    });
    expect(res.status).toBe(200);
    expect(inner).toHaveBeenCalledTimes(1);
    const init = inner.mock.calls[0][1]!;
    expect(init.headers).toBe(headers);
    expect(init.method).toBe("POST");
    expect(init.body).toBe("payload");
    expect(init.redirect).toBe("manual");
  });

  it("strips sensitive headers and bodies on cross-origin 307 redirects", async () => {
    const inner = jest
      .fn<(url: string, init?: RequestInit) => Promise<Response>>()
      .mockResolvedValueOnce(
        makeResponse(307, { location: "https://evil.example.com/steal" })
      )
      .mockResolvedValueOnce(makeResponse(200));
    const wrapped = _wrapFetchWithSafeRedirects(inner);
    await wrapped("https://api.example.com/foo", {
      method: "POST",
      headers: { "x-api-key": "secret", "Content-Type": "application/json" },
      body: "sensitive-body",
    });

    expect(inner).toHaveBeenCalledTimes(2);
    const secondInit = inner.mock.calls[1][1]!;
    expect(inner.mock.calls[1][0]).toBe("https://evil.example.com/steal");
    expect(getHeader(secondInit, "x-api-key")).toBeNull();
    expect(secondInit.body).toBeUndefined();
  });

  it("preserves credentials and body on same-origin 307 redirects", async () => {
    const inner = jest
      .fn<(url: string, init?: RequestInit) => Promise<Response>>()
      .mockResolvedValueOnce(
        makeResponse(307, { location: "https://api.example.com/new" })
      )
      .mockResolvedValueOnce(makeResponse(200));
    const wrapped = _wrapFetchWithSafeRedirects(inner);
    await wrapped("https://api.example.com/foo", {
      method: "POST",
      headers: { "x-api-key": "secret" },
      body: "payload",
    });

    expect(inner).toHaveBeenCalledTimes(2);
    const secondInit = inner.mock.calls[1][1]!;
    expect(inner.mock.calls[1][0]).toBe("https://api.example.com/new");
    expect(getHeader(secondInit, "x-api-key")).toBe("secret");
    expect(secondInit.body).toBe("payload");
  });

  it("converts 302 POST redirects to GET and drops body", async () => {
    const inner = jest
      .fn<(url: string, init?: RequestInit) => Promise<Response>>()
      .mockResolvedValueOnce(
        makeResponse(302, { location: "https://api.example.com/new" })
      )
      .mockResolvedValueOnce(makeResponse(200));
    const wrapped = _wrapFetchWithSafeRedirects(inner);
    await wrapped("https://api.example.com/foo", {
      method: "POST",
      headers: { "x-api-key": "secret" },
      body: "payload",
    });

    const secondInit = inner.mock.calls[1][1]!;
    expect(secondInit.method).toBe("GET");
    expect(secondInit.body).toBeUndefined();
    expect(getHeader(secondInit, "x-api-key")).toBe("secret");
  });

  it("throws after too many redirects", async () => {
    const inner = jest
      .fn<(url: string, init?: RequestInit) => Promise<Response>>()
      .mockResolvedValue(
        makeResponse(307, { location: "https://api.example.com/again" })
      );
    const wrapped = _wrapFetchWithSafeRedirects(inner);
    await expect(
      wrapped("https://api.example.com/foo", { method: "GET" })
    ).rejects.toThrow(/Exceeded maximum redirects/);
  });
});
