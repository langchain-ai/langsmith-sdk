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

function createRuleNodeProcessor(
  rules: StringNodeRule[],
  options?: { prefilter?: (value: string) => boolean },
): StringNodeProcessor {
  const replacers: [regex: RegExp, replace: string][] = rules.map(
    ({ pattern, type, replace }) => {
      if (type != null && type !== "pattern")
        throw new Error("Invalid anonymizer type");
      return [
        typeof pattern === "string" ? new RegExp(pattern, "g") : pattern,
        replace ?? "[redacted]",
      ];
    },
  );

  if (replacers.length === 0) throw new Error("No replacers provided");
  return {
    maskNodes: (nodes: StringNode[]) => {
      return nodes.reduce<StringNode[]>((memo, item) => {
        if (options?.prefilter != null && !options.prefilter(item.value)) {
          return memo;
        }

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
 *  - Provider rules are anchored to well-known key prefixes.
 *  - Structural rules only fire when a sensitive *name* (api_key, token,
 *    password, …) is paired with an assignment/separator, so ordinary code,
 *    UUIDs, and hashes are left intact.
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
  { pattern: /sk-ant-[A-Za-z0-9_-]{20,}/g, replace: SECRET_PLACEHOLDER },
  // OpenAI: project / service-account / admin keys, then legacy `sk-...`
  {
    pattern: /sk-(?:proj|svcacct|admin)-[A-Za-z0-9_-]{20,}/g,
    replace: SECRET_PLACEHOLDER,
  },
  { pattern: /sk-[A-Za-z0-9]{32,}/g, replace: SECRET_PLACEHOLDER },
  // LangSmith (keys are multi-segment: lsv2_pt_<key>_<tail> — match the
  // full underscore-delimited tail so none of it leaks past the placeholder)
  {
    pattern: /lsv2_(?:pt|sk)_[A-Za-z0-9]{32,}(?:_[A-Za-z0-9]+)*/g,
    replace: SECRET_PLACEHOLDER,
  },
  { pattern: /ls__[A-Za-z0-9]{16,}/g, replace: SECRET_PLACEHOLDER },
  // GitHub personal access / app tokens
  { pattern: /gh[pousr]_[A-Za-z0-9]{36,}/g, replace: SECRET_PLACEHOLDER },
  { pattern: /github_pat_[A-Za-z0-9_]{82}/g, replace: SECRET_PLACEHOLDER },
  // GitLab personal access token
  { pattern: /glpat-[A-Za-z0-9_-]{20,}/g, replace: SECRET_PLACEHOLDER },
  // AWS access key id (covers AKIA/ASIA/ABIA/ACCA/A3T* prefixes)
  {
    pattern: /\b(?:AKIA|ASIA|ABIA|ACCA|A3T[A-Z0-9])[0-9A-Z]{16}\b/g,
    replace: SECRET_PLACEHOLDER,
  },
  // Google API key + OAuth access token
  { pattern: /AIza[0-9A-Za-z_-]{35}/g, replace: SECRET_PLACEHOLDER },
  { pattern: /ya29\.[0-9A-Za-z_-]+/g, replace: SECRET_PLACEHOLDER },
  // Slack tokens (bot/user + app-level) + incoming webhooks
  { pattern: /xox[baprs]-[A-Za-z0-9-]{10,}/g, replace: SECRET_PLACEHOLDER },
  { pattern: /xapp-\d-[A-Za-z0-9-]{10,}/g, replace: SECRET_PLACEHOLDER },
  {
    pattern: /https:\/\/hooks\.slack\.com\/services\/[A-Za-z0-9/]+/g,
    replace: SECRET_PLACEHOLDER,
  },
  // Stripe
  {
    pattern: /\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{20,}\b/g,
    replace: SECRET_PLACEHOLDER,
  },
  // npm
  { pattern: /npm_[A-Za-z0-9]{36}/g, replace: SECRET_PLACEHOLDER },
  // PyPI upload token
  {
    pattern: /pypi-AgEIcHlwaS[A-Za-z0-9_-]{50,}/g,
    replace: SECRET_PLACEHOLDER,
  },
  // SendGrid
  {
    pattern: /SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}/g,
    replace: SECRET_PLACEHOLDER,
  },

  // ── Structured tokens ────────────────────────────────────────────────────
  // JWT (header.payload.signature)
  {
    pattern: /eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g,
    replace: SECRET_PLACEHOLDER,
  },
  // PEM private key blocks (RSA/EC/OPENSSH/DSA/plain + PGP "...KEY BLOCK")
  {
    pattern:
      /-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY(?: BLOCK)?-----[\s\S]+?-----END (?:[A-Z0-9 ]+ )?PRIVATE KEY(?: BLOCK)?-----/g,
    replace: SECRET_PLACEHOLDER,
  },

  // ── Structural / contextual (sensitive NAME + assignment) ─────────────────
  // KEY=value or "key": "value" where the name looks sensitive. Keep the name
  // and separator ($1), redact the value. Notes:
  //  - (?![A-Za-z0-9]) after the keyword requires a component boundary, so
  //    `token` matches `api_token`/`mytoken` but NOT `tokenizer`/`tokens`.
  //  - the value may start with an auth scheme word (Bearer/Token/Basic) so a
  //    `X-Api-Key: Bearer <tok>` shape redacts the credential, not just "Bearer".
  //  - value excludes & and ; so query-string params past the secret survive.
  //  - requires a 6+ char value so short non-secret values are not touched.
  {
    pattern:
      /\b([A-Za-z0-9_.-]*(?:API[_-]?KEY|SECRET|TOKEN|PASSWORD|PASSWD|PRIVATE[_-]?KEY|ACCESS[_-]?KEY|AUTH[_-]?TOKEN|CLIENT[_-]?SECRET)(?![A-Za-z0-9])(?:[_.-][A-Za-z0-9]+)*["']?\s*[:=]\s*["']?)(?:(?:bearer|token|basic)\s+)?[^\s"'&;]{6,}/gi,
    replace: `$1${SECRET_PLACEHOLDER}`,
  },
  // Authorization / API-key headers. Keep the header name + separator ($1$2)
  // and an optional scheme ($3); redact the credential.
  {
    pattern:
      /\b(authorization|x-api-key|x-auth-token)(["']?\s*[:=]\s*["']?)(bearer\s+|token\s+|basic\s+)?[A-Za-z0-9._~+/-]{8,}=*/gi,
    replace: `$1$2$3${SECRET_PLACEHOLDER}`,
  },
  // Bare "Bearer <token>" (any case; the scheme word is preserved via $1).
  {
    pattern: /\b(Bearer\s+)[A-Za-z0-9._~+/-]{10,}=*/gi,
    replace: `$1${SECRET_PLACEHOLDER}`,
  },
  // Credentials embedded in URLs: proto://user:PASS@host -> redact PASS only.
  // Username is optional so proto://:PASS@host (empty user) is still covered.
  {
    pattern: /\b([a-z][a-z0-9+.-]*:\/\/[^:@/\s]*:)[^@/\s]+(@)/gi,
    replace: `$1${SECRET_PLACEHOLDER}$2`,
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
    "api[_-]?key",
    "secret",
    "token",
    "password",
    "passwd",
    "private[_-]?key",
    "access[_-]?key",
    "auth[_-]?token",
    "client[_-]?secret",
    "authorization",
    "x-api-key",
    "x-auth-token",
    "bearer",
    "basic",
    "[a-z][a-z0-9+.-]*://[^:@/\\s]*:",
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
  const processor =
    extraRules.length > 0
      ? createRuleNodeProcessor([...DEFAULT_SECRET_RULES, ...extraRules])
      : createRuleNodeProcessor(DEFAULT_SECRET_RULES, {
          prefilter: mayContainSecret,
        });
  const maxDepth = options?.maxDepth ?? 24;
  return <T>(data: T): T => {
    const serialized = textDecoder.decode(serializePayloadForTracing(data));
    if (extraRules.length === 0 && !mayContainSecret(serialized)) {
      return data;
    }
    return applyProcessor(JSON.parse(serialized), processor, { maxDepth });
  };
}
