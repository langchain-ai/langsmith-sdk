import type {
  GCSMountSpec,
  GitMountRefSpec,
  GitMountSpec,
  MountCacheConfig,
  SandboxAwsMountAuth,
  SandboxGcpMountAuth,
  S3MountSpec,
  SandboxMount,
  SandboxMountAuth,
  SandboxMountAuthConfig,
  SandboxMountConfig,
  SandboxProxyConfig,
  SandboxProxyRule,
  SandboxProxySecret,
} from "./types.js";

function requireNonEmptyString(value: string, field: string): string {
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error(`${field} must be a non-empty string`);
  }
  return value.trim();
}

function copyMountSecret(secret: unknown, field: string): SandboxProxySecret {
  if (secret === null || typeof secret !== "object" || Array.isArray(secret)) {
    throw new Error(`${field} must be a sandbox secret`);
  }
  const candidate = secret as Partial<SandboxProxySecret>;
  if (candidate.type !== "workspace_secret" && candidate.type !== "opaque") {
    throw new Error(`${field} must use workspace_secret or opaque`);
  }
  if (typeof candidate.value !== "string" || candidate.value.trim() === "") {
    throw new Error(`${field}.value must be a non-empty string`);
  }
  return {
    type: candidate.type,
    value: candidate.value,
  };
}

export function awsMountAuth({
  accessKeyId,
  secretAccessKey,
}: {
  accessKeyId: SandboxProxySecret;
  secretAccessKey: SandboxProxySecret;
}): SandboxAwsMountAuth {
  return {
    type: "aws",
    aws: {
      access_key_id: copyMountSecret(accessKeyId, "accessKeyId"),
      secret_access_key: copyMountSecret(secretAccessKey, "secretAccessKey"),
    },
  };
}

export function gcpMountAuth({
  serviceAccountJson,
}: {
  serviceAccountJson: SandboxProxySecret;
}): SandboxGcpMountAuth {
  return {
    type: "gcp",
    gcp: {
      service_account_json: copyMountSecret(
        serviceAccountJson,
        "serviceAccountJson",
      ),
    },
  };
}

function requireGitRemoteUrl(remoteUrl: string): string {
  if (typeof remoteUrl !== "string" || remoteUrl === "") {
    throw new Error("remoteUrl must be a non-empty string");
  }
  if (
    remoteUrl.trim() !== remoteUrl ||
    /\s/u.test(remoteUrl) ||
    remoteUrl.includes(String.fromCharCode(0))
  ) {
    throw new Error("remoteUrl must not contain whitespace or NUL bytes");
  }

  let parsed: URL;
  try {
    parsed = new URL(remoteUrl);
  } catch {
    throw new Error("remoteUrl must be an absolute HTTPS URL");
  }

  if (parsed.protocol !== "https:" || parsed.host === "") {
    throw new Error("remoteUrl must be an absolute HTTPS URL");
  }
  if (parsed.username !== "" || parsed.password !== "") {
    throw new Error("remoteUrl must not include embedded credentials");
  }
  if (parsed.pathname === "" || parsed.pathname === "/") {
    throw new Error("remoteUrl must include a repository path");
  }
  if (parsed.search !== "" || parsed.hash !== "") {
    throw new Error("remoteUrl must not include query or fragment");
  }
  return remoteUrl;
}

function copyGitRef(ref: GitMountRefSpec): GitMountRefSpec {
  if (ref === null || typeof ref !== "object" || Array.isArray(ref)) {
    throw new Error("ref must be an object");
  }
  if (ref.type !== "branch" && ref.type !== "tag") {
    throw new Error("ref.type must be branch or tag");
  }
  return {
    type: ref.type,
    name: requireNonEmptyString(ref.name, "ref.name"),
  };
}

