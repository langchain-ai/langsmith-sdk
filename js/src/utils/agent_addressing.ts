import {
  getEnvironmentVariable,
  getLangSmithEnvironmentVariable,
} from "./env.js";
import { warnOnce } from "./warn.js";

/**
 * Resolving whether a run is addressed by project or by agent.
 *
 * Agent addressing is in beta. The rules changed repeatedly while it was
 * being built, so they live in one module rather than spread across the
 * client and the run tree, where copies had already drifted apart in the
 * Python SDK this mirrors.
 */

/**
 * Get the agent environment for a LangSmith tracer.
 *
 * Experimental: in beta and enabled per workspace. A workspace without
 * agent addressing rejects the runs, so tracing is lost rather than falling
 * back to a project.
 *
 * Must be one of `local`, `development`, `staging` or `production` --
 * matched case-insensitively, surrounding space ignored. The endpoint
 * rejects anything else rather than defaulting it, so a near miss like
 * `prod` fails the whole batch.
 *
 * Read from `LANGSMITH_AGENT_ENVIRONMENT` only. Unlike most LangSmith
 * variables it has no `LANGCHAIN_` alias, so that the newer namespace is
 * the only one to learn for this. There is also no default -- an
 * agent-addressed run must name its environment.
 */
export function getDefaultTracerAgentEnvironment(): string | undefined {
  return getLangsmithOnlyVariable("AGENT_ENVIRONMENT");
}

/**
 * Get the agent ID for a LangSmith tracer.
 *
 * Experimental: in beta and enabled per workspace. A workspace without
 * agent addressing rejects the runs, so tracing is lost rather than falling
 * back to a project.
 *
 * Must be 1 to 255 characters.
 *
 * Read from `LANGSMITH_AGENT_ID` only -- there is no `LANGCHAIN_` alias,
 * so that the newer namespace is the only one to learn. This is an agent
 * identifier, not a credential: the server resolves the agent by this ID and
 * creates one if it doesn't exist yet. When unset the run is addressed by
 * project instead.
 */
export function getDefaultTracerAgentId(): string | undefined {
  return getLangsmithOnlyVariable("AGENT_ID");
}

// Unlike most LangSmith variables these two have no `LANGCHAIN_` alias, so
// they are read from the `LANGSMITH_` namespace only. A value that is unset
// or blank names nothing.
function getLangsmithOnlyVariable(name: string): string | undefined {
  try {
    const value =
      typeof process !== "undefined"
        ? // eslint-disable-next-line no-process-env
          process.env?.[`LANGSMITH_${name}`]
        : undefined;
    return value !== undefined && value.trim() !== "" ? value : undefined;
  } catch (_e) {
    return undefined;
  }
}

/**
 * Fill each half of the agent pair from its env var unless given.
 *
 * An explicitly provided value is left alone, including when the other half
 * comes from the environment -- that combination is a complete pair.
 */
export function resolveAgentPair(
  agentId?: string | null,
  agentEnvironment?: string | null,
): [string | undefined, string | undefined] {
  // `null` counts as unset, matching Python's `is not None`: untyped or
  // JSON input can carry it, and it must not stand in for a value.
  return [
    agentId ?? getDefaultTracerAgentId(),
    agentEnvironment ?? getDefaultTracerAgentEnvironment(),
  ];
}

/**
 * Whether a run is addressed by agent rather than by project.
 *
 * Either half is enough. A lone `agent_environment` is incomplete and the
 * endpoint rejects it, but it must not fall through to a project the caller
 * never named -- that would quietly send the run somewhere else instead of
 * reporting the mistake.
 */
export function isAgentAddressed(
  agentId?: string | null,
  agentEnvironment?: string | null,
): boolean {
  return agentId != null || agentEnvironment != null;
}

/**
 * Warn the first time a run is actually addressed to an agent.
 *
 * The docstrings say the feature is in beta, but a caller who reaches it
 * through an env var never read them, and the first sign of trouble would
 * otherwise be a 400 from a workspace without the flag. Emitted where the
 * addressing is settled rather than at client construction: a process that
 * configures an agent and never traces to one has nothing to hear about.
 */
export function warnIsBeta(): void {
  warnOnce(
    "Agent addressing (`agent_id` / `agent_environment`) is in beta and is " +
      "enabled per workspace. A workspace without it rejects the run, so the " +
      "trace is lost rather than falling back to a project. The behavior may " +
      "change without notice.",
  );
}

