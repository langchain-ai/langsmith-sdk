/**
 * (beta) Addresses that name where runs are sent instead of a project.
 * Enabled per workspace; a workspace without it rejects the runs.
 *
 * An `Address` names a tracing project held by a feature: an `Agent`, an
 * `Experiment` or the workspace's `Evaluator`s. Any of them can be resolved to
 * its project. Only an `Agent` can receive traces, and ingestion rejects the
 * others at its entry points.
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

/** The backend's form of an address, as the resolve endpoint takes it. */
export type ApiAddress = {
  kind: "AGENT" | "EXPERIMENT" | "EVALUATOR";
  id?: string;
  environment?: string;
};

/** (beta) A feature that holds traces in a tracing project. */
export interface Address {
  /** The address in the backend's form. */
  toApiAddress(): ApiAddress;
}

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// The server's agent id rule: a DNS label, so a hostname can carry the id.
const AGENT_ID_PATTERN = /^[a-z]([a-z0-9-]{0,61}[a-z0-9])?$/;
const ENVIRONMENTS: string[] = [
  "local",
  "development",
  "staging",
  "production",
];

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

  toApiAddress(): ApiAddress {
    return {
      kind: "AGENT",
      id: this.id,
      environment: this.env.toUpperCase(),
    };
  }

  /** @internal */
  _toLrn(): Lrn {
    return `lrn:agents/${this.id}/environments/${this.env}`;
  }

  /** @internal */
  _toFields(): Record<string, string> {
    return { agent_id: this.id, agent_environment: this.env };
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

/** (beta) The address of an experiment's tracing project. */
export class Experiment implements Address {
  /** Always lowercase. */
  readonly id: string;

  /**
   * @param id The experiment's UUID.
   * @throws If `id` is not a UUID.
   */
  constructor(id: string) {
    if (typeof id !== "string" || !UUID_PATTERN.test(id)) {
      throw new Error(
        `Experiment id must be a UUID, got ${JSON.stringify(id)}.`,
      );
    }
    this.id = id.toLowerCase();
    Object.freeze(this);
  }

  toApiAddress(): ApiAddress {
    return { kind: "EXPERIMENT", id: this.id };
  }
}

/** (beta) The address of the workspace's shared evaluators project. */
export class Evaluator implements Address {
  constructor() {
    Object.freeze(this);
  }

  toApiAddress(): ApiAddress {
    return { kind: "EVALUATOR" };
  }
}

/**
 * @internal The ingestion entry-point guard: `value` must be an `Agent` (or
 * absent), and is returned as is. Other addresses and strings are rejected.
 * @throws If `value` is not an `Agent`.
 */
export function ensureAgent(value: unknown): Agent | undefined {
  if (value == null) {
    return undefined;
  }
  if (value instanceof Agent) {
    return value;
  }
  if (
    typeof value === "object" &&
    typeof (value as Address).toApiAddress === "function"
  ) {
    throw new Error(
      `Only an Agent can receive traces, got ${
        (value as object).constructor?.name ?? "an unknown address"
      }.`,
    );
  }
  throw new Error(
    "address must be an Agent such as `new Agent(id, env)`, got " +
      `${typeof value === "string" ? JSON.stringify(value) : typeof value}.`,
  );
}

/**
 * @internal Rebuild an address from its header fields; only the fields it
 * knows are read.
 * @returns `undefined` if there are no fields.
 * @throws If the fields are half-present or invalid.
 */
export function addressFromFields(
  fields: Record<string, unknown>,
): Agent | undefined {
  const { agent_id: id, agent_environment: env } = fields;
  if (id == null && env == null) {
    return undefined;
  }
  if (id == null || env == null) {
    throw new Error("The address fields are incomplete.");
  }
  return new Agent(id as string, env as string);
}

/** @internal The `LANGSMITH_AGENT_*` env var names an address reads. */
export function envNames(): string[] {
  return ENV_NAMES;
}
