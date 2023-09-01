// Inlined from https://github.com/flexdinesh/browser-or-node
declare global {
  const Deno:
    | {
        version: {
          deno: string;
        };
      }
    | undefined;
}

export const isBrowser = () =>
  typeof window !== "undefined" && typeof window.document !== "undefined";

export const isWebWorker = () =>
  typeof globalThis === "object" &&
  globalThis.constructor &&
  globalThis.constructor.name === "DedicatedWorkerGlobalScope";

export const isJsDom = () =>
  (typeof window !== "undefined" && window.name === "nodejs") ||
  (typeof navigator !== "undefined" &&
    (navigator.userAgent.includes("Node.js") ||
      navigator.userAgent.includes("jsdom")));

// Supabase Edge Function provides a `Deno` global object
// without `version` property
export const isDeno = () => typeof Deno !== "undefined";

// Mark not-as-node if in Supabase Edge Function
export const isNode = () =>
  typeof process !== "undefined" &&
  typeof process.versions !== "undefined" &&
  typeof process.versions.node !== "undefined" &&
  !isDeno();

export const getEnv = () => {
  let env: string;
  if (isBrowser()) {
    env = "browser";
  } else if (isNode()) {
    env = "node";
  } else if (isWebWorker()) {
    env = "webworker";
  } else if (isJsDom()) {
    env = "jsdom";
  } else if (isDeno()) {
    env = "deno";
  } else {
    env = "other";
  }

  return env;
};

export type RuntimeEnvironment = {
  library: string;
  libraryVersion?: string;
  runtime: string;
  runtimeVersion?: string;
};

let runtimeEnvironment: RuntimeEnvironment | undefined;

export async function getRuntimeEnvironment(): Promise<RuntimeEnvironment> {
  if (runtimeEnvironment === undefined) {
    const env = getEnv();
    const releaseEnv = getShas();

    runtimeEnvironment = {
      library: "langsmith",
      runtime: env,
      ...releaseEnv,
    };
  }
  return runtimeEnvironment;
}

export function getEnvironmentVariable(name: string): string | undefined {
  // Certain Deno setups will throw an error if you try to access environment variables
  // https://github.com/hwchase17/langchainjs/issues/1412
  try {
    return typeof process !== "undefined"
      ? // eslint-disable-next-line no-process-env
        process.env?.[name]
      : undefined;
  } catch (e) {
    return undefined;
  }
}

export function setEnvironmentVariable(name: string, value: string): void {
  if (typeof process !== "undefined") {
    // eslint-disable-next-line no-process-env
    process.env[name] = value;
  }
}

interface ICommitSHAs {
  [key: string]: string;
}
let cachedCommitSHAs: ICommitSHAs | undefined;
/**
 * Get the Git commit SHA from common environment variables
 * used by different CI/CD platforms.
 * @returns {string | undefined} The Git commit SHA or undefined if not found.
 */
export function getShas(): ICommitSHAs {
  if (cachedCommitSHAs !== undefined) {
    return cachedCommitSHAs;
  }
  const common_release_envs = [
    "VERCEL_GIT_COMMIT_SHA",
    "NEXT_PUBLIC_VERCEL_GIT_COMMIT_SHA",
    "COMMIT_REF",
    "RENDER_GIT_COMMIT",
    "CI_COMMIT_SHA",
    "CIRCLE_SHA1",
    "CF_PAGES_COMMIT_SHA",
    "REACT_APP_GIT_SHA",
    "SOURCE_VERSION",
    "GITHUB_SHA",
    "TRAVIS_COMMIT",
    "GIT_COMMIT",
    "BUILD_VCS_NUMBER",
    "bamboo_planRepository_revision",
    "Build.SourceVersion",
    "BITBUCKET_COMMIT",
    "DRONE_COMMIT_SHA",
    "SEMAPHORE_GIT_SHA",
    "BUILDKITE_COMMIT",
  ] as const;

  const shas: ICommitSHAs = {};
  for (const env of common_release_envs) {
    const envVar = getEnvironmentVariable(env);
    if (envVar !== undefined) {
      shas[env] = envVar;
    }
  }
  cachedCommitSHAs = shas;
  return shas;
}
