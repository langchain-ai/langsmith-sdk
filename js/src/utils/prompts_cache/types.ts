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
 * Configuration options for prompt cache.
 */
export interface PromptCacheConfig {
  /** Maximum entries in cache (LRU eviction when exceeded). Default: 100 */
  maxSize?: number;
  /** Time in seconds before entry is stale. null = infinite TTL. Default: 60 */
  ttlSeconds?: number | null;
}
