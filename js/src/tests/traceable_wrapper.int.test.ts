import { Client } from "../client.js";
import { traceable } from "../run_helpers.js";
import { RunTree } from "../run_trees.js";

async function deleteProject(langchainClient: Client, projectName: string) {
  try {
    await langchainClient.readProject({ projectName });
    await langchainClient.deleteProject({ projectName });
  } catch (e) {
    // Pass
  }
}

test.concurrent(
  "Test traceable wrapper",
  async () => {
    const langchainClient = new Client({
      callerOptions: { maxRetries: 0 },
    });
    const projectName = "__test_traceable_wrapper";
    const addValueTraceable = traceable(
      (a: string, b: number) => {
        return a + b;
      },
      { name: "add_value" }
    );

    expect(
      await addValueTraceable("testing", 9, {
        config: {
          name: "test_run_tree_single",
          run_type: "chain",
          client: langchainClient,
          project_name: projectName,
        },
      })
    ).toBe("testing9");

    const entryTraceable = traceable(
      (complex: { value: string }, runTree: RunTree) =>
        addValueTraceable(complex.value, 1, runTree),
      { name: "run_with_nesting" }
    );

    expect(
      await entryTraceable(
        { value: "testing" },
        {
          config: {
            name: "test_run_tree_composed",
            run_type: "chain",
            client: langchainClient,
            project_name: projectName,
          },
        }
      )
    ).toBe("testing1");

    await deleteProject(langchainClient, projectName);
  },
  180_000
);
