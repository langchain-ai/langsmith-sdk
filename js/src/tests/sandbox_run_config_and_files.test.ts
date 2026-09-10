/* eslint-disable @typescript-eslint/no-explicit-any */
import { jest, describe, it, expect } from "@jest/globals";
import { SandboxClient } from "../sandbox/client.js";
import { Sandbox } from "../sandbox/sandbox.js";
import { CommandHandle } from "../sandbox/command_handle.js";
import { WSStreamControl } from "../sandbox/ws_execute.js";
import {
  buildRangeHeader,
  fileChunkFromResponse,
  fileStatFromResponse,
  resolveCloseInput,
} from "../sandbox/helpers.js";
import {
  LangSmithSandboxOperationError,
  LangSmithValidationError,
} from "../sandbox/errors.js";

const DATAPLANE = "https://sandbox-router.example.com/sb-123";

const jsonResponse = (body: unknown, init: ResponseInit = {}) =>
  new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });

const createMockClient = (fetchImpl: any) =>
  ({
    _fetch: fetchImpl,
    getApiKey: () => "test-key",
    getDefaultHeaders: () => ({}),
    deleteSandbox: jest.fn<() => Promise<void>>().mockResolvedValue(undefined),
  }) as unknown as SandboxClient;

const makeSandbox = (fetchImpl: any) =>
  new Sandbox(
    { name: "test-sandbox", dataplane_url: DATAPLANE },
    createMockClient(fetchImpl),
  );

const forceHttpFallback = (sandbox: any) =>
  jest.spyOn(sandbox, "_wsAvailable").mockResolvedValue(false);

describe("resolveCloseInput", () => {
  it("defaults on for a non-PTY command", () => {
    expect(resolveCloseInput(undefined, false)).toBe(true);
  });

  it("stays off under a PTY, even when asked for", () => {
    expect(resolveCloseInput(true, true)).toBe(false);
    expect(resolveCloseInput(undefined, true)).toBe(false);
  });

  it("honours an explicit opt-out", () => {
    expect(resolveCloseInput(false, false)).toBe(false);
  });
});

describe("run config on requests", () => {
  it("createSandbox sends run_config", async () => {
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

    await client.createSandbox("snap-1", {
      runConfig: { user: "app", env_vars: { A: "1" } },
    });

    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(init.body as string).run_config).toEqual({
      user: "app",
      env_vars: { A: "1" },
    });
  });

  it("updateSandbox sends run_config", async () => {
    const mockFetch = jest
      .fn<(url: string, init?: RequestInit) => Promise<Response>>()
      .mockResolvedValue(jsonResponse({ name: "sb", status: "ready" }));
    const client = new SandboxClient({
      apiEndpoint: "http://test-server:8080",
      apiKey: "test-key",
    });
    (client as any)._fetch = mockFetch;

    await client.updateSandbox("sb", { runConfig: { work_dir: "/srv" } });

    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body as string).run_config).toEqual({
      work_dir: "/srv",
    });
  });

  it("run sends run_config on the HTTP fallback", async () => {
    const mockFetch = jest
      .fn<(url: string, init?: RequestInit) => Promise<Response>>()
      .mockResolvedValue(
        jsonResponse({ stdout: "", stderr: "", exit_code: 0 }),
      );
    const sandbox = makeSandbox(mockFetch);
    forceHttpFallback(sandbox);

    await sandbox.run("echo hi", { runConfig: { user: "app" } });

    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(init.body as string).run_config).toEqual({
      user: "app",
    });
  });

  it.each([{ env: { A: "1" } }, { cwd: "/tmp" }])(
    "rejects run_config combined with %p",
    async (deprecated) => {
      const sandbox = makeSandbox(
        jest
          .fn<(url: string, init?: RequestInit) => Promise<Response>>()
          .mockResolvedValue(jsonResponse({})),
      );
      await expect(
        sandbox.run("echo hi", { runConfig: { user: "app" }, ...deprecated }),
      ).rejects.toThrow(LangSmithValidationError);
    },
  );

  it("still accepts the deprecated env/cwd on their own", async () => {
    const mockFetch = jest
      .fn<(url: string, init?: RequestInit) => Promise<Response>>()
      .mockResolvedValue(
        jsonResponse({ stdout: "", stderr: "", exit_code: 0 }),
      );
    const sandbox = makeSandbox(mockFetch);
    forceHttpFallback(sandbox);

    await sandbox.run("echo hi", { cwd: "/tmp", env: { A: "1" } });

    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(init.body as string);
    expect(body.cwd).toBe("/tmp");
    expect(body.env).toEqual({ A: "1" });
    expect(body.run_config).toBeUndefined();
  });
});

