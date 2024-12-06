import { Run } from "../../schemas.js";

export function getAssumedTreeFromCalls(calls: unknown[][]) {
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
      { method: string; body: string }
    ];
    const req = `${fetchArgs.method} ${new URL(url as string).pathname}`;
    const body: Run = JSON.parse(fetchArgs.body);

    if (req === "POST /runs") {
      const id = body.id;
      upsertId(id);
      nodeMap[id] = { ...nodeMap[id], ...body };
      if (nodeMap[id].parent_run_id) {
        // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
        edges.push([nodeMap[id].parent_run_id!, nodeMap[id].id]);
      }
    } else if (req.startsWith("PATCH /runs/")) {
      const id = req.substring("PATCH /runs/".length);
      upsertId(id);
      nodeMap[id] = { ...nodeMap[id], ...body };
    }
  }

  return {
    nodes: idMap.map(getId),
    edges: edges.map(([source, target]) => [getId(source), getId(target)]),
    data: Object.fromEntries(
      Object.entries(nodeMap).map(([id, value]) => [getId(id), value] as const)
    ),
  };
}
