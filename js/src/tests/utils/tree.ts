import { Run } from "../../schemas.js";

export function getAssumedTreeFromCalls(calls: unknown[][]) {
  const edges: Array<[string, string]> = [];

  const nodeMap: Record<string, Run> = {};
  const idMap: { id: string; startTime: string }[] = [];

  function upsertId(id: string, startTime: string) {
    const idx = idMap.findIndex(({ id: existingId }) => id === existingId);
    if (idx < 0) {
      idMap.push({ id, startTime });
      idMap.sort((a, b) => a.startTime.localeCompare(b.startTime));
      const insertedIdx = idMap.findIndex(
        ({ id: existingId }) => id === existingId
      );
      return insertedIdx;
    }
    return idx;
  }

  function getId(id: string) {
    const order = idMap.findIndex(({ id: existingId }) => id === existingId);
    const name = nodeMap[id].name;
    return [name, order].join(":");
  }

  for (let i = 0; i < calls.length; ++i) {
    const call = calls[i];

    // Handle both old format [callable, url, init] and new format [url, init]
    const [url, fetchArgs] =
      call.length === 2
        ? (call as [string, { method: string; body: string }])
        : (call.slice(-2) as [string, { method: string; body: string }]);
    const req = `${fetchArgs.method} ${new URL(url as string).pathname}`;
    let body: Run;
    if (typeof fetchArgs.body === "string") {
      body = JSON.parse(fetchArgs.body);
    } else {
      const decoded = new TextDecoder().decode(fetchArgs.body);

      if (decoded.trim().startsWith("{")) {
        body = JSON.parse(decoded);
      }
    }

    if (req === "POST /runs") {
      const id = body!.id;
      upsertId(id, new Date(body!.start_time!).toISOString());
      nodeMap[id] = { ...nodeMap[id], ...body! };
      if (nodeMap[id].parent_run_id) {
        // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
        edges.push([nodeMap[id].parent_run_id!, nodeMap[id].id]);
      }
    } else if (req.startsWith("PATCH /runs/")) {
      const id = req.substring("PATCH /runs/".length);
      // upsertId(id);
      nodeMap[id] = { ...nodeMap[id], ...body! };
    }
  }

  // Sort edges by the start time of the target node
  const sortedEdges = edges.sort(([, targetA], [, targetB]) => {
    const targetAStartTime = nodeMap[targetA]?.start_time || "";
    const targetBStartTime = nodeMap[targetB]?.start_time || "";
    return (
      new Date(targetAStartTime).getTime() -
      new Date(targetBStartTime).getTime()
    );
  });

  return {
    nodes: idMap.map(({ id }) => getId(id)),
    edges: sortedEdges.map(([source, target]) => [
      getId(source),
      getId(target),
    ]),
    data: Object.fromEntries(
      Object.entries(nodeMap).map(([id, value]) => [getId(id), value] as const)
    ),
  };
}
