// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import type { RequestInit, RequestInfo, BodyInit } from './internal/builtin-types.js';
import type { HTTPMethod, PromiseOrValue, MergedRequestInit, FinalizedRequestInit } from './internal/types.js';
import { uuid4 } from './internal/utils/uuid.js';
import { validatePositiveInteger, isAbsoluteURL, safeJSON } from './internal/utils/values.js';
import { sleep } from './internal/utils/sleep.js';
export type { Logger, LogLevel } from './internal/utils/log.js';
import { castToError, isAbortError } from './internal/errors.js';
import type { APIResponseProps } from './internal/parse.js';
import { getPlatformHeaders } from './internal/detect-platform.js';
import * as Shims from './internal/shims.js';
import * as Opts from './internal/request-options.js';
import { stringifyQuery } from './internal/utils/query.js';
import { VERSION } from './version.js';
import * as Errors from './core/error.js';
import * as Pagination from './core/pagination.js';
import {
  AbstractPage,
  type CursorPaginationParams,
  CursorPaginationResponse,
  type ItemsCursorGetPaginationParams,
  ItemsCursorGetPaginationResponse,
  type ItemsCursorPostPaginationParams,
  ItemsCursorPostPaginationResponse,
  type OffsetPaginationCommitsParams,
  OffsetPaginationCommitsResponse,
  type OffsetPaginationInsightsClusteringJobsParams,
  OffsetPaginationInsightsClusteringJobsResponse,
  type OffsetPaginationIssuesParams,
  OffsetPaginationIssuesResponse,
  type OffsetPaginationOnlineEvaluatorsParams,
  OffsetPaginationOnlineEvaluatorsResponse,
  type OffsetPaginationReposParams,
  OffsetPaginationReposResponse,
  type OffsetPaginationTopLevelArrayParams,
  OffsetPaginationTopLevelArrayResponse,
} from './core/pagination.js';
import * as Uploads from './core/uploads.js';
import * as API from './resources/index.js';
import { APIPromise } from './core/api-promise.js';
import { Info, InfoListResponse } from './resources/info.js';
import { Issue, IssueListParams, Issues, IssuesOffsetPaginationIssues } from './resources/issues.js';
import {
  BulkDeleteEvaluatorFailedItem,
  BulkDeleteEvaluatorsResponse,
  CreateOnlineCodeEvaluatorRequest,
  CreateOnlineEvaluatorRequest,
  CreateOnlineEvaluatorResponse,
  CreateOnlineLlmEvaluatorRequest,
  GetOnlineEvaluatorSpendResponse,
  OnlineCodeEvaluator,
  OnlineEvaluator,
  OnlineEvaluatorBulkDeleteParams,
  OnlineEvaluatorCreateParams,
  OnlineEvaluatorDeleteParams,
  OnlineEvaluatorListParams,
  OnlineEvaluatorRunRule,
  OnlineEvaluatorSpendDay,
  OnlineEvaluatorSpendGroup,
  OnlineEvaluatorSpendParams,
  OnlineEvaluatorType,
  OnlineEvaluatorUpdateParams,
  OnlineEvaluators,
  OnlineEvaluatorsOffsetPaginationOnlineEvaluators,
  OnlineLlmEvaluator,
  OnlineSpendLimit,
  UpdateOnlineCodeEvaluatorRequest,
  UpdateOnlineEvaluatorRequest,
  UpdateOnlineEvaluatorResponse,
  UpdateOnlineLlmEvaluatorRequest,
} from './resources/online-evaluators.js';
import {
  ResponseBodyForRunsGenerateQuery,
  Run,
  RunIngest,
  RunQueryParams,
  RunQueryV2Params,
  RunRetrieveParams,
  RunRetrieveV2Params,
  RunSchema,
  RunStatsQueryParams,
  RunTypeEnum,
  Runs,
  RunsFilterDataSourceTypeEnum,
  RunsItemsCursorPostPagination,
} from './resources/runs.js';
import {
  DataType,
  Dataset,
  DatasetTransformation,
  DatasetVersion,
  Datasets,
  FeedbackCreateCoreSchema,
  Missing,
  SortByDatasetColumn,
} from './resources/datasets/datasets.js';
import {
  SandboxListResponse,
  SandboxResponse,
  SandboxStatusResponse,
  Sandboxes,
  ServiceURLResponse,
  SnapshotListResponse,
  SnapshotResponse,
} from './resources/sandboxes/sandboxes.js';
import { type Fetch } from './internal/builtin-types.js';
import { HeadersLike, NullableHeaders, buildHeaders } from './internal/headers.js';
import { FinalRequestOptions, RequestOptions } from './internal/request-options.js';
import { readEnv } from './internal/utils/env.js';
import {
  type LogLevel,
  type Logger,
  formatRequestDetails,
  loggerFor,
  parseLogLevel,
} from './internal/utils/log.js';
import { isEmptyObj } from './internal/utils/values.js';

