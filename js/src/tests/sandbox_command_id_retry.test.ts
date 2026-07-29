/**
 * Idempotent retry when a command WebSocket fails before 'started'.
 *
 * run() sends a client-generated command_id and the server does get-or-create
 * keyed on it, so re-issuing a command whose tunnel closed before 'started' —
 * or whose connect never completed — reattaches to the same session instead of
 * spawning a second one. A rejected handshake is permanent and must not retry.
 */
import { jest, describe, it, expect, beforeEach } from "@jest/globals";
import type { WsMessage } from "../sandbox/types.js";
import {
  LangSmithSandboxConnectionError,
  LangSmithSandboxConnectTimeoutError,
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
