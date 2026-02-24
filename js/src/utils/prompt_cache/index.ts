/**
 * Prompt caching module for LangSmith SDK.
 *
 * Provides an LRU cache with background refresh for prompt caching.
 * Uses stale-while-revalidate pattern for optimal performance.
 *
 * Works in all environments. File operations (dump/load) use the shared
 * fs abstraction which is swapped for browser builds via package.json
 * browser field (no-ops in browser — cache just doesn't persist).
 */

import type { PromptCommit } from "../../schemas.js";
import {
  path,
  existsSync,
  mkdirSync,
  writeFileSync,
  renameSync,
  unlinkSync,
  readFileSync,
} from "../fs.js";

/**
 * A single cache entry with metadata for TTL tracking.
 */
export interface CacheEntry<T = unknown> {
  value: T;
  createdAt: number; // Date.now() when entry was created/refreshed
  refreshFunc?: () => Promise<T>;
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
}

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
 * - Uses the most recently used client for a key for refreshes
 * - JSON dump/load for offline use
 *
 * @example
 * ```typescript
 * const cache = new Cache({
 *   maxSize: 100,
 *   ttlSeconds: 3600,
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
export class PromptCache {
  private cache: Map<string, CacheEntry<PromptCommit>> = new Map();
  private maxSize: number;
  private ttlSeconds: number | null;
  private refreshIntervalSeconds: number;
  private refreshTimer?: ReturnType<typeof setInterval>;
  private _metrics: CacheMetrics = {
    hits: 0,
    misses: 0,
    refreshes: 0,
    refreshErrors: 0,
  };

  constructor(config: CacheConfig = {}) {
    this.configure(config);
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
   * Returns the cached value or undefined if not found.
   * Stale entries are still returned (background refresh handles updates).
   */
  get(
    key: string,
    refreshFunc: () => Promise<PromptCommit>
  ): PromptCommit | undefined {
    // If max_size is 0, cache is disabled
    if (this.maxSize === 0) {
      return undefined;
    }

    const entry = this.cache.get(key);
    if (!entry) {
      this._metrics.misses += 1;
      return undefined;
    }

    // Move to end for LRU (delete and re-add)
    this.cache.delete(key);
    this.cache.set(key, { ...entry, refreshFunc });

    this._metrics.hits += 1;
    return entry.value;
  }

  /**
   * Set a value in the cache.
   */
  set(
    key: string,
    value: PromptCommit,
    refreshFunc: () => Promise<PromptCommit>
  ): void {
    // If max_size is 0, cache is disabled - do nothing
    if (this.maxSize === 0) {
      return;
    }

    if (this.refreshTimer === undefined) {
      this.startRefreshLoop();
    }
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
      refreshFunc,
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
   * Stop background refresh.
   * Should be called when the client is being cleaned up.
   */
  stop(): void {
    if (this.refreshTimer) {
      clearInterval(this.refreshTimer);
      this.refreshTimer = undefined;
    }
  }

  /**
   * Dump cache contents to a JSON file for offline use.
   */
  dump(filePath: string): void {
    const entries: Record<string, PromptCommit> = {};
    for (const [key, entry] of this.cache.entries()) {
      entries[key] = entry.value;
    }

    const dir = path.dirname(filePath);
    if (!existsSync(dir)) {
      mkdirSync(dir);
    }
    const tempPath = `${filePath}.tmp`;
    try {
      writeFileSync(tempPath, JSON.stringify({ entries }, null, 2));
      renameSync(tempPath, filePath);
    } catch (e) {
      if (existsSync(tempPath)) {
        unlinkSync(tempPath);
      }
      throw e;
    }
  }

  /**
   * Load cache contents from a JSON file.
   *
   * Loaded entries get a fresh TTL starting from load time.
   *
   * @returns Number of entries loaded.
   */
  load(filePath: string): number {
    if (!existsSync(filePath)) {
      return 0;
    }
    let entries: Record<string, unknown> | null;
    try {
      const content = readFileSync(filePath);
      const data = JSON.parse(content);
      entries = data.entries ?? null;
    } catch {
      return 0;
    }
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

  /**
   * Start the background refresh loop.
   */
  startRefreshLoop(): void {
    this.stop();
    if (this.ttlSeconds !== null) {
      this.refreshTimer = setInterval(() => {
        this.refreshStaleEntries().catch((e) => {
          // Log but don't die - keep the refresh loop running
          console.warn("Unexpected error in cache refresh loop:", e);
        });
      }, this.refreshIntervalSeconds * 1000);

      // Don't block Node.js from exiting
      if (this.refreshTimer.unref) {
        this.refreshTimer.unref();
      }
    }
  }

  /**
   * Get list of stale cache keys.
   */
  private getStaleEntries(): [string, CacheEntry<PromptCommit>][] {
    const staleEntries: [string, CacheEntry<PromptCommit>][] = [];
    for (const [key, value] of this.cache.entries()) {
      if (isStale(value, this.ttlSeconds)) {
        staleEntries.push([key, value]);
      }
    }
    return staleEntries;
  }

  /**
   * Check for stale entries and refresh them.
   */
  private async refreshStaleEntries(): Promise<void> {
    const staleEntries = this.getStaleEntries();
    if (staleEntries.length === 0) {
      return;
    }

    for (const [key, value] of staleEntries) {
      if (value.refreshFunc !== undefined) {
        try {
          const newValue = await value.refreshFunc();
          this.set(key, newValue, value.refreshFunc);
          this._metrics.refreshes += 1;
        } catch (e) {
          // Keep stale data on refresh failure
          this._metrics.refreshErrors += 1;
          console.warn(`Failed to refresh cache entry ${key}:`, e);
        }
      }
    }
  }

  configure(config: CacheConfig): void {
    this.stop();
    this.refreshIntervalSeconds = config.refreshIntervalSeconds ?? 60;
    this.maxSize = config.maxSize ?? 100;
    this.ttlSeconds = config.ttlSeconds ?? 5 * 60;
  }
}

/**
 * Global singleton instance of PromptCache.
 * Use configureGlobalPromptCache(), enableGlobalPromptCache(), or disableGlobalPromptCache() instead.
 */
export const promptCacheSingleton = new PromptCache();

/**
 * Configure the global prompt cache.
 *
 * This should be called before any cache instances are created.
 *
 * @param config - Cache configuration options
 *
 * @example
 * ```typescript
 * import { configureGlobalPromptCache } from 'langsmith';
 *
 * configureGlobalPromptCache({ maxSize: 200, ttlSeconds: 7200 });
 * ```
 */
export function configureGlobalPromptCache(config: CacheConfig): void {
  promptCacheSingleton.configure(config);
}

/**
 * @deprecated Use `PromptCache` instead. This is a deprecated alias.
 *
 * Deprecated alias for PromptCache. Use PromptCache instead.
 */
export class Cache extends PromptCache {
  constructor(config: CacheConfig = {}) {
    console.warn(
      "The 'Cache' class is deprecated and will be removed in a future version. " +
        "Use 'PromptCache' instead."
    );
    super(config);
  }
}
