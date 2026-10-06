// Address a traced function with `traceable`.
//
// Needs LANGSMITH_API_KEY and LANGSMITH_TRACING=true.

import { Agent, Client } from "langsmith";
import { traceable } from "langsmith/traceable";

const client = new Client();

const handleOrder = traceable(
  async (orderId: string) => ({ orderId, status: "charged" }),
  { name: "handle_order", client, address: new Agent("checkout", "production") },
);

await handleOrder("A-1");
await client.awaitPendingTraceBatches();
