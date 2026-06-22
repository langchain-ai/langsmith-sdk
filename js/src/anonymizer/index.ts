import { serialize as serializePayloadForTracing } from "../utils/fast-safe-stringify/index.js";

const textDecoder = new TextDecoder();

export interface StringNode {
  value: string;
  path: string;
}

interface StringNodeInternal extends StringNode {
  // Unique identity for matching after maskNodes processing.
  _id: number;
  // Internal path segments from the original traversal. This lets us apply
  // updates to a clone without parsing the public dotted path string.
  pathParts: string[];
}

function extractStringNodes(data: unknown, options: { maxDepth?: number }) {
  const parsedOptions = { ...options, maxDepth: options.maxDepth ?? 10 };
  const seen = new WeakSet<object>();

  const queue: [
    value: unknown,
    depth: number,
    path: string,
    pathParts: string[],
  ][] = [[data, 0, "", []]];

  let nextId = 0;
  const result: StringNodeInternal[] = [];
  let queueIndex = 0;
  while (queueIndex < queue.length) {
    const task = queue[queueIndex++];
    if (task == null) continue;
    const [value, depth, path, pathParts] = task;
    if (typeof value === "string") {
      result.push({
        value,
        path,
        _id: nextId++,
        pathParts,
      });
    } else if (Array.isArray(value)) {
      if (depth >= parsedOptions.maxDepth) continue;
      if (seen.has(value)) continue;
      seen.add(value);
      for (let i = 0; i < value.length; i++) {
        queue.push([
          value[i],
          depth + 1,
          `${path}[${i}]`,
          [...pathParts, String(i)],
        ]);
      }
    } else if (typeof value === "object" && value != null) {
      if (depth >= parsedOptions.maxDepth) continue;
      if (seen.has(value)) continue;
      seen.add(value);
      for (const [k, nestedValue] of Object.entries(value)) {
        queue.push([
          nestedValue,
          depth + 1,
          path ? `${path}.${k}` : k,
          [...pathParts, k],
        ]);
      }
    }
  }

  return result;
}

