/**
 * Idempotent retry when a command WebSocket fails before 'started'.
 *
 * run() sends a client-generated command_id and the server does get-or-create
 * keyed on it, so re-issuing a command whose tunnel closed before 'started' —
 * or whose connect never completed — reattaches to the same session instead of
 * spawning a second one. Transient 5xx handshake rejections are safe to retry;
 * permanent 4xx rejections still propagate immediately.
 */
import { jest, describe, it, expect, beforeEach } from "@jest/globals";
import type { WsMessage } from "../sandbox/types.js";
import {
  LangSmithSandboxConnectionError,
  LangSmithSandboxConnectTimeoutError,
  LangSmithSandboxRetryableConnectionError,
} from "../sandbox/errors.js";

// Virtual clock so budget assertions do not depend on real elapsed time.
const clock = { now: 0 };

const runWsStream = jest.fn<any>();
const reconnectWsStream = jest.fn<any>();

jest.unstable_mockModule("../sandbox/ws_execute.js", () => ({
  runWsStream,
  reconnectWsStream,
  WSStreamControl: class {},
  isWsAvailable: () => Promise.resolve(true),
  WS_OPEN_TIMEOUT: 30,
  WS_CONNECT_BUDGET: 120,
  connectDeadline: () => clock.now + 120,
  remainingBudget: (deadline?: number) =>
    deadline === undefined ? undefined : deadline - clock.now,
  openTimeoutFor: (deadline?: number) =>
    deadline === undefined
      ? 30
      : Math.min(30, Math.max(deadline - clock.now, 0)),
}));

const { Sandbox } = await import("../sandbox/sandbox.js");

function makeStream(messages: WsMessage[]): AsyncIterableIterator<WsMessage> {
  let i = 0;
  return {
    next: async () =>
      i < messages.length
        ? { value: messages[i++], done: false }
        : { value: undefined as never, done: true },
    [Symbol.asyncIterator]() {
      return this;
    },
  };
}

function failingStream(err: Error): AsyncIterableIterator<WsMessage> {
  return {
    next: async () => {
      throw err;
    },
    [Symbol.asyncIterator]() {
      return this;
    },
  } as AsyncIterableIterator<WsMessage>;
}

function makeSandbox() {
  const client = {
    getApiKey: () => "test-key",
    getDefaultHeaders: () => ({}),
    getRequestHeaders: async () => ({ "x-api-key": "test-key" }),
    getSandboxRuntimeUrl: () => "https://api.example.com/api/v2/sandboxes/sb",
  };
  return new Sandbox(
    {
      name: "sb",
      dataplane_url: "https://dp.example.com/sb-123",
      status: "ready",
    } as never,
    client as never,
  );
}

