/**
 * A handle that names where runs are sent.
 *
 * Experimental: addressing runs is in beta and enabled per workspace. A
 * workspace without it rejects the runs, so tracing is lost rather than
 * falling back to a project. This API may change without notice.
 *
 * The handle is propagated whole -- through run trees, replicas and
 * distributed-tracing headers -- and only unpacked into wire fields where a
 * run or feedback is serialized. Every dimension is an entry in `FIELDS`; the
 * env var, header and payload handling are derived from it, so a new
 * dimension is a new entry.
 *
 * @example
 * ```ts
 * import { address } from "langsmith";
 * import { traceable } from "langsmith/traceable";
 *
 * const support = address({
 *   agentId: "customer-support",
 *   agentEnvironment: "production",
 * });
 *
 * const handle = traceable(async (order) => ..., { address: support });
 * ```
 */

// A leaf module: `utils/env` imports the package index, which imports the
// tracing modules that import this one.
import type { WriteReplica } from "./run_trees.js";

function getEnvironmentVariable(name: string): string | undefined {
  try {
    // eslint-disable-next-line no-process-env
    return typeof process !== "undefined" ? process.env?.[name] : undefined;
  } catch {
    return undefined;
  }
}

const MAX_ID_LENGTH = 255;

/**
 * The `LANGSMITH_AGENT_*` / project env vars can't address a run.
 *
 * Thrown for half an address, or an address beside a project. Tracing entry
 * points (`traceable`, `RunTree`, `Client.createRun`) catch it, log it and
 * leave the call untraced, so a bad environment never breaks the code being
 * traced. Explicit ingestion calls (`batchIngestRuns`, `multipartIngestRuns`)
 * let it throw for runs that name no destination, rather than drop part of a
 * batch the caller built.
 */
export class EnvAddressError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "EnvAddressError";
  }
}

type FieldName = "agentId" | "agentEnvironment";

type Field = {
  name: FieldName;
  /** The run / feedback payload key. */
  wire: string;
  required: boolean;
};

// The only code that knows what an address holds.
const FIELDS: readonly Field[] = [
  { name: "agentId", wire: "agent_id", required: true },
  { name: "agentEnvironment", wire: "agent_environment", required: true },
];

function envName(field: Field): string {
  return `LANGSMITH_${field.wire.toUpperCase()}`;
}

export type AddressFields = {
  /** The agent's ID. The server creates it on first use. */
  agentId: string;
  /**
   * The agent's environment. Not validated client-side; the server decides
   * which environments are accepted.
   */
  agentEnvironment: string;
};

/**
 * (experimental) A destination that runs can be addressed to.
 *
 * Build one with `address()`. Required fields must be set at construction;
 * which values exist is left to the server.
 */
export class Address {
  /** The agent's immutable ID. */
  readonly agentId: string;
  /** The agent's environment, passed to the server as given. */
  readonly agentEnvironment: string;

  constructor(fields: AddressFields) {
    for (const field of FIELDS) {
      const value: unknown = fields?.[field.name];
      if (value == null && !field.required) {
        continue;
      }
      if (typeof value !== "string" || value === "") {
        throw new Error(
          `Address ${field.name} must be a non-empty string, got ${JSON.stringify(
            value,
          )}.`,
        );
      }
    }
    if (fields.agentId.length > MAX_ID_LENGTH) {
      throw new Error(
        `Address agentId must be at most ${MAX_ID_LENGTH} characters.`,
      );
    }
    this.agentId = fields.agentId;
    this.agentEnvironment = fields.agentEnvironment;
    Object.freeze(this);
  }

  /** The payload keys an address renders to. */
  static wireKeys(): string[] {
    return FIELDS.map((f) => f.wire);
  }

  /** Render as run / feedback payload fields, omitting unset ones. */
  toWire(): Record<string, string> {
    const wire: Record<string, string> = {};
    for (const field of FIELDS) {
      const value = this[field.name];
      if (value != null) {
        wire[field.wire] = value;
      }
    }
    return wire;
  }

  /**
   * Build from payload-keyed values, or `undefined` if none are set.
   *
   * @throws If some but not all required fields are set.
   */
  static fromWire(values: Record<string, unknown>): Address | undefined {
    const fields: Record<string, unknown> = {};
    for (const field of FIELDS) {
      fields[field.name] = values[field.wire] ?? undefined;
    }
    if (Object.values(fields).every((v) => v === undefined)) {
      return undefined;
    }
    const missing = FIELDS.filter(
      (f) => f.required && fields[f.name] === undefined,
    ).map((f) => f.wire);
    if (missing.length > 0) {
      throw new Error(`An address needs ${missing.join(" and ")} as well.`);
    }
    return new Address(fields as AddressFields);
  }

  /**
   * Read the address named by `LANGSMITH_AGENT_*` env vars, if any.
   *
   * @throws {EnvAddressError} If only some of the required ones are set.
   */
  static fromEnv(): Address | undefined {
    const values: Record<string, string | undefined> = {};
    for (const field of FIELDS) {
      values[field.wire] = getEnvironmentVariable(envName(field)) || undefined;
    }
    try {
      return Address.fromWire(values);
    } catch (e) {
      const present = Object.entries(Address.envValues())
        .filter(([, value]) => value)
        .map(([name, value]) => `${name}=${JSON.stringify(value)}`)
        .join(", ");
      throw new EnvAddressError(
        `The LANGSMITH_AGENT_* env vars name an incomplete address ` +
          `(${present}): ${(e as Error).message}`,
      );
    }
  }

  /** Each `LANGSMITH_AGENT_*` env var an address reads, with its value. */
  static envValues(): Record<string, string | undefined> {
    const values: Record<string, string | undefined> = {};
    for (const field of FIELDS) {
      values[envName(field)] = getEnvironmentVariable(envName(field));
    }
    return values;
  }

  /** Identify this destination for deterministic replica run ids. */
  seed(): string {
    return ["agent", ...Object.values(this.toWire())].join("/");
  }

  equals(other: Address | undefined | null): boolean {
    return (
      other instanceof Address &&
      FIELDS.every((f) => this[f.name] === other[f.name])
    );
  }

  /** Return a handle to the same agent in another environment. */
  withAgentEnvironment(agentEnvironment: string): Address {
    return new Address({ ...this.fields(), agentEnvironment });
  }

  /**
   * Build a `WriteReplica` that sends runs to this address.
   *
   * Only needed to set other replica fields; the handle itself can be passed
   * in `replicas`.
   */
  replica(fields: Omit<WriteReplica, "address" | "projectName"> = {}) {
    const named = ["address", "projectName"].filter((k) => k in fields);
    if (named.length > 0) {
      throw new Error(
        `An Address already addresses the replica; drop ${named.join(", ")}.`,
      );
    }
    return { ...fields, address: this } as WriteReplica;
  }

  toJSON(): Record<string, string> {
    return this.toWire();
  }

  toString(): string {
    return `Address(${FIELDS.map(
      (f) => `${f.name}=${JSON.stringify(this[f.name])}`,
    ).join(", ")})`;
  }

  private fields(): AddressFields {
    return { agentId: this.agentId, agentEnvironment: this.agentEnvironment };
  }
}

/**
 * (experimental) Build an address to send runs to.
 *
 * @throws If a value is invalid.
 */
export function address(fields: AddressFields): Address {
  return new Address(fields);
}
