import { jest, describe, test, expect, beforeEach } from "@jest/globals";
import type { Example } from "../schemas.js";

let remoteUrl = "https://github.com/langchain-ai/langsmith-sdk.git";

const execMock = jest.fn(
  (
    command: string,
    callback: (error: Error | null, stdout: string) => void,
  ) => {
    const outputs: Record<string, string> = {
      "git rev-parse --is-inside-work-tree": "true",
      "git remote get-url origin": remoteUrl,
      "git rev-parse HEAD": "abc123",
      "git log -1 --format=%ct": "1720000000",
      "git rev-parse --abbrev-ref HEAD": "main",
      "git describe --tags --exact-match --always --dirty": "abc123",
      "git status --porcelain": "",
      "git log -1 --format=%an": "LangSmith",
      "git log -1 --format=%ae": "langsmith@example.com",
    };
    const output = outputs[command];
    if (output === undefined) {
      callback(new Error(`Unexpected command: ${command}`), "");
      return;
    }
    callback(null, `${output}\n`);
  },
);

jest.unstable_mockModule("child_process", () => ({
  exec: execMock,
}));

const { getGitInfo } = await import("../utils/_git.js");
const { _ExperimentManager } = await import("../evaluation/_runner.js");

function makeExample(): Example {
  const now = new Date().toISOString();
  return {
    id: "00000000-0000-0000-0000-000000000001",
    inputs: { input: "hello" },
    outputs: {},
    dataset_id: "00000000-0000-0000-0000-000000000000",
    created_at: now,
    modified_at: now,
    runs: [],
  };
}

describe("git info", () => {
  beforeEach(() => {
    remoteUrl = "https://github.com/langchain-ai/langsmith-sdk.git";
    execMock.mockClear();
  });

  test.each([
    [
      "credential-bearing HTTPS",
      "https://user:token@github.com/langchain-ai/langsmith-sdk.git",
      "https://github.com/langchain-ai/langsmith-sdk.git",
    ],
    [
      "percent-encoded userinfo",
      "https://user%40example.com:p%40ss%2Fword@github.com/org/repo.git",
      "https://github.com/org/repo.git",
    ],
    [
      "safe HTTPS",
      "https://github.com/langchain-ai/langsmith-sdk.git",
      "https://github.com/langchain-ai/langsmith-sdk.git",
    ],
    [
      "SSH URL",
      "ssh://git@github.com/langchain-ai/langsmith-sdk.git",
      "ssh://git@github.com/langchain-ai/langsmith-sdk.git",
    ],
    [
      "scp-style remote",
      "git@github.com:langchain-ai/langsmith-sdk.git",
      "git@github.com:langchain-ai/langsmith-sdk.git",
    ],
  ])("getGitInfo handles %s", async (_name, input, expected) => {
    remoteUrl = input;
    const gitInfo = await getGitInfo();
    expect(gitInfo?.remoteUrl).toBe(expected);
  });

  test("evaluation project payloads use sanitized git remotes", async () => {
    const rawRemoteUrl =
      "https://user:token@github.com/langchain-ai/langsmith-sdk.git";
    const sanitizedRemoteUrl =
      "https://github.com/langchain-ai/langsmith-sdk.git";
    remoteUrl = rawRemoteUrl;
    const createProjectCalls: any[] = [];
    const updateProjectCalls: any[] = [];
    const client = {
      createProject: async (params: any) => {
        createProjectCalls.push(params);
        return {
          id: "00000000-0000-0000-0000-000000000004",
          name: "test-project",
          reference_dataset_id: "00000000-0000-0000-0000-000000000000",
          extra: { metadata: {} },
        };
      },
      updateProject: async (id: string, params: any) => {
        updateProjectCalls.push([id, params]);
        return {};
      },
      getDatasetUrl: async () => "http://test.com",
    } as any;

    const manager = new _ExperimentManager({
      examples: [makeExample()],
      client,
    });
    const startedManager = await manager.start();
    await startedManager._end();

    expect(createProjectCalls).toHaveLength(1);
    expect(createProjectCalls[0].metadata.git.remoteUrl).toBe(
      sanitizedRemoteUrl,
    );
    expect(JSON.stringify(createProjectCalls[0])).not.toContain(rawRemoteUrl);
    expect(updateProjectCalls).toHaveLength(1);
    expect(updateProjectCalls[0][1].metadata.git.remoteUrl).toBe(
      sanitizedRemoteUrl,
    );
    expect(JSON.stringify(updateProjectCalls[0][1])).not.toContain(
      rawRemoteUrl,
    );
  });
});
