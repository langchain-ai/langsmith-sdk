import { exec, execSync } from "child_process";

interface GitInfo {
  remoteUrl?: string | null;
  commit?: string | null;
  branch?: string | null;
  authorName?: string | null;
  authorEmail?: string | null;
  commitMessage?: string | null;
  commitTime?: string | null;
  dirty?: boolean | null;
  tags?: string | null;
}

const execGit = (command: string[]): Promise<string | null> => {
  return new Promise((resolve) => {
    exec(`git ${command.join(" ")}`, (error, stdout) => {
      if (error) {
        resolve(null);
      } else {
        resolve(stdout.trim());
      }
    });
  });
};

const execSyncGit = (command: string[]): string | null => {
  try {
    return execSync(`git ${command.join(" ")}`, { encoding: "utf8" }).trim();
  } catch (error) {
    return null;
  }
};

export const getGitInfoSync = (remote = "origin"): GitInfo | null => {
  const isInsideWorkTree = execSyncGit(["rev-parse", "--is-inside-work-tree"]);
  if (!isInsideWorkTree) {
    return null;
  }

  const remoteUrl = execSyncGit(["remote", "get-url", remote]);
  const commit = execSyncGit(["rev-parse", "HEAD"]);
  const commitTime = execSyncGit(["log", "-1", "--format=%ct"]);
  const branch = execSyncGit(["rev-parse", "--abbrev-ref", "HEAD"]);
  const tags = execSyncGit([
    "describe",
    "--tags",
    "--exact-match",
    "--always",
    "--dirty",
  ]);
  const dirty = execSyncGit(["status", "--porcelain"]) !== "";
  const authorName = execSyncGit(["log", "-1", "--format=%an"]);
  const authorEmail = execSyncGit(["log", "-1", "--format=%ae"]);

  return {
    remoteUrl,
    commit,
    commitTime,
    branch,
    tags,
    dirty,
    authorName,
    authorEmail,
  };
};

export const getGitInfo = async (
  remote = "origin"
): Promise<GitInfo | null> => {
  const isInsideWorkTree = await execGit([
    "rev-parse",
    "--is-inside-work-tree",
  ]);
  if (!isInsideWorkTree) {
    return null;
  }

  const [
    remoteUrl,
    commit,
    commitTime,
    branch,
    tags,
    dirty,
    authorName,
    authorEmail,
  ] = await Promise.all([
    execGit(["remote", "get-url", remote]),
    execGit(["rev-parse", "HEAD"]),
    execGit(["log", "-1", "--format=%ct"]),
    execGit(["rev-parse", "--abbrev-ref", "HEAD"]),
    execGit(["describe", "--tags", "--exact-match", "--always", "--dirty"]),
    execGit(["status", "--porcelain"]).then((output) => output !== ""),
    execGit(["log", "-1", "--format=%an"]),
    execGit(["log", "-1", "--format=%ae"]),
  ]);

  return {
    remoteUrl,
    commit,
    commitTime,
    branch,
    tags,
    dirty,
    authorName,
    authorEmail,
  };
};
