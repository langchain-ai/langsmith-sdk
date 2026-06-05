/**
 * File system abstraction (Node.js version).
 *
 * This file is swapped with fs.browser.ts for browser builds
 * via the package.json browser field.
 */

import * as nodeFs from "node:fs";
import * as nodeFsPromises from "node:fs/promises";
import * as nodePath from "node:path";

export const path = nodePath;

// ---------------------------------------------------------------------------
// Async operations (used by trace dump fallback)
// ---------------------------------------------------------------------------

export async function mkdir(dir: string): Promise<void> {
  await nodeFsPromises.mkdir(dir, { recursive: true });
}

export async function writeFileAtomic(
  filePath: string,
  content: string,
): Promise<void> {
  const tempPath = `${filePath}.tmp`;
  await nodeFsPromises.writeFile(tempPath, content, {
    encoding: "utf8",
    mode: 0o600,
  });
  await nodeFsPromises.rename(tempPath, filePath);
}

export async function readdir(dir: string): Promise<string[]> {
  return nodeFsPromises.readdir(dir);
}

export async function stat(filePath: string): Promise<{ size: number }> {
  return nodeFsPromises.stat(filePath);
}

export async function unlink(filePath: string): Promise<void> {
  await nodeFsPromises.unlink(filePath);
}

// ---------------------------------------------------------------------------
// Sync operations (used by prompt cache)
// ---------------------------------------------------------------------------

export function existsSync(p: string): boolean {
  return nodeFs.existsSync(p);
}

export function mkdirSync(dir: string): void {
  nodeFs.mkdirSync(dir, { recursive: true });
}

export function writeFileSync(filePath: string, content: string): void {
  nodeFs.writeFileSync(filePath, content);
}

export function renameSync(oldPath: string, newPath: string): void {
  nodeFs.renameSync(oldPath, newPath);
}

export function unlinkSync(filePath: string): void {
  nodeFs.unlinkSync(filePath);
}

export function readFileSync(filePath: string): string {
  return nodeFs.readFileSync(filePath, "utf-8");
}

// ---------------------------------------------------------------------------
// Lock primitives (used by the OAuth refresh directory lock)
// ---------------------------------------------------------------------------

export async function mkdirExclusive(dir: string): Promise<void> {
  // Non-recursive mkdir throws EEXIST if the directory already exists, which
  // is the atomic test-and-set the cross-process lock relies on.
  await nodeFsPromises.mkdir(dir, { mode: 0o700 });
}

export function statMtimeMs(filePath: string): number | undefined {
  try {
    return nodeFs.statSync(filePath).mtimeMs;
  } catch {
    return undefined;
  }
}

export async function rmRecursive(filePath: string): Promise<void> {
  await nodeFsPromises.rm(filePath, { recursive: true, force: true });
}
