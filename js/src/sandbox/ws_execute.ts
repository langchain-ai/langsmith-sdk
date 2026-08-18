/**
 * WebSocket-based command execution for long-running commands.
 *
 * Uses the `ws` npm package (optional peer dependency).
 * Install with: npm install ws
 */

import {
  LangSmithCommandTimeoutError,
  LangSmithSandboxConnectionError,
  LangSmithSandboxConnectTimeoutError,
  LangSmithSandboxOperationError,
  LangSmithSandboxRetryableConnectionError,
  LangSmithSandboxServerReloadError,
} from "./errors.js";
import type { WsMessage, WsRunOptions } from "./types.js";
import { getLangSmithEnvironmentVariable } from "../utils/env.js";

/** Read a WebSocket timeout override, in seconds. `<= 0` disables it. */
function envTimeout(name: string, defaultSeconds: number): number | undefined {
  const raw = getLangSmithEnvironmentVariable(name);
  if (raw === undefined || raw.trim() === "") return defaultSeconds;
  const value = Number(raw);
  if (!Number.isFinite(value)) {
    console.warn(
      `Ignoring invalid LANGSMITH_${name}=${raw}, using ${defaultSeconds}`,
    );
    return defaultSeconds;
  }
  return value > 0 ? value : undefined;
}

// A slow cold start is recovered by the retry loop in run(), not by waiting here.
export const WS_OPEN_TIMEOUT = envTimeout("SANDBOX_WS_TIMEOUT_OPEN", 30);
// Ceiling on the whole connect phase. Without it, retrying a blackholed
// handshake costs MAX_AUTO_RECONNECTS + 1 full open timeouts plus backoff.
export const WS_CONNECT_BUDGET = envTimeout(
  "SANDBOX_WS_TIMEOUT_CONNECT_BUDGET",
  120,
);
const RETRYABLE_HANDSHAKE_STATUS_CODES = new Set([500, 502, 503, 504]);

function nowSeconds(): number {
  return performance.now() / 1000;
}

/** Instant after which connect attempts must stop, if bounded. */
export function connectDeadline(): number | undefined {
  return WS_CONNECT_BUDGET === undefined
    ? undefined
    : nowSeconds() + WS_CONNECT_BUDGET;
}

/** Seconds left in the connect budget, or undefined when unbounded. */
export function remainingBudget(
  deadline: number | undefined,
): number | undefined {
  return deadline === undefined ? undefined : deadline - nowSeconds();
}

/** Per-attempt open timeout, clamped so it cannot outlive `deadline`. */
export function openTimeoutFor(
  deadline: number | undefined,
): number | undefined {
  if (deadline === undefined) return WS_OPEN_TIMEOUT;
  const remaining = Math.max(deadline - nowSeconds(), 0);
  return WS_OPEN_TIMEOUT === undefined
    ? remaining
    : Math.min(WS_OPEN_TIMEOUT, remaining);
}

// =============================================================================
// Lazy ws import (optional peer dependency)
// =============================================================================

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type WsWebSocket = any;

// Load the optional 'ws' package once, at module load, instead of importing on
// every call. Resolves to the WebSocket constructor, or null if 'ws' isn't
// installed. run() reads isWsAvailable() to choose WS vs the HTTP fallback.
const wsWebSocketPromise: Promise<WsWebSocket | null> = import("ws").then(
  (ws) => ws.default || ws.WebSocket || ws,
  () => null,
);

/** Whether the optional `ws` package could be loaded (resolved once). */
export async function isWsAvailable(): Promise<boolean> {
  return (await wsWebSocketPromise) !== null;
}

async function ensureWs(): Promise<{
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  WebSocket: any;
}> {
  const WebSocket = await wsWebSocketPromise;
  if (!WebSocket) {
    throw new Error(
      "WebSocket-based execution requires the 'ws' package. " +
        "Install it with: npm install ws",
    );
  }
  return { WebSocket };
}

// =============================================================================
// URL and Auth Helpers
// =============================================================================

/**
 * Convert a sandbox runtime HTTP URL to a WebSocket URL for /execute/ws.
 */
export function buildWsUrl(runtimeUrl: string): string {
  const wsUrl = runtimeUrl
    .replace("https://", "wss://")
    .replace("http://", "ws://");
  return `${wsUrl}/execute/ws`;
}

/**
 * Build auth headers for the WebSocket upgrade request.
 */