export interface ClientOptions {
  /**
   * Defaults to process.env['LANGSMITH_API_KEY'].
   */
  apiKey?: string | null | undefined;

  /**
   * Defaults to process.env['LANGSMITH_TENANT_ID'].
   */
  tenantID?: string | null | undefined;

  /**
   * Override the default base URL for the API, e.g., "https://api.example.com/v2/"
   *
   * Defaults to process.env['LANGCHAIN_BASE_URL'].
   */
  baseURL?: string | null | undefined;

  /**
   * The maximum amount of time (in milliseconds) that the client should wait for a response
   * from the server before timing out a single request.
   *
   * Note that request timeouts are retried by default, so in a worst-case scenario you may wait
   * much longer than this timeout before the promise succeeds or fails.
   *
   * @unit milliseconds
   */
  timeout?: number | undefined;
  /**
   * Additional `RequestInit` options to be passed to `fetch` calls.
   * Properties will be overridden by per-request `fetchOptions`.
   */
  fetchOptions?: MergedRequestInit | undefined;

  /**
   * Specify a custom `fetch` function implementation.
   *
   * If not provided, we expect that `fetch` is defined globally.
   */
  fetch?: Fetch | undefined;

  /**
   * The maximum number of times that the client will retry a request in case of a
   * temporary failure, like a network error or a 5XX error from the server.
   *
   * @default 2
   */
  maxRetries?: number | undefined;

  /**
   * Default headers to include with every request to the API.
   *
   * These can be removed in individual requests by explicitly setting the
   * header to `null` in request options.
   */
  defaultHeaders?: HeadersLike | undefined;

  /**
   * Default query parameters to include with every request to the API.
   *
   * These can be removed in individual requests by explicitly setting the
   * param to `undefined` in request options.
   */
  defaultQuery?: Record<string, string | undefined> | undefined;

  /**
   * Set the log level.
   *
   * Defaults to process.env['LANGCHAIN_LOG'] or 'warn' if it isn't set.
   */
  logLevel?: LogLevel | undefined;

  /**
   * Set the logger.
   *
   * Defaults to globalThis.console.
   */
  logger?: Logger | undefined;
}

/**
 * API Client for interfacing with the LangChain API.
 */
export class Langsmith {
  apiKey: string | null;
  tenantID: string | null;

  baseURL: string;
  maxRetries: number;
  timeout: number;
  logger: Logger;
  logLevel: LogLevel | undefined;
  fetchOptions: MergedRequestInit | undefined;

  private fetch: Fetch;
  #encoder: Opts.RequestEncoder;
  protected idempotencyHeader?: string;
  private _options: ClientOptions;

  /**
   * API Client for interfacing with the LangChain API.
   *
   * @param {string | null | undefined} [opts.apiKey=process.env['LANGSMITH_API_KEY'] ?? null]
   * @param {string | null | undefined} [opts.tenantID=process.env['LANGSMITH_TENANT_ID'] ?? null]
   * @param {string} [opts.baseURL=process.env['LANGCHAIN_BASE_URL'] ?? https://api.smith.langchain.com/] - Override the default base URL for the API.
   * @param {number} [opts.timeout=1.5 minutes] - The maximum amount of time (in milliseconds) the client will wait for a response before timing out.
   * @param {MergedRequestInit} [opts.fetchOptions] - Additional `RequestInit` options to be passed to `fetch` calls.
   * @param {Fetch} [opts.fetch] - Specify a custom `fetch` function implementation.
   * @param {number} [opts.maxRetries=2] - The maximum number of times the client will retry a request.
   * @param {HeadersLike} opts.defaultHeaders - Default headers to include with every request to the API.
   * @param {Record<string, string | undefined>} opts.defaultQuery - Default query parameters to include with every request to the API.
   */
  constructor({
    baseURL = readEnv('LANGCHAIN_BASE_URL'),
    apiKey = readEnv('LANGSMITH_API_KEY') ?? null,
    tenantID = readEnv('LANGSMITH_TENANT_ID') ?? null,
    ...opts
  }: ClientOptions = {}) {
    const options: ClientOptions = {
      apiKey,
      tenantID,
      ...opts,
      baseURL: baseURL || `https://api.smith.langchain.com/`,
    };

    this.baseURL = options.baseURL!;
    this.timeout = options.timeout ?? Langsmith.DEFAULT_TIMEOUT /* 1.5 minutes */;
    this.logger = options.logger ?? console;
    const defaultLogLevel = 'warn';
    // Set default logLevel early so that we can log a warning in parseLogLevel.
    this.logLevel = defaultLogLevel;
    this.logLevel =
      parseLogLevel(options.logLevel, 'ClientOptions.logLevel', this) ??
      parseLogLevel(readEnv('LANGCHAIN_LOG'), "process.env['LANGCHAIN_LOG']", this) ??
      defaultLogLevel;
    this.fetchOptions = options.fetchOptions;
    this.maxRetries = options.maxRetries ?? 2;
    this.fetch = options.fetch ?? Shims.getDefaultFetch();
    this.#encoder = Opts.FallbackEncoder;

    const customHeadersEnv = readEnv('LANGCHAIN_CUSTOM_HEADERS');
    if (customHeadersEnv) {
      const parsed: Record<string, string> = {};
      for (const line of customHeadersEnv.split('\n')) {
        const colon = line.indexOf(':');
        if (colon >= 0) {
          parsed[line.substring(0, colon).trim()] = line.substring(colon + 1).trim();
        }
      }
      options.defaultHeaders = { ...parsed, ...options.defaultHeaders };
    }

    this._options = options;

    this.apiKey = apiKey;
    this.tenantID = tenantID;
  }

