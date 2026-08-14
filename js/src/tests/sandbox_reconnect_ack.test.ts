/**
 * A silent command must outlive more socket losses than the reconnect budget.
 *
 * A command and its WebSocket are separate things: the command keeps running on
 * the server and the socket is only this client's attachment to it. The server
 * acknowledges every successful reattachment with a 'started' frame, which for a
 * command producing no output is the only evidence the reattachment landed.
 *
 * The budget is meant to bound *consecutive failed* reattachments. Reset it only
 * on stdout/stderr and it instead counts socket closures since the last output,
 * so a healthy, attached, quiet command dies one loss at a time.
 */
import { jest, describe, it, expect, beforeEach } from "@jest/globals";
import type { WsMessage } from "../sandbox/types.js";
import { LangSmithSandboxConnectionError } from "../sandbox/errors.js";

const runWsStream = jest.fn<any>();
const reconnectWsStream = jest.fn<any>();

jest.unstable_mockModule("../sandbox/ws_execute.js", () => ({
  runWsStream,
  reconnectWsStream,
  WSStreamControl: class {},
  isWsAvailable: () => Promise.resolve(true),
  WS_OPEN_TIMEOUT: 30,
  WS_CONNECT_BUDGET: 120,
  connectDeadline: () => 120,
  remainingBudget: () => 120,
  openTimeoutFor: () => 30,
}));

const { Sandbox } = await import("../sandbox/sandbox.js");
const { CommandHandle } = await import("../sandbox/command_handle.js");

const COMMAND_ID = "cmd-123";

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

/** Yields the given frames, then loses the socket. */
function thenLost(
  messages: WsMessage[],
  err: Error,
): AsyncIterableIterator<WsMessage> {
  let i = 0;
  return {
    next: async () => {
      if (i < messages.length) return { value: messages[i++], done: false };
      throw err;
    },
    [Symbol.asyncIterator]() {
      return this;
    },
  } as AsyncIterableIterator<WsMessage>;
}

function startedMsg(commandId: string = COMMAND_ID): WsMessage {
  return { type: "started", command_id: commandId, pid: 42 } as WsMessage;
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

/** A handle already attached to a running command, whose socket then drops. */
async function handleThatLosesItsSocket(sandbox: InstanceType<typeof Sandbox>) {
  runWsStream.mockImplementationOnce(() => [
    thenLost(
      [startedMsg()],
      new LangSmithSandboxConnectionError("connection lost"),
    ),
    null,
  ]);
  return (await sandbox.run("sleep 60", {
    wait: false,
    commandId: COMMAND_ID,
  })) as InstanceType<typeof CommandHandle>;
}

describe("reconnect acknowledgement", () => {
  beforeEach(() => {
    runWsStream.mockReset();
    reconnectWsStream.mockReset();
    jest.spyOn(global, "setTimeout").mockImplementation(((fn: () => void) => {
      fn();
      return 0 as never;
    }) as never);
  });

  it("resets the budget on a 'started' ack with no output", async () => {
    const sandbox = makeSandbox();
    const losses = CommandHandle.MAX_AUTO_RECONNECTS + 3;
    let attempts = 0;

    reconnectWsStream.mockImplementation(() => {
      attempts += 1;
      if (attempts < losses) {
        return [
          thenLost(
            [startedMsg()],
            new LangSmithSandboxConnectionError("lost again"),
          ),
          null,
        ];
      }
      return [
        makeStream([startedMsg(), { type: "exit", exit_code: 7 } as WsMessage]),
        null,
      ];
    });

    const handle = await handleThatLosesItsSocket(sandbox);
    const chunks = [];
    for await (const chunk of handle) chunks.push(chunk);

    expect(chunks).toEqual([]);
    expect(attempts).toBe(losses);
    expect((await handle.result).exit_code).toBe(7);
  });

  it("does not reset the budget on an ack for a different command", async () => {
    const sandbox = makeSandbox();

    reconnectWsStream.mockImplementation(() => [
      thenLost(
        [startedMsg("someone-elses-cmd")],
        new LangSmithSandboxConnectionError("lost again"),
      ),
      null,
    ]);

    const handle = await handleThatLosesItsSocket(sandbox);
    await expect(
      (async () => {
        for await (const _ of handle) {
          /* drain */
        }
      })(),
    ).rejects.toThrow(/giving up/);
    expect(reconnectWsStream).toHaveBeenCalledTimes(
      CommandHandle.MAX_AUTO_RECONNECTS,
    );
  });

  it("consumes the ack without yielding a chunk or moving offsets", async () => {
    const sandbox = makeSandbox();
    const seen: string[] = [];

    runWsStream.mockImplementationOnce(() => [
      thenLost(
        [
          startedMsg(),
          { type: "stdout", data: "before", offset: 0 } as WsMessage,
        ],
        new LangSmithSandboxConnectionError("connection lost"),
      ),
      null,
    ]);
    reconnectWsStream.mockImplementationOnce(() => [
      makeStream([
        startedMsg(),
        { type: "stdout", data: "after", offset: 6 } as WsMessage,
        { type: "exit", exit_code: 0 } as WsMessage,
      ]),
      null,
    ]);

    const handle = (await sandbox.run("cmd", {
      wait: false,
      commandId: COMMAND_ID,
      onStdout: (d: string) => seen.push(d),
    })) as InstanceType<typeof CommandHandle>;

    const chunks = [];
    for await (const chunk of handle) chunks.push(chunk);

    expect(chunks.map((c) => c.data)).toEqual(["before", "after"]);
    expect(seen).toEqual(["before", "after"]);
    // Offsets are the ones "before" left behind: the ack carried no bytes.
    expect(reconnectWsStream.mock.calls[0][3]).toMatchObject({
      stdoutOffset: 6,
      stderrOffset: 0,
    });
    expect((await handle.result).stdout).toBe("beforeafter");
  });
});
