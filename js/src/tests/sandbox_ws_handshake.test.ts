import { EventEmitter } from "node:events";
import { beforeEach, describe, expect, it, jest } from "@jest/globals";
import {
  LangSmithSandboxConnectionError,
  LangSmithSandboxRetryableConnectionError,
} from "../sandbox/errors.js";

const response = {
  statusCode: 503,
  headers: {} as Record<string, string>,
  resume: jest.fn(),
};
const request = { destroy: jest.fn() };

class MockWebSocket extends EventEmitter {
  readyState = 0;

  constructor() {
    super();
    queueMicrotask(() => {
      this.emit("unexpected-response", request, response);
    });
  }
}

jest.unstable_mockModule("ws", () => ({ default: MockWebSocket }));

const { runWsStream } = await import("../sandbox/ws_execute.js");

async function rejectedUpgrade(statusCode: number): Promise<unknown> {
  response.statusCode = statusCode;
  const [stream] = await runWsStream(
    "https://dp.example.com/sb-123",
    undefined,
    "echo hi",
  );
  return stream.next();
}

describe("WebSocket upgrade rejection", () => {
  beforeEach(() => {
    response.headers = {};
    response.resume.mockClear();
    request.destroy.mockClear();
  });

  it.each([500, 502, 503, 504])(
    "treats HTTP %i as retryable",
    async (statusCode) => {
      await expect(rejectedUpgrade(statusCode)).rejects.toBeInstanceOf(
        LangSmithSandboxRetryableConnectionError,
      );
      expect(response.resume).toHaveBeenCalledTimes(1);
      expect(request.destroy).toHaveBeenCalledTimes(1);
    },
  );

  it("treats HTTP 429 as retryable and preserves Retry-After", async () => {
    response.headers = { "retry-after": "10" };

    const error = await rejectedUpgrade(429).catch(
      (rejection: unknown) => rejection,
    );

    expect(error).toBeInstanceOf(LangSmithSandboxRetryableConnectionError);
    expect(error).toHaveProperty("retryAfterSeconds", 10);
  });

  it.each(["", "-1", "nan", "Infinity"])(
    "ignores unusable Retry-After %p",
    async (retryAfter) => {
      response.headers = { "retry-after": retryAfter };

      const error = await rejectedUpgrade(429).catch(
        (rejection: unknown) => rejection,
      );

      expect(error).toHaveProperty("retryAfterSeconds", undefined);
    },
  );

  it.each([400, 401, 403, 404, 505])(
    "keeps HTTP %i permanent",
    async (statusCode) => {
      const error = await rejectedUpgrade(statusCode).catch(
        (rejection: unknown) => rejection,
      );
      expect(error).toBeInstanceOf(LangSmithSandboxConnectionError);
      expect(error).not.toBeInstanceOf(
        LangSmithSandboxRetryableConnectionError,
      );
    },
  );
});
