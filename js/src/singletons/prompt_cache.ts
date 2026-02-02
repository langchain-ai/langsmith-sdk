/**
 * Singleton cache manager for prompts.
 *
 * This module provides a singleton cache that is shared across all Client instances,
 * improving cache hit rates and memory efficiency when multiple clients are used in the same process.
 */

import { Cache } from "../utils/prompts_cache/index.js";
import type { PromptCacheConfig } from "../utils/prompts_cache/types.js";

// Module-level singleton cache instance
let _cacheInstance: Cache | undefined;

class PromptCacheManager {
  /**
   * Get the cache instance.
   * Returns undefined if not initialized.
   */
  getInstance(): Cache | undefined {
    return _cacheInstance;
  }

  /**
   * Initialize the cache instance.
   * If already initialized, this is a no-op unless force=true.
   *
   * @param config - Cache configuration options
   * @param force - If true, replace existing cache instance (will stop the old one)
   * @returns The cache instance
   */
  initializeInstance(config?: PromptCacheConfig, force = false): Cache {
    if (_cacheInstance && !force) {
      // Already initialized, return existing
      return _cacheInstance;
    }

    if (_cacheInstance && force) {
      // Stop the existing cache before replacing
      _cacheInstance.stop();
    }

    // Create new cache instance
    _cacheInstance = new Cache(config);
    return _cacheInstance;
  }

  /**
   * Check if the cache has been initialized.
   */
  isInitialized(): boolean {
    return _cacheInstance !== undefined;
  }

  /**
   * Clear and stop the cache instance.
   */
  cleanup(): void {
    if (_cacheInstance) {
      _cacheInstance.stop();
      _cacheInstance = undefined;
    }
  }
}

export const PromptCacheManagerSingleton = new PromptCacheManager();

/**
 * Get or initialize the prompt cache singleton.
 *
 * @param config - Configuration to use if cache is not yet initialized (ignored if already initialized)
 * @returns The singleton cache instance
 */
export function getOrInitializeCache(config?: PromptCacheConfig): Cache {
  const existing = PromptCacheManagerSingleton.getInstance();
  if (existing) {
    return existing;
  }
  return PromptCacheManagerSingleton.initializeInstance(config);
}
