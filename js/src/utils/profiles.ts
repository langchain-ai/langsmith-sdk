import { getEnv, getEnvironmentVariable } from "./env.js";
import * as fsUtils from "./fs.js";

export const DEFAULT_API_URL = "https://api.smith.langchain.com";

const OAUTH_CLIENT_ID = "langsmith-cli";
const TOKEN_REFRESH_LEEWAY_MS = 60_000;
const TOKEN_REFRESH_TIMEOUT_MS = 10_000;

type LangSmithProfileOAuth = {
  access_token?: string;
  refresh_token?: string;
  expires_at?: string;
};

type LangSmithProfile = {
  api_key?: string;
  api_url?: string;
  workspace_id?: string;
  oauth?: LangSmithProfileOAuth;
};

type LangSmithProfileConfigFile = {
  current_profile?: string;
  profiles?: Record<string, LangSmithProfile>;
};

type LangSmithProfileState = {
  configPath: string;
  config: LangSmithProfileConfigFile;
  profileName: string;
  profile: LangSmithProfile;
};

export type ProfileAuthHeader = {
  name: "Authorization" | "x-api-key";
  value: string;
};

export type ProfileClientConfig = {
  apiUrl?: string;
  apiKey?: string;
  workspaceId?: string;
  oauthAccessToken?: string;
  oauthRefreshToken?: string;
  profileAuth?: ProfileAuth;
};

function isBrowserLikeRuntime(): boolean {
  const env = getEnv();
  return env === "browser" || env === "webworker";
}

function getProfileConfigPath(): string | undefined {
  const explicitPath = getEnvironmentVariable("LANGSMITH_CONFIG_FILE");
  if (explicitPath) {
    return explicitPath;
  }
  const home =
    getEnvironmentVariable("HOME") ?? getEnvironmentVariable("USERPROFILE");
  if (!home) {
    return undefined;
  }
  return fsUtils.path.join(home, ".langsmith", "config.json");
}

function resolveProfileName(
  config: LangSmithProfileConfigFile,
): string | undefined {
  const envProfile = getEnvironmentVariable("LANGSMITH_PROFILE");
  if (envProfile) {
    return envProfile;
  }
  if (config.current_profile) {
    return config.current_profile;
  }
  if (config.profiles?.default) {
    return "default";
  }
  return undefined;
}

function loadProfileState(): LangSmithProfileState | undefined {
  if (isBrowserLikeRuntime()) {
    return undefined;
  }
  const configPath = getProfileConfigPath();
  if (!configPath || !fsUtils.existsSync(configPath)) {
    return undefined;
  }
  try {
    const config = JSON.parse(
      fsUtils.readFileSync(configPath),
    ) as LangSmithProfileConfigFile;
    const profileName = resolveProfileName(config);
    const profile = profileName ? config.profiles?.[profileName] : undefined;
    if (!profileName || !profile) {
      return undefined;
    }
    return { configPath, config, profileName, profile };
  } catch {
    return undefined;
  }
}

export function hasValue(value?: string | null): boolean {
  return value !== undefined && value !== null && value.trim() !== "";
}

