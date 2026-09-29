import {
  type Address,
  EnvAddressError,
  addressFromEnv,
  envNames,
  normalizeAddress,
  toWire,
  wireKeys,
} from "../address.js";
import {
  getEnvironmentVariable,
  getLangSmithEnvironmentVariable,
} from "./env.js";
import { warnOnce } from "./warn.js";

/** One precedence level: the `[project, address]` it names. */
export type Tier = [string | undefined, Address | undefined];

/** Validate an address at an entry point; the SDK carries the frozen copy. */
export function checkAddress(address: unknown): Readonly<Address> | undefined {
  return address == null ? undefined : normalizeAddress(address);
}

export function rejectConflicting(project: unknown, address: unknown): void {
  if (project && address) {
    throw new Error(
      `A run is sent to a project (${JSON.stringify(project)}) or to an ` +
        `address (${JSON.stringify(address)}), not both.`,
    );
  }
}

/** The highest level naming a project or an address, whichever it names. */
export function firstNamed(...tiers: Tier[]): Tier {
  for (const [project, address] of tiers) {
    rejectConflicting(project, address);
    if (project || address) {
      return [project || undefined, address];
    }
  }
  return [undefined, undefined];
}

function getEnvProject(): string | undefined {
  return (
    getLangSmithEnvironmentVariable("PROJECT") ||
    getEnvironmentVariable("LANGCHAIN_SESSION") ||
    undefined
  );
}

/**
 * The env's destination: its address, else its project, else "default".
 * @throws {EnvAddressError} For half an address, or an address and a project.
 */
export function resolveFromEnv(): Tier {
  const project = getEnvProject();
  const address = addressFromEnv();
  if (project && address) {
    throw new EnvAddressError(
      "LANGSMITH_AGENT_* and a project are both set in the environment.",
    );
  }
  return address ? [undefined, address] : [project ?? "default", undefined];
}

export function logUntraced(error: EnvAddressError): void {
  warnOnce(`LangSmith is not tracing this call: ${error.message}`);
}

/** Warn once, at client construction, if the env can't address runs. */
export function warnOnEnv(): void {
  if (!envNames().some((name) => getEnvironmentVariable(name))) {
    return;
  }
  try {
    resolveFromEnv();
  } catch (e) {
    warnOnce(
      `${(e as Error).message} Runs that name no destination in code are ` +
        "not traced.",
    );
  }
}

/**
 * Render `address` into its wire fields, in place. Without one, a create
 * naming no project takes the env address. Already-rendered payloads (runs
 * re-prepared when batched) are left alone.
 *
 * @throws {EnvAddressError} If the env names half an address.
 */
export function applyToPayload(
  run: { address?: Address; session_id?: string; session_name?: string },
  { update = false }: { update?: boolean } = {},
): void {
  const payload = run as Record<string, unknown>;
  let address = checkAddress(payload.address);
  delete payload.address;
  const namedProject =
    payload.session_id != null || payload.session_name != null;
  const rendered = wireKeys().some((key) => payload[key] != null);
  if (!address && !update && !namedProject && !rendered) {
    address = addressFromEnv();
  }
  if (!address) {
    return;
  }
  warnOnce(
    "Sending runs to an `address` is in beta and enabled per workspace; a " +
      "workspace without it rejects the runs.",
  );
  Object.assign(payload, toWire(address));
  if (!namedProject) {
    delete payload.session_name;
    delete payload.session_id;
  }
}
