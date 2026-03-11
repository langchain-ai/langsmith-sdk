/**
 * CommandHandle - async handle to a running command with streaming output
 * and auto-reconnect.
 *
 * Port of Python's AsyncCommandHandle to TypeScript.
 */

import type { ExecutionResult, OutputChunk, WsMessage } from "./types.js";
import type { WSStreamControl } from "./ws_execute.js";
import type { Sandbox } from "./sandbox.js";
import {
  LangSmithSandboxConnectionError,
  LangSmithSandboxOperationError,
} from "./errors.js";

/**
 * Async handle to a running command with streaming output and auto-reconnect.
 *
 * Async iterable, yielding OutputChunk objects (stdout and stderr interleaved
 * in arrival order). Access .result after iteration to get the full
 * ExecutionResult.
 *
 * Auto-reconnect behavior:
 * - Server hot-reload (1001 Going Away): reconnect immediately
 * - Network error / unexpected close:    reconnect with exponential backoff
 * - User called kill():                  do NOT reconnect (propagate error)
 *
 * @example
 * ```typescript
 * const handle = await sandbox.run("make build", { timeout: 600, wait: false });
 *
 * for await (const chunk of handle) {  // auto-reconnects on transient errors
 *   process.stdout.write(chunk.data);
 * }
 *
 * const result = await handle.result;
 * console.log(`Exit code: ${result.exit_code}`);
 * ```
 */
export class CommandHandle {
  static MAX_AUTO_RECONNECTS = 5;
  static BACKOFF_BASE = 0.5; // seconds
  static BACKOFF_MAX = 8.0; // seconds

  private _stream: AsyncIterableIterator<WsMessage>;
  private _control: WSStreamControl | null;
  private _sandbox: Sandbox;
  private _commandId: string | null = null;
  private _pid: number | null = null;
  private _result: ExecutionResult | null = null;
  private _stdoutParts: string[] = [];
  private _stderrParts: string[] = [];
  private _exhausted = false;
  private _lastStdoutOffset: number;
  private _lastStderrOffset: number;
  private _started: boolean;

  /** @internal */
  constructor(
    messageStream: AsyncIterableIterator<WsMessage>,
    control: WSStreamControl | null,
    sandbox: Sandbox,
    options?: {
      commandId?: string;
      stdoutOffset?: number;
      stderrOffset?: number;
    }
  ) {
    this._stream = messageStream;
    this._control = control;
    this._sandbox = sandbox;
    this._lastStdoutOffset = options?.stdoutOffset ?? 0;
    this._lastStderrOffset = options?.stderrOffset ?? 0;

    // New executions (no commandId): _ensureStarted reads "started".
    // Reconnections (commandId set): skip since reconnect streams
    // don't send a "started" message.
    if (options?.commandId) {
      this._commandId = options.commandId;
      this._started = true;
    } else {
      this._started = false;
    }
  }

  /**
   * Read the 'started' message to populate commandId and pid.
   *
   * Must be called (and awaited) before iterating for new executions.
   */
  async _ensureStarted(): Promise<void> {
    if (this._started) return;

    const firstResult = await this._stream.next();
    if (firstResult.done) {
      throw new LangSmithSandboxOperationError(
        "Command stream ended before 'started' message",
        "command"
      );
    }
    const firstMsg = firstResult.value;
    if (firstMsg.type !== "started") {
      throw new LangSmithSandboxOperationError(
        `Expected 'started' message, got '${firstMsg.type}'`,
        "command"
      );
    }
    this._commandId = (firstMsg.command_id as string) ?? null;
    this._pid = (firstMsg.pid as number) ?? null;
    this._started = true;
  }

  /** The server-assigned command ID. Available after _ensureStarted(). */
  get commandId(): string | null {
    return this._commandId;
  }

  /** The process ID on the sandbox. Available after _ensureStarted(). */
  get pid(): number | null {
    return this._pid;
  }

  /**
   * The final execution result. Drains the stream if not already exhausted.
   */
  get result(): Promise<ExecutionResult> {
    return this._getResult();
  }

  private async _getResult(): Promise<ExecutionResult> {
    if (this._result === null) {
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      for await (const _ of this) {
        // drain
      }
    }
    if (this._result === null) {
      throw new LangSmithSandboxOperationError(
        "Command stream ended without exit message",
        "command"
      );
    }
    return this._result;
  }

