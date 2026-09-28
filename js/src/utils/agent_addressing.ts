/**
 * Resolving whether a run is addressed by project or by address.
 *
 * The address travels as a whole `Address` everywhere -- run trees, replicas,
 * headers -- and is unpacked into wire fields only here, in `applyToPayload`,
 * and in `Client.createFeedback`.
 */

import { Address, EnvAddressError } from "../address.js";
import {
  getEnvironmentVariable,
  getLangSmithEnvironmentVariable,
} from "./env.js";
import { warnOnce } from "./warn.js";

export { Address, EnvAddressError };

/**
 * Return `address` if it is an `Address` or unset, else throw.
 */
export function checkAddress(address: unknown): Address | undefined {
  if (address == null) {
    return undefined;
  }
  if (address instanceof Address) {
    return address;
  }
  throw new Error(
    "`address` must be a langsmith `Address`. Build one with " +
      "`address({ agentId, agentEnvironment })`.",
  );
}

export function warnIsBeta(): void {
  warnOnce(
    "Addressing runs with `address` is in beta and is enabled per workspace. " +
      "A workspace without it rejects the run, so the trace is lost rather " +
      "than falling back to a project. The behavior may change without notice.",
  );
}

/** One precedence level: the `[project, address]` it names, either may be unset. */
export type Tier = [string | undefined, Address | undefined];

function bothAtOneLevel(project: string, address: Address, where: string) {
  return (
    `A project (${JSON.stringify(project)}) and an address (${address}) are ` +
    `both set ${where}, so neither outranks the other. Set only one there, ` +
    "or set the one you want at a higher-precedence level."
  );
}

/**
 * Return the highest level that names a destination, without the env vars.
 *
 * @throws If that level names both.
 */
export function firstNamed(...tiers: Tier[]): Tier {
  for (const [index, [project, address]] of tiers.entries()) {
    if (project && address) {
      throw new Error(
        bothAtOneLevel(project, address, `at precedence level ${index + 1}`),
      );
    }
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
 * Settle a run's single destination, as `[project, address]`.
 *
 * `tiers` are the levels named in code, highest precedence first; the env
 * vars are the last level, consulted here. The first level that names
 * anything decides, whichever mode it names.
 *
 * @throws If one level named in code names both.
 * @throws {EnvAddressError} If the env vars are the deciding level and name
 *   both, or half an address.
 */
export function resolve(...tiers: Tier[]): Tier {
  const [project, address] = firstNamed(...tiers);
  if (project || address) {
    return [project, address];
  }
  const envProject = getEnvProject();
  const envAddress = Address.fromEnv();
  if (envProject && envAddress) {
    throw new EnvAddressError(
      bothAtOneLevel(envProject, envAddress, "in the environment"),
    );
  }
  if (envAddress) {
    return [undefined, envAddress];
  }
  return [envProject ?? "default", undefined];
}

/** Log, once per distinct cause, that calls run untraced for a bad env. */
export function logUntraced(error: EnvAddressError): void {
  warnOnce(`LangSmith is not tracing this call: ${error.message}`);
}

/**
 * Warn when the environment's address cannot be used.
 *
 * Half an address, or one beside a configured project, leaves calls that name
 * nothing in code untraced -- and a name like `LANGSMITH_AGENT_ENVIRONMENT`
 * is generic enough to be set by accident. Emitted at client construction
 * rather than per run, so it is seen once.
 */
export function warnOnEnv(): void {
  const present = Object.entries(Address.envValues())
    .filter(([, value]) => value)
    .map(([name]) => name);
  if (present.length === 0) {
    return;
  }
  let address: Address | undefined;
  try {
    address = Address.fromEnv();
  } catch {
    warnOnce(
      `${present.join(", ")} is set, but not every LANGSMITH_AGENT_* ` +
        "variable an address needs, so calls that name no destination in " +
        "code are not traced.",
    );
    return;
  }
  const project = getEnvProject();
  if (address === undefined || project === undefined) {
    return;
  }
  warnOnce(
    `LANGSMITH_AGENT_ID (${JSON.stringify(address.agentId)}) and a ` +
      `configured project (${JSON.stringify(project)}) are both set in the ` +
      "environment, so calls that name no destination in code are not " +
      "traced. Unset one of them.",
  );
}

/**
 * Refuse to build a run URL the SDK cannot know.
 *
 * A run URL is keyed on the project id, and the endpoint resolves an address
 * to its project without telling the SDK which.
 */
export function rejectUrl(sessionId: unknown, address: unknown): void {
  if (sessionId != null || address == null) {
    return;
  }
  throw new Error(
    "No run URL is available for an addressed run yet. The endpoint " +
      "resolves the address to its project, so only it knows the project " +
      "this run is in. Read the run back and build the URL from its " +
      "`session_id`.",
  );
}

/**
 * Reject a call that names both a project and an address.
 *
 * Pass only values the caller supplied in this call: an inherited address
 * beside an explicit project is not a conflict -- the project wins.
 */
export function rejectConflicting(project: unknown, address: unknown): void {
  if (project != null && project !== "" && address != null) {
    throw new Error(
      `A run is addressed by project (${JSON.stringify(project)}) or by ` +
        `address (${address}), not both.`,
    );
  }
}

/**
 * Render a run payload's address into its wire fields, in place.
 *
 * The one place a run's `address` is unpacked. A project already on the
 * payload addresses the run, so the environment is not consulted. With no
 * project, an ambient address fills in and the null project keys are dropped.
 *
 * On an update the environment is not consulted: a patch inherits its address
 * from the post that established it, and one naming nothing is resolved by
 * run id. A payload already carrying wire fields was rendered before (runs
 * pass through here again when they are batched) and is left alone.
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
  const rendered = Address.wireKeys().some((key) => payload[key] != null);
  if (address === undefined && !(update || namedProject || rendered)) {
    address = Address.fromEnv();
  }
  if (address === undefined) {
    return;
  }
  warnIsBeta();
  Object.assign(payload, address.toWire());
  if (!namedProject) {
    delete payload.session_name;
    delete payload.session_id;
  }
}
