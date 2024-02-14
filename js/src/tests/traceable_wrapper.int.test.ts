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
    const projectName = "__test_traceable_wrapper";
    const runId = uuidv4();
    const rootRunTree = new RunTree({
      name: "test_run_tree",
      run_type: "chain",
      id: runId,
      client: langchainClient,
      project_name: projectName,
    });

    const addValueTraceable = traceable(
      (a: string, b: number) => {
        return a + b;
      },
      { name: "testinger" }
    );

    expect(await addValueTraceable("testing", 9, rootRunTree)).toBe("testing9");

    const entryTraceable = traceable(
      (complex: { value: string }, runTree: RunTree) =>
        addValueTraceable(complex.value, 1, runTree),
      { name: "nested_testinger" }
    );

    expect(await entryTraceable({ value: "testing" }, rootRunTree)).toBe(
      "testing1"
    );

    // await deleteProject(langchainClient, projectName);
  },
  180_000
);