  /**
   * Create a new client instance re-using the same options given to the current client with optional overriding.
   */
  withOptions(options: Partial<ClientOptions>): this {
    const client = new (this.constructor as any as new (props: ClientOptions) => typeof this)({
      ...this._options,
      baseURL: this.baseURL,
      maxRetries: this.maxRetries,
      timeout: this.timeout,
      logger: this.logger,
      logLevel: this.logLevel,
      fetch: this.fetch,
      fetchOptions: this.fetchOptions,
      apiKey: this.apiKey,
      tenantID: this.tenantID,
      ...options,
    });
    return client;
  }

  /**
   * Check whether the base URL is set to its default.
   */
  #baseURLOverridden(): boolean {
    return this.baseURL !== 'https://api.smith.langchain.com/';
  }

  protected defaultQuery(): Record<string, string | undefined> | undefined {
    return this._options.defaultQuery;
  }

  protected validateHeaders({ values, nulls }: NullableHeaders) {
    if (this.apiKey && values.get('x-api-key')) {
      return;
    }
    if (nulls.has('x-api-key')) {
      return;
    }

    if (this.tenantID && values.get('x-tenant-id')) {
      return;
    }
    if (nulls.has('x-tenant-id')) {
      return;
    }

    throw new Error(
      'Could not resolve authentication method. Expected either apiKey or tenantID to be set. Or for one of the "X-API-Key" or "X-Tenant-Id" headers to be explicitly omitted',
    );
  }

  protected async authHeaders(opts: FinalRequestOptions): Promise<NullableHeaders | undefined> {
    return buildHeaders([await this.apiKeyAuth(opts), await this.tenantIDAuth(opts)]);
  }

  protected async apiKeyAuth(opts: FinalRequestOptions): Promise<NullableHeaders | undefined> {
    if (this.apiKey == null) {
      return undefined;
    }
    return buildHeaders([{ 'X-API-Key': this.apiKey }]);
  }

  protected async tenantIDAuth(opts: FinalRequestOptions): Promise<NullableHeaders | undefined> {
    if (this.tenantID == null) {
      return undefined;
    }
    return buildHeaders([{ 'X-Tenant-Id': this.tenantID }]);
  }

  protected stringifyQuery(query: object | Record<string, unknown>): string {
    return stringifyQuery(query);
  }

  private getUserAgent(): string {
    return `${this.constructor.name}/JS ${VERSION}`;
  }

  protected defaultIdempotencyKey(): string {
    return `stainless-node-retry-${uuid4()}`;
  }

  protected makeStatusError(
    status: number,
    error: Object,
    message: string | undefined,
    headers: Headers,
  ): Errors.APIError {
    return Errors.APIError.generate(status, error, message, headers);
  }

  buildURL(
    path: string,
    query: Record<string, unknown> | null | undefined,
    defaultBaseURL?: string | undefined,
  ): string {
    const baseURL = (!this.#baseURLOverridden() && defaultBaseURL) || this.baseURL;
    const url =
      isAbsoluteURL(path) ?
        new URL(path)
      : new URL(baseURL + (baseURL.endsWith('/') && path.startsWith('/') ? path.slice(1) : path));

    const defaultQuery = this.defaultQuery();
    const pathQuery = Object.fromEntries(url.searchParams);
    if (!isEmptyObj(defaultQuery) || !isEmptyObj(pathQuery)) {
      query = { ...pathQuery, ...defaultQuery, ...query };
    }

    if (typeof query === 'object' && query && !Array.isArray(query)) {
      url.search = this.stringifyQuery(query);
    }

    return url.toString();
  }

  /**
   * Used as a callback for mutating the given `FinalRequestOptions` object.
   */
  protected async prepareOptions(options: FinalRequestOptions): Promise<void> {}

  /**
   * Used as a callback for mutating the given `RequestInit` object.
   *
   * This is useful for cases where you want to add certain headers based off of
   * the request properties, e.g. `method` or `url`.
   */
  protected async prepareRequest(
    request: RequestInit,
    { url, options }: { url: string; options: FinalRequestOptions },
  ): Promise<void> {}

  get<Rsp>(path: string, opts?: PromiseOrValue<RequestOptions>): APIPromise<Rsp> {
    return this.methodRequest('get', path, opts);
  }

  post<Rsp>(path: string, opts?: PromiseOrValue<RequestOptions>): APIPromise<Rsp> {
    return this.methodRequest('post', path, opts);
  }

  patch<Rsp>(path: string, opts?: PromiseOrValue<RequestOptions>): APIPromise<Rsp> {
    return this.methodRequest('patch', path, opts);
  }

  put<Rsp>(path: string, opts?: PromiseOrValue<RequestOptions>): APIPromise<Rsp> {
    return this.methodRequest('put', path, opts);
  }

  delete<Rsp>(path: string, opts?: PromiseOrValue<RequestOptions>): APIPromise<Rsp> {
    return this.methodRequest('delete', path, opts);
  }

  private methodRequest<Rsp>(
    method: HTTPMethod,
    path: string,
    opts?: PromiseOrValue<RequestOptions>,
  ): APIPromise<Rsp> {
    return this.request(
      Promise.resolve(opts).then((opts) => {
        return { method, path, ...opts };
      }),
    );
  }

  request<Rsp>(
    options: PromiseOrValue<FinalRequestOptions>,
    remainingRetries: number | null = null,
  ): APIPromise<Rsp> {
    return new APIPromise(this, this.makeRequest(options, remainingRetries, undefined));
  }

  private async makeRequest(
    optionsInput: PromiseOrValue<FinalRequestOptions>,
    retriesRemaining: number | null,
    retryOfRequestLogID: string | undefined,
  ): Promise<APIResponseProps> {
    const options = await optionsInput;
    const maxRetries = options.maxRetries ?? this.maxRetries;
    if (retriesRemaining == null) {
      retriesRemaining = maxRetries;
    }

    await this.prepareOptions(options);

    const { req, url, timeout } = await this.buildRequest(options, {
      retryCount: maxRetries - retriesRemaining,
    });

    await this.prepareRequest(req, { url, options });

    /** Not an API request ID, just for correlating local log entries. */
    const requestLogID = 'log_' + ((Math.random() * (1 << 24)) | 0).toString(16).padStart(6, '0');
    const retryLogStr = retryOfRequestLogID === undefined ? '' : `, retryOf: ${retryOfRequestLogID}`;
    const startTime = Date.now();

    loggerFor(this).debug(
      `[${requestLogID}] sending request`,
      formatRequestDetails({
        retryOfRequestLogID,
        method: options.method,
        url,
        options,
        headers: req.headers,
      }),
    );

    if (options.signal?.aborted) {
      throw new Errors.APIUserAbortError();
    }

    const controller = new AbortController();
    const response = await this.fetchWithTimeout(url, req, timeout, controller).catch(castToError);
    const headersTime = Date.now();

    if (response instanceof globalThis.Error) {
      const retryMessage = `retrying, ${retriesRemaining} attempts remaining`;
      if (options.signal?.aborted) {
        throw new Errors.APIUserAbortError();
      }
      // detect native connection timeout errors
      // deno throws "TypeError: error sending request for url (https://example/): client error (Connect): tcp connect error: Operation timed out (os error 60): Operation timed out (os error 60)"
      // undici throws "TypeError: fetch failed" with cause "ConnectTimeoutError: Connect Timeout Error (attempted address: example:443, timeout: 1ms)"
      // others do not provide enough information to distinguish timeouts from other connection errors
      const isTimeout =
        isAbortError(response) ||
        /timed? ?out/i.test(String(response) + ('cause' in response ? String(response.cause) : ''));
      if (retriesRemaining) {
        loggerFor(this).info(
          `[${requestLogID}] connection ${isTimeout ? 'timed out' : 'failed'} - ${retryMessage}`,
        );
        loggerFor(this).debug(
          `[${requestLogID}] connection ${isTimeout ? 'timed out' : 'failed'} (${retryMessage})`,
          formatRequestDetails({
            retryOfRequestLogID,
            url,
            durationMs: headersTime - startTime,
            message: response.message,
          }),
        );
        return this.retryRequest(options, retriesRemaining, retryOfRequestLogID ?? requestLogID);
      }
      loggerFor(this).info(
        `[${requestLogID}] connection ${isTimeout ? 'timed out' : 'failed'} - error; no more retries left`,
      );
      loggerFor(this).debug(
        `[${requestLogID}] connection ${isTimeout ? 'timed out' : 'failed'} (error; no more retries left)`,
        formatRequestDetails({
          retryOfRequestLogID,
          url,
          durationMs: headersTime - startTime,
          message: response.message,
        }),
      );
      if (isTimeout) {
        throw new Errors.APIConnectionTimeoutError();
      }
      throw new Errors.APIConnectionError({ cause: response });
    }

    const responseInfo = `[${requestLogID}${retryLogStr}] ${req.method} ${url} ${
      response.ok ? 'succeeded' : 'failed'
    } with status ${response.status} in ${headersTime - startTime}ms`;

    if (!response.ok) {
      const shouldRetry = await this.shouldRetry(response);
      if (retriesRemaining && shouldRetry) {
        const retryMessage = `retrying, ${retriesRemaining} attempts remaining`;

        // We don't need the body of this response.
        await Shims.CancelReadableStream(response.body);
        loggerFor(this).info(`${responseInfo} - ${retryMessage}`);
        loggerFor(this).debug(
          `[${requestLogID}] response error (${retryMessage})`,
          formatRequestDetails({
            retryOfRequestLogID,
            url: response.url,
            status: response.status,
            headers: response.headers,
            durationMs: headersTime - startTime,
          }),
        );
        return this.retryRequest(
          options,
          retriesRemaining,
          retryOfRequestLogID ?? requestLogID,
          response.headers,
        );
      }

      const retryMessage = shouldRetry ? `error; no more retries left` : `error; not retryable`;

      loggerFor(this).info(`${responseInfo} - ${retryMessage}`);

      const errText = await response.text().catch((err: any) => castToError(err).message);
      const errJSON = safeJSON(errText) as any;
      const errMessage = errJSON ? undefined : errText;

      loggerFor(this).debug(
        `[${requestLogID}] response error (${retryMessage})`,
        formatRequestDetails({
          retryOfRequestLogID,
          url: response.url,
          status: response.status,
          headers: response.headers,
          message: errMessage,
          durationMs: Date.now() - startTime,
        }),
      );

      const err = this.makeStatusError(response.status, errJSON, errMessage, response.headers);
      throw err;
    }

    loggerFor(this).info(responseInfo);
    loggerFor(this).debug(
      `[${requestLogID}] response start`,
      formatRequestDetails({
        retryOfRequestLogID,
        url: response.url,
        status: response.status,
        headers: response.headers,
        durationMs: headersTime - startTime,
      }),
    );

    return { response, options, controller, requestLogID, retryOfRequestLogID, startTime };
  }

  getAPIList<Item, PageClass extends Pagination.AbstractPage<Item> = Pagination.AbstractPage<Item>>(
    path: string,
    Page: new (...args: any[]) => PageClass,
    opts?: PromiseOrValue<RequestOptions>,
  ): Pagination.PagePromise<PageClass, Item> {
    return this.requestAPIList(
      Page,
      opts && 'then' in opts ?
        opts.then((opts) => ({ method: 'get', path, ...opts }))
      : { method: 'get', path, ...opts },
    );
  }

  requestAPIList<
    Item = unknown,
    PageClass extends Pagination.AbstractPage<Item> = Pagination.AbstractPage<Item>,
  >(
    Page: new (...args: ConstructorParameters<typeof Pagination.AbstractPage>) => PageClass,
    options: PromiseOrValue<FinalRequestOptions>,
  ): Pagination.PagePromise<PageClass, Item> {
    const request = this.makeRequest(options, null, undefined);
    return new Pagination.PagePromise<PageClass, Item>(this as any as Langsmith, request, Page);
  }

  async fetchWithTimeout(
    url: RequestInfo,
    init: RequestInit | undefined,
    ms: number,
    controller: AbortController,
  ): Promise<Response> {
    const { signal, method, ...options } = init || {};
    const abort = this._makeAbort(controller);
    if (signal) signal.addEventListener('abort', abort, { once: true });

    const timeout = setTimeout(abort, ms);

    const isReadableBody =
      ((globalThis as any).ReadableStream && options.body instanceof (globalThis as any).ReadableStream) ||
      (typeof options.body === 'object' && options.body !== null && Symbol.asyncIterator in options.body);

    const fetchOptions: RequestInit = {
      signal: controller.signal as any,
      ...(isReadableBody ? { duplex: 'half' } : {}),
      method: 'GET',
      ...options,
    };
    if (method) {
      // Custom methods like 'patch' need to be uppercased
      // See https://github.com/nodejs/undici/issues/2294
      fetchOptions.method = method.toUpperCase();
    }

    try {
      // use undefined this binding; fetch errors if bound to something else in browser/cloudflare
      return await this.fetch.call(undefined, url, fetchOptions);
    } finally {
      clearTimeout(timeout);
    }
  }

  private async shouldRetry(response: Response): Promise<boolean> {
    // Note this is not a standard header.
    const shouldRetryHeader = response.headers.get('x-should-retry');

    // If the server explicitly says whether or not to retry, obey.
    if (shouldRetryHeader === 'true') return true;
    if (shouldRetryHeader === 'false') return false;

    // Retry on request timeouts.
    if (response.status === 408) return true;

    // Retry on lock timeouts.
    if (response.status === 409) return true;

    // Retry on rate limits.
    if (response.status === 429) return true;

    // Retry internal errors.
    if (response.status >= 500) return true;

    return false;
  }

  private async retryRequest(
    options: FinalRequestOptions,
    retriesRemaining: number,
    requestLogID: string,
    responseHeaders?: Headers | undefined,
  ): Promise<APIResponseProps> {
    let timeoutMillis: number | undefined;

    // Note the `retry-after-ms` header may not be standard, but is a good idea and we'd like proactive support for it.
    const retryAfterMillisHeader = responseHeaders?.get('retry-after-ms');
    if (retryAfterMillisHeader) {
      const timeoutMs = parseFloat(retryAfterMillisHeader);
      if (!Number.isNaN(timeoutMs)) {
        timeoutMillis = timeoutMs;
      }
    }

    // About the Retry-After header: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Retry-After
    const retryAfterHeader = responseHeaders?.get('retry-after');
    if (retryAfterHeader && !timeoutMillis) {
      const timeoutSeconds = parseFloat(retryAfterHeader);
      if (!Number.isNaN(timeoutSeconds)) {
        timeoutMillis = timeoutSeconds * 1000;
      } else {
        timeoutMillis = Date.parse(retryAfterHeader) - Date.now();
      }
    }

    // If the API asks us to wait a certain amount of time, just do what it
    // says, but otherwise calculate a default
    if (timeoutMillis === undefined) {
      const maxRetries = options.maxRetries ?? this.maxRetries;
      timeoutMillis = this.calculateDefaultRetryTimeoutMillis(retriesRemaining, maxRetries);
    }
    await sleep(timeoutMillis);

    return this.makeRequest(options, retriesRemaining - 1, requestLogID);
  }

  private calculateDefaultRetryTimeoutMillis(retriesRemaining: number, maxRetries: number): number {
    const initialRetryDelay = 0.5;
    const maxRetryDelay = 16.0;

    const numRetries = maxRetries - retriesRemaining;

    // Apply exponential backoff, but not more than the max.
    const sleepSeconds = Math.min(initialRetryDelay * Math.pow(2, numRetries), maxRetryDelay);

    // Apply some jitter, take up to at most 25 percent of the retry time.
    const jitter = 1 - Math.random() * 0.25;

    return sleepSeconds * jitter * 1000;
  }

  async buildRequest(
    inputOptions: FinalRequestOptions,
    { retryCount = 0 }: { retryCount?: number } = {},
  ): Promise<{ req: FinalizedRequestInit; url: string; timeout: number }> {
    const options = { ...inputOptions };
    const { method, path, query, defaultBaseURL } = options;

    const url = this.buildURL(path!, query as Record<string, unknown>, defaultBaseURL);
    if ('timeout' in options) validatePositiveInteger('timeout', options.timeout);
    options.timeout = options.timeout ?? this.timeout;
    const { bodyHeaders, body } = this.buildBody({ options });
    const reqHeaders = await this.buildHeaders({ options: inputOptions, method, bodyHeaders, retryCount });

    const req: FinalizedRequestInit = {
      method,
      headers: reqHeaders,
      ...(options.signal && { signal: options.signal }),
      ...((globalThis as any).ReadableStream &&
        body instanceof (globalThis as any).ReadableStream && { duplex: 'half' }),
      ...(body && { body }),
      ...((this.fetchOptions as any) ?? {}),
      ...((options.fetchOptions as any) ?? {}),
    };

    return { req, url, timeout: options.timeout };
  }

  private async buildHeaders({
    options,
    method,
    bodyHeaders,
    retryCount,
  }: {
    options: FinalRequestOptions;
    method: HTTPMethod;
    bodyHeaders: HeadersLike;
    retryCount: number;
  }): Promise<Headers> {
    let idempotencyHeaders: HeadersLike = {};
    if (this.idempotencyHeader && method !== 'get') {
      if (!options.idempotencyKey) options.idempotencyKey = this.defaultIdempotencyKey();
      idempotencyHeaders[this.idempotencyHeader] = options.idempotencyKey;
    }

    const headers = buildHeaders([
      idempotencyHeaders,
      {
        Accept: 'application/json',
        'User-Agent': this.getUserAgent(),
        'X-Stainless-Retry-Count': String(retryCount),
        ...(options.timeout ? { 'X-Stainless-Timeout': String(Math.trunc(options.timeout / 1000)) } : {}),
        ...getPlatformHeaders(),
      },
      await this.authHeaders(options),
      this._options.defaultHeaders,
      bodyHeaders,
      options.headers,
    ]);

    this.validateHeaders(headers);

    return headers.values;
  }

  private _makeAbort(controller: AbortController) {
    // note: we can't just inline this method inside `fetchWithTimeout()` because then the closure
    //       would capture all request options, and cause a memory leak.
    return () => controller.abort();
  }

  private buildBody({ options: { body, headers: rawHeaders } }: { options: FinalRequestOptions }): {
    bodyHeaders: HeadersLike;
    body: BodyInit | undefined;
  } {
    if (!body) {
      return { bodyHeaders: undefined, body: undefined };
    }
    const headers = buildHeaders([rawHeaders]);
    if (
      // Pass raw type verbatim
      ArrayBuffer.isView(body) ||
      body instanceof ArrayBuffer ||
      body instanceof DataView ||
      (typeof body === 'string' &&
        // Preserve legacy string encoding behavior for now
        headers.values.has('content-type')) ||
      // `Blob` is superset of `File`
      ((globalThis as any).Blob && body instanceof (globalThis as any).Blob) ||
      // `FormData` -> `multipart/form-data`
      body instanceof FormData ||
      // `URLSearchParams` -> `application/x-www-form-urlencoded`
      body instanceof URLSearchParams ||
      // Send chunked stream (each chunk has own `length`)
      ((globalThis as any).ReadableStream && body instanceof (globalThis as any).ReadableStream)
    ) {
      return { bodyHeaders: undefined, body: body as BodyInit };
    } else if (
      typeof body === 'object' &&
      (Symbol.asyncIterator in body ||
        (Symbol.iterator in body && 'next' in body && typeof body.next === 'function'))
    ) {
      return { bodyHeaders: undefined, body: Shims.ReadableStreamFrom(body as AsyncIterable<Uint8Array>) };
    } else if (
      typeof body === 'object' &&
      headers.values.get('content-type') === 'application/x-www-form-urlencoded'
    ) {
      return {
        bodyHeaders: { 'content-type': 'application/x-www-form-urlencoded' },
        body: this.stringifyQuery(body),
      };
    } else {
      return this.#encoder({ body, headers });
    }
  }

  static Langsmith = this;
  static DEFAULT_TIMEOUT = 90000; // 1.5 minutes

  static LangsmithError = Errors.LangsmithError;
  static APIError = Errors.APIError;
  static APIConnectionError = Errors.APIConnectionError;
  static APIConnectionTimeoutError = Errors.APIConnectionTimeoutError;
  static APIUserAbortError = Errors.APIUserAbortError;
  static NotFoundError = Errors.NotFoundError;
  static ConflictError = Errors.ConflictError;
  static RateLimitError = Errors.RateLimitError;
  static BadRequestError = Errors.BadRequestError;
  static AuthenticationError = Errors.AuthenticationError;
  static InternalServerError = Errors.InternalServerError;
  static PermissionDeniedError = Errors.PermissionDeniedError;
  static UnprocessableEntityError = Errors.UnprocessableEntityError;

  static toFile = Uploads.toFile;

  datasets: API.Datasets = new API.Datasets(this);
  runs: API.Runs = new API.Runs(this);
  onlineEvaluators: API.OnlineEvaluators = new API.OnlineEvaluators(this);
  info: API.Info = new API.Info(this);
  issues: API.Issues = new API.Issues(this);
  sandboxes: API.Sandboxes = new API.Sandboxes(this);
}

