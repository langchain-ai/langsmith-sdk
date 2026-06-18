// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { LangsmithError } from './error.js';
import { FinalRequestOptions } from '../internal/request-options.js';
import { defaultParseResponse } from '../internal/parse.js';
import { type Langsmith } from '../client.js';
import { APIPromise } from './api-promise.js';
import { type APIResponseProps } from '../internal/parse.js';
import { maybeObj } from '../internal/utils/values.js';

export type PageRequestOptions = Pick<FinalRequestOptions, 'query' | 'headers' | 'body' | 'path' | 'method'>;

export abstract class AbstractPage<Item> implements AsyncIterable<Item> {
  #client: Langsmith;
  protected options: FinalRequestOptions;

  protected response: Response;
  protected body: unknown;

  constructor(client: Langsmith, response: Response, body: unknown, options: FinalRequestOptions) {
    this.#client = client;
    this.options = options;
    this.response = response;
    this.body = body;
  }

  abstract nextPageRequestOptions(): PageRequestOptions | null;

  abstract getPaginatedItems(): Item[];

  hasNextPage(): boolean {
    const items = this.getPaginatedItems();
    if (!items.length) return false;
    return this.nextPageRequestOptions() != null;
  }

  async getNextPage(): Promise<this> {
    const nextOptions = this.nextPageRequestOptions();
    if (!nextOptions) {
      throw new LangsmithError(
        'No next page expected; please check `.hasNextPage()` before calling `.getNextPage()`.',
      );
    }

    return await this.#client.requestAPIList(this.constructor as any, nextOptions);
  }

  async *iterPages(): AsyncGenerator<this> {
    let page: this = this;
    yield page;
    while (page.hasNextPage()) {
      page = await page.getNextPage();
      yield page;
    }
  }

  async *[Symbol.asyncIterator](): AsyncGenerator<Item> {
    for await (const page of this.iterPages()) {
      for (const item of page.getPaginatedItems()) {
        yield item;
      }
    }
  }
}

/**
 * This subclass of Promise will resolve to an instantiated Page once the request completes.
 *
 * It also implements AsyncIterable to allow auto-paginating iteration on an unawaited list call, eg:
 *
 *    for await (const item of client.items.list()) {
 *      console.log(item)
 *    }
 */
export class PagePromise<
    PageClass extends AbstractPage<Item>,
    Item = ReturnType<PageClass['getPaginatedItems']>[number],
  >
  extends APIPromise<PageClass>
  implements AsyncIterable<Item>
{
  constructor(
    client: Langsmith,
    request: Promise<APIResponseProps>,
    Page: new (...args: ConstructorParameters<typeof AbstractPage>) => PageClass,
  ) {
    super(
      client,
      request,
      async (client, props) =>
        new Page(client, props.response, await defaultParseResponse(client, props), props.options),
    );
  }

  /**
   * Allow auto-paginating iteration on an unawaited list call, eg:
   *
   *    for await (const item of client.items.list()) {
   *      console.log(item)
   *    }
   */
  async *[Symbol.asyncIterator](): AsyncGenerator<Item> {
    const page = await this;
    for await (const item of page) {
      yield item;
    }
  }
}

export type OffsetPaginationTopLevelArrayResponse<Item> = Item[];

export interface OffsetPaginationTopLevelArrayParams {
  offset?: number;

  limit?: number;
}

export class OffsetPaginationTopLevelArray<Item> extends AbstractPage<Item> {
  items: Array<Item>;

  constructor(
    client: Langsmith,
    response: Response,
    body: OffsetPaginationTopLevelArrayResponse<Item>,
    options: FinalRequestOptions,
  ) {
    super(client, response, body, options);

    this.items = body || [];
  }

  getPaginatedItems(): Item[] {
    return this.items ?? [];
  }

  nextPageRequestOptions(): PageRequestOptions | null {
    const offset = (this.options.query as OffsetPaginationTopLevelArrayParams).offset ?? 0;
    const length = this.getPaginatedItems().length;
    const currentCount = offset + length;

    return {
      ...this.options,
      query: {
        ...maybeObj(this.options.query),
        offset: currentCount,
      },
    };
  }
}