export function s3Mount({
  id,
  mountPath,
  bucket,
  region = "us-east-1",
  prefix,
  endpointUrl = "https://s3.amazonaws.com",
  pathStyle = false,
  readOnly,
  cache,
}: {
  id: string;
  mountPath: string;
  bucket: string;
  region?: string;
  prefix?: string;
  endpointUrl?: string;
  pathStyle?: boolean;
  readOnly?: boolean;
  cache?: MountCacheConfig;
}): S3MountSpec {
  const mount: S3MountSpec = {
    id: requireNonEmptyString(id, "id"),
    type: "s3",
    mount_path: requireNonEmptyString(mountPath, "mountPath"),
    s3: {
      endpoint_url: requireNonEmptyString(endpointUrl, "endpointUrl"),
      region: requireNonEmptyString(region, "region"),
      bucket: requireNonEmptyString(bucket, "bucket"),
      path_style: pathStyle,
    },
  };
  if (prefix !== undefined) {
    mount.s3.prefix = requireNonEmptyString(prefix, "prefix");
  }
  if (readOnly !== undefined) {
    mount.read_only = readOnly;
  }
  if (cache !== undefined) {
    mount.cache = { ...cache };
  }
  return mount;
}

export function gitMount({
  id,
  mountPath,
  remoteUrl,
  ref,
  refreshIntervalSeconds,
}: {
  id: string;
  mountPath: string;
  remoteUrl: string;
  ref?: GitMountRefSpec;
  refreshIntervalSeconds?: number;
}): GitMountSpec {
  const mount: GitMountSpec = {
    id: requireNonEmptyString(id, "id"),
    type: "git",
    mount_path: requireNonEmptyString(mountPath, "mountPath"),
    git: {
      remote_url: requireGitRemoteUrl(remoteUrl),
    },
  };
  if (ref !== undefined) {
    mount.git.ref = copyGitRef(ref);
  }
  if (refreshIntervalSeconds !== undefined) {
    if (refreshIntervalSeconds < 1) {
      throw new Error("refreshIntervalSeconds must be at least 1");
    }
    mount.git.refresh_interval_seconds = refreshIntervalSeconds;
  }
  return mount;
}

export function gcsMount({
  id,
  mountPath,
  bucket,
  prefix,
  readOnly,
  cache,
}: {
  id: string;
  mountPath: string;
  bucket: string;
  prefix?: string;
  readOnly?: boolean;
  cache?: MountCacheConfig;
}): GCSMountSpec {
  const mount: GCSMountSpec = {
    id: requireNonEmptyString(id, "id"),
    type: "gcs",
    mount_path: requireNonEmptyString(mountPath, "mountPath"),
    gcs: {
      bucket: requireNonEmptyString(bucket, "bucket"),
    },
  };
  if (prefix !== undefined) {
    mount.gcs.prefix = requireNonEmptyString(prefix, "prefix");
  }
  if (readOnly !== undefined) {
    mount.read_only = readOnly;
  }
  if (cache !== undefined) {
    mount.cache = { ...cache };
  }
  return mount;
}

function normalizeMounts(mounts: SandboxMount[]): SandboxMount[] {
  if (!Array.isArray(mounts) || mounts.length === 0) {
    throw new Error("mounts must be a non-empty array of mount objects");
  }
  return mounts.map((mount) => {
    if (mount === null || typeof mount !== "object" || Array.isArray(mount)) {
      throw new Error("mounts must be a non-empty array of mount objects");
    }
    if (mount.type !== "s3" && mount.type !== "gcs" && mount.type !== "git") {
      throw new Error("mountConfig only supports s3, gcs, and git mounts");
    }
    rejectProviderCredentialsInMount(mount);
    return mount;
  });
}

const FORBIDDEN_MOUNT_CREDENTIAL_FIELDS = new Set([
  "access_key_id",
  "secret_access_key",
  "session_token",
  "service_account_json",
  "access_token",
  "refresh_token",
  "credentials",
  "credential",
]);

