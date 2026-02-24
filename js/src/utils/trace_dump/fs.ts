/**
 * File system operations for trace dump fallback (Node.js version).
 *
 * This file is swapped with fs.browser.ts for browser builds
 * via the package.json browser field.
 */

import * as fs from "node:fs/promises";
import * as path from "node:path";
import { randomUUID } from "node:crypto";

export { path, randomUUID };

export async function mkdir(dir: string): Promise<void> {
  await fs.mkdir(dir, { recursive: true });
}

export async function writeFileAtomic(
  filePath: string,
  content: string
): Promise<void> {
  const tempPath = `${filePath}.tmp`;
  await fs.writeFile(tempPath, content, { encoding: "utf8", mode: 0o600 });
  await fs.rename(tempPath, filePath);
}

export async function readdir(dir: string): Promise<string[]> {
  return fs.readdir(dir);
}

export async function stat(filePath: string): Promise<{ size: number }> {
  return fs.stat(filePath);
}

export async function unlink(filePath: string): Promise<void> {
  await fs.unlink(filePath);
}
