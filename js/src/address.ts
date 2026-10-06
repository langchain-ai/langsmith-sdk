/**
 * (beta) Addresses that name where runs are sent instead of a project.
 * Enabled per workspace; a workspace without it rejects the runs.
 *
 * An `Address` is anything that names a destination for runs; `Agent` is the
 * implementation that names an agent's environment, with its environment always
 * lowercase. Others can follow without changing the tracing API.
 *
 * Anywhere an address is accepted, only an `Address` is. It is validated once
 * at that entry point and carried as an `Agent` from there on. The backend's
 * identifier for it stays private to the SDK and appears only on the wire.
 *
 * @example
 * ```ts
 * import { Agent, traceable } from "langsmith";
 *
 * const support = new Agent("customer-support", "production");
 * const handle = traceable(fn, { address: support });
 * ```
 */
import { getEnvironmentVariable } from "./utils/env.js";

/** (beta) An agent environment. */
export type Environment = "local" | "development" | "staging" | "production";

/**
 * @internal The wire identifier, `lrn:agents/{id}/environments/{environment}`,
 * typed as a template literal so a literal is checked at compile time.
 */
export type Lrn = `lrn:agents/${string}/environments/${Environment}`;

/** (beta) A destination that runs can be addressed to. */
export interface Address {
  /** @internal The wire identifier; not part of the public surface. */
  _toLrn(): Lrn;
}

// The server's agent id rule: a DNS label, so a hostname can carry the id.
const AGENT_ID_PATTERN = /^[a-z]([a-z0-9-]{0,61}[a-z0-9])?$/;
const ENVIRONMENTS: string[] = [
  "local",
  "development",
  "staging",
  "production",
];
const LRN_PATTERN = /^lrn:agents\/([^/]*)\/environments\/([^/]*)$/;

const ENV_NAMES = ["LANGSMITH_AGENT_ID", "LANGSMITH_AGENT_ENVIRONMENT"];

/** The `LANGSMITH_AGENT_*` / project env vars name half an address, or both. */
export class EnvAddressError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "EnvAddressError";
  }
}

/**
 * (beta) The address of an agent's environment.
 *
 * @example
 * ```ts
 * new Agent("customer-support", "production");
 * ```
 */
export class Agent implements Address {
  readonly id: string;

  /** Always lowercase. */
  readonly env: Environment;

  /**
   * @param id 1 to 63 lowercase ASCII letters, digits or hyphens, starting
   *   with a letter and ending with a letter or digit. The server creates the
   *   agent on first use.
   * @param env One of `local`, `development`, `staging` or `production`, in
   *   any case.
   * @throws If a value is invalid.
   */
  constructor(id: string, env: Environment | (string & {})) {
    if (typeof id !== "string" || !AGENT_ID_PATTERN.test(id)) {
      throw new Error(
        "Address agent id must be 1 to 63 lowercase ASCII letters, digits, or " +
          "hyphens, start with a letter, and end with a letter or digit, got " +
          `${JSON.stringify(id)}. Use an id such as "support-agent".`,
      );
    }
    const environment = typeof env === "string" ? env.toLowerCase() : undefined;
    if (environment === undefined || !ENVIRONMENTS.includes(environment)) {
      throw new Error(
        `Address environment must be one of ${ENVIRONMENTS.join(", ")}, got ` +
          `${JSON.stringify(env)}.`,
      );
    }
    this.id = id;
    this.env = environment as Environment;
    Object.freeze(this);
  }

  /** @internal */
  _toLrn(): Lrn {
    return `lrn:agents/${this.id}/environments/${this.env}`;
  }

  /**
   * Read the agent named by `LANGSMITH_AGENT_ID` and
   * `LANGSMITH_AGENT_ENVIRONMENT`; `undefined` if neither is set.
   * @throws {EnvAddressError} If only one is set, or a value is invalid.
   */
  static fromEnv(): Agent | undefined {
    const values = ENV_NAMES.map((name) => getEnvironmentVariable(name));
    if (!values.some(Boolean)) {
      return undefined;
    }
    try {
      const missing = ENV_NAMES.filter((_, i) => !values[i]);
      if (missing.length > 0) {
        throw new Error(`An address needs ${missing.join(" and ")} as well.`);
      }
      return new Agent(values[0] as string, values[1] as string);
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
}

function isAddress(value: unknown): value is Address {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as Address)._toLrn === "function"
  );
}

/**
 * @internal Build an `Agent` from a wire LRN, lowercasing its environment.
 * @throws If `lrn` is not a valid agent LRN.
 */
export function agentFromLrn(lrn: unknown): Agent {
  const match = typeof lrn === "string" ? LRN_PATTERN.exec(lrn) : null;
  if (!match) {
    throw new Error("The address is not a valid agent address.");
  }
  return new Agent(match[1], match[2]);
}

/**
 * @internal Validate an `Address` and return it as a normalized `Agent`: frozen,
 * with a lowercase environment. Strings are rejected.
 * @throws If `value` is not a valid address.
 */
export function checkedAddress(value: unknown): Agent {
  if (!isAddress(value)) {
    throw new Error(
      "address must be an Address such as `new Agent(id, env)`, got " +
        `${typeof value === "string" ? JSON.stringify(value) : typeof value}.`,
    );
  }
  // A custom Address renders an LRN; read it back as an Agent.
  return agentFromLrn(value._toLrn());
}

/** @internal The `LANGSMITH_AGENT_*` env var names an address reads. */
export function envNames(): string[] {
  return ENV_NAMES;
}