Langsmith.Datasets = Datasets;
Langsmith.Runs = Runs;
Langsmith.OnlineEvaluators = OnlineEvaluators;
Langsmith.Info = Info;
Langsmith.Issues = Issues;
Langsmith.Sandboxes = Sandboxes;

export declare namespace Langsmith {
  export type RequestOptions = Opts.RequestOptions;

  export import OffsetPaginationTopLevelArray = Pagination.OffsetPaginationTopLevelArray;
  export {
    type OffsetPaginationTopLevelArrayParams as OffsetPaginationTopLevelArrayParams,
    type OffsetPaginationTopLevelArrayResponse as OffsetPaginationTopLevelArrayResponse,
  };

  export import OffsetPaginationIssues = Pagination.OffsetPaginationIssues;
  export {
    type OffsetPaginationIssuesParams as OffsetPaginationIssuesParams,
    type OffsetPaginationIssuesResponse as OffsetPaginationIssuesResponse,
  };

  export import OffsetPaginationRepos = Pagination.OffsetPaginationRepos;
  export {
    type OffsetPaginationReposParams as OffsetPaginationReposParams,
    type OffsetPaginationReposResponse as OffsetPaginationReposResponse,
  };

  export import OffsetPaginationCommits = Pagination.OffsetPaginationCommits;
  export {
    type OffsetPaginationCommitsParams as OffsetPaginationCommitsParams,
    type OffsetPaginationCommitsResponse as OffsetPaginationCommitsResponse,
  };