/**
 * Settle a run's single destination, as
 * `[project, agentId, agentEnvironment]`.
 *
 * The arguments are the values named in code -- a parameter, a parent run.
 * The environment fills in below them, so callers pass their own chain of
 * code-level tiers and leave the env vars to this function.
 *
 * Code beats the environment in both directions: a project named in code
 * drops the ambient agent, and an agent named in code drops the ambient
 * project. Half an agent named in code is completed from the environment
 * rather than competing with it.
 *
 * When only the environment addresses the run, both modes travel and the
 * endpoint refuses the pair -- there is no tier to choose between, and
 * picking one would move the caller's traces without telling them. Only the
 * `default` project the SDK would otherwise invent is suppressed.
 *
 * A project variable set to the empty string names no project, so it falls
 * back to `default` the way an unset one does.
 */
export function resolveAgentAddressing(
  project?: string,
  agentId?: string,
  agentEnvironment?: string,
): [string | undefined, string | undefined, string | undefined] {
  if (project) {
    return [project, undefined, undefined];
  }
  if (isAgentAddressed(agentId, agentEnvironment)) {
    const [pairId, pairEnvironment] = resolveAgentPair(
      agentId,
      agentEnvironment,
    );
    return [undefined, pairId, pairEnvironment];
  }
  const envAgentId = getDefaultTracerAgentId();
  const envAgentEnvironment = getDefaultTracerAgentEnvironment();
  if (isAgentAddressed(envAgentId, envAgentEnvironment)) {
    return [getConfiguredProjectName(), envAgentId, envAgentEnvironment];
  }
  return [getConfiguredProjectName() ?? "default", undefined, undefined];
}

/**
 * The project configured in the environment, without the `default` fallback.
 *
 * The empty string names no project, matching how an unset one is treated.
 */
function getConfiguredProjectName(): string | undefined {
  const project = getLangSmithEnvironmentVariable("PROJECT");
  if (project !== undefined && project.trim() !== "") {
    return project;
  }
  const session = getEnvironmentVariable("LANGCHAIN_SESSION");
  if (session !== undefined && session.trim() !== "") {
    return session;
  }
  return undefined;
}

/**
 * Warn when the environment's agent addressing cannot reach the endpoint.
 *
 * Either half of the pair addresses a run, so either half alone is refused
 * with a 400 that takes the whole batch with it -- and `AGENT_ENVIRONMENT`
 * is a generic enough name to be set by accident. A project configured
 * beside a complete pair is refused the same way.
 *
 * Emitted at client construction rather than per run, so it is seen once
 * instead of drowned out by the background flush's warnings, which only
 * log.
 */
export function warnOnAgentAddressingEnv(): void {
  const agentId = getDefaultTracerAgentId();
  const agentEnvironment = getDefaultTracerAgentEnvironment();
  if (!isAgentAddressed(agentId, agentEnvironment)) {
    return;
  }
  if (agentId === undefined || agentEnvironment === undefined) {
    const [missing, present] =
      agentId === undefined
        ? [
            "LANGSMITH_AGENT_ID",
            `LANGSMITH_AGENT_ENVIRONMENT (${JSON.stringify(agentEnvironment)})`,
          ]
        : [
            "LANGSMITH_AGENT_ENVIRONMENT",
            `LANGSMITH_AGENT_ID (${JSON.stringify(agentId)})`,
          ];
    warnOnce(
      `${present} is set without ${missing}. Agent addressing needs both, ` +
        "so the API refuses the request and the whole batch of runs is " +
        `dropped. Set ${missing}, or unset the other to trace to a project.`,
    );
    return;
  }
  const project = getConfiguredProjectName();
  if (project === undefined) {
    return;
  }
  warnOnce(
    `LANGSMITH_AGENT_ID (${JSON.stringify(agentId)}) and a configured project ` +
      `(${JSON.stringify(project)}) both address runs, and the API accepts ` +
      "only one. Unset LANGSMITH_AGENT_ID to trace to the project, or unset " +
      "LANGSMITH_PROJECT (and LANGCHAIN_PROJECT / LANGCHAIN_SESSION) to " +
      "trace to the agent.",
  );
}

/**
 * Refuse to build a run URL the SDK cannot know.
 *
 * A run URL is keyed on the project id. The endpoint resolves an agent to
 * its environment's project and never tells the SDK which, so an
 * agent-addressed run has no project id here until it is read back. Falling
 * through would resolve the literal `default` project and hand back a link
 * to the wrong place, or raise a not-found from inside what callers treat as
 * a convenience.
 */
