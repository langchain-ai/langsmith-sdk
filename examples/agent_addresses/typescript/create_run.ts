// Address a run sent through the client with `createRun`.
//
// Needs LANGSMITH_API_KEY and LANGSMITH_TRACING=true.

import { randomUUID } from "node:crypto";

import { Agent, Client } from "langsmith";

const client = new Client();
const agent = new Agent("checkout", "production");
const id = randomUUID();

await client.createRun({
  id,
  name: "handle_order",
  run_type: "chain",
  inputs: { orderId: "A-1" },
  address: agent,
});
await client.updateRun(id, {
  outputs: { status: "charged" },
  end_time: Date.now(),
  address: agent,
});
await client.awaitPendingTraceBatches();
