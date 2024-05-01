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

async function importChildProcess() {
  const { exec } = await import("child_process");
  return { exec };
}

const execGit = (
  command: string[],
  exec: (...args: any[]) => any
): Promise<string | null> => {
  return new Promise((resolve) => {
    exec(`git ${command.join(" ")}`, (error: any, stdout: any) => {
      if (error) {
        resolve(null);
      } else {
        resolve(stdout.trim());
      }
    });
  });
};

export const getGitInfo = async (
  remote = "origin"
): Promise<GitInfo | null> => {
  let exec: (...args: any[]) => any;
  try {
    const execImport = await importChildProcess();
    exec = execImport.exec;
  } catch (e) {
    // no-op
    return null;
  }

  const isInsideWorkTree = await execGit(
    ["rev-parse", "--is-inside-work-tree"],
    exec
  );
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
    execGit(["remote", "get-url", remote], exec),
    execGit(["rev-parse", "HEAD"], exec),
    execGit(["log", "-1", "--format=%ct"], exec),
    execGit(["rev-parse", "--abbrev-ref", "HEAD"], exec),
    execGit(
      ["describe", "--tags", "--exact-match", "--always", "--dirty"],
      exec
    ),
    execGit(["status", "--porcelain"], exec).then((output) => output !== ""),
    execGit(["log", "-1", "--format=%an"], exec),
    execGit(["log", "-1", "--format=%ae"], exec),
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

export const getDefaultRevisionId = async (): Promise<string | null> => {
  let exec: (...args: any[]) => any;
  try {
    const execImport = await importChildProcess();
    exec = execImport.exec;
  } catch (e) {
    // no-op
    return null;
  }

  const commit = await execGit(["rev-parse", "HEAD"], exec);
  if (!commit) {
    return null;
  }
  return commit;
};
