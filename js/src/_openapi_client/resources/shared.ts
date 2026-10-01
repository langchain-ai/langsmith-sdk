// @ts-nocheck
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

export interface AgentAddress {
  /**
   * `id` is the Agent's user-assigned id.
   */
  id: string;

  /**
   * `environment` is the Agent environment.
   */
  environment: 'LOCAL' | 'DEVELOPMENT' | 'STAGING' | 'PRODUCTION';

  kind: 'AGENT';
}
