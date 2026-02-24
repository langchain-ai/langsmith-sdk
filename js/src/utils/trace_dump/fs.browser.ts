/**
 * File system operations for trace dump fallback (Browser stub).
 *
 * This stub is used in browser/bundler builds via the package.json browser field.
 * File operations are never called in browser environments because failedTracesDir
 * is always undefined when fs is unavailable (cleared at Client construction time).
 */

export const path = {
  join: (...parts: string[]) => parts.join("/"),
  dirname: (p: string) => p.split("/").slice(0, -1).join("/"),
};

export function randomUUID(): string {
  // Web Crypto API is available in all modern browsers, Node 19+, Bun, Deno
  return globalThis.crypto.randomUUID();
}

export async function mkdir(_dir: string): Promise<void> {
  // no-op in browser
}

export async function writeFileAtomic(
  _filePath: string,
  _content: string
): Promise<void> {
  // no-op in browser
}

export async function readdir(_dir: string): Promise<string[]> {
  return [];
}

export async function stat(_filePath: string): Promise<{ size: number }> {
  return { size: 0 };
}

export async function unlink(_filePath: string): Promise<void> {
  // no-op in browser
}