describe("closeInput on the command handle", () => {
  const makeHandle = (stdinClosed: boolean, pty = false) => {
    const control = new WSStreamControl();
    const sendInput = jest
      .spyOn(control, "sendInput")
      .mockImplementation(() => {});
    const sendCloseStdin = jest
      .spyOn(control, "sendCloseStdin")
      .mockImplementation(() => {});
    const handle = new CommandHandle(
      (async function* () {})() as any,
      control,
      {} as any,
      { commandId: "cmd-1", stdinClosed, pty },
    );
    return { handle, sendInput, sendCloseStdin };
  };

  it("sendInput throws once stdin is closed", () => {
    const { handle, sendInput } = makeHandle(true);
    expect(() => handle.sendInput("data")).toThrow(
      LangSmithSandboxOperationError,
    );
    expect(() => handle.sendInput("data")).toThrow("closeInput: false");
    expect(sendInput).not.toHaveBeenCalled();
  });

  it("closeInput sends the message once", () => {
    const { handle, sendCloseStdin } = makeHandle(false);
    handle.closeInput();
    handle.closeInput();
    expect(sendCloseStdin).toHaveBeenCalledTimes(1);
    expect(() => handle.sendInput("data")).toThrow(
      LangSmithSandboxOperationError,
    );
  });

  it("closeInput is a no-op under a PTY", () => {
    const { handle, sendInput, sendCloseStdin } = makeHandle(false, true);
    handle.closeInput();
    expect(sendCloseStdin).not.toHaveBeenCalled();
    handle.sendInput("");
    expect(sendInput).toHaveBeenCalledWith("");
  });
});

describe("filesystem search", () => {
  it("glob posts the pattern and parses matches", async () => {
    const mockFetch = jest
      .fn<(url: string, init?: RequestInit) => Promise<Response>>()
      .mockResolvedValue(
        jsonResponse({
          matches: [
            {
              path: "/workspace/app.py",
              is_dir: false,
              size_bytes: 12,
              modified_at: "2026-07-14T00:00:00Z",
            },
          ],
          truncated: true,
        }),
      );
    const sandbox = makeSandbox(mockFetch);

    const result = await sandbox.glob("**/*.py", "/workspace", { limit: 200 });

    const [url, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${DATAPLANE}/glob`);
    expect(JSON.parse(init.body as string)).toEqual({
      pattern: "**/*.py",
      path: "/workspace",
      limit: 200,
    });
    expect(result.truncated).toBe(true);
    expect(result.matches[0].size_bytes).toBe(12);
  });

  it("ls is the non-recursive glob case", async () => {
    const mockFetch = jest
      .fn<(url: string, init?: RequestInit) => Promise<Response>>()
      .mockResolvedValue(jsonResponse({ matches: [], truncated: false }));
    const sandbox = makeSandbox(mockFetch);

    await sandbox.ls("/workspace");

    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({
      pattern: "*",
      path: "/workspace",
    });
  });

  it("grep passes the file filter through", async () => {
    const mockFetch = jest
      .fn<(url: string, init?: RequestInit) => Promise<Response>>()
      .mockResolvedValue(
        jsonResponse({
          matches: [{ path: "/w/app.py", line: 12, text: "# TODO" }],
          truncated: false,
        }),
      );
    const sandbox = makeSandbox(mockFetch);

    const result = await sandbox.grep("TODO", "/w", { glob: "*.py" });

    const [url, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${DATAPLANE}/grep`);
    expect(JSON.parse(init.body as string)).toEqual({
      pattern: "TODO",
      path: "/w",
      glob: "*.py",
    });
    expect(result.matches[0].line).toBe(12);
  });
});