function trimConfigValue(value?: string): string | undefined {
  return value?.trim().replace(/^["']|["']$/g, "");
}

function shouldRefreshProfileToken(profile: LangSmithProfile): boolean {
  const oauth = profile.oauth;
  if (!oauth?.refresh_token) {
    return false;
  }
  if (!oauth.access_token) {
    return true;
  }
  if (!oauth.expires_at) {
    return false;
  }
  const expiresAt = Date.parse(oauth.expires_at);
  if (Number.isNaN(expiresAt)) {
    return false;
  }
  return expiresAt <= Date.now() + TOKEN_REFRESH_LEEWAY_MS;
}

function normalizeConfigUrl(apiUrl: string): string {
  let normalized = apiUrl;
  while (normalized.endsWith("/")) {
    normalized = normalized.slice(0, -1);
  }
  const apiV1Suffix = "/api/v1";
  return normalized.endsWith(apiV1Suffix)
    ? normalized.slice(0, -apiV1Suffix.length)
    : normalized;
}

function applyTokenResponse(
  profile: LangSmithProfile,
  token: {
    access_token?: string;
    refresh_token?: string;
    expires_in?: number;
  },
): void {
  profile.oauth ??= {};
  if (token.access_token) {
    profile.oauth.access_token = token.access_token;
  }
  if (token.refresh_token) {
    profile.oauth.refresh_token = token.refresh_token;
  }
  if (typeof token.expires_in === "number" && token.expires_in > 0) {
    profile.oauth.expires_at = new Date(
      Date.now() + token.expires_in * 1000,
    ).toISOString();
  }
}

function getAbortReason(signal: AbortSignal): unknown {
  return (
    (signal as AbortSignal & { reason?: unknown }).reason ??
    new Error("The operation was aborted.")
  );
}

async function waitForAbortSignal<T>(
  promise: Promise<T>,
  signal?: AbortSignal | null,
): Promise<T> {
  if (!signal) {
    return promise;
  }
  if (signal.aborted) {
    throw getAbortReason(signal);
  }
  let cleanup: (() => void) | undefined;
  const abortPromise = new Promise<never>((_, reject) => {
    const onAbort = () => {
      reject(getAbortReason(signal));
    };
    signal.addEventListener("abort", onAbort, { once: true });
    cleanup = () => {
      signal.removeEventListener("abort", onAbort);
    };
  });
  try {
    return await Promise.race([promise, abortPromise]);
  } finally {
    cleanup?.();
  }
}

export function loadProfileClientConfig(): ProfileClientConfig {
  const state = loadProfileState();
  const profile = state?.profile;
  if (!state || !profile) {
    return {};
  }
  const apiKey = trimConfigValue(profile.api_key);
  const oauthAccessToken = trimConfigValue(profile.oauth?.access_token);
  const oauthRefreshToken = trimConfigValue(profile.oauth?.refresh_token);
  return {
    apiUrl: profile.api_url,
    apiKey,
    workspaceId: profile.workspace_id,
    oauthAccessToken,
    oauthRefreshToken,
    profileAuth:
      apiKey || oauthAccessToken || oauthRefreshToken
        ? new ProfileAuth(state)
        : undefined,
  };
}

export class ProfileAuth {
  private refreshPromise?: Promise<void>;

  private managedAuthorizationValues = new Set<string>();

  constructor(private state: LangSmithProfileState) {
    this.rememberProfileAuthHeader(this.currentAuthHeader());
  }

  currentAuthHeader(): ProfileAuthHeader | undefined {
    const header = currentAuthHeaderFromProfile(this.state.profile);
    this.rememberProfileAuthHeader(header);
    return header;
  }

  async getAuthHeader(
    fetchImplementation: typeof fetch,
    signal?: AbortSignal | null,
  ): Promise<ProfileAuthHeader | undefined> {
    if (shouldRefreshProfileToken(this.state.profile)) {
      if (!this.refreshPromise) {
        this.refreshPromise = this.refreshOAuthToken(
          fetchImplementation,
        ).finally(() => {
          this.refreshPromise = undefined;
        });
      }
      await waitForAbortSignal(this.refreshPromise, signal);
    }
    const header = authHeaderFromProfile(this.state.profile);
    this.rememberProfileAuthHeader(header);
    return header;
  }

  isProfileAuthorizationHeader(value: string): boolean {
    return this.managedAuthorizationValues.has(value);
  }

  private async refreshOAuthToken(
    fetchImplementation: typeof fetch,
  ): Promise<void> {
    const refreshToken = this.state.profile.oauth?.refresh_token;
    if (!refreshToken) {
      return;
    }
    const refreshApiUrl =
      trimConfigValue(this.state.profile.api_url) ?? DEFAULT_API_URL;
    try {
      const body = new URLSearchParams({
        grant_type: "refresh_token",
        client_id: OAUTH_CLIENT_ID,
        refresh_token: refreshToken,
      });
      const response = await fetchImplementation(
        `${normalizeConfigUrl(refreshApiUrl)}/oauth/token`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/x-www-form-urlencoded",
          },
          body: body.toString(),
          signal: AbortSignal.timeout(TOKEN_REFRESH_TIMEOUT_MS),
        },
      );
      if (!response.ok) {
        return;
      }
      const token = (await response.json()) as {
        access_token?: string;
        refresh_token?: string;
        expires_in?: number;
      };
      if (!token.access_token) {
        return;
      }
      applyTokenResponse(this.state.profile, token);
      this.state.config.profiles ??= {};
      this.state.config.profiles[this.state.profileName] = this.state.profile;
      await fsUtils.writeFileAtomic(
        this.state.configPath,
        `${JSON.stringify(this.state.config, null, 2)}\n`,
      );
    } catch {
      return;
    }
  }

  private rememberProfileAuthHeader(
    header: ProfileAuthHeader | undefined,
  ): void {
    if (header?.name === "Authorization") {
      this.managedAuthorizationValues.add(header.value);
    }
  }
}

function currentAuthHeaderFromProfile(
  profile: LangSmithProfile,
): ProfileAuthHeader | undefined {
  const oauthAccessToken = trimConfigValue(profile.oauth?.access_token);
  if (oauthAccessToken) {
    return { name: "Authorization", value: `Bearer ${oauthAccessToken}` };
  }
  if (trimConfigValue(profile.oauth?.refresh_token)) {
    return undefined;
  }
  return authHeaderFromProfile(profile);
}

function authHeaderFromProfile(
  profile: LangSmithProfile,
): ProfileAuthHeader | undefined {
  const oauthAccessToken = trimConfigValue(profile.oauth?.access_token);
  if (oauthAccessToken) {
    return { name: "Authorization", value: `Bearer ${oauthAccessToken}` };
  }
  const apiKey = trimConfigValue(profile.api_key);
  if (apiKey) {
    return { name: "x-api-key", value: apiKey };
  }
  return undefined;
}
