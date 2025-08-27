import pRetry from "p-retry";
import PQueueMod from "p-queue";
import { _getFetchImplementation } from "../singletons/fetch.js";

const STATUS_RETRYABLE = [
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

  onFailedResponseHook?: ResponseCallback;

  debug?: boolean;
}

export interface AsyncCallerCallOptions {
  signal?: AbortSignal;
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

  queue: typeof import("p-queue")["default"]["prototype"];

  private onFailedResponseHook?: ResponseCallback;

  constructor(params: AsyncCallerParams) {
    this.maxConcurrency = params.maxConcurrency ?? Infinity;
    this.maxRetries = params.maxRetries ?? 6;

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
    const onFailedResponseHook = this.onFailedResponseHook;
    return this.queue.add(
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
            async onFailedAttempt(error: any) {
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
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  callWithOptions<A extends any[], T extends (...args: A) => Promise<any>>(
    options: AsyncCallerCallOptions,
    callable: T,
    ...args: Parameters<T>
  ): Promise<Awaited<ReturnType<T>>> {
    // Note this doesn't cancel the underlying request,
    // when available prefer to use the signal option of the underlying call
    if (options.signal) {
      return Promise.race([
        this.call<A, T>(callable, ...args),
        new Promise<never>((_, reject) => {
          options.signal?.addEventListener("abort", () => {
            reject(new Error("AbortError"));
          });
        }),
      ]);
    }
    return this.call<A, T>(callable, ...args);
  }
}
