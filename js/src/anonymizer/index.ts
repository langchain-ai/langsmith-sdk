export interface StringNode {
  value: string;
  path: string;
}

interface StringNodeInternal extends StringNode {
  // Direct reference to the parent object and key, so we can write back
  // without path parsing/traversal (avoids prototype pollution entirely).
  parent: Record<string, unknown>;
  key: string;
  // Unique identity for matching after maskNodes processing.
  _id: number;
}

function extractStringNodes(data: unknown, options: { maxDepth?: number }) {
  const parsedOptions = { ...options, maxDepth: options.maxDepth ?? 10 };

  const queue: [
    value: unknown,
    depth: number,
    path: string,
    parent: Record<string, unknown> | null,
    key: string
  ][] = [[data, 0, "", null, ""]];

  let nextId = 0;
  const result: StringNodeInternal[] = [];
  while (queue.length > 0) {
    const task = queue.shift();
    if (task == null) continue;
    const [value, depth, path, parent, key] = task;
    if (typeof value === "string") {
      result.push({
        value,
        path,
        parent: parent as Record<string, unknown>,
        key,
        _id: nextId++,
      });
    } else if (Array.isArray(value)) {
      if (depth >= parsedOptions.maxDepth) continue;
      for (let i = 0; i < value.length; i++) {
        queue.push([
          value[i],
          depth + 1,
          `${path}[${i}]`,
          value as unknown as Record<string, unknown>,
          String(i),
        ]);
      }
    } else if (typeof value === "object" && value != null) {
      if (depth >= parsedOptions.maxDepth) continue;
      for (const [k, nestedValue] of Object.entries(value)) {
        queue.push([
          nestedValue,
          depth + 1,
          path ? `${path}.${k}` : k,
          value as Record<string, unknown>,
          k,
        ]);
      }
    }
  }

  return result;
}

function deepClone<T>(data: T): T {
  return JSON.parse(JSON.stringify(data));
}

export interface StringNodeProcessor {
  maskNodes: (nodes: StringNode[]) => StringNode[];
}

export interface StringNodeRule {
  type?: "pattern";
  pattern: RegExp | string;
  replace?: string;
}

export type ReplacerType =
  | ((value: string, path?: string) => string)
  | StringNodeRule[]
  | StringNodeProcessor;

export function createAnonymizer(
  replacer: ReplacerType,
  options?: { maxDepth?: number }
) {
  return <T>(data: T): T => {
    let mutateValue = deepClone(data);
    const nodes = extractStringNodes(mutateValue, {
      maxDepth: options?.maxDepth,
    });

    const processor: StringNodeProcessor = Array.isArray(replacer)
      ? (() => {
          const replacers: [regex: RegExp, replace: string][] = replacer.map(
            ({ pattern, type, replace }) => {
              if (type != null && type !== "pattern")
                throw new Error("Invalid anonymizer type");
              return [
                typeof pattern === "string"
                  ? new RegExp(pattern, "g")
                  : pattern,
                replace ?? "[redacted]",
              ];
            }
          );

          if (replacers.length === 0) throw new Error("No replacers provided");
          return {
            maskNodes: (nodes: StringNode[]) => {
              return nodes.reduce<StringNode[]>((memo, item) => {
                const newValue = replacers.reduce((value, [regex, replace]) => {
                  const result = value.replace(regex, replace);

                  // make sure we reset the state of regex
                  regex.lastIndex = 0;

                  return result;
                }, item.value);

                if (newValue !== item.value) {
                  memo.push({ ...item, value: newValue });
                }

                return memo;
              }, []);
            },
          };
        })()
      : typeof replacer === "function"
      ? {
          maskNodes: (nodes: StringNode[]) =>
            nodes.reduce<StringNode[]>((memo, item) => {
              const newValue = replacer(item.value, item.path);
              if (newValue !== item.value) {
                memo.push({ ...item, value: newValue });
              }

              return memo;
            }, []),
        }
      : replacer;

    // Build a lookup from _id to internal node for direct write-back.
    const nodesById = new Map<number, StringNodeInternal>();
    for (const node of nodes) {
      nodesById.set(node._id, node);
    }

    const toUpdate = processor.maskNodes(nodes);
    for (const node of toUpdate) {
      if (node.path === "") {
        mutateValue = node.value as unknown as T;
      } else {
        // Match by _id if available (built-in replacers propagate it from
        // the input nodes), otherwise fall back to path matching.
        const asInternal = node as Partial<StringNodeInternal>;
        const internal =
          asInternal._id !== undefined
            ? nodesById.get(asInternal._id)
            : nodes.find((n) => n.path === node.path);
        if (internal) {
          internal.parent[internal.key] = node.value;
        }
      }
    }

    return mutateValue;
  };
}
