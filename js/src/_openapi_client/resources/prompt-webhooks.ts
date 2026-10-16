// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../core/resource.js';
import { APIPromise } from '../core/api-promise.js';
import { buildHeaders } from '../internal/headers.js';
import { RequestOptions } from '../internal/request-options.js';
import { path } from '../internal/utils/path.js';

export class PromptWebhooks extends APIResource {
  /**
   * Create a new prompt webhook.
   *
   * LangSmith sends a POST request to the webhook URL for each event listed in
   * triggers on the prompts it matches. A workspace can have one prompt webhook
   * unless its limit was raised; creating one past the limit returns 400.
   */
  create(body: PromptWebhookCreateParams, options?: RequestOptions): APIPromise<PromptWebhook> {
    return this._client.post('/api/v1/prompt-webhooks', { body, ...options });
  }

  /**
   * Get a specific prompt webhook.
   */
  retrieve(webhookID: string, options?: RequestOptions): APIPromise<PromptWebhook> {
    return this._client.get(path`/api/v1/prompt-webhooks/${webhookID}`, options);
  }

  /**
   * Update a specific prompt webhook.
   *
   * Omitted fields keep their current values; list fields and headers that are set
   * replace the stored values.
   */
  update(
    webhookID: string,
    body: PromptWebhookUpdateParams,
    options?: RequestOptions,
  ): APIPromise<PromptWebhook> {
    return this._client.patch(path`/api/v1/prompt-webhooks/${webhookID}`, { body, ...options });
  }

  /**
   * List all prompt webhooks for the current tenant.
   */
  list(options?: RequestOptions): APIPromise<PromptWebhookListResponse> {
    return this._client.get('/api/v1/prompt-webhooks', options);
  }

  /**
   * Delete a specific prompt webhook.
   */
  delete(webhookID: string, options?: RequestOptions): APIPromise<void> {
    return this._client.delete(path`/api/v1/prompt-webhooks/${webhookID}`, {
      ...options,
      headers: buildHeaders([{ Accept: '*/*' }, options?.headers]),
    });
  }

  /**
   * Test a specific prompt webhook.
   *
   * Sends the sample payload to the webhook configuration in the request body
   * without saving it, but only if the webhook's triggers include the payload's
   * event and its prompt filters match the payload's prompt. Otherwise nothing is
   * sent. Fails if the destination does not accept the payload.
   */
  test(body: PromptWebhookTestParams, options?: RequestOptions): APIPromise<PromptWebhookTestResponse> {
    return this._client.post('/api/v1/prompt-webhooks/test', { body, ...options });
  }
}

/**
 * Schema for a prompt webhook.
 */
export interface PromptWebhook {
  id: string;

  created_at: string;

  tenant_id: string;

  updated_at: string;

  /**
   * URL that receives a POST request with the prompt event payload.
   */
  url: string;

  /**
   * IDs of prompts whose events never fire the webhook.
   */
  exclude_prompts?: Array<string> | null;

  /**
   * HTTP headers sent with each request, for example an Authorization header. Values
   * are stored encrypted and are masked in responses to callers who cannot update
   * prompts.
   */
  headers?: { [key: string]: unknown } | null;

  /**
   * IDs of the prompts whose events fire the webhook. When empty, events from every
   * prompt in the workspace fire it.
   */
  include_prompts?: Array<string> | null;

  /**
   * Events that fire the webhook: commit (a new prompt commit), tag:create, and
   * tag:update. A webhook with no triggers never fires.
   */
  triggers?: Array<'commit' | 'tag:create' | 'tag:update'>;
}

export type PromptWebhookListResponse = Array<PromptWebhook>;

export type PromptWebhookTestResponse = { [key: string]: string };

export interface PromptWebhookCreateParams {
  /**
   * URL that receives a POST request with the prompt event payload.
   */
  url: string;

  /**
   * ID to assign to the webhook. Generated when omitted.
   */
  id?: string | null;

  /**
   * IDs of prompts whose events never fire the webhook.
   */
  exclude_prompts?: Array<string> | null;

  /**
   * HTTP headers sent with each request, for example an Authorization header. Values
   * are stored encrypted and are masked in responses to callers who cannot update
   * prompts.
   */
  headers?: { [key: string]: unknown } | null;

  /**
   * IDs of the prompts whose events fire the webhook. When empty, events from every
   * prompt in the workspace fire it.
   */
  include_prompts?: Array<string> | null;

  /**
   * Events that fire the webhook: commit (a new prompt commit), tag:create, and
   * tag:update. A webhook with no triggers never fires.
   */
  triggers?: Array<'commit' | 'tag:create' | 'tag:update'>;
}

export interface PromptWebhookUpdateParams {
  /**
   * IDs of prompts whose events never fire the webhook, replacing the current list.
   * Omit to keep it.
   */
  exclude_prompts?: Array<string> | null;

  /**
   * HTTP headers sent with each request, replacing all current headers. Omit to keep
   * them. Masked values (**\*\*\*\***) from a read are rejected.
   */
  headers?: { [key: string]: unknown } | null;

  /**
   * IDs of the prompts whose events fire the webhook, replacing the current list.
   * Omit to keep it.
   */
  include_prompts?: Array<string> | null;

  /**
   * Events that fire the webhook (commit, tag:create, tag:update), replacing the
   * current list. Omit to keep it.
   */
  triggers?: Array<'commit' | 'tag:create' | 'tag:update'> | null;

  /**
   * URL that receives the POST requests. Omit to keep the current URL.
   */
  url?: string | null;
}

export interface PromptWebhookTestParams {
  payload: PromptWebhookTestParams.Payload;

  /**
   * Base schema for prompt webhooks.
   */
  webhook: PromptWebhookTestParams.Webhook;
}

export namespace PromptWebhookTestParams {
  export interface Payload {
    commit_hash: string;

    created_at: string;

    created_by: string;

    /**
     * Valid trigger types for prompt webhooks.
     */
    event: 'commit' | 'tag:create' | 'tag:update';

    manifest: { [key: string]: unknown };

    prompt_id: string;

    prompt_name: string;

    tag_name?: string | null;
  }

  /**
   * Base schema for prompt webhooks.
   */
  export interface Webhook {
    /**
     * URL that receives a POST request with the prompt event payload.
     */
    url: string;

    /**
     * IDs of prompts whose events never fire the webhook.
     */
    exclude_prompts?: Array<string> | null;

    /**
     * HTTP headers sent with each request, for example an Authorization header. Values
     * are stored encrypted and are masked in responses to callers who cannot update
     * prompts.
     */
    headers?: { [key: string]: unknown } | null;

    /**
     * IDs of the prompts whose events fire the webhook. When empty, events from every
     * prompt in the workspace fire it.
     */
    include_prompts?: Array<string> | null;

    /**
     * Events that fire the webhook: commit (a new prompt commit), tag:create, and
     * tag:update. A webhook with no triggers never fires.
     */
    triggers?: Array<'commit' | 'tag:create' | 'tag:update'>;
  }
}

export declare namespace PromptWebhooks {
  export {
    type PromptWebhook as PromptWebhook,
    type PromptWebhookListResponse as PromptWebhookListResponse,
    type PromptWebhookTestResponse as PromptWebhookTestResponse,
    type PromptWebhookCreateParams as PromptWebhookCreateParams,
    type PromptWebhookUpdateParams as PromptWebhookUpdateParams,
    type PromptWebhookTestParams as PromptWebhookTestParams,
  };
}
