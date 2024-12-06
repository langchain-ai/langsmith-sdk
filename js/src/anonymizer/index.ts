import set from "../utils/lodash/set.js";

export interface StringNode {
  value: string;
  path: string;
}

function extractStringNodes(data: unknown, options: { maxDepth?: number }) {
  const parsedOptions = { ...options, maxDepth: options.maxDepth ?? 10 };

  const queue: [value: unknown, depth: number, path: string][] = [
    [data, 0, ""],
  ];

  const result: StringNode[] = [];
  while (queue.length > 0) {
    const task = queue.shift();
    if (task == null) continue;
    const [value, depth, path] = task;
    if (typeof value === "object" && value != null) {
      if (depth >= parsedOptions.maxDepth) continue;
      for (const [key, nestedValue] of Object.entries(value)) {
        queue.push([nestedValue, depth + 1, path ? `${path}.${key}` : key]);
      }
    } else if (Array.isArray(value)) {
      if (depth >= parsedOptions.maxDepth) continue;
      for (let i = 0; i < value.length; i++) {
        queue.push([value[i], depth + 1, `${path}[${i}]`]);
      }
    } else if (typeof value === "string") {
      result.push({ value, path });
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
                  memo.push({ value: newValue, path: item.path });
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
                memo.push({ value: newValue, path: item.path });
              }

              return memo;
            }, []),
        }
      : replacer;

    const toUpdate = processor.maskNodes(nodes);
    for (const node of toUpdate) {
      if (node.path === "") {
        mutateValue = node.value as unknown as T;
      } else {
        set(mutateValue as unknown as object, node.path, node.value);
      }
    }

    return mutateValue;
  };
}
