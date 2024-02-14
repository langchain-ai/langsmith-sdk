import { Client } from "../client.js";
import { traceable } from "../run_helpers.js";
import { RunTree } from "../run_trees.js";
import { v4 as uuidv4 } from "uuid";

// async function deleteProject(langchainClient: Client, projectName: string) {
//   try {
//     await langchainClient.readProject({ projectName });
//     await langchainClient.deleteProject({ projectName });
//   } catch (e) {
//     // Pass
//   }
// }

test.concurrent(
  "Test traceable wrapper",
  async () => {
    const langchainClient = new Client({
      callerOptions: { maxRetries: 0 },
    });
    const testFunction = (a: string, b: number) => {
      return a + b;
    };
    const projectName = "__test_traceable_wrapper";
    const runId = uuidv4();
    const rootRunTree = new RunTree({
      name: "test_run_tree",
      run_type: "chain",
      id: runId,
      client: langchainClient,
      project_name: projectName,
    });

    const traceableFunction = traceable(testFunction, { name: "testinger" });
    // const openaiCompletions = traceable(openai.chat.completions.create);

    const [response, runTree] = await traceableFunction(rootRunTree, "testing", 9);
    const [response2, runTree2] = await traceableFunction(runTree, "testing2", 10);

    // await deleteProject(langchainClient, projectName);
  },
  180_000
);
