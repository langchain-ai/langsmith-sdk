// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../core/resource.js';
import { APIPromise } from '../core/api-promise.js';
import { RequestOptions } from '../internal/request-options.js';

export class Settings extends APIResource {
  /**
   * Get settings.
   */
  list(options?: RequestOptions): APIPromise<AppHubCrudTenantsTenant> {
    return this._client.get('/api/v1/settings', options);
  }
}

export interface AppHubCrudTenantsTenant {
  id: string;

  created_at: string;

  display_name: string;

  tenant_handle?: string | null;
}

export declare namespace Settings {
  export { type AppHubCrudTenantsTenant as AppHubCrudTenantsTenant };
}