function deepClone<T>(data: T): T {
  return JSON.parse(textDecoder.decode(serializePayloadForTracing(data)));
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

// ── Combined-alternation optimization ─────────────────────────────────────
// When a rule set contains many patterns that all share the same replacement
// string and don't use capture groups, we can combine them into a single
// alternation regex: `(?:pat1|pat2|pat3|...)`. This lets the engine do one
// pass over the string instead of N, reducing per-string overhead from N
// replace() calls to 1.
//
// For the secret anonymizer, we go further: instead of parsing the serialized
// JSON, walking the object tree to extract string nodes, running regex per
// node, and walking the tree again to apply updates, we run the combined
// regex directly on the serialized JSON string and parse once at the end.
// This eliminates extractStringNodes, applyUpdateAtPath, and the intermediate
// JSON.parse entirely.

type SimpleRule = { source: string; flags: string; replace: string };
type StructuralRule = { regex: RegExp; replace: string };

function partitionRules(
  rules: StringNodeRule[],
): { simple: Map<string, SimpleRule[]>; structural: StructuralRule[] } {
  const simple = new Map<string, SimpleRule[]>();
  const structural: StructuralRule[] = [];

  for (const { pattern, type, replace } of rules) {
    if (type != null && type !== "pattern")
      throw new Error("Invalid anonymizer type");
    const re = typeof pattern === "string" ? new RegExp(pattern, "g") : pattern;
    const repl = replace ?? "[redacted]";
    // A rule is "simple" if its replacement is a plain string with no $-refs
    // AND the pattern has no capture groups (so alternation won't shift
    // group indices).
    const hasGroupRef = /\$[1-9]/.test(repl);
    const hasCaptureGroup = /\((?!\?[:=!]|<)/.test(re.source);
    if (hasGroupRef || hasCaptureGroup) {
      structural.push({ regex: re, replace: repl });
    } else {
      const key = repl;
      let group = simple.get(key);
      if (!group) {
        group = [];
        simple.set(key, group);
      }
      group.push({ source: re.source, flags: re.flags, replace: repl });
    }
  }
  return { simple, structural };
}

function combineSimpleRules(
  groups: Map<string, SimpleRule[]>,
): { regex: RegExp; replace: string }[] {
  const result: { regex: RegExp; replace: string }[] = [];
  for (const [replace, group] of groups) {
    // All patterns in a group should have compatible flags. We use the
    // union of flags seen. In practice the secret rules all use "g" or
    // "gi", and combining is safe.
    const flagSet = new Set<string>();
    for (const { flags } of group) {
      for (const f of flags) flagSet.add(f);
    }
    const combinedFlags = [...flagSet].join("");
    const combined = group.map(({ source }) => `(?:${source})`).join("|");
    result.push({ regex: new RegExp(combined, combinedFlags), replace });
  }
  return result;
}

function createRuleNodeProcessor(
  rules: StringNodeRule[],
  options?: { prefilter?: (value: string) => boolean },
): StringNodeProcessor {
  const { simple, structural } = partitionRules(rules);
  const combined = combineSimpleRules(simple);
  const allReplacers: { regex: RegExp; replace: string }[] = [
    ...combined,
    ...structural,
  ];

  if (allReplacers.length === 0) throw new Error("No replacers provided");

  return {
    maskNodes: (nodes: StringNode[]) => {
      return nodes.reduce<StringNode[]>((memo, item) => {
        if (options?.prefilter != null && !options.prefilter(item.value)) {
          return memo;
        }

        const newValue = allReplacers.reduce((value, { regex, replace }) => {
          const result = value.replace(regex, replace);
          // Reset lastIndex for stateful (global) regexes.
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
}

function getNodeProcessor(replacer: ReplacerType): StringNodeProcessor {
  return Array.isArray(replacer)
    ? createRuleNodeProcessor(replacer)
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
}

function applyUpdateAtPath<T>(
  root: T,
  pathParts: string[],
  value: string,
): void {
  let target = root as Record<string, unknown>;
  for (const part of pathParts.slice(0, -1)) {
    const next = target[part];
    if (typeof next !== "object" || next == null) {
      return;
    }
    target = next as Record<string, unknown>;
  }
  target[pathParts[pathParts.length - 1]] = value;
}

function applyProcessor<T>(
  mutateValue: T,
  processor: StringNodeProcessor,
  options?: { maxDepth?: number },
): T {
  const nodes = extractStringNodes(mutateValue, {
    maxDepth: options?.maxDepth,
  });
  if (nodes.length === 0) {
    return mutateValue;
  }

  const toUpdate = processor.maskNodes(nodes);
  if (toUpdate.length === 0) {
    return mutateValue;
  }

  const nodesById = new Map<number, StringNodeInternal>();
  const nodesByPath = new Map<string, StringNodeInternal>();
  for (const node of nodes) {
    nodesById.set(node._id, node);
    nodesByPath.set(node.path, node);
  }

  for (const node of toUpdate) {
    if (node.path === "") {
      mutateValue = node.value as unknown as T;
    } else {
      const asInternal = node as Partial<StringNodeInternal>;
      const internal =
        asInternal._id !== undefined
          ? nodesById.get(asInternal._id)
          : nodesByPath.get(node.path);
      if (internal) {
        applyUpdateAtPath(mutateValue, internal.pathParts, node.value);
      }
    }
  }

  return mutateValue;
}

export function createAnonymizer(
  replacer: ReplacerType,
  options?: { maxDepth?: number },
) {
  const processor = getNodeProcessor(replacer);

  return <T>(data: T): T => {
    return applyProcessor(deepClone(data), processor, options);
  };
}

/**
 * Replacement token written in place of detected secrets by
 * {@link DEFAULT_SECRET_RULES} / {@link createSecretAnonymizer}.
 */
export const SECRET_PLACEHOLDER = "[SECRET_DETECTED]";

/**
 * A curated, high-precision rule set for detecting common credentials in
 * traced data (prompts, tool inputs/outputs, file contents, shell commands).
 *
 * Designed to favor *low false positives* over exhaustive coverage:
 *  - All rules are prefix-anchored to well-known token shapes (provider key
 *    formats, JWT structure, PEM armor). No contextual/heuristic patterns.
 *  - No "KEY=value" or "Authorization: Bearer" structural rules — those
 *    generated false positives and couldn't be combined into a single regex.
 *
 * This is NOT a port of gitleaks/secretlint; pattern shapes are drawn from
 * those projects (and provider docs) as a reference only. Every rule sets an
 * explicit `replace` because {@link createAnonymizer}'s default is
 * `[redacted]`, whereas the shared token here is {@link SECRET_PLACEHOLDER}.
 *
 * Patterns are written to port 1:1 to the Python SDK preset (no lookbehind).
 */
export const DEFAULT_SECRET_RULES: StringNodeRule[] = [
  // ── Provider API keys (prefix-anchored) ─────────────────────────────────
  // Anthropic
  { pattern: /\bsk-ant-[A-Za-z0-9_-]{20,}(?![A-Za-z0-9_-])/g, replace: SECRET_PLACEHOLDER },
  // OpenAI: project / service-account / admin keys, then legacy `sk-...`
  {
    pattern: /\bsk-(?:proj|svcacct|admin)-[A-Za-z0-9_-]{20,}(?![A-Za-z0-9_-])/g,
    replace: SECRET_PLACEHOLDER,
  },
  { pattern: /\bsk-[A-Za-z0-9]{32,}(?![A-Za-z0-9])/g, replace: SECRET_PLACEHOLDER },
  // LangSmith (keys are multi-segment: lsv2_pt_<key>_<tail> — match the
  // full underscore-delimited tail so none of it leaks past the placeholder)
  {
    pattern: /\blsv2_(?:pt|sk)_[A-Za-z0-9]{32,}(?:_[A-Za-z0-9]+)*(?![A-Za-z0-9_])/g,
    replace: SECRET_PLACEHOLDER,
  },
  { pattern: /\bls__[A-Za-z0-9]{16,}(?![A-Za-z0-9])/g, replace: SECRET_PLACEHOLDER },
  // GitHub personal access / app tokens
  { pattern: /\bgh[pousr]_[A-Za-z0-9]{36,}(?![A-Za-z0-9])/g, replace: SECRET_PLACEHOLDER },
  { pattern: /\bgithub_pat_[A-Za-z0-9_]{82}(?![A-Za-z0-9_])/g, replace: SECRET_PLACEHOLDER },
  // GitLab personal access token
  { pattern: /\bglpat-[A-Za-z0-9_-]{20,}(?![A-Za-z0-9_-])/g, replace: SECRET_PLACEHOLDER },
  // AWS access key id (covers AKIA/ASIA/ABIA/ACCA/A3T* prefixes)
  {
    pattern: /\b(?:AKIA|ASIA|ABIA|ACCA|A3T[A-Z0-9])[0-9A-Z]{16}\b/g,
    replace: SECRET_PLACEHOLDER,
  },
  // Google API key + OAuth access token
  { pattern: /\bAIza[0-9A-Za-z_-]{35}(?![0-9A-Za-z_-])/g, replace: SECRET_PLACEHOLDER },
  { pattern: /\bya29\.[0-9A-Za-z_-]+(?![0-9A-Za-z_-])/g, replace: SECRET_PLACEHOLDER },
  // Slack tokens (bot/user + app-level) + incoming webhooks
  { pattern: /\bxox[baprs]-[A-Za-z0-9-]{10,}(?![A-Za-z0-9-])/g, replace: SECRET_PLACEHOLDER },
  { pattern: /\bxapp-\d-[A-Za-z0-9-]{10,}(?![A-Za-z0-9-])/g, replace: SECRET_PLACEHOLDER },
  {
    pattern: /\bhttps:\/\/hooks\.slack\.com\/services\/[A-Za-z0-9/]+(?![A-Za-z0-9/])/g,
    replace: SECRET_PLACEHOLDER,
  },
  // Stripe
  {
    pattern: /\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{20,}\b/g,
    replace: SECRET_PLACEHOLDER,
  },
  // npm
  { pattern: /\bnpm_[A-Za-z0-9]{36}(?![A-Za-z0-9])/g, replace: SECRET_PLACEHOLDER },
  // PyPI upload token
  {
    pattern: /\bpypi-AgEIcHlwaS[A-Za-z0-9_-]{50,}(?![A-Za-z0-9_-])/g,
    replace: SECRET_PLACEHOLDER,
  },
  // SendGrid
  {
    pattern: /\bSG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])/g,
    replace: SECRET_PLACEHOLDER,
  },

  // ── Structured tokens ────────────────────────────────────────────────────
  // JWT (header.payload.signature)
  {
    pattern: /\beyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+(?![A-Za-z0-9_-])/g,
    replace: SECRET_PLACEHOLDER,
  },
  // PEM private key blocks (RSA/EC/OPENSSH/DSA/plain + PGP "...KEY BLOCK")
  {
    pattern:
      /-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY(?: BLOCK)?-----[\s\S]+?-----END (?:[A-Z0-9 ]+ )?PRIVATE KEY(?: BLOCK)?-----/g,
    replace: SECRET_PLACEHOLDER,
  },
];

const SECRET_RULE_PREFILTER = new RegExp(
  [
    "sk-",
    "lsv2_",
    "ls__",
    "gh[pousr]_",
    "github_pat_",
    "glpat-",
    "AKIA",
    "ASIA",
    "ABIA",
    "ACCA",
    "A3T[A-Z0-9]",
    "AIza",
    "ya29\\.",
    "xox[baprs]-",
    "xapp-\\d-",
    "hooks\\.slack\\.com/services",
    "(?:sk|rk)_(?:live|test)_",
    "npm_",
    "pypi-AgEIcHlwaS",
    "SG\\.",
    "eyJ",
    "-----BEGIN",
  ].join("|"),
  "i",
);

function mayContainSecret(value: string): boolean {
  return SECRET_RULE_PREFILTER.test(value);
}

/**
 * Build an anonymizer pre-loaded with {@link DEFAULT_SECRET_RULES} suitable for
 * passing to `new Client({ anonymizer })`. It redacts detected secrets from run
 * inputs, outputs, and metadata client-side, before they are uploaded.
 *
 * @param options.extraRules - Additional rules appended after the defaults.
 * @param options.maxDepth - Max recursion depth (default 24; higher than
 *   `createAnonymizer`'s default of 10 because traced payloads nest deeply,
 *   e.g. `messages[].content[].args`).
 *
 * @example
 * ```ts
 * import { Client } from "langsmith";
 * import { createSecretAnonymizer } from "langsmith/anonymizer";
 *
 * const client = new Client({ anonymizer: createSecretAnonymizer() });
 * ```
 */
export function createSecretAnonymizer(options?: {
  extraRules?: StringNodeRule[];
  maxDepth?: number;
}) {
  const extraRules = options?.extraRules ?? [];
  const maxDepth = options?.maxDepth ?? 24;

  if (extraRules.length > 0) {
    // When extra rules are provided, fall back to the node-based pipeline
    // because extra rules may have capture groups or different replacements.
    const processor = createRuleNodeProcessor([
      ...DEFAULT_SECRET_RULES,
      ...extraRules,
    ]);
    return <T>(data: T): T => {
      const serialized = textDecoder.decode(serializePayloadForTracing(data));
      return applyProcessor(JSON.parse(serialized), processor, { maxDepth });
    };
  }

  // Default path: all rules are "simple" (no capture groups, same replacement).
  // Build one combined regex and run it directly on the serialized JSON string.
  const { simple, structural } = partitionRules(DEFAULT_SECRET_RULES);
  // All default rules are simple (no structural rules remain).
  const combined = combineSimpleRules(simple);
  // One regex, one replacement — run on the whole serialized string.
  const replacers = [...combined, ...structural];

  return <T>(data: T): T => {
    const serialized = textDecoder.decode(serializePayloadForTracing(data));
    if (!mayContainSecret(serialized)) {
      return data;
    }
    const redacted = replacers.reduce(
      (s, { regex, replace }) => s.replace(regex, replace),
      serialized,
    );
    return JSON.parse(redacted) as T;
  };
}
