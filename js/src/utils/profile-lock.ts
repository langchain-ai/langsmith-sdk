import * as fsUtils from "./fs.js";

const LOCK_POLL_INTERVAL_MS = 10;
const LOCK_STALE_AFTER_MS = 10_000;
const LOCK_METADATA_FILE = "created_at";

export interface OAuthRefreshLock {
  release(): Promise<void>;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isEEXIST(err: unknown): boolean {
  return (
    typeof err === "object" &&
    err !== null &&
    (err as { code?: string }).code === "EEXIST"
  );
}

function lockMetadataLines(lockDir: string): string[] | undefined {
  try {
    return fsUtils
      .readFileSync(fsUtils.path.join(lockDir, LOCK_METADATA_FILE))
      .split("\n");
  } catch {
    return undefined;
  }
}

function lockCreatedAtMs(lockDir: string): number | undefined {
  const lines = lockMetadataLines(lockDir);
  if (lines && lines[0] && lines[0].trim()) {
    const parsed = Date.parse(lines[0].trim());
    if (!Number.isNaN(parsed)) {
      return parsed;
    }
  }
  return fsUtils.statMtimeMs(lockDir);
}

function lockOwner(lockDir: string): string | undefined {
  const lines = lockMetadataLines(lockDir);
  if (lines && lines.length >= 2 && lines[1].trim()) {
    return lines[1].trim();
  }
  return undefined;
}

async function removeStaleLock(lockDir: string): Promise<boolean> {
  const createdAt = lockCreatedAtMs(lockDir);
  if (createdAt === undefined || Date.now() - createdAt <= LOCK_STALE_AFTER_MS) {
    return false;
  }
  await fsUtils.rmRecursive(lockDir);
  return true;
}

/**
 * Acquire an exclusive cross-process lock for refreshing OAuth tokens.
 *
 * Uses an atomic-`mkdir` directory lock at `<configPath>.oauth.lock.lock` with a
 * stale-break heuristic and owner-checked release, mirroring langsmith-go's
 * non-POSIX path. `deadline` is a `Date.now()`-based timestamp; acquisition
 * rejects once it passes. Callers treat any rejection as "skip refresh, use the
 * current token".
 */
export async function acquireOAuthRefreshLock(
  configPath: string,
  deadline: number,
): Promise<OAuthRefreshLock> {
  const lockDir = `${configPath}.oauth.lock.lock`;
  const parent = fsUtils.path.dirname(lockDir);
  if (parent) {
    await fsUtils.mkdir(parent);
  }
  const owner = globalThis.crypto.randomUUID();
  for (;;) {
    try {
      await fsUtils.mkdirExclusive(lockDir);
    } catch (err) {
      if (!isEEXIST(err)) {
        throw err;
      }
      if (!(await removeStaleLock(lockDir))) {
        if (Date.now() >= deadline) {
          throw new Error("timed out acquiring OAuth refresh lock");
        }
        await sleep(
          Math.min(LOCK_POLL_INTERVAL_MS, Math.max(0, deadline - Date.now())),
        );
      }
      continue;
    }
    try {
      await fsUtils.writeFileAtomic(
        fsUtils.path.join(lockDir, LOCK_METADATA_FILE),
        `${new Date().toISOString()}\n${owner}\n`,
      );
    } catch (err) {
      await fsUtils.rmRecursive(lockDir);
      throw err;
    }
    break;
  }
  return {
    async release() {
      if (lockOwner(lockDir) === owner) {
        await fsUtils.rmRecursive(lockDir);
      }
    },
  };
}

// Exposed for tests only.
export const _internal = {
  LOCK_METADATA_FILE,
  LOCK_STALE_AFTER_MS,
  lockOwner,
};
