/**
 * Idempotent retry when a command WebSocket closes before 'started'.
 *
 * run() sends a client-generated command_id and the server does get-or-create
 * keyed on it, so re-issuing a command whose tunnel closed before 'started'
 * reattaches to the same session instead of spawning a second one.
 */
import { jest, describe, it, expect, beforeEach } from "@jest/globals";
import type { WsMessage } from "../sandbox/types.js";

const runWsStream = jest.fn<any>();
const reconnectWsStream = jest.fn<any>();

jest.unstable_mockModule("../sandbox/ws_execute.js", () => ({
  runWsStream,
  reconnectWsStream,
  WSStreamControl: class {},
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