export function rejectAgentRunUrl(
  sessionId?: string,
  agentId?: string,
  agentEnvironment?: string,
): void {
  if (sessionId != null || !isAgentAddressed(agentId, agentEnvironment)) {
    return;
  }
  throw new Error(
    "No run URL is available for an agent-addressed run yet. The endpoint " +
      "resolves the agent to its environment's project, so only it knows " +
      "the project this run is in; there is no agent-shaped run URL. Read " +
      "the run back and build the URL from its `session_id`.",
  );
}

/**
 * Reject a call that names both a project and an agent.
 *
 * A run goes to one or the other, and the endpoint never sees this particular
 * conflict: resolution drops the agent before the payload is built, so without
 * this the agent would be discarded in silence. Every other rejection is left
 * to the endpoint, which can see what it is sent.
 *
 * Callers pass only values a caller supplied in this one call. A resolved run
 * body can legitimately carry both -- a project configured in the environment
 * travels with the agent so the endpoint refuses the pair -- and an inherited
 * pair must not be mistaken for a conflict.
 */
export function rejectConflictingAgentAddressing(args: {
  project?: unknown;
  sessionId?: unknown;
  agentId?: string;
  agentEnvironment?: string;
}): void {
  const namedProject = args.project != null ? args.project : args.sessionId;
  const namedAgent = args.agentId ?? args.agentEnvironment;
  if (namedProject != null && namedAgent != null) {
    throw new Error(
      `A run is addressed by project (${JSON.stringify(namedProject)}) or by ` +
        `agent (${JSON.stringify(namedAgent)}), not both. Pass one of them, ` +
        "or set LANGSMITH_AGENT_ID and leave the project off the call.",
    );
  }
}

/**
 * Settle the addressing mode on a run payload, in place.
 *
 * A project already on the payload addresses the run, so the environment
 * is not consulted; whatever agent fields the caller put there travel
 * alongside it and the endpoint refuses the pair. With no project, the
 * agent env vars fill in and the null project keys are dropped, so the
 * payload never carries a null for the mode it isn't using.
 *
 * Which project reaches this payload is decided upstream, in `createRun`
 * and in the `RunTree` constructor: a project named on the call replaces the
 * agent outright, and only one the caller *configured* travels with it.
 *
 * On an update the environment is not consulted: a patch inherits its
 * target from the post that established it. Filling it in here would
 * address a patch to the agent while its post went to a project, because
 * an update carries a project only when the caller passed one and most
 * callers don't -- the endpoint resolves the run by id. A patch that
 * names nothing falls to that same lookup, which is how every patch is
 * resolved today.
 *
 * Both members are required, but the endpoint is the one that says so:
 * whatever resolved is forwarded, and a partial pair comes back as a 400
 * carrying the server's own message. Dropping it instead would route the
 * run to the `default` project, so a typo would quietly succeed in the
 * wrong place rather than failing.
 *
 * The keys read are the keys written, so running this twice re-resolves an
 * explicit value to itself rather than letting the environment replace it.
 *
 * Applies to creates and updates alike: a `patch.<run_id>` part has to be
 * addressed the same way as the `post.<run_id>` it belongs to.
 */
export function applyAgentAddressingToPayload(
  payload: Record<string, unknown>,
  update = false,
): void {
  // `null` counts as unset: it must not trigger agent addressing, drop the
  // project, or be forwarded to the endpoint.
  let agentId = (payload["agent_id"] ?? undefined) as string | undefined;
  let agentEnvironment = (payload["agent_environment"] ?? undefined) as
    | string
    | undefined;
  delete payload["agent_id"];
  delete payload["agent_environment"];
  const namedProject =
    payload["session_id"] != null ||
    (payload["session_name"] != null && payload["session_name"] !== "");
  if (!update && !namedProject) {
    // A patch inherits its post's target, and a project already on the
    // payload addresses the run on its own; neither consults the
    // environment. Every other create does, including one that named
    // half an agent in code -- the missing half comes from the env var
    // rather than reaching the endpoint as an incomplete pair.
    [agentId, agentEnvironment] = resolveAgentPair(agentId, agentEnvironment);
  }
  if (!isAgentAddressed(agentId, agentEnvironment)) {
    // Neither mode is addressed; leave the server-side fallback to it.
    return;
  }
  warnIsBeta();
  if (agentId !== undefined) {
    payload["agent_id"] = agentId;
  }
  if (agentEnvironment !== undefined) {
    payload["agent_environment"] = agentEnvironment;
  }
  if (!namedProject) {
    // Nothing to drop, and nothing to keep: the null project keys would
    // otherwise be serialized.
    delete payload["session_name"];
    delete payload["session_id"];
  }
}