  export import OffsetPaginationOnlineEvaluators = Pagination.OffsetPaginationOnlineEvaluators;
  export {
    type OffsetPaginationOnlineEvaluatorsParams as OffsetPaginationOnlineEvaluatorsParams,
    type OffsetPaginationOnlineEvaluatorsResponse as OffsetPaginationOnlineEvaluatorsResponse,
  };

  export import OffsetPaginationInsightsClusteringJobs = Pagination.OffsetPaginationInsightsClusteringJobs;
  export {
    type OffsetPaginationInsightsClusteringJobsParams as OffsetPaginationInsightsClusteringJobsParams,
    type OffsetPaginationInsightsClusteringJobsResponse as OffsetPaginationInsightsClusteringJobsResponse,
  };

  export import CursorPagination = Pagination.CursorPagination;
  export {
    type CursorPaginationParams as CursorPaginationParams,
    type CursorPaginationResponse as CursorPaginationResponse,
  };

  export import ItemsCursorPostPagination = Pagination.ItemsCursorPostPagination;
  export {
    type ItemsCursorPostPaginationParams as ItemsCursorPostPaginationParams,
    type ItemsCursorPostPaginationResponse as ItemsCursorPostPaginationResponse,
  };

  export import ItemsCursorGetPagination = Pagination.ItemsCursorGetPagination;
  export {
    type ItemsCursorGetPaginationParams as ItemsCursorGetPaginationParams,
    type ItemsCursorGetPaginationResponse as ItemsCursorGetPaginationResponse,
  };

