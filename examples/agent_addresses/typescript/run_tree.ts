// Address a run you build by hand with `RunTree`.
//
// Needs LANGSMITH_API_KEY and LANGSMITH_TRACING=true.

import { AgentAddress, Client, RunTree } from "langsmith";

const client = new Client();

const run = new RunTree({
  name: "handle_order",
  run_type: "chain",
  inputs: { orderId: "A-1" },
  client,
  address: new AgentAddress("checkout", "production"),
});
await run.postRun();
await run.end({ status: "charged" });
await run.patchRun();
await client.awaitPendingTraceBatches();
