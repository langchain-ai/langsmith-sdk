/**
 * Prompt caching module for LangSmith SDK.
 *
 * Provides an LRU cache with background refresh for prompt caching.
 * Uses stale-while-revalidate pattern for optimal performance.
 */

import * as fs from "node:fs";
import * as path from "node:path";

import type { PromptCommit } from "../schemas.js";

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
 * Configuration options for PromptCache.
 */
export interface PromptCacheConfig {
  /** Maximum entries in cache (LRU eviction when exceeded). Default: 100 */
  maxSize?: number;
  /** Time in seconds before entry is stale. null = infinite TTL. Default: 3600 */
  ttlSeconds?: number | null;
  /** How often to check for stale entries in seconds. Default: 60 */
  refreshIntervalSeconds?: number;
  /** Callback to fetch fresh data for a cache key */
  fetchFunc?: (key: string) => Promise<PromptCommit>;
  /** Whether caching is enabled. Default: true */
  enabled?: boolean;
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
 * - JSON dump/load for offline use
 *
 * @example
 * ```typescript
 * const cache = new PromptCache({
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
export class PromptCache {
  private cache: Map<string, CacheEntry<PromptCommit>> = new Map();
  private maxSize: number;
  private ttlSeconds: number | null;
  private refreshIntervalSeconds: number;
  private fetchFunc?: (key: string) => Promise<PromptCommit>;
  private enabled: boolean;
  private refreshTimer?: ReturnType<typeof setInterval>;
  private _metrics: CacheMetrics = {
    hits: 0,
    misses: 0,
    refreshes: 0,
    refreshErrors: 0,
  };

  constructor(config: PromptCacheConfig = {}) {
    this.maxSize = config.maxSize ?? 100;
    this.ttlSeconds = config.ttlSeconds ?? 3600;
    this.refreshIntervalSeconds = config.refreshIntervalSeconds ?? 60;
    this.fetchFunc = config.fetchFunc;
    this.enabled = config.enabled ?? true;

    // Start background refresh if fetch function provided and TTL is set
    if (this.enabled && this.fetchFunc && this.ttlSeconds !== null) {
      this.startRefreshLoop();
    }
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
  get(key: string): PromptCommit | undefined {
    if (!this.enabled) {
      this._metrics.misses += 1;
      return undefined;
    }

    const entry = this.cache.get(key);
    if (!entry) {
      this._metrics.misses += 1;
      return undefined;
    }

    // Move to end for LRU (delete and re-add)
    this.cache.delete(key);
    this.cache.set(key, entry);

    this._metrics.hits += 1;
    return entry.value;
  }

  /**
   * Set a value in the cache.
   */
  set(key: string, value: PromptCommit): void {
    if (!this.enabled) {
      return;
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
    };

    // Delete first to ensure it's at the end
    this.cache.delete(key);
    this.cache.set(key, entry);
  }

  /**
   * Remove a specific entry from cache.
   */
  invalidate(key: string): void {
    if (!this.enabled) {
      return;
    }
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
    const dir = path.dirname(filePath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }

    const entries: Record<string, PromptCommit> = {};
    for (const [key, entry] of this.cache.entries()) {
      entries[key] = entry.value;
    }

    const data = { entries };

    // Atomic write: write to temp file then rename
    const tempPath = `${filePath}.tmp`;
    try {
      fs.writeFileSync(tempPath, JSON.stringify(data, null, 2));
      fs.renameSync(tempPath, filePath);
    } catch (e) {
      // Clean up temp file on failure
      if (fs.existsSync(tempPath)) {
        fs.unlinkSync(tempPath);
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
    if (!fs.existsSync(filePath)) {
      return 0;
    }

    let data: { entries?: Record<string, PromptCommit> };
    try {
      const content = fs.readFileSync(filePath, "utf-8");
      data = JSON.parse(content);
    } catch {
      return 0;
    }

    const entries = data.entries ?? {};
    let loaded = 0;
    const now = Date.now();

    for (const [key, value] of Object.entries(entries)) {
      if (this.cache.size >= this.maxSize) {
        break;
      }

      const entry: CacheEntry<PromptCommit> = {
        value,
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
  private startRefreshLoop(): void {
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

  /**
   * Get list of stale cache keys.
   */
  private getStaleKeys(): string[] {
    const staleKeys: string[] = [];
    for (const [key, entry] of this.cache.entries()) {
      if (isStale(entry, this.ttlSeconds)) {
        staleKeys.push(key);
      }
    }
    return staleKeys;
  }

  /**
   * Check for stale entries and refresh them.
   */
  private async refreshStaleEntries(): Promise<void> {
    if (!this.fetchFunc) {
      return;
    }

    const staleKeys = this.getStaleKeys();
    if (staleKeys.length === 0) {
      return;
    }

    for (const key of staleKeys) {
      try {
        const newValue = await this.fetchFunc(key);
        this.set(key, newValue);
        this._metrics.refreshes += 1;
      } catch {
        // Keep stale data on refresh failure
        this._metrics.refreshErrors += 1;
      }
    }
  }
}