export interface OffsetPaginationReposResponse<Item> {
  repos: Array<Item>;

  total: number;
}

export interface OffsetPaginationReposParams {
  offset?: number;

  limit?: number;
}

export class OffsetPaginationRepos<Item>
  extends AbstractPage<Item>
  implements OffsetPaginationReposResponse<Item>
{
  repos: Array<Item>;

  total: number;

  constructor(
    client: Langsmith,
    response: Response,
    body: OffsetPaginationReposResponse<Item>,
    options: FinalRequestOptions,
  ) {
    super(client, response, body, options);

    this.repos = body.repos || [];
    this.total = body.total || 0;
  }

  getPaginatedItems(): Item[] {
    return this.repos ?? [];
  }

  nextPageRequestOptions(): PageRequestOptions | null {
    const offset = (this.options.query as OffsetPaginationReposParams).offset ?? 0;
    const length = this.getPaginatedItems().length;
    const currentCount = offset + length;

    return {
      ...this.options,
      query: {
        ...maybeObj(this.options.query),
        offset: currentCount,
      },
    };
  }
}

export interface OffsetPaginationCommitsResponse<Item> {
  commits: Array<Item>;

  total: number;
}

export interface OffsetPaginationCommitsParams {
  offset?: number;

  limit?: number;
}

export class OffsetPaginationCommits<Item>
  extends AbstractPage<Item>
  implements OffsetPaginationCommitsResponse<Item>
{
  commits: Array<Item>;

  total: number;

  constructor(
    client: Langsmith,
    response: Response,
    body: OffsetPaginationCommitsResponse<Item>,
    options: FinalRequestOptions,
  ) {
    super(client, response, body, options);

    this.commits = body.commits || [];
    this.total = body.total || 0;
  }

  getPaginatedItems(): Item[] {
    return this.commits ?? [];
  }

  nextPageRequestOptions(): PageRequestOptions | null {
    const offset = (this.options.query as OffsetPaginationCommitsParams).offset ?? 0;
    const length = this.getPaginatedItems().length;
    const currentCount = offset + length;

    return {
      ...this.options,
      query: {
        ...maybeObj(this.options.query),
        offset: currentCount,
      },
    };
  }
}

export interface OffsetPaginationOnlineEvaluatorsResponse<Item> {
  evaluators: Array<Item>;

  total: number;
}

export interface OffsetPaginationOnlineEvaluatorsParams {
  offset?: number;

  limit?: number;
}

export class OffsetPaginationOnlineEvaluators<Item>
  extends AbstractPage<Item>
  implements OffsetPaginationOnlineEvaluatorsResponse<Item>
{
  evaluators: Array<Item>;

  total: number;

  constructor(
    client: Langsmith,
    response: Response,
    body: OffsetPaginationOnlineEvaluatorsResponse<Item>,
    options: FinalRequestOptions,
  ) {
    super(client, response, body, options);

    this.evaluators = body.evaluators || [];
    this.total = body.total || 0;
  }

  getPaginatedItems(): Item[] {
    return this.evaluators ?? [];
  }

  nextPageRequestOptions(): PageRequestOptions | null {
    const offset = (this.options.query as OffsetPaginationOnlineEvaluatorsParams).offset ?? 0;
    const length = this.getPaginatedItems().length;
    const currentCount = offset + length;

    return {
      ...this.options,
      query: {
        ...maybeObj(this.options.query),
        offset: currentCount,
      },
    };
  }
}

export interface OffsetPaginationInsightsClusteringJobsResponse<Item> {
  clustering_jobs: Array<Item>;
}

export interface OffsetPaginationInsightsClusteringJobsParams {
  offset?: number;

  limit?: number;
}

