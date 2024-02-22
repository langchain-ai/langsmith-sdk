import { Client } from "../client.js";

export async function toArray<T>(iterable: AsyncIterable<T>): Promise<T[]> {
  const result: T[] = [];
  for await (const item of iterable) {
    result.push(item);
  }
  return result;
}

export async function waitUntil(
  condition: () => Promise<boolean>,
  timeout: number,
  interval: number
): Promise<void> {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    try {
      if (await condition()) {
        return;
      }
    } catch (e) {
      // Pass
    }
    await new Promise((resolve) => setTimeout(resolve, interval));
  }
  const elapsed = Date.now() - start;
  throw new Error(`Timeout after ${elapsed / 1000}s`);
}

export async function pollRunsUntilCount(
  client: Client,
  projectName: string,
  count: number,
  timeout?: number
): Promise<void> {
  await waitUntil(
    async () => {
      try {
        const runs = await toArray(client.listRuns({ projectName }));
        return runs.length === count;
      } catch (e) {
        return false;
      }
    },
    timeout ?? 120_000, // Wait up to 120 seconds
    5000 // every 5 second
  );
}

export async function deleteProject(
  langchainClient: Client,
  projectName: string
) {
  try {
    await langchainClient.readProject({ projectName });
    await langchainClient.deleteProject({ projectName });
  } catch (e) {
    // Pass
  }
}
export async function deleteDataset(
  langchainClient: Client,
  datasetName: string
) {
  try {
    const existingDataset = await langchainClient.readDataset({ datasetName });
    await langchainClient.deleteDataset({ datasetId: existingDataset.id });
  } catch (e) {
    // Pass
  }
}

export async function waitUntilRunFound(
  client: Client,
  runId: string,
  checkOutputs = false
) {
  return waitUntil(
    async () => {
      try {
        const run = await client.readRun(runId);
        if (checkOutputs) {
          return (
            run.outputs !== null &&
            run.outputs !== undefined &&
            Object.keys(run.outputs).length !== 0
          );
        }
        return true;
      } catch (e) {
        return false;
      }
    },
    30_000,
    5_000
  );
}
