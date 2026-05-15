import { getEnv, getEnvironmentVariable } from "./env.js";
import * as fsUtils from "./fs.js";

export const DEFAULT_API_URL = "https://api.smith.langchain.com";

const OAUTH_CLIENT_ID = "langsmith-cli";
export const PROFILE_USER_ID_HEADER = "x-user-id";
const OAUTH_USER_ID_CLAIM = "sub";
const TOKEN_REFRESH_LEEWAY_MS = 60_000;
const TOKEN_REFRESH_TIMEOUT_MS = 10_000;
const TOKEN_REFRESH_LOCK_POLL_MS = 50;
const TOKEN_REFRESH_LOCK_STALE_MS = TOKEN_REFRESH_TIMEOUT_MS + 30_000;
const TOKEN_REFRESH_LOCK_TIMEOUT_MS =
  TOKEN_REFRESH_LOCK_STALE_MS + TOKEN_REFRESH_TIMEOUT_MS;
const profileRefreshPromises = new Map<string, Promise<void>>();

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
  userId?: string;
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

function reloadProfileState(
  state: LangSmithProfileState,
): LangSmithProfileState {
  try {
    const config = JSON.parse(
      fsUtils.readFileSync(state.configPath),
    ) as LangSmithProfileConfigFile;
    const profile = config.profiles?.[state.profileName];
    if (!profile) {
      return state;
    }
    state.config = config;
    state.profile = profile;
  } catch {
    return state;
  }
  return state;
}

function getProfileRefreshKey(state: LangSmithProfileState): string {
  return `${state.configPath}\0${state.profileName}`;
}

function getProfileRefreshLockPath(state: LangSmithProfileState): string {
  return `${state.configPath}.oauth-refresh.lock`;
}

function isLockFileStale(lockPath: string): boolean {
  try {
    return (
      Date.now() - fsUtils.statSync(lockPath).mtimeMs >
      TOKEN_REFRESH_LOCK_STALE_MS
    );
  } catch {
    return false;
  }
}

function sleep(milliseconds: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function withFilesystemRefreshLock(
  state: LangSmithProfileState,
  refresh: () => Promise<void>,
): Promise<void> {
  const lockPath = getProfileRefreshLockPath(state);
  const deadline = Date.now() + TOKEN_REFRESH_LOCK_TIMEOUT_MS;
  let hasLock = false;
  while (!hasLock) {
    try {
      fsUtils.writeFileExclusiveSync(lockPath, `${Date.now()}\n`);
      hasLock = true;
      break;
    } catch (error) {
      const code = (error as { code?: string }).code;
      if (code !== "EEXIST") {
        await refresh();
        return;
      }
      if (isLockFileStale(lockPath)) {
        try {
          fsUtils.unlinkSync(lockPath);
        } catch {
          // Another process may have replaced the lock before us.
        }
        continue;
      }
      if (Date.now() >= deadline) {
        await refresh();
        return;
      }
      await sleep(TOKEN_REFRESH_LOCK_POLL_MS);
    }
  }
  try {
    await refresh();
  } finally {
    try {
      fsUtils.unlinkSync(lockPath);
    } catch {
      // Another process may have already removed a stale lock.
    }
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
  private managedAuthorizationValues = new Set<string>();

  private managedUserIdValues = new Set<string>();

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
      reloadProfileState(this.state);
    }
    if (shouldRefreshProfileToken(this.state.profile)) {
      const refreshKey = getProfileRefreshKey(this.state);
      let refreshPromise = profileRefreshPromises.get(refreshKey);
      if (!refreshPromise) {
        refreshPromise = withFilesystemRefreshLock(this.state, async () => {
          reloadProfileState(this.state);
          if (shouldRefreshProfileToken(this.state.profile)) {
            await this.refreshOAuthToken(fetchImplementation);
          }
        }).finally(() => {
          if (profileRefreshPromises.get(refreshKey) === refreshPromise) {
            profileRefreshPromises.delete(refreshKey);
          }
        });
        profileRefreshPromises.set(refreshKey, refreshPromise);
      }
      await waitForAbortSignal(refreshPromise, signal);
      reloadProfileState(this.state);
    }
    const header = authHeaderFromProfile(this.state.profile);
    this.rememberProfileAuthHeader(header);
    return header;
  }

  isProfileAuthorizationHeader(value: string): boolean {
    return this.managedAuthorizationValues.has(value);
  }

  isProfileUserIdHeader(value: string): boolean {
    return this.managedUserIdValues.has(value);
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
      if (header.userId) {
        this.managedUserIdValues.add(header.userId);
      }
    }
  }
}

function oauthAuthHeaderFromAccessToken(
  accessToken: string,
): ProfileAuthHeader {
  const header: ProfileAuthHeader = {
    name: "Authorization",
    value: `Bearer ${accessToken}`,
  };
  const userId = oauthUserIdFromAccessToken(accessToken);
  if (userId) {
    header.userId = userId;
  }
  return header;
}

function currentAuthHeaderFromProfile(
  profile: LangSmithProfile,
): ProfileAuthHeader | undefined {
  const oauthAccessToken = trimConfigValue(profile.oauth?.access_token);
  if (oauthAccessToken) {
    return oauthAuthHeaderFromAccessToken(oauthAccessToken);
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
    return oauthAuthHeaderFromAccessToken(oauthAccessToken);
  }
  const apiKey = trimConfigValue(profile.api_key);
  if (apiKey) {
    return { name: "x-api-key", value: apiKey };
  }
  return undefined;
}

function oauthUserIdFromAccessToken(accessToken: string): string | undefined {
  const [, encodedPayload] = accessToken.split(".");
  if (!encodedPayload) {
    return undefined;
  }
  try {
    const payload = JSON.parse(decodeBase64Url(encodedPayload)) as unknown;
    if (payload === null || typeof payload !== "object") {
      return undefined;
    }
    const value = (payload as Record<string, unknown>)[OAUTH_USER_ID_CLAIM];
    return typeof value === "string" && value.trim() ? value.trim() : undefined;
  } catch {
    return undefined;
  }
}

function decodeBase64Url(value: string): string {
  const base64 = value.replace(/-/g, "+").replace(/_/g, "/");
  const padded = base64.padEnd(
    base64.length + ((4 - (base64.length % 4)) % 4),
    "=",
  );
  return Buffer.from(padded, "base64").toString("utf8");
}