export class OffsetPaginationInsightsClusteringJobs<Item>
  extends AbstractPage<Item>
  implements OffsetPaginationInsightsClusteringJobsResponse<Item>
{
  clustering_jobs: Array<Item>;

  constructor(
    client: Langsmith,
    response: Response,
    body: OffsetPaginationInsightsClusteringJobsResponse<Item>,
    options: FinalRequestOptions,
  ) {
    super(client, response, body, options);

    this.clustering_jobs = body.clustering_jobs || [];
  }

  getPaginatedItems(): Item[] {
    return this.clustering_jobs ?? [];
  }

  nextPageRequestOptions(): PageRequestOptions | null {
    const offset = (this.options.query as OffsetPaginationInsightsClusteringJobsParams).offset ?? 0;
    const length = this.getPaginatedItems().length;
    const currentCount = offset + length;

    return {
      ...this.options,
      query: {
        ...maybeObj(this.options.query),
        offset: currentCount,
      },
    };
  }
}

export interface CursorPaginationResponse<Item> {
  runs: Array<Item>;

  cursors: CursorPaginationResponse.Cursors;
}

export namespace CursorPaginationResponse {
  export interface Cursors {
    next?: string;
  }
}

export interface CursorPaginationParams {
  cursor?: string;

  limit?: number;
}

export class CursorPagination<Item> extends AbstractPage<Item> implements CursorPaginationResponse<Item> {
  runs: Array<Item>;

  cursors: CursorPaginationResponse.Cursors;

  constructor(
    client: Langsmith,
    response: Response,
    body: CursorPaginationResponse<Item>,
    options: FinalRequestOptions,
  ) {
    super(client, response, body, options);

    this.runs = body.runs || [];
    this.cursors = body.cursors || {};
  }

  getPaginatedItems(): Item[] {
    return this.runs ?? [];
  }

  nextPageRequestOptions(): PageRequestOptions | null {
    const cursor = this.cursors?.next;
    if (!cursor) {
      return null;
    }

    return {
      ...this.options,
      query: {
        ...maybeObj(this.options.query),
        cursor,
      },
    };
  }
}

export interface ItemsCursorPostPaginationResponse<Item> {
  items: Array<Item>;

  next_cursor: string;
}

export interface ItemsCursorPostPaginationParams {
  cursor?: string;

  page_size?: number;
}

export class ItemsCursorPostPagination<Item>
  extends AbstractPage<Item>
  implements ItemsCursorPostPaginationResponse<Item>
{
  items: Array<Item>;

  next_cursor: string;

  constructor(
    client: Langsmith,
    response: Response,
    body: ItemsCursorPostPaginationResponse<Item>,
    options: FinalRequestOptions,
  ) {
    super(client, response, body, options);

    this.items = body.items || [];
    this.next_cursor = body.next_cursor || '';
  }

  getPaginatedItems(): Item[] {
    return this.items ?? [];
  }

  nextPageRequestOptions(): PageRequestOptions | null {
    const cursor = this.next_cursor;
    if (!cursor) {
      return null;
    }

    return {
      ...this.options,
      body: {
        ...maybeObj(this.options.body),
        cursor,
      },
    };
  }
}

export interface ItemsCursorGetPaginationResponse<Item> {
  items: Array<Item>;

  next_cursor: string;
}

export interface ItemsCursorGetPaginationParams {
  cursor?: string;

  page_size?: number;
}

export class ItemsCursorGetPagination<Item>
  extends AbstractPage<Item>
  implements ItemsCursorGetPaginationResponse<Item>
{
  items: Array<Item>;

  next_cursor: string;

  constructor(
    client: Langsmith,
    response: Response,
    body: ItemsCursorGetPaginationResponse<Item>,
    options: FinalRequestOptions,
  ) {
    super(client, response, body, options);

    this.items = body.items || [];
    this.next_cursor = body.next_cursor || '';
  }

  getPaginatedItems(): Item[] {
    return this.items ?? [];
  }

  nextPageRequestOptions(): PageRequestOptions | null {
    const cursor = this.next_cursor;
    if (!cursor) {
      return null;
    }

    return {
      ...this.options,
      query: {
        ...maybeObj(this.options.query),
        cursor,
      },
    };
  }
}