export function buildAuthHeaders(
  apiKey: string | undefined,
  extraHeaders?: Record<string, string>,
): Record<string, string> {
  const headers: Record<string, string> = {};
  if (apiKey) {
    headers["X-Api-Key"] = apiKey;
  }
  if (extraHeaders) {
    Object.assign(headers, extraHeaders);
  }
  return headers;
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
      errorType,
    );
  }
  if (errorType === "SessionExpired") {
    throw new LangSmithSandboxOperationError(
      commandId ? `Session expired: ${commandId}` : errorMsg,
      commandId ? "reconnect" : "command",
      errorType,
    );
  }

  throw new LangSmithSandboxOperationError(
    errorMsg,
    commandId ? "reconnect" : "command",
    errorType,
  );
}

// =============================================================================
// WebSocket Stream Helpers
// =============================================================================

/**
 * Create a ws WebSocket connection and return a promise that resolves when open
 * or rejects on error.
 *
 * Socket-level failures and transient 5xx responses are retryable. Other
 * non-101 responses are permanent connection errors.
 */
async function connectWs(
  url: string,
  headers: Record<string, string>,
  openTimeout: number | undefined = WS_OPEN_TIMEOUT,
): Promise<WsWebSocket> {
  const { WebSocket: WS } = await ensureWs();
  return new Promise((resolve, reject) => {
    const ws = new WS(url, {
      headers,
      handshakeTimeout:
        openTimeout === undefined ? undefined : openTimeout * 1000,
    });
    let settled = false;

    ws.on("open", () => {
      if (settled) return;
      settled = true;
      resolve(ws);
    });

    // Attaching this suppresses ws's own "error" for a non-101 response, so the
    // rejected upgrade cannot be misreported as a retryable socket failure. ws
    // leaves cleanup to the handler once a listener is present.
    ws.on(
      "unexpected-response",
      (
        req: { destroy?: () => void },
        res: { statusCode?: number; resume?: () => void },
      ) => {
        res.resume?.();
        req.destroy?.();
        if (settled) return;
        settled = true;
        const ErrorType = RETRYABLE_HANDSHAKE_STATUS_CODES.has(
          res.statusCode ?? 0,
        )
          ? LangSmithSandboxRetryableConnectionError
          : LangSmithSandboxConnectionError;
        reject(
          new ErrorType(
            `WebSocket upgrade to ${url} rejected by server (HTTP ${res.statusCode})`,
          ),
        );
      },
    );

    // Stays attached after settling so a late error has a listener and cannot
    // become an unhandled 'error' event.
    ws.on("error", (err: Error) => {
      if (settled) return;
      settled = true;
      reject(
        new LangSmithSandboxConnectTimeoutError(
          `Failed to connect to sandbox WebSocket: ${err.message}`,
        ),
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
  ws: WsWebSocket,
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
        "Server is reloading, reconnect to resume",
      );
    } else if (code !== 1000) {
      error = new LangSmithSandboxConnectionError(
        `WebSocket connection closed unexpectedly (code: ${code}, reason: ${reason.toString()})`,
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
        `WebSocket connection error: ${err.message}`,
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
  runtimeUrl: string,
  apiKey: string | undefined,
  command: string,
  options: WsRunOptions = {},
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
    headers: extraHeaders,
    openTimeout = WS_OPEN_TIMEOUT,
  } = options;

  const wsUrl = buildWsUrl(runtimeUrl);
  const headers = buildAuthHeaders(apiKey, extraHeaders);
  const control = new WSStreamControl();

  async function* stream(): AsyncIterableIterator<WsMessage> {
    let ws: WsWebSocket | undefined;
    try {
      ws = await connectWs(wsUrl, headers, openTimeout);
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
 * The iterator yields the server's 'started' acknowledgement, then stdout,
 * stderr, exit, and error messages. That acknowledgement is the only evidence a
 * reattachment landed for a command producing no output, so it is forwarded
 * rather than dropped.
 */
export async function reconnectWsStream(
  runtimeUrl: string,
  apiKey: string | undefined,
  commandId: string,
  options: {
    stdoutOffset?: number;
    stderrOffset?: number;
    headers?: Record<string, string>;
  } = {},
): Promise<[AsyncIterableIterator<WsMessage>, WSStreamControl]> {
  const { stdoutOffset = 0, stderrOffset = 0, headers: extraHeaders } = options;

  const wsUrl = buildWsUrl(runtimeUrl);
  const headers = buildAuthHeaders(apiKey, extraHeaders);
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
        }),
      );

      // Read messages until exit or error
      for await (const msg of readWsMessages(ws)) {
        const msgType = msg.type;

        if (
          msgType === "started" ||
          msgType === "stdout" ||
          msgType === "stderr"
        ) {
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
