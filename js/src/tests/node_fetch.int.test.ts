import { v4 as uuidv4 } from "uuid";
import nodeFetch from "node-fetch";

import { Client } from "../client.js";
import {
  deleteProject,
  waitUntilProjectFound,
  skipOnRateLimit,
} from "./utils.js";
import { traceable } from "../traceable.js";
import { overrideFetchImplementation } from "../singletons/fetch.js";

test("multipart should work with overridden node-fetch", async () => {
  await skipOnRateLimit(async () => {
    overrideFetchImplementation(nodeFetch);

    const langchainClient = new Client({
      autoBatchTracing: true,
      callerOptions: { maxRetries: 6 },
      timeout_ms: 120_000,
    });

    const projectName = "__test_node_fetch" + uuidv4().substring(0, 4);
    await deleteProject(langchainClient, projectName);

    await traceable(
      async () => {
        return "testing with node fetch";
      },
      {
        project_name: projectName,
        client: langchainClient,
        tracingEnabled: true,
      }
    )();

    await langchainClient.awaitPendingTraceBatches();

    await Promise.all([waitUntilProjectFound(langchainClient, projectName)]);

    await langchainClient.deleteProject({ projectName });
  });
});