describe("buildRangeHeader", () => {
  it.each([
    [{ start: 0, end: 1023 }, "bytes=0-1023"],
    [{ start: 1024 }, "bytes=1024-"],
    [{ suffixBytes: 512 }, "bytes=-512"],
  ])("renders %p", (options, expected) => {
    expect(buildRangeHeader(options)).toBe(expected);
  });

  it.each([
    {},
    { start: 1, suffixBytes: 2 },
    { start: 5, end: 1 },
    { start: -1 },
    { suffixBytes: 0 },
  ])("rejects %p", (options) => {
    expect(() => buildRangeHeader(options)).toThrow(LangSmithValidationError);
  });
});

describe("ranged reads", () => {
  it("reports a 206 as partial, with its offsets", async () => {
    const chunk = await fileChunkFromResponse(
      new Response("0123", {
        status: 206,
        headers: { "Content-Range": "bytes 10-13/100", ETag: '"abc"' },
      }),
    );
    expect(chunk.partial).toBe(true);
    expect(chunk.start).toBe(10);
    expect(chunk.total_bytes).toBe(100);
    expect(chunk.etag).toBe('"abc"');
    expect(new TextDecoder().decode(chunk.content)).toBe("0123");
  });

  it("reports a stale If-Range 200 from byte zero", async () => {
    const chunk = await fileChunkFromResponse(
      new Response("whole", { status: 200, headers: { ETag: '"new"' } }),
    );
    expect(chunk.partial).toBe(false);
    expect(chunk.start).toBe(0);
    expect(chunk.total_bytes).toBe(5);
  });

  it("reports a 304 as unchanged, with no bytes", async () => {
    const chunk = await fileChunkFromResponse(
      new Response(null, { status: 304, headers: { ETag: '"same"' } }),
    );
    expect(chunk.unchanged).toBe(true);
    expect(chunk.content.length).toBe(0);
  });

  it("sends the range and validator headers", async () => {
    const mockFetch = jest
      .fn<(url: string, init?: RequestInit) => Promise<Response>>()
      .mockResolvedValue(
        new Response("0123", {
          status: 206,
          headers: { "Content-Range": "bytes 0-3/100" },
        }),
      );
    const sandbox = makeSandbox(mockFetch);

    await sandbox.readRange("/big.bin", {
      start: 0,
      end: 3,
      ifRange: '"abc"',
    });

    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Record<string, string>;
    expect(headers.Range).toBe("bytes=0-3");
    expect(headers["If-Range"]).toBe('"abc"');
  });

  it("surfaces a 416 as an operation error", async () => {
    const mockFetch = jest
      .fn<(url: string, init?: RequestInit) => Promise<Response>>()
      .mockResolvedValue(
        new Response("invalid range", {
          status: 416,
          headers: { "Content-Range": "bytes */100" },
        }),
      );
    const sandbox = makeSandbox(mockFetch);

    await expect(sandbox.readRange("/big.bin", { start: 500 })).rejects.toThrow(
      "past the end",
    );
  });

  it("stat reads size and validators from the headers", () => {
    const stat = fileStatFromResponse(
      new Response(null, {
        status: 200,
        headers: {
          "Content-Length": "100",
          ETag: '"abc"',
          "Content-Type": "application/octet-stream",
        },
      }),
    );
    expect(stat.size_bytes).toBe(100);
    expect(stat.etag).toBe('"abc"');
    expect(stat.content_type).toBe("application/octet-stream");
  });
});
