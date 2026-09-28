/**
 * (beta) An address that runs are sent to instead of a project.
 * Enabled per workspace; a workspace without it rejects the runs.
 */

// Wire key per field; env var is `LANGSMITH_<WIRE KEY>`.
const FIELDS = {
  agentId: "agent_id",
  agentEnvironment: "agent_environment",
} as const;

const MAX_ID_LENGTH = 255;

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

export type AddressFields = {
  agentId: string;
  agentEnvironment: string;
};

export class Address {
  readonly agentId: string;
  readonly agentEnvironment: string;

  constructor(fields: AddressFields) {
    for (const name of Object.keys(FIELDS) as (keyof AddressFields)[]) {
      const value: unknown = fields?.[name];
      if (typeof value !== "string" || value === "") {
        throw new Error(`Address ${name} must be a non-empty string.`);
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

  /** @internal */
  static wireKeys(): string[] {
    return Object.values(FIELDS);
  }

  /** @internal */
  static envNames(): string[] {
    return Address.wireKeys().map((key) => `LANGSMITH_${key.toUpperCase()}`);
  }

  /** @internal */
  toWire(): Record<string, string> {
    return {
      [FIELDS.agentId]: this.agentId,
      [FIELDS.agentEnvironment]: this.agentEnvironment,
    };
  }

  /** @internal `undefined` if no field is set; throws if only some are. */
  static fromWire(values: Record<string, unknown>): Address | undefined {
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
    return new Address(fields as AddressFields);
  }

  /**
   * @internal
   * @throws {EnvAddressError} If only some `LANGSMITH_AGENT_*` vars are set.
   */
  static fromEnv(): Address | undefined {
    const values = Object.fromEntries(
      Address.wireKeys().map((key, i) => [
        key,
        getEnv(Address.envNames()[i]) || undefined,
      ]),
    );
    try {
      return Address.fromWire(values);
    } catch (e) {
      throw new EnvAddressError(
        `The LANGSMITH_AGENT_* env vars name an incomplete address: ${
          (e as Error).message
        }`,
      );
    }
  }

  /** @internal Replica id derivation seed. */
  seed(): string {
    return ["agent", ...Object.values(this.toWire())].join("/");
  }

  equals(other: Address | undefined): boolean {
    return (
      other instanceof Address &&
      this.agentId === other.agentId &&
      this.agentEnvironment === other.agentEnvironment
    );
  }

  withAgentEnvironment(agentEnvironment: string): Address {
    return new Address({ agentId: this.agentId, agentEnvironment });
  }

  toJSON(): Record<string, string> {
    return this.toWire();
  }
}

/** (beta) Build an address to send runs to. */
export function address(fields: AddressFields): Address {
  return new Address(fields);
}
