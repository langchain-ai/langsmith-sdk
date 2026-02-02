/**
 * Type definitions for prompt cache.
 * Separated to avoid circular dependencies.
 */

import type { PromptCommit } from "../../schemas.js";

/**
 * A single cache entry with metadata for TTL tracking.
 */
export interface CacheEntry<T = unknown> {
  value: T;
  createdAt: number; // Date.now() when entry was created/refreshed
}

/**
 * Cache performance metrics.
 */
export interface CacheMetrics {
  hits: number;
  misses: number;
  refreshes: number;
  refreshErrors: number;
}

/**
 * Configuration options for Cache.
 */
export interface CacheConfig {
  /** Maximum entries in cache (LRU eviction when exceeded). Default: 100 */
  maxSize?: number;
  /** Time in seconds before entry is stale. null = infinite TTL. Default: 3600 */
  ttlSeconds?: number | null;
  /** How often to check for stale entries in seconds. Default: 60 */
  refreshIntervalSeconds?: number;
  /** Callback to fetch fresh data for a cache key */
  fetchFunc?: (key: string) => Promise<PromptCommit>;
}
