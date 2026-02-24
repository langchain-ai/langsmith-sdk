/**
 * File system operations for prompt cache (Node.js version).
 *
 * This file is swapped with fs.browser.ts for browser builds
 * via the package.json browser field.
 */

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
 * Dump cache entries to a JSON file.
 */
export function dumpCache(
  filePath: string,
  entries: Record<string, unknown>
): void {
  const dir = path.dirname(filePath);
  if (!existsSync(dir)) {
    mkdirSync(dir);
  }

  const data = { entries };

  // Atomic write: write to temp file then rename
  const tempPath = `${filePath}.tmp`;
  try {
    writeFileSync(tempPath, JSON.stringify(data, null, 2));
    renameSync(tempPath, filePath);
  } catch (e) {
    // Clean up temp file on failure
    if (existsSync(tempPath)) {
      unlinkSync(tempPath);
    }
    throw e;
  }
}

/**
 * Load cache entries from a JSON file.
 *
 * @returns The entries object, or null if file doesn't exist or is invalid.
 */
export function loadCache(filePath: string): Record<string, unknown> | null {
  if (!existsSync(filePath)) {
    return null;
  }

  try {
    const content = readFileSync(filePath);
    const data = JSON.parse(content);
    return data.entries ?? null;
  } catch {
    return null;
  }
}
