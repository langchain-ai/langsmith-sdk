/**
 * WebSocket-based command execution for long-running commands.
 *
 * Uses the `ws` npm package (optional peer dependency).
 * Install with: npm install ws
 */

import {
  LangSmithCommandTimeoutError,
  LangSmithSandboxConnectionError,
  LangSmithSandboxOperationError,
  LangSmithSandboxServerReloadError,
} from "./errors.js";
import type { WsMessage, WsRunOptions } from "./types.js";

// =============================================================================
// Lazy ws import (optional peer dependency)
// =============================================================================

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type WsWebSocket = any;

async function ensureWs(): Promise<{
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  WebSocket: any;
}> {
  try {
    const ws = await import("ws");
    return { WebSocket: ws.default || ws.WebSocket || ws };
  } catch {
    throw new Error(
      "WebSocket-based execution requires the 'ws' package. " +
        "Install it with: npm install ws"
    );
  }
}

// =============================================================================
// URL and Auth Helpers
// =============================================================================

/**
 * Convert a dataplane HTTP URL to a WebSocket URL for /execute/ws.
 */
export function buildWsUrl(dataplaneUrl: string): string {
  const wsUrl = dataplaneUrl
    .replace("https://", "wss://")
    .replace("http://", "ws://");
  return `${wsUrl}/execute/ws`;
}

/**
 * Build auth headers for the WebSocket upgrade request.
 */
export function buildAuthHeaders(
  apiKey: string | undefined
): Record<string, string> {
  if (apiKey) {
    return { "X-Api-Key": apiKey };
  }
  return {};
}

// =============================================================================
// Stream Control
// =============================================================================

/**
 * Control interface for an active WebSocket stream.
 *
 * Created before the async generator starts, bound to the WebSocket once
 * the connection opens. The CommandHandle holds a reference to this
 * object to send kill/input messages.
 */
export class WSStreamControl {
  private _ws: WsWebSocket = null;
  private _closed = false;
  private _killed = false;

  /** Bind to the active WebSocket. Called inside the generator. */
  _bind(ws: WsWebSocket): void {
    this._ws = ws;
  }

  /** Mark as closed. Called when the generator exits. */
  _unbind(): void {
    this._closed = true;
    this._ws = null;
  }

  /** True if kill() has been called on this stream. */
  get killed(): boolean {
    return this._killed;
  }

  /** Send a kill message to abort the running command. */
  sendKill(): void {
    this._killed = true;
    if (this._ws && !this._closed && this._ws.readyState === 1) {
      this._ws.send(JSON.stringify({ type: "kill" }));
    }
  }

  /** Send stdin data to the running command. */
  sendInput(data: string): void {
    if (this._ws && !this._closed && this._ws.readyState === 1) {
      this._ws.send(JSON.stringify({ type: "input", data }));
    }
  }
}

// =============================================================================
// Error Handling
// =============================================================================

/**
 * Raise the appropriate exception from a server error message.
 */
export function raiseForWsError(msg: WsMessage, commandId = ""): never {
  const errorType = (msg.error_type as string | undefined) ?? "CommandError";
  const errorMsg = (msg.error as string | undefined) ?? "Unknown error";

  if (errorType === "CommandTimeout") {
    throw new LangSmithCommandTimeoutError(errorMsg);
  }
  if (errorType === "CommandNotFound") {
    throw new LangSmithSandboxOperationError(
      commandId ? `Command not found: ${commandId}` : errorMsg,
      commandId ? "reconnect" : "command",
      errorType
    );
  }
  if (errorType === "SessionExpired") {
    throw new LangSmithSandboxOperationError(
      commandId ? `Session expired: ${commandId}` : errorMsg,
      commandId ? "reconnect" : "command",
      errorType
    );
  }

  throw new LangSmithSandboxOperationError(
    errorMsg,
    commandId ? "reconnect" : "command",
    errorType
  );
}

// =============================================================================
// WebSocket Stream Helpers
// =============================================================================

/**
 * Create a ws WebSocket connection and return a promise that resolves when open
 * or rejects on error.
 */
async function connectWs(
  url: string,
  headers: Record<string, string>
): Promise<WsWebSocket> {
  const { WebSocket: WS } = await ensureWs();
  return new Promise((resolve, reject) => {
    const ws = new WS(url, { headers });

    ws.on("open", () => {
      ws.removeAllListeners("error");
      resolve(ws);
    });

    ws.on("error", (err: Error) => {
      ws.removeAllListeners("open");
      reject(
        new LangSmithSandboxConnectionError(
          `Failed to connect to sandbox WebSocket: ${err.message}`
        )
      );
    });
  });
}

/**
 * Read messages from a ws WebSocket as an async iterable.
 *
 * Yields parsed WsMessage objects. Handles close events and errors,
 * mapping them to appropriate exceptions.
 */
