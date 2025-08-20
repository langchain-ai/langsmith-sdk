import { traceable } from "../traceable.js";
import { Client } from "../client.js";

import * as fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

test.skip("Test performance with large runs and concurrency", async () => {
  const pathname = path.join(
    path.dirname(fileURLToPath(import.meta.url)),
    "test_data",
    "beemovie.txt"
  );

  const largeInput = { bee: fs.readFileSync(pathname).toString() };
  const client = new Client({
    debug: true,
  });
  const largeTest = traceable(
    async (foo: Record<string, any>) => {
      await new Promise((resolve) => setTimeout(resolve, 100));
      return { reversebee: foo.bee.toString().split("").reverse().join("") };
    },
    {
      client,
    }
  );

  await Promise.all(
    Array.from({ length: 1000 }, async () => {
      await largeTest(largeInput);
    })
  );

  await client.awaitPendingTraceBatches();
});
