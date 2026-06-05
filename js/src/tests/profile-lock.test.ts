import { jest } from "@jest/globals";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { acquireOAuthRefreshLock, _internal } from "../utils/profile-lock.js";

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