async function* readWsMessages(
  ws: WsWebSocket
): AsyncIterableIterator<WsMessage> {
  // Buffer incoming messages so the consumer can process them at its own pace
  const messageQueue: WsMessage[] = [];
  let resolve: (() => void) | null = null;
  let error: Error | null = null;
  let done = false;

  const onMessage = (data: Buffer | string) => {
    const raw = typeof data === "string" ? data : data.toString();
    const msg = JSON.parse(raw) as WsMessage;
    messageQueue.push(msg);
    if (resolve) {
      const r = resolve;
      resolve = null;
      r();
    }
  };

  const onClose = (code: number, reason: Buffer) => {
    done = true;
    if (code === 1001) {
      error = new LangSmithSandboxServerReloadError(
        "Server is reloading, reconnect to resume"
      );
    } else if (code !== 1000) {
      error = new LangSmithSandboxConnectionError(
        `WebSocket connection closed unexpectedly (code: ${code}, reason: ${reason.toString()})`
      );
    }
    if (resolve) {
      const r = resolve;
      resolve = null;
      r();
    }
  };

  const onError = (err: Error) => {
    done = true;
    if (!error) {
      error = new LangSmithSandboxConnectionError(
        `WebSocket connection error: ${err.message}`
      );
    }
    if (resolve) {
      const r = resolve;
      resolve = null;
      r();
    }
  };

  ws.on("message", onMessage);
  ws.on("close", onClose);
  ws.on("error", onError);

  try {
    while (true) {
      // Drain buffered messages first
      while (messageQueue.length > 0) {
        yield messageQueue.shift()!;
      }

      // If done and queue is empty, we're finished
      if (done) {
        if (error) {
          throw error;
        }
        return;
      }

      // Wait for next message or close/error
      await new Promise<void>((r) => {
        resolve = r;
      });
    }
  } finally {
    ws.removeListener("message", onMessage);
    ws.removeListener("close", onClose);
    ws.removeListener("error", onError);
  }
}

// =============================================================================
// Async Stream Functions
// =============================================================================

/**
 * Execute a command over WebSocket, yielding raw message dicts.
 *
 * Returns a tuple of [async_message_iterator, control]. The control object
 * provides sendKill() and sendInput() methods for the CommandHandle.
 *
 * The iterator yields WsMessage objects with a "type" field:
 * - { type: "started", command_id: "...", pid: N }
 * - { type: "stdout", data: "...", offset: N }
 * - { type: "stderr", data: "...", offset: N }
 * - { type: "exit", exit_code: N }
 *
 * If onStdout/onStderr callbacks are provided, they are invoked as
 * data arrives in addition to yielding the messages.
 */
export async function runWsStream(
  dataplaneUrl: string,
  apiKey: string | undefined,
  command: string,
  options: WsRunOptions = {}
): Promise<[AsyncIterableIterator<WsMessage>, WSStreamControl]> {
  const {
    timeout = 60,
    env,
    cwd,
    shell = "/bin/bash",
    onStdout,
    onStderr,
    commandId,
    idleTimeout = 300,
    killOnDisconnect = false,
    ttlSeconds = 600,
    pty,
  } = options;

  const wsUrl = buildWsUrl(dataplaneUrl);
  const headers = buildAuthHeaders(apiKey);
  const control = new WSStreamControl();

  async function* stream(): AsyncIterableIterator<WsMessage> {
    let ws: WsWebSocket | undefined;
    try {
      ws = await connectWs(wsUrl, headers);
      control._bind(ws);

      // Send execute request
      const payload: Record<string, unknown> = {
        type: "execute",
        command,
        timeout_seconds: timeout,
        shell,
        idle_timeout_seconds: idleTimeout,
        kill_on_disconnect: killOnDisconnect,
        ttl_seconds: ttlSeconds,
      };
      if (env) payload.env = env;
      if (cwd) payload.cwd = cwd;
      if (commandId) payload.command_id = commandId;
      if (pty) payload.pty = true;

      ws.send(JSON.stringify(payload));

      // Read messages until exit or error
      for await (const msg of readWsMessages(ws)) {
        const msgType = msg.type;

        if (msgType === "started") {
          yield msg;
        } else if (msgType === "stdout") {
          if (onStdout) onStdout(msg.data as string);
          yield msg;
        } else if (msgType === "stderr") {
          if (onStderr) onStderr(msg.data as string);
          yield msg;
        } else if (msgType === "exit") {
          yield msg;
          return;
        } else if (msgType === "error") {
          raiseForWsError(msg);
        }
      }
    } finally {
      control._unbind();
      if (ws && ws.readyState === 1) {
        ws.close();
      }
    }
  }

  return [stream(), control];
}

/**
 * Reconnect to an existing command over WebSocket.
 *
 * Returns a tuple of [async_message_iterator, control], same as runWsStream.
 * The iterator yields stdout, stderr, exit, and error messages.
 * No 'started' message is sent on reconnection.
 */
export async function reconnectWsStream(
  dataplaneUrl: string,
  apiKey: string | undefined,
  commandId: string,
  options: {
    stdoutOffset?: number;
    stderrOffset?: number;
  } = {}
): Promise<[AsyncIterableIterator<WsMessage>, WSStreamControl]> {
  const { stdoutOffset = 0, stderrOffset = 0 } = options;

  const wsUrl = buildWsUrl(dataplaneUrl);
  const headers = buildAuthHeaders(apiKey);
  const control = new WSStreamControl();

  async function* stream(): AsyncIterableIterator<WsMessage> {
    let ws: WsWebSocket | undefined;
    try {
      ws = await connectWs(wsUrl, headers);
      control._bind(ws);

      // Send reconnect request
      ws.send(
        JSON.stringify({
          type: "reconnect",
          command_id: commandId,
          stdout_offset: stdoutOffset,
          stderr_offset: stderrOffset,
        })
      );

      // Read messages until exit or error
      for await (const msg of readWsMessages(ws)) {
        const msgType = msg.type;

        if (msgType === "stdout" || msgType === "stderr") {
          yield msg;
        } else if (msgType === "exit") {
          yield msg;
          return;
        } else if (msgType === "error") {
          raiseForWsError(msg, commandId);
        }
      }
    } finally {
      control._unbind();
      if (ws && ws.readyState === 1) {
        ws.close();
      }
    }
  }

  return [stream(), control];
}
