import { Run } from "../../schemas.js";
import { Client } from "../../client.js";

export async function getAssumedTreeFromCalls(
  calls: unknown[][],
  client: Client,
): Promise<{
  nodes: string[];
  edges: Array<[string, string]>;
  data: Record<string, Run>;
}> {
  await client.awaitPendingTraceBatches();

  const edges: Array<[string, string]> = [];

  const nodeMap: Record<string, Run> = {};
  const idMap: string[] = [];

  function upsertId(id: string) {
    const idx = idMap.indexOf(id);
    if (idx < 0) {
      idMap.push(id);
      return idMap.length - 1;
    }
    return idx;
  }

  function getId(id: string) {
    const stableId = upsertId(id);

    const name = nodeMap[id].name;
    return [name, stableId].join(":");
  }

  for (let i = 0; i < calls.length; ++i) {
    const call = calls[i];

    const [url, fetchArgs] = call.slice(-2) as [
      string,
      { method: string; body: string },
    ];
    const { method } = fetchArgs;
    // The API base URL carries a different prefix per deployment ("" on beta,
    // "/api" on self-hosted, "/api/v1" elsewhere), so match on the endpoint
    // suffix rather than the whole pathname.
    const pathname = new URL(url as string).pathname;
    const createRun = method === "POST" && /(?:^|\/)runs$/.test(pathname);
    const updateRun =
      method === "PATCH" && /(?:^|\/)runs\/[^/]+$/.test(pathname);
    let body: Run;
    if (typeof fetchArgs.body === "string") {
      body = JSON.parse(fetchArgs.body);
    } else {
      const decoded = new TextDecoder().decode(fetchArgs.body);
      if (decoded.trim().startsWith("{")) {
        body = JSON.parse(decoded);
      }
    }

    if (createRun) {
      const id = body!.id;
      upsertId(id);
      nodeMap[id] = { ...nodeMap[id], ...body! };
      if (nodeMap[id].parent_run_id) {
        // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
        edges.push([nodeMap[id].parent_run_id!, nodeMap[id].id]);
      }
    } else if (updateRun) {
      const id = pathname.slice(pathname.lastIndexOf("/") + 1);
      upsertId(id);
      nodeMap[id] = { ...nodeMap[id], ...body! };
    }
  }

  return {
    nodes: idMap.map(getId),
    edges: edges.map(([source, target]) => [getId(source), getId(target)]),
    data: Object.fromEntries(
      Object.entries(nodeMap).map(([id, value]) => [getId(id), value] as const),
    ),
  };
}

type MagicRunResult = {
  name: string;
  [key: string]: unknown;
};

type MagicRun = (
  rawName: TemplateStringsArray,
) => (props: Record<string, unknown>, ...children: string[]) => string;

export function asTree(cb: (run: MagicRun) => void): {
  nodes: string[];
  edges: Array<[string, string]>;
  data: Record<string, unknown>;
} {
  const acc: {
    nodes: string[];
    edges: Array<[string, string]>;
    data: Record<string, MagicRunResult>;
  } = { nodes: [], edges: [], data: {} };

  function run(rawId: TemplateStringsArray) {
    const id = rawId.join("");
    const name = id.split(":")[0];

    acc.nodes.push(id);
    return (props: Record<string, unknown>, ...children: string[]): string => {
      for (const childId of children) acc.edges.push([id, childId]);
      acc.data[id] = { name, ...props };
      return id;
    };
  }

  cb(run);
  const nodeOrder = new Map(acc.nodes.map((id, idx) => [id, idx]));

  return {
    ...acc,
    edges: [...acc.edges].sort(
      ([, left], [, right]) =>
        (nodeOrder.get(left) ?? 0) - (nodeOrder.get(right) ?? 0),
    ),
  };
}
