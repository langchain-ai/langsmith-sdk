/* eslint-disable no-process-env */

import { jest } from "@jest/globals";
import { Client } from "../client.js";
import { RunTree } from "../run_trees.js";

test.concurrent(
  "Should work with manually set API key",
  async () => {
    const key = process.env.LANGCHAIN_API_KEY;
    delete process.env.LANGCHAIN_API_KEY;
    const langchainClient = new Client({
      autoBatchTracing: true,
      callerOptions: { maxRetries: 0 },
      timeout_ms: 30_000,
      apiKey: key,
    });
    const callSpy = jest
      .spyOn((langchainClient as any).caller, "call")
      .mockResolvedValue({
        ok: true,
        text: () => "",
      });
    const projectName = "__test_persist_update_run_tree";
    const runTree = new RunTree({
      name: "Test Run Tree",
      inputs: { input: "foo1" },
      client: langchainClient,
      project_name: projectName,
    });
    await runTree.postRun();
    await new Promise((resolve) => setTimeout(resolve, 1000));
    expect(callSpy).toHaveBeenCalled();
  },
  180_000
);
