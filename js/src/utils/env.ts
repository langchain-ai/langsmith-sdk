import { exec } from "child_process";

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

export async function getDockerEnvironment(): Promise<{
  dockerVersion: string | undefined;
  dockerComposeCommand: string | undefined;
  dockerComposeVersion: string | undefined;
}> {
  const getDockerVersion = () =>
    new Promise<string | undefined>((resolve) => {
      exec("docker --version", (error, stdout) => {
        if (error) {
          resolve(undefined);
        } else {
          resolve(stdout.trim());
        }
      });
    });

  const getDockerComposeCommand = () =>
    new Promise<string | undefined>((resolve) => {
      exec("which docker-compose", (error, stdout) => {
        if (error) {
          resolve(undefined);
        } else {
          resolve(stdout.trim());
        }
      });
    });

  const getDockerComposeVersion = () =>
    new Promise<string | undefined>((resolve) => {
      exec("docker-compose --version", (error, stdout) => {
        if (error) {
          resolve(undefined);
        } else {
          resolve(stdout.trim());
        }
      });
    });

  const [dockerVersion, dockerComposeCommand, dockerComposeVersion] =
    await Promise.all([
      getDockerVersion(),
      getDockerComposeCommand(),
      getDockerComposeVersion(),
    ]);

  return {
    dockerVersion,
    dockerComposeCommand,
    dockerComposeVersion,
  };
}

/**
 * Retrieves the LangChain-specific environment variables from the current runtime environment.
 * Sensitive keys (containing the word "key") have their values redacted for security.
 *
 * @returns {Record<string, string>}
 *  - A record of LangChain-specific environment variables.
 */
export function getLangChainEnvVars(): Record<string, string> {
  const allEnvVars = getEnvironmentVariables() || {};
  const envVars: Record<string, string> = {};

  for (const [key, value] of Object.entries(allEnvVars)) {
    if (key.startsWith("LANGCHAIN_") && typeof value === "string") {
      envVars[key] = value;
    }
  }

  for (const key in envVars) {
    if (key.toLowerCase().includes("key") && typeof envVars[key] === "string") {
      const value = envVars[key];
      envVars[key] =
        value.slice(0, 2) + "*".repeat(value.length - 4) + value.slice(-2);
    }
  }

  return envVars;
}

/**
 * Retrieves the environment variables from the current runtime environment.
 *
 * This function is designed to operate in a variety of JS environments,
 * including Node.js, Deno, browsers, etc.
 *
 * @returns {Record<string, string> | undefined}
 *  - A record of environment variables if available.
 *  - `undefined` if the environment does not support or allows access to environment variables.
 */
export function getEnvironmentVariables(): Record<string, string> | undefined {
  try {
    // Check for Node.js environment
    // eslint-disable-next-line no-process-env
    if (typeof process !== "undefined" && process.env) {
      // eslint-disable-next-line no-process-env
      Object.entries(process.env).reduce(
        (acc: { [key: string]: string }, [key, value]) => {
          acc[key] = String(value);
          return acc;
        },
        {}
      );
    }

    // For browsers and other environments, we may not have direct access to env variables
    // Return undefined or any other fallback as required.
    return undefined;
  } catch (e) {
    // Catch any errors that might occur while trying to access environment variables
    return undefined;
  }
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