  export {
    Datasets as Datasets,
    type DataType as DataType,
    type Dataset as Dataset,
    type DatasetTransformation as DatasetTransformation,
    type DatasetVersion as DatasetVersion,
    type FeedbackCreateCoreSchema as FeedbackCreateCoreSchema,
    type Missing as Missing,
    type SortByDatasetColumn as SortByDatasetColumn,
  };

  export {
    Runs as Runs,
    type ResponseBodyForRunsGenerateQuery as ResponseBodyForRunsGenerateQuery,
    type Run as Run,
    type RunIngest as RunIngest,
    type RunSchema as RunSchema,
    type RunStatsQueryParams as RunStatsQueryParams,
    type RunTypeEnum as RunTypeEnum,
    type RunsFilterDataSourceTypeEnum as RunsFilterDataSourceTypeEnum,
    type RunsItemsCursorPostPagination as RunsItemsCursorPostPagination,
    type RunQueryV2Params as RunQueryV2Params,
    type RunRetrieveV2Params as RunRetrieveV2Params,
    type RunRetrieveParams as RunRetrieveParams,
    type RunQueryParams as RunQueryParams,
  };

  export {
    OnlineEvaluators as OnlineEvaluators,
    type BulkDeleteEvaluatorFailedItem as BulkDeleteEvaluatorFailedItem,
    type BulkDeleteEvaluatorsResponse as BulkDeleteEvaluatorsResponse,
    type CreateOnlineCodeEvaluatorRequest as CreateOnlineCodeEvaluatorRequest,
    type CreateOnlineEvaluatorRequest as CreateOnlineEvaluatorRequest,
    type CreateOnlineEvaluatorResponse as CreateOnlineEvaluatorResponse,
    type CreateOnlineLlmEvaluatorRequest as CreateOnlineLlmEvaluatorRequest,
    type GetOnlineEvaluatorSpendResponse as GetOnlineEvaluatorSpendResponse,
    type OnlineCodeEvaluator as OnlineCodeEvaluator,
    type OnlineEvaluator as OnlineEvaluator,
    type OnlineEvaluatorRunRule as OnlineEvaluatorRunRule,
    type OnlineEvaluatorSpendDay as OnlineEvaluatorSpendDay,
    type OnlineEvaluatorSpendGroup as OnlineEvaluatorSpendGroup,
    type OnlineEvaluatorType as OnlineEvaluatorType,
    type OnlineLlmEvaluator as OnlineLlmEvaluator,
    type OnlineSpendLimit as OnlineSpendLimit,
    type UpdateOnlineCodeEvaluatorRequest as UpdateOnlineCodeEvaluatorRequest,
    type UpdateOnlineEvaluatorRequest as UpdateOnlineEvaluatorRequest,
    type UpdateOnlineEvaluatorResponse as UpdateOnlineEvaluatorResponse,
    type UpdateOnlineLlmEvaluatorRequest as UpdateOnlineLlmEvaluatorRequest,
    type OnlineEvaluatorsOffsetPaginationOnlineEvaluators as OnlineEvaluatorsOffsetPaginationOnlineEvaluators,
    type OnlineEvaluatorCreateParams as OnlineEvaluatorCreateParams,
    type OnlineEvaluatorUpdateParams as OnlineEvaluatorUpdateParams,
    type OnlineEvaluatorListParams as OnlineEvaluatorListParams,
    type OnlineEvaluatorDeleteParams as OnlineEvaluatorDeleteParams,
    type OnlineEvaluatorBulkDeleteParams as OnlineEvaluatorBulkDeleteParams,
    type OnlineEvaluatorSpendParams as OnlineEvaluatorSpendParams,
  };

  export { Info as Info, type InfoListResponse as InfoListResponse };

  export {
    Issues as Issues,
    type Issue as Issue,
    type IssuesOffsetPaginationIssues as IssuesOffsetPaginationIssues,
    type IssueListParams as IssueListParams,
  };

  export {
    Sandboxes as Sandboxes,
    type SandboxListResponse as SandboxListResponse,
    type SandboxResponse as SandboxResponse,
    type SandboxStatusResponse as SandboxStatusResponse,
    type ServiceURLResponse as ServiceURLResponse,
    type SnapshotListResponse as SnapshotListResponse,
    type SnapshotResponse as SnapshotResponse,
  };
}