  /**
   * Iterate over output chunks from the current stream (no reconnect).
   */
  private async *_iterStream(): AsyncIterableIterator<OutputChunk> {
    await this._ensureStarted();
    if (this._exhausted) return;

    for await (const msg of this._stream) {
      const msgType = msg.type;
      if (msgType === "stdout" || msgType === "stderr") {
        const chunk: OutputChunk = {
          stream: msgType,
          data: msg.data as string,
          offset: (msg.offset as number) ?? 0,
        };
        if (msgType === "stdout") {
          this._stdoutParts.push(msg.data as string);
        } else {
          this._stderrParts.push(msg.data as string);
        }
        yield chunk;
      } else if (msgType === "exit") {
        this._result = {
          stdout: this._stdoutParts.join(""),
          stderr: this._stderrParts.join(""),
          exit_code: (msg.exit_code as number) ?? -1,
        };
        this._exhausted = true;
        return;
      }
    }
    this._exhausted = true;
  }

  /**
   * Async iterate over output chunks with auto-reconnect on transient errors.
   *
   * Reconnect strategy:
   * - 1001 Going Away (hot-reload): immediate reconnect, no delay
   * - Other SandboxConnectionError:  exponential backoff (0.5s, 1s, 2s...)
   * - After kill():                  no reconnect, error propagates
   */
  async *[Symbol.asyncIterator](): AsyncIterableIterator<OutputChunk> {
    let reconnectAttempts = 0;

    while (true) {
      try {
        for await (const chunk of this._iterStream()) {
          reconnectAttempts = 0; // Reset on successful data
          if (chunk.stream === "stdout") {
            this._lastStdoutOffset =
              chunk.offset + new TextEncoder().encode(chunk.data).length;
          } else {
            this._lastStderrOffset =
              chunk.offset + new TextEncoder().encode(chunk.data).length;
          }
          yield chunk;
        }
        return; // Stream ended normally (exit message received)
      } catch (e) {
        const eName =
          e != null && typeof e === "object" ? (e as Error).name : "";
        if (
          eName !== "LangSmithSandboxConnectionError" &&
          eName !== "LangSmithSandboxServerReloadError"
        ) {
          throw e;
        }

        if (this._control && this._control.killed) {
          throw e;
        }

        reconnectAttempts++;
        if (reconnectAttempts > CommandHandle.MAX_AUTO_RECONNECTS) {
          throw new LangSmithSandboxConnectionError(
            `Lost connection ${reconnectAttempts} times in succession, giving up`
          );
        }

        const isHotReload = eName === "LangSmithSandboxServerReloadError";
        if (!isHotReload) {
          const delay = Math.min(
            CommandHandle.BACKOFF_BASE * 2 ** (reconnectAttempts - 1),
            CommandHandle.BACKOFF_MAX
          );
          await new Promise((r) => setTimeout(r, delay * 1000));
        }

        if (this._commandId === null) {
          throw e;
        }

        const newHandle = await this._sandbox.reconnect(this._commandId, {
          stdoutOffset: this._lastStdoutOffset,
          stderrOffset: this._lastStderrOffset,
        });
        this._stream = newHandle._stream;
        this._control = newHandle._control;
        this._exhausted = false;
      }
    }
  }

  /**
   * Send a kill signal to the running command (SIGKILL).
   *
   * The server kills the entire process group. The stream will
   * subsequently yield an exit message with a non-zero exit code.
   */
  kill(): void {
    if (this._control) {
      this._control.sendKill();
    }
  }

  /**
   * Write data to the command's stdin.
   */
  sendInput(data: string): void {
    if (this._control) {
      this._control.sendInput(data);
    }
  }

  /** Last known stdout byte offset (for manual reconnection). */
  get lastStdoutOffset(): number {
    return this._lastStdoutOffset;
  }

  /** Last known stderr byte offset (for manual reconnection). */
  get lastStderrOffset(): number {
    return this._lastStderrOffset;
  }

  /**
   * Reconnect to this command from the last known offsets.
   *
   * Returns a new CommandHandle that resumes output from where this one
   * left off.
   */
  async reconnect(): Promise<CommandHandle> {
    if (this._commandId === null) {
      throw new LangSmithSandboxOperationError(
        "Cannot reconnect: command ID not available",
        "reconnect"
      );
    }
    return this._sandbox.reconnect(this._commandId, {
      stdoutOffset: this._lastStdoutOffset,
      stderrOffset: this._lastStderrOffset,
    });
  }
}
