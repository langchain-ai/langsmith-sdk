/* eslint-disable @typescript-eslint/no-explicit-any */
import { jest, describe, expect, it } from "@jest/globals";
import { Client } from "../client.js";

const okResponse = (body: any) =>
  ({
    ok: true,
    status: 200,
    statusText: "OK",
    text: () => Promise.resolve(JSON.stringify(body)),
    json: () => Promise.resolve(body),
    headers: new Headers({ "Content-Type": "application/json" }),
  }) as unknown as Response;

describe("application_tag wiring", () => {
  it("createDataset sends application_tag in the POST body", async () => {
    const calls: { url: string; init: any }[] = [];
    const mockFetch = jest.fn(async (...args: any[]) => {
      calls.push({ url: args[0], init: args[1] });
      return okResponse({ id: "ds-1", name: "ds" });
    });

    const client = new Client({
      apiKey: "test",
      autoBatchTracing: false,
      fetchImplementation: mockFetch as any,
    });

    await client.createDataset("ds", { applicationTag: "my-app" });

    const post = calls.find((c) => c.url.endsWith("/datasets"));
    expect(post).toBeDefined();
    expect(post!.init.method).toBe("POST");
    const body = JSON.parse(post!.init.body as string);
    expect(body.application_tag).toBe("my-app");
  });

  it("createDataset omits application_tag when not provided", async () => {
    const calls: { url: string; init: any }[] = [];
    const mockFetch = jest.fn(async (...args: any[]) => {
      calls.push({ url: args[0], init: args[1] });
      return okResponse({ id: "ds-1", name: "ds" });
    });

    const client = new Client({
      apiKey: "test",
      autoBatchTracing: false,
      fetchImplementation: mockFetch as any,
    });

    await client.createDataset("ds");

    const post = calls.find((c) => c.url.endsWith("/datasets"));
    const body = JSON.parse(post!.init.body as string);
    expect(body).not.toHaveProperty("application_tag");
  });

  it("listPrompts sends application_tag as a query param", async () => {
    const calls: { url: string }[] = [];
    const mockFetch = jest.fn(async (...args: any[]) => {
      calls.push({ url: args[0] });
      return okResponse({ repos: [], total: 0 });
    });

    const client = new Client({
      apiKey: "test",
      autoBatchTracing: false,
      fetchImplementation: mockFetch as any,
    });

    const iter = client.listPrompts({ applicationTag: "my-app" });
    // Consume one tick of the iterator so the GET fires.
    await iter.next();

    const get = calls.find((c) => c.url.includes("/repos"));
    expect(get).toBeDefined();
    expect(get!.url).toContain("application_tag=my-app");
  });

  it("listPrompts omits application_tag when not provided", async () => {
    const calls: { url: string }[] = [];
    const mockFetch = jest.fn(async (...args: any[]) => {
      calls.push({ url: args[0] });
      return okResponse({ repos: [], total: 0 });
    });

    const client = new Client({
      apiKey: "test",
      autoBatchTracing: false,
      fetchImplementation: mockFetch as any,
    });

    const iter = client.listPrompts();
    await iter.next();

    const get = calls.find((c) => c.url.includes("/repos"));
    expect(get!.url).not.toContain("application_tag");
  });

  it("listDatasets sends application_tag as a query param", async () => {
    const calls: { url: string }[] = [];
    const mockFetch = jest.fn(async (...args: any[]) => {
      calls.push({ url: args[0] });
      return okResponse([]);
    });

    const client = new Client({
      apiKey: "test",
      autoBatchTracing: false,
      fetchImplementation: mockFetch as any,
    });

    const iter = client.listDatasets({ applicationTag: "my-app" });
    await iter[Symbol.asyncIterator]().next();

    const get = calls.find((c) => c.url.includes("/datasets"));
    expect(get).toBeDefined();
    expect(get!.url).toContain("application_tag=my-app");
  });
});
