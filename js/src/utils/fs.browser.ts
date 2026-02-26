/**
 * File system abstraction (browser stub).
 *
 * This stub is used in browser/bundler builds via the package.json browser
 * field. Async operations are no-ops; sync operations are no-ops that return
 * safe defaults. Higher-level consumers (e.g. prompt_cache/fs.browser.ts) may
 * still throw on their own if browser use is unsupported at that layer.
 */

export const path = {
  join: (...parts: string[]) => parts.join("/"),
  dirname: (p: string) => p.split("/").slice(0, -1).join("/"),
};

// ---------------------------------------------------------------------------
// Async operations – no-op in browser
// ---------------------------------------------------------------------------

export async function mkdir(_dir: string): Promise<void> {}

export async function writeFileAtomic(
  _filePath: string,
  _content: string
): Promise<void> {}

export async function readdir(_dir: string): Promise<string[]> {
  return [];
}

export async function stat(_filePath: string): Promise<{ size: number }> {
  return { size: 0 };
}

export async function unlink(_filePath: string): Promise<void> {}

// ---------------------------------------------------------------------------
// Sync operations – no-op / safe defaults in browser
// ---------------------------------------------------------------------------

export function existsSync(_p: string): boolean {
  return false;
}

export function mkdirSync(_dir: string): void {}

export function writeFileSync(_filePath: string, _content: string): void {}

export function renameSync(_oldPath: string, _newPath: string): void {}

export function unlinkSync(_filePath: string): void {}

export function readFileSync(_filePath: string): string {
  return "";
}