describe("run() early-close retry", () => {
  beforeEach(() => {
    runWsStream.mockReset();
    clock.now = 0;
  });

  it("retries with the same command_id after a close before 'started'", async () => {
    const sandbox = makeSandbox();

    runWsStream
      .mockImplementationOnce((..._args: unknown[]) => [makeStream([]), null])
      .mockImplementationOnce((...args: unknown[]) => {
        const opts = args[3] as { commandId: string };
        return [
          makeStream([
            { type: "started", command_id: opts.commandId, pid: 1 },
            { type: "exit", exit_code: 0 },
          ]),
          null,
        ];
      });

    const result = await sandbox.run("echo hi");

    expect(result.exit_code).toBe(0);
    expect(runWsStream).toHaveBeenCalledTimes(2);
    const first = runWsStream.mock.calls[0][3] as { commandId: string };
    const second = runWsStream.mock.calls[1][3] as { commandId: string };
    expect(first.commandId).toBe(second.commandId);
  });

  it("retries with the same command_id after a failed connect", async () => {
    const sandbox = makeSandbox();

    runWsStream
      .mockImplementationOnce((..._args: unknown[]) => [
        failingStream(new LangSmithSandboxConnectTimeoutError("timed out")),
        null,
      ])
      .mockImplementationOnce((...args: unknown[]) => {
        const opts = args[3] as { commandId: string };
        return [
          makeStream([
            { type: "started", command_id: opts.commandId, pid: 1 },
            { type: "exit", exit_code: 0 },
          ]),
          null,
        ];
      });

    const result = await sandbox.run("echo hi");

    expect(result.exit_code).toBe(0);
    expect(runWsStream).toHaveBeenCalledTimes(2);
    const first = runWsStream.mock.calls[0][3] as { commandId: string };
    const second = runWsStream.mock.calls[1][3] as { commandId: string };
    expect(first.commandId).toBe(second.commandId);
  });

  it("retries a transient rejected handshake with the same command_id", async () => {
    const sandbox = makeSandbox();

    runWsStream
      .mockImplementationOnce((..._args: unknown[]) => [
        failingStream(
          new LangSmithSandboxRetryableConnectionError(
            "WebSocket upgrade rejected by server (HTTP 503)",
          ),
        ),
        null,
      ])
      .mockImplementationOnce((...args: unknown[]) => {
        const opts = args[3] as { commandId: string };
        return [
          makeStream([
            { type: "started", command_id: opts.commandId, pid: 1 },
            { type: "exit", exit_code: 0 },
          ]),
          null,
        ];
      });

    const result = await sandbox.run("echo hi");

    expect(result.exit_code).toBe(0);
    expect(runWsStream).toHaveBeenCalledTimes(2);
    const first = runWsStream.mock.calls[0][3] as { commandId: string };
    const second = runWsStream.mock.calls[1][3] as { commandId: string };
    expect(first.commandId).toBe(second.commandId);
  });

  it("does not retry a rejected handshake", async () => {
    const sandbox = makeSandbox();
    runWsStream.mockImplementation((..._args: unknown[]) => [
      failingStream(
        new LangSmithSandboxConnectionError(
          "WebSocket upgrade rejected by server (HTTP 404)",
        ),
      ),
      null,
    ]);

    await expect(sandbox.run("echo hi")).rejects.toThrow("HTTP 404");
    expect(runWsStream).toHaveBeenCalledTimes(1);
  });

  it("caps total connect wall clock at the budget", async () => {
    const sandbox = makeSandbox();
    const opens: (number | undefined)[] = [];

    runWsStream.mockImplementation((...args: unknown[]) => {
      const opts = args[3] as { openTimeout?: number };
      opens.push(opts.openTimeout);
      // Each attempt burns its full open timeout.
      clock.now += opts.openTimeout ?? 0;
      return [
        failingStream(new LangSmithSandboxConnectTimeoutError("timed out")),
        null,
      ];
    });

    await expect(sandbox.run("echo hi")).rejects.toThrow(
      LangSmithSandboxConnectTimeoutError,
    );

    expect(clock.now).toBeLessThanOrEqual(120);
    expect(opens[0]).toBe(30);
    const total = opens.reduce((a, b) => (a ?? 0) + (b ?? 0), 0) ?? 0;
    expect(total).toBeLessThanOrEqual(120);
  });

  it("never starts an attempt once the budget is spent", async () => {
    const sandbox = makeSandbox();
    const opens: (number | undefined)[] = [];

    runWsStream.mockImplementation((...args: unknown[]) => {
      const opts = args[3] as { openTimeout?: number };
      opens.push(opts.openTimeout);
      // Land just short of the deadline so the clamped backoff spends the rest.
      clock.now = 119.9;
      return [
        failingStream(new LangSmithSandboxConnectTimeoutError("timed out")),
        null,
      ];
    });

    await expect(sandbox.run("echo hi")).rejects.toThrow(
      LangSmithSandboxConnectTimeoutError,
    );

    // A 0 openTimeout would disable ws's handshakeTimeout entirely.
    expect(opens).not.toContain(0);
  });

  it("retries a connect timeout while reconnecting a live command", async () => {
    const sandbox = makeSandbox();

    // Stream dies mid-command; the handle must reconnect to finish it.
    runWsStream.mockImplementationOnce((...args: unknown[]) => {
      const opts = args[3] as { commandId: string };
      return [
        (function () {
          const msgs: WsMessage[] = [
            { type: "started", command_id: opts.commandId, pid: 1 },
          ];
          let i = 0;
          return {
            next: async () => {
              if (i < msgs.length) return { value: msgs[i++], done: false };
              throw new LangSmithSandboxConnectionError("connection lost");
            },
            [Symbol.asyncIterator]() {
              return this;
            },
          } as AsyncIterableIterator<WsMessage>;
        })(),
        null,
      ];
    });

    // First reconnect attempt fails at the socket level (the subclass that a
    // name-based check would have let escape), the second succeeds.
    reconnectWsStream
      .mockImplementationOnce(() => [
        failingStream(new LangSmithSandboxConnectTimeoutError("timed out")),
        null,
      ])
      .mockImplementationOnce(() => [
        makeStream([{ type: "exit", exit_code: 0 }]),
        null,
      ]);

    const handle = await sandbox.run("echo hi", { wait: false });
    const result = await handle.result;

    expect(result.exit_code).toBe(0);
    expect(reconnectWsStream).toHaveBeenCalledTimes(2);
  });

  it("does not retry a non-early-close error (e.g. wrong first frame)", async () => {
    const sandbox = makeSandbox();
    runWsStream.mockImplementation((..._args: unknown[]) => [
      makeStream([{ type: "stdout", data: "oops", offset: 0 }]),
      null,
    ]);

    await expect(sandbox.run("echo hi", { wait: false })).rejects.toThrow(
      "Expected 'started'",
    );
    expect(runWsStream).toHaveBeenCalledTimes(1);
  });
});
