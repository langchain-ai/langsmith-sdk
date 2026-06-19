/* eslint-disable no-process-env */
import { expect, test, vi } from "vitest";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { acquireOAuthRefreshLock, _internal } from "../utils/profile-lock.js";
import { loadProfileClientConfig } from "../utils/profiles.js";

function newConfigPath(): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ls-lock-"));
  return path.join(dir, "config.json");
}

function writeMeta(lockDir: string, iso: string, owner: string): void {
  fs.mkdirSync(lockDir, { recursive: true });
  fs.writeFileSync(
    path.join(lockDir, _internal.LOCK_METADATA_FILE),
    `${iso}\n${owner}\n`,
  );
}

test("acquire creates the lock dir and release removes it", async () => {
  const configPath = newConfigPath();
  const lockDir = `${configPath}.oauth.lock.lock`;
  const lock = await acquireOAuthRefreshLock(configPath, Date.now() + 5000);
  expect(fs.existsSync(lockDir)).toBe(true);
  await lock.release();
  expect(fs.existsSync(lockDir)).toBe(false);
});

test("acquire times out when the lock is held", async () => {
  const configPath = newConfigPath();
  const held = await acquireOAuthRefreshLock(configPath, Date.now() + 5000);
  await expect(
    acquireOAuthRefreshLock(configPath, Date.now() + 50),
  ).rejects.toThrow(/timed out/);
  await held.release();
});

test("a stale lock (expired timestamp) is broken and reacquired", async () => {
  const configPath = newConfigPath();
  const lockDir = `${configPath}.oauth.lock.lock`;
  const stale = new Date(
    Date.now() - _internal.LOCK_STALE_AFTER_MS - 1000,
  ).toISOString();
  writeMeta(lockDir, stale, "someone-else");
  const lock = await acquireOAuthRefreshLock(configPath, Date.now() + 5000);
  expect(_internal.lockOwner(lockDir)).not.toBe("someone-else");
  await lock.release();
});

test("release does not remove a lock owned by someone else", async () => {
  const configPath = newConfigPath();
  const lockDir = `${configPath}.oauth.lock.lock`;
  const lock = await acquireOAuthRefreshLock(configPath, Date.now() + 5000);
  // Simulate another owner reclaiming the dir.
  writeMeta(lockDir, new Date().toISOString(), "new-owner");
  await lock.release();
  expect(fs.existsSync(lockDir)).toBe(true);
  fs.rmSync(lockDir, { recursive: true, force: true });
});

test("two ProfileAuth instances refresh the token endpoint only once", async () => {
  const configPath = newConfigPath();
  fs.writeFileSync(
    configPath,
    JSON.stringify({
      current_profile: "default",
      profiles: {
        default: {
          api_url: "https://api.smith.langchain.com",
          oauth: {
            access_token: "stale",
            refresh_token: "refresh-abc",
            expires_at: "2000-01-01T00:00:00Z",
          },
        },
      },
    }),
  );
  const prev = process.env.LANGSMITH_CONFIG_FILE;
  process.env.LANGSMITH_CONFIG_FILE = configPath;
  try {
    let calls = 0;
    const fakeFetch = vi.fn(async () => {
      calls += 1;
      return {
        ok: true,
        json: async () => ({
          access_token: "network-token",
          refresh_token: "refresh-xyz",
          expires_in: 3600,
        }),
      } as unknown as Response;
    });

    const authA = loadProfileClientConfig().profileAuth;
    const authB = loadProfileClientConfig().profileAuth;
    if (!authA || !authB) {
      throw new Error("expected profileAuth to be defined");
    }
    const headerA = await authA.getAuthHeader(
      fakeFetch as unknown as typeof fetch,
    );
    const headerB = await authB.getAuthHeader(
      fakeFetch as unknown as typeof fetch,
    );

    expect(calls).toBe(1);
    expect(headerA).toEqual({
      name: "Authorization",
      value: "Bearer network-token",
    });
    expect(headerB).toEqual({
      name: "Authorization",
      value: "Bearer network-token",
    });
    const onDisk = JSON.parse(fs.readFileSync(configPath, "utf-8"));
    expect(onDisk.profiles.default.oauth.access_token).toBe("network-token");
  } finally {
    if (prev === undefined) {
      delete process.env.LANGSMITH_CONFIG_FILE;
    } else {
      process.env.LANGSMITH_CONFIG_FILE = prev;
    }
  }
});
