/**
 * Prompt caching module for LangSmith SDK.
 *
 * Provides an LRU cache with background refresh for prompt caching.
 * Uses stale-while-revalidate pattern for optimal performance.
 *
 * Works in all environments. File operations (dump/load) use helpers
 * that are swapped for browser builds via package.json browser field.
 */

import type { PromptCommit } from "../../schemas.js";
import { dumpCache, loadCache } from "./fs.js";
import type { CacheEntry, CacheMetrics, PromptCacheConfig } from "./types.js";

// Re-export types for convenience
export type { CacheEntry, CacheMetrics, PromptCacheConfig };

/**
 * Check if a cache entry is stale based on TTL.
 */
function isStale(entry: CacheEntry, ttlSeconds: number | null): boolean {
  if (ttlSeconds === null) {
    return false; // Infinite TTL, never stale
  }
  const ageMs = Date.now() - entry.createdAt;
  return ageMs > ttlSeconds * 1000;
}

/**
 * LRU cache with background refresh for prompts.
 *
 * Features:
 * - In-memory LRU cache with configurable max size
 * - Background refresh using setInterval
 * - Stale-while-revalidate: returns stale data while refresh happens
 * - JSON dump/load for offline use
 *
 * @example
 * ```typescript
 * const cache = new Cache({
 *   maxSize: 100,
 *   ttlSeconds: 3600,
 *   fetchFunc: async (key) => client.pullPromptCommit(key),
 * });
 *
 * // Use the cache
 * cache.set("my-prompt:latest", promptCommit);
 * const cached = cache.get("my-prompt:latest");
 *
 * // Cleanup
 * cache.stop();
 * ```
 */
export class Cache {
  private cache: Map<string, CacheEntry<PromptCommit>> = new Map();
  private maxSize: number;
  private ttlSeconds: number | null;
  private _metrics: CacheMetrics = {
    hits: 0,
    misses: 0,
    refreshes: 0,
    refreshErrors: 0,
  };

  constructor(config: PromptCacheConfig = {}) {
    this.maxSize = config.maxSize ?? 100;
    this.ttlSeconds = config.ttlSeconds ?? 60;
  }

  /**
   * Get cache performance metrics.
   */
  get metrics(): Readonly<CacheMetrics> {
    return { ...this._metrics };
  }

  /**
   * Get total cache requests (hits + misses).
   */
  get totalRequests(): number {
    return this._metrics.hits + this._metrics.misses;
  }

  /**
   * Get cache hit rate (0.0 to 1.0).
   */
  get hitRate(): number {
    const total = this.totalRequests;
    return total > 0 ? this._metrics.hits / total : 0;
  }

  /**
   * Reset all metrics to zero.
   */
  resetMetrics(): void {
    this._metrics = {
      hits: 0,
      misses: 0,
      refreshes: 0,
      refreshErrors: 0,
    };
  }

  /**
   * Get a value from cache.
   *
   * Returns the cached value and metadata, or undefined if not found.
   * The caller is responsible for checking staleness and refreshing if needed.
   *
   * @param key - The cache key
   * @returns The cache entry (with value and metadata) or undefined if not found
   */
  get(key: string): { value: PromptCommit; isStale: boolean } | undefined {
    const entry = this.cache.get(key);
    if (!entry) {
      this._metrics.misses += 1;
      return undefined;
    }

    // Move to end for LRU
    this.cache.delete(key);
    this.cache.set(key, entry);

    this._metrics.hits += 1;

    return {
      value: entry.value,
      isStale: isStale(entry, this.ttlSeconds),
    };
  }

  /**
   * Set a value in the cache.
   */
  set(key: string, value: PromptCommit): void {
    // Check if we need to evict (and key is new)
    if (!this.cache.has(key) && this.cache.size >= this.maxSize) {
      // Evict oldest (first item in Map)
      const oldestKey = this.cache.keys().next().value;
      if (oldestKey !== undefined) {
        this.cache.delete(oldestKey);
      }
    }

    const entry: CacheEntry<PromptCommit> = {
      value,
      createdAt: Date.now(),
    };

    // Delete first to ensure it's at the end
    this.cache.delete(key);
    this.cache.set(key, entry);
  }

  /**
   * Remove a specific entry from cache.
   */
  invalidate(key: string): void {
    this.cache.delete(key);
  }

  /**
   * Clear all cache entries.
   */
  clear(): void {
    this.cache.clear();
  }

  /**
   * Get the number of entries in the cache.
   */
  get size(): number {
    return this.cache.size;
  }

  /**
   * Dump cache contents to a JSON file for offline use.
   */
  dump(filePath: string): void {
    const entries: Record<string, PromptCommit> = {};
    for (const [key, entry] of this.cache.entries()) {
      entries[key] = entry.value;
    }
    dumpCache(filePath, entries);
  }

  /**
   * Load cache contents from a JSON file.
   *
   * Loaded entries get a fresh TTL starting from load time.
   *
   * @returns Number of entries loaded.
   */
  load(filePath: string): number {
    const entries = loadCache(filePath);
    if (!entries) {
      return 0;
    }

    let loaded = 0;
    const now = Date.now();

    for (const [key, value] of Object.entries(entries)) {
      if (this.cache.size >= this.maxSize) {
        break;
      }

      const entry: CacheEntry<PromptCommit> = {
        value: value as PromptCommit,
        createdAt: now, // Fresh TTL from load time
      };
      this.cache.set(key, entry);
      loaded += 1;
    }

    return loaded;
  }
}
