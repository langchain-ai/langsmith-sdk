/**
 * (beta) Addresses that name where runs are sent instead of a project.
 * Enabled per workspace; a workspace without it rejects the runs.
 *
 * An `Address` is anything that names a destination for runs and can render
 * itself as an LRN, a string like `lrn:agents/{id}/environments/{environment}`.
 * `Agent` is the implementation that names an agent's environment; others can
 * follow without changing the tracing API. The environment is always rendered
 * lowercase.
 *
 * Anywhere an address is accepted, an `Address` or an LRN string is. It is
 * validated once at that entry point, and only its LRN is carried from there on
 * and sent in the `address` field of the payload.
 *
 * @example
 * ```ts
 * import { Agent, traceable } from "langsmith";
 *
 * const support = new Agent("customer-support", "production");
 * const handle = traceable(fn, { address: support });
 * // or an LRN literal: { address: "lrn:agents/customer-support/environments/staging" }
 * ```
 */
import { getEnvironmentVariable } from "./utils/env.js";

/** (beta) An agent environment. */
export type Environment = "local" | "development" | "staging" | "production";

/**
 * (beta) An LRN string, `lrn:agents/{id}/environments/{environment}`, typed as
 * a template literal so a literal is checked at compile time.
 */
export type Lrn = `lrn:agents/${string}/environments/${Environment}`;

/** (beta) A destination that runs can be addressed to. */
export interface Address {
  /** This address as an LRN string. */
  toLrn(): Lrn;
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

  toLrn(): Lrn {
    return `lrn:agents/${this.id}/environments/${this.env}`;
  }

  toString(): string {
    return this.toLrn();
  }

  /**
   * Build from an agent LRN, lowercasing its environment.
   * @throws If `lrn` is not a valid agent LRN.
   */
  static parse(lrn: string): Agent {
    const match = typeof lrn === "string" ? LRN_PATTERN.exec(lrn) : null;
    if (!match) {
      throw new Error(
        "An address must be an `Address` or a string like " +
          `"lrn:agents/{id}/environments/{environment}", got ${JSON.stringify(lrn)}.`,
      );
    }
    return new Agent(match[1], match[2]);
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
    typeof (value as Address).toLrn === "function"
  );
}

/**
 * @internal Validate an `Address` or LRN string and return its normalized LRN.
 * The one place an address becomes the string the SDK carries and sends.
 * @throws If `value` is not a valid address.
 */
export function toLrn(value: unknown): Lrn {
  return Agent.parse(
    isAddress(value) ? value.toLrn() : (value as string),
  ).toLrn();
}

/**
 * @internal The LRN named by the `LANGSMITH_AGENT_*` env vars, if any.
 * @throws {EnvAddressError} If only one is set, or a value is invalid.
 */
export function lrnFromEnv(): Lrn | undefined {
  return Agent.fromEnv()?.toLrn();
}

/** @internal The `LANGSMITH_AGENT_*` env var names an address reads. */
export function envNames(): string[] {
  return ENV_NAMES;
}
