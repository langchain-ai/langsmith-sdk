import PQueueMod from "p-queue";

// Helper to handle both default and named exports of p-queue
export const PQueue = (
  "default" in PQueueMod ? PQueueMod.default : PQueueMod
) as typeof import("p-queue").default;

export type PQueueType = InstanceType<typeof PQueue>;