function rejectProviderCredentialsInMount(value: unknown): void {
  if (Array.isArray(value)) {
    for (const child of value) {
      rejectProviderCredentialsInMount(child);
    }
    return;
  }
  if (value !== null && typeof value === "object") {
    for (const [key, child] of Object.entries(value)) {
      if (FORBIDDEN_MOUNT_CREDENTIAL_FIELDS.has(key)) {
        throw new Error(
          "provider credentials must be supplied in mountConfig.auth, not individual mount specs",
        );
      }
      rejectProviderCredentialsInMount(child);
    }
  }
}

function normalizeMountAuth(auth: SandboxMountAuth[]): SandboxMountAuthConfig {
  if (!Array.isArray(auth)) {
    throw new Error("auth must be an array of provider auth blocks");
  }
  const byProvider: SandboxMountAuthConfig = {};
  for (const block of auth) {
    if (block === null || typeof block !== "object" || Array.isArray(block)) {
      throw new Error("auth must be an array of provider auth blocks");
    }
    const provider = (block as unknown as Record<string, unknown>).type;
    if (provider !== "aws" && provider !== "gcp") {
      throw new Error("mountConfig auth only supports aws and gcp blocks");
    }
    if (byProvider[provider] !== undefined) {
      throw new Error(`duplicate ${provider} auth rule in mountConfig`);
    }
    if (provider === "aws") {
      const aws = (block as Partial<SandboxAwsMountAuth>).aws;
      if (aws === undefined) {
        throw new Error("aws mount auth must include an aws block");
      }
      byProvider.aws = {
        access_key_id: copyMountSecret(aws.access_key_id, "accessKeyId"),
        secret_access_key: copyMountSecret(
          aws.secret_access_key,
          "secretAccessKey",
        ),
      };
    } else {
      const gcp = (block as Partial<SandboxGcpMountAuth>).gcp;
      if (gcp === undefined) {
        throw new Error("gcp mount auth must include a gcp block");
      }
      byProvider.gcp = {
        service_account_json: copyMountSecret(
          gcp.service_account_json,
          "serviceAccountJson",
        ),
      };
    }
  }
  return byProvider;
}

export function mountConfig({
  auth = [],
  mounts,
}: {
  auth?: SandboxMountAuth[];
  mounts: SandboxMount[];
}): SandboxMountConfig {
  const normalizedMounts = normalizeMounts(mounts);
  const authByProvider = normalizeMountAuth(auth);
  const mountProviders = new Set(normalizedMounts.map((mount) => mount.type));

  if (mountProviders.has("s3") && authByProvider.aws === undefined) {
    throw new Error("s3 mounts require aws auth in mountConfig");
  }
  if (mountProviders.has("gcs") && authByProvider.gcp === undefined) {
    throw new Error("gcs mounts require gcp auth in mountConfig");
  }
  if (authByProvider.aws !== undefined && !mountProviders.has("s3")) {
    throw new Error("aws auth requires at least one s3 mount in mountConfig");
  }
  if (authByProvider.gcp !== undefined && !mountProviders.has("gcs")) {
    throw new Error("gcp auth requires at least one gcs mount in mountConfig");
  }

  return {
    auth: authByProvider,
    mounts: normalizedMounts,
  };
}

export function validateMountConfigProxyConfig(
  mountConfig: SandboxMountConfig,
  proxyConfig: SandboxProxyConfig | undefined,
): void {
  if (proxyConfig === undefined) {
    return;
  }
  const rules = proxyConfig.rules ?? [];
  if (!Array.isArray(rules)) {
    throw new Error("proxyConfig rules must be an array");
  }
  for (const rule of rules) {
    if (rule === null || typeof rule !== "object" || Array.isArray(rule)) {
      continue;
    }
    const ruleType = (rule as SandboxProxyRule).type;
    if (
      (ruleType === "aws" || ruleType === "gcp") &&
      mountConfig.auth[ruleType] !== undefined
    ) {
      throw new Error(
        `${ruleType} auth cannot be provided in both mountConfig and proxyConfig`,
      );
    }
  }
}
