/**
 * (beta) An address that runs are sent to instead of a project.
 * Enabled per workspace; a workspace without it rejects the runs.
 */
export interface Address {
  /** 1 to 63 lowercase ASCII letters, digits or hyphens; starts with a letter. */
  agentId: string;
  agentEnvironment: string;
}

// Wire key per field; env var is `LANGSMITH_<WIRE KEY>`.
const FIELDS = {
  agentId: "agent_id",
  agentEnvironment: "agent_environment",
} as const;

// The server's agent id rule: a DNS label, so a hostname can carry the id.
const AGENT_ID_PATTERN = /^[a-z]([a-z0-9-]{0,61}[a-z0-9])?$/;

// Not `utils/env`: it imports the package index, which imports this module.
function getEnv(name: string): string | undefined {
  try {
    // eslint-disable-next-line no-process-env
    return typeof process !== "undefined" ? process.env?.[name] : undefined;
  } catch {
    return undefined;
  }
}

/** The `LANGSMITH_AGENT_*` / project env vars name half an address, or both. */
export class EnvAddressError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "EnvAddressError";
  }
}

/**
 * @internal Validate `value` and return a frozen copy of its fields.
 * @throws If it isn't an object with exactly the address fields, or a value is invalid.
 */
export function normalizeAddress(value: unknown): Readonly<Address> {
  if (value == null || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(
      "`address` must be an object: { agentId, agentEnvironment }.",
    );
  }
  const fields = value as Record<string, unknown>;
  const unknown = Object.keys(fields).filter((key) => !(key in FIELDS));
  if (unknown.length > 0) {
    throw new Error(`Unknown address fields: ${unknown.join(", ")}.`);
  }
  for (const name of Object.keys(FIELDS)) {
    const field: unknown = fields[name];
    if (typeof field !== "string" || field === "") {
      throw new Error(`Address ${name} must be a non-empty string.`);
    }
  }
  const { agentId, agentEnvironment } = fields as unknown as Address;
  if (!AGENT_ID_PATTERN.test(agentId)) {
    throw new Error(
      "Address agentId must be 1 to 63 lowercase ASCII letters, digits, or " +
        "hyphens, start with a letter, and end with a letter or digit, got " +
        `${JSON.stringify(agentId)}. Use an id such as "support-agent".`,
    );
  }
  return Object.freeze({ agentId, agentEnvironment });
}

/** @internal */
export function wireKeys(): string[] {
  return Object.values(FIELDS);
}

/** @internal */
export function envNames(): string[] {
  return wireKeys().map((key) => `LANGSMITH_${key.toUpperCase()}`);
}

/** @internal */
export function toWire(address: Address): Record<string, string> {
  return {
    [FIELDS.agentId]: address.agentId,
    [FIELDS.agentEnvironment]: address.agentEnvironment,
  };
}

/** @internal `undefined` if no field is set; throws if only some are. */
export function fromWire(
  values: Record<string, unknown>,
): Readonly<Address> | undefined {
  const fields = Object.fromEntries(
    Object.entries(FIELDS).map(([name, key]) => [
      name,
      values[key] ?? undefined,
    ]),
  );
  const missing = Object.entries(FIELDS)
    .filter(([name]) => fields[name] === undefined)
    .map(([, key]) => key);
  if (missing.length === Object.keys(FIELDS).length) {
    return undefined;
  }
  if (missing.length > 0) {
    throw new Error(`An address needs ${missing.join(" and ")} as well.`);
  }
  return normalizeAddress(fields);
}

/**
 * @internal
 * @throws {EnvAddressError} If only some `LANGSMITH_AGENT_*` vars are set, or one is invalid.
 */
export function addressFromEnv(): Readonly<Address> | undefined {
  const values = Object.fromEntries(
    wireKeys().map((key, i) => [key, getEnv(envNames()[i]) || undefined]),
  );
  try {
    return fromWire(values);
  } catch (e) {
    throw new EnvAddressError(
      `The LANGSMITH_AGENT_* env vars can't address a run: ${
        (e as Error).message
      }`,
    );
  }
}

/** @internal Replica id derivation seed. */
export function seed(address: Address): string {
  return ["agent", ...Object.values(toWire(address))].join("/");
}

/** @internal */
export function sameAddress(a?: Address, b?: Address): boolean {
  if (!a || !b) {
    return a === b;
  }
  return a.agentId === b.agentId && a.agentEnvironment === b.agentEnvironment;
}
