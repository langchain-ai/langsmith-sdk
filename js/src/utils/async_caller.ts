import pRetry from "../utils/p-retry/index.js";
import PQueueMod from "p-queue";
import { _getFetchImplementation } from "../singletons/fetch.js";

const STATUS_RETRYABLE = [
  408, // Request Timeout
  425, // Too Early
  429, // Too Many Requests
  500, // Internal Server Error
  502, // Bad Gateway
  503, // Service Unavailable
  504, // Gateway Timeout
];

type ResponseCallback = (response?: Response) => Promise<boolean>;

export interface AsyncCallerParams {
  /**
   * The maximum number of concurrent calls that can be made.
   * Defaults to `Infinity`, which means no limit.
   */
  maxConcurrency?: number;
  /**
   * The maximum number of retries that can be made for a single call,
   * with an exponential backoff between each attempt. Defaults to 6.
   */
  maxRetries?: number;
  /**
   * The maximum size of the queue buffer in bytes. When the queue reaches this size,
   * new calls will be dropped instead of queued.
   * If not specified, no limit is enforced.
   */
  maxQueueSizeBytes?: number;

  onFailedResponseHook?: ResponseCallback;

  debug?: boolean;
}

export interface AsyncCallerCallOptions {
  signal?: AbortSignal;
  /**
   * The size of this call in bytes, used for queue size tracking.
   * If not provided, size tracking is skipped for this call.
   */
  sizeBytes?: number;
}

/**
 * A class that can be used to make async calls with concurrency and retry logic.
 *
 * This is useful for making calls to any kind of "expensive" external resource,
 * be it because it's rate-limited, subject to network issues, etc.
 *
 * Concurrent calls are limited by the `maxConcurrency` parameter, which defaults
 * to `Infinity`. This means that by default, all calls will be made in parallel.
 *
 * Retries are limited by the `maxRetries` parameter, which defaults to 6. This
 * means that by default, each call will be retried up to 6 times, with an
 * exponential backoff between each attempt.
 */
export class AsyncCaller {
  protected maxConcurrency: AsyncCallerParams["maxConcurrency"];

  protected maxRetries: AsyncCallerParams["maxRetries"];

  protected maxQueueSizeBytes: AsyncCallerParams["maxQueueSizeBytes"];

  queue: typeof import("p-queue")["default"]["prototype"];

  private onFailedResponseHook?: ResponseCallback;

  private queueSizeBytes = 0;

  constructor(params: AsyncCallerParams) {
    this.maxConcurrency = params.maxConcurrency ?? Infinity;
    this.maxRetries = params.maxRetries ?? 6;
    this.maxQueueSizeBytes = params.maxQueueSizeBytes;

    if ("default" in PQueueMod) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      this.queue = new (PQueueMod.default as any)({
        concurrency: this.maxConcurrency,
      });
    } else {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      this.queue = new (PQueueMod as any)({ concurrency: this.maxConcurrency });
    }
    this.onFailedResponseHook = params?.onFailedResponseHook;
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  call<A extends any[], T extends (...args: A) => Promise<any>>(
    callable: T,
    ...args: Parameters<T>
  ): Promise<Awaited<ReturnType<T>>> {
    return this.callWithOptions({}, callable, ...args);
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  callWithOptions<A extends any[], T extends (...args: A) => Promise<any>>(
    options: AsyncCallerCallOptions,
    callable: T,
    ...args: Parameters<T>
  ): Promise<Awaited<ReturnType<T>>> {
    const sizeBytes = options.sizeBytes ?? 0;

    // Check if adding this call would exceed the byte size limit
    if (
      this.maxQueueSizeBytes !== undefined &&
      sizeBytes > 0 &&
      this.queueSizeBytes + sizeBytes > this.maxQueueSizeBytes
    ) {
      return Promise.reject(
        new Error(
          `Queue size limit (${this.maxQueueSizeBytes} bytes) exceeded. ` +
            `Current queue size: ${this.queueSizeBytes} bytes, attempted addition: ${sizeBytes} bytes.`
        )
      );
    }

    // Add to queue size tracking
    if (sizeBytes > 0) {
      this.queueSizeBytes += sizeBytes;
    }

    const onFailedResponseHook = this.onFailedResponseHook;
    let promise = this.queue.add(
      () =>
        pRetry(
          () =>
            callable(...(args as Parameters<T>)).catch((error) => {
              // eslint-disable-next-line no-instanceof/no-instanceof
              if (error instanceof Error) {
                throw error;
              } else {
                throw new Error(error);
              }
            }),
          {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            async onFailedAttempt({ error }: { error: any }) {
              if (
                error.message.startsWith("Cancel") ||
                error.message.startsWith("TimeoutError") ||
                error.name === "TimeoutError" ||
                error.message.startsWith("AbortError")
              ) {
                throw error;
              }
              if (error?.code === "ECONNABORTED") {
                throw error;
              }
              const response: Response | undefined = error?.response;
              if (onFailedResponseHook) {
                const handled = await onFailedResponseHook(response);
                if (handled) {
                  return;
                }
              }
              const status = response?.status ?? error?.status;
              if (status) {
                if (!STATUS_RETRYABLE.includes(+status)) {
                  throw error;
                }
              }
            },
            retries: this.maxRetries,
            randomize: true,
          }
        ),
      { throwOnTimeout: true }
    );

    // Decrement queue size when the call completes (success or failure)
    if (sizeBytes > 0) {
      promise = promise.finally(() => {
        this.queueSizeBytes -= sizeBytes;
      });
    }

    // Handle signal cancellation
    if (options.signal) {
      return Promise.race([
        promise,
        new Promise<never>((_, reject) => {
          options.signal?.addEventListener("abort", () => {
            reject(new Error("AbortError"));
          });
        }),
      ]);
    }

    return promise;
  }
}
