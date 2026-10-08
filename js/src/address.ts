/**
 * (beta) Addresses that name where runs are sent instead of a project.
 * Enabled per workspace; a workspace without it rejects the runs.
 *
 * An address is a plain string, `lrn:agents/{id}/environments/{environment}`,
 * typed as a template literal so a literal is checked at compile time. A
 * dynamic `string` goes through `address.parse`, which validates it at
 * runtime (JS callers are validated the same way). The environment is always
 * rendered lowercase.
 *
 * @example
 * ```ts
 * import { address, traceable } from "langsmith";
 *
 * const support = address.agent("customer-support", "production");
 * const handle = traceable(fn, { address: support });
 * // or a literal: { address: "lrn:agents/customer-support/environments/staging" }
 * ```
 */
import { getEnvironmentVariable } from "./utils/env.js";

/** (beta) An agent environment. */
export type Environment = "local" | "development" | "staging" | "production";

/** (beta) An address string, `lrn:agents/{id}/environments/{environment}`. */
export type Address = `lrn:agents/${string}/environments/${Environment}`;

// The server's agent id rule: a DNS label, so a hostname can carry the id.
const AGENT_ID_PATTERN = /^[a-z]([a-z0-9-]{0,61}[a-z0-9])?$/;
const ENVIRONMENTS: string[] = [
  "local",
  "development",
  "staging",
  "production",
];
const ADDRESS_PATTERN = /^lrn:agents\/([^/]*)\/environments\/([^/]*)$/;

const ENV_NAMES = ["LANGSMITH_AGENT_ID", "LANGSMITH_AGENT_ENVIRONMENT"];

/** The `LANGSMITH_AGENT_*` / project env vars name half an address, or both. */
export class EnvAddressError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "EnvAddressError";
  }
}

/**
 * (beta) Build the address of an agent's environment.
 * @param agentId 1 to 63 lowercase ASCII letters, digits or hyphens, starting
 *   with a letter and ending with a letter or digit.
 * @param agentEnvironment One of `local`, `development`, `staging` or
 *   `production`, in any case.
 * @throws If a value is invalid.
 */
export function agent(
  agentId: string,
  agentEnvironment: Environment | (string & {}),
): Address {
  if (typeof agentId !== "string" || !AGENT_ID_PATTERN.test(agentId)) {
    throw new Error(
      "Address agent id must be 1 to 63 lowercase ASCII letters, digits, or " +
        "hyphens, start with a letter, and end with a letter or digit, got " +
        `${JSON.stringify(agentId)}. Use an id such as "support-agent".`,
    );
  }
  const environment =
    typeof agentEnvironment === "string"
      ? agentEnvironment.toLowerCase()
      : undefined;
  if (environment === undefined || !ENVIRONMENTS.includes(environment)) {
    throw new Error(
      `Address environment must be one of ${ENVIRONMENTS.join(", ")}, got ` +
        `${JSON.stringify(agentEnvironment)}.`,
    );
  }
  return `lrn:agents/${agentId}/environments/${environment as Environment}`;
}

/**
 * (beta) Validate an address string, lowercasing its environment.
 * Only agent addresses, `lrn:agents/{id}/environments/{environment}`, exist.
 * @throws If `value` is not a valid agent address.
 */
export function parse(value: string): Address {
  const match =
    typeof value === "string" ? ADDRESS_PATTERN.exec(value) : undefined;
  if (!match) {
    throw new Error(
      "An address must be a string like " +
        `"lrn:agents/{id}/environments/{environment}", got ${JSON.stringify(value)}.`,
    );
  }
  return agent(match[1], match[2]);
}

/**
 * (beta) Read the address named by `LANGSMITH_AGENT_ID` and
 * `LANGSMITH_AGENT_ENVIRONMENT`; `undefined` if neither is set.
 * @throws {EnvAddressError} If only one is set, or a value is invalid.
 */
export function fromEnv(): Address | undefined {
  const values = ENV_NAMES.map((name) => getEnvironmentVariable(name));
  if (!values.some(Boolean)) {
    return undefined;
  }
  try {
    const missing = ENV_NAMES.filter((_, i) => !values[i]);
    if (missing.length > 0) {
      throw new Error(`An address needs ${missing.join(" and ")} as well.`);
    }
    return agent(values[0] as string, values[1] as string);
  } catch (e) {
    const present = ENV_NAMES.flatMap((name, i) =>
      values[i] ? [`${name}=${JSON.stringify(values[i])}`] : [],
    ).join(", ");
    throw new EnvAddressError(
      `The LANGSMITH_AGENT_* env vars can't address a run (${present}): ${
        (e as Error).message
      }`,
    );
  }
}

/** (beta) Build, validate and read addresses. */
export const address = { agent, parse, fromEnv };

/** @internal The `LANGSMITH_AGENT_*` env var names an address reads. */
export function envNames(): string[] {
  return ENV_NAMES;
}
