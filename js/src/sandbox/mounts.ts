import type {
  AzureBlobMountSpec,
  ContextHubMountSpec,
  GCSMountSpec,
  GitMountRefSpec,
  GitMountSpec,
  MountCacheConfig,
  SandboxAwsAuthRule,
  SandboxAzureAuthRule,
  SandboxAzureMountAuthConfig,
  SandboxGcpAuthRule,
  SandboxGcpMountWorkloadIdentityAuthConfig,
  S3MountSpec,
  SandboxMount,
  SandboxMountAuth,
  SandboxMountAuthConfig,
  SandboxMountConfig,
  SandboxProxyConfig,
  SandboxProxyRule,
  SandboxProxySecret,
} from "./types.js";
import { getAwsRoleConfig } from "./proxy_config.js";

function requireNonEmptyString(value: unknown, field: string): string {
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

export function azureBlobMount({
  id,
  mountPath,
  storageAccount,
  container,
  prefix,
  readOnly,
  cache,
}: {
  id: string;
  mountPath: string;
  storageAccount: string;
  container: string;
  prefix?: string;
  readOnly?: boolean;
  cache?: MountCacheConfig;
}): AzureBlobMountSpec {
  const mount: AzureBlobMountSpec = {
    id: requireNonEmptyString(id, "id"),
    type: "azure_blob",
    mount_path: requireNonEmptyString(mountPath, "mountPath"),
    azure_blob: {
      storage_account: requireNonEmptyString(storageAccount, "storageAccount"),
      container: requireNonEmptyString(container, "container"),
    },
  };
  if (prefix !== undefined) {
    mount.azure_blob.prefix = requireNonEmptyString(prefix, "prefix");
  }
  if (readOnly !== undefined) {
    mount.read_only = readOnly;
  }
  if (cache !== undefined) {
    mount.cache = { ...cache };
  }
  return mount;
}

/**
 * Build a read-only Context Hub mount. The sync is one-way: files written
 * under the mount path inside the sandbox are never pushed back to the repo,
 * and the next sync overwrites them.
 */
export function contextHubMount({
  id,
  mountPath,
  repo,
  initialPullOnly,
}: {
  id: string;
  mountPath: string;
  repo: string;
  initialPullOnly?: boolean;
}): ContextHubMountSpec {
  const mount: ContextHubMountSpec = {
    id: requireNonEmptyString(id, "id"),
    type: "contexthub",
    mount_path: requireNonEmptyString(mountPath, "mountPath"),
    contexthub: {
      repo: requireNonEmptyString(repo, "repo"),
    },
  };
  if (initialPullOnly !== undefined) {
    mount.contexthub.initial_pull_only = initialPullOnly;
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
    if (
      mount.type !== "s3" &&
      mount.type !== "gcs" &&
      mount.type !== "azure_blob" &&
      mount.type !== "git" &&
      mount.type !== "contexthub"
    ) {
      throw new Error(
        "mountConfig only supports s3, gcs, azure_blob, git, and contexthub mounts",
      );
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
  "account_key",
  "sas_token",
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

function gcpMountAuth(
  gcp: SandboxGcpAuthRule["gcp"],
): SandboxMountAuthConfig["gcp"] {
  if (!gcp.workload_identity_provider) {
    return {
      service_account_json: copyMountSecret(
        gcp.service_account_json,
        "serviceAccountJson",
      ),
    };
  }
  if (gcp.service_account_json !== undefined) {
    throw new Error(
      "workloadIdentityProvider and serviceAccountJson are mutually exclusive",
    );
  }
  const config: SandboxGcpMountWorkloadIdentityAuthConfig = {
    workload_identity_provider: requireNonEmptyString(
      gcp.workload_identity_provider,
      "workloadIdentityProvider",
    ),
  };
  if (gcp.service_account_email !== undefined) {
    config.service_account_email = requireNonEmptyString(
      gcp.service_account_email,
      "serviceAccountEmail",
    );
  }
  if (gcp.subject_scope !== undefined) {
    config.subject_scope = requireNonEmptyString(
      gcp.subject_scope,
      "subjectScope",
    );
  }
  return config;
}

/**
 * Keep only the fields mount_config.auth.azure accepts. A static block's
 * storage_account is checked against the mounts by mountConfig; resources do
 * not apply to mounts.
 */
function azureMountAuth(
  azure: Record<string, unknown>,
): SandboxAzureMountAuthConfig {
  if (azure.tenant_id || azure.client_id) {
    if (azure.account_key !== undefined || azure.sas_token !== undefined) {
      throw new Error(
        "tenantId/clientId and accountKey or sasToken are mutually exclusive",
      );
    }
    const config: SandboxAzureMountAuthConfig = {
      tenant_id: requireNonEmptyString(azure.tenant_id, "tenantId"),
      client_id: requireNonEmptyString(azure.client_id, "clientId"),
    };
    if (azure.subject_scope !== undefined) {
      config.subject_scope = requireNonEmptyString(
        azure.subject_scope,
        "subjectScope",
      );
    }
    return config;
  }
  const hasKey = azure.account_key !== undefined;
  if (hasKey === (azure.sas_token !== undefined)) {
    throw new Error(
      "azure mount auth requires tenantId and clientId, or exactly one of accountKey or sasToken",
    );
  }
  return hasKey
    ? { account_key: copyMountSecret(azure.account_key, "accountKey") }
    : { sas_token: copyMountSecret(azure.sas_token, "sasToken") };
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
    if (provider !== "aws" && provider !== "gcp" && provider !== "azure") {
      throw new Error(
        "mountConfig auth only supports aws, gcp, and azure blocks",
      );
    }
    if (byProvider[provider] !== undefined) {
      throw new Error(`duplicate ${provider} auth rule in mountConfig`);
    }
    if (provider === "aws") {
      const aws = (block as Partial<SandboxAwsAuthRule>).aws;
      if (aws === undefined) {
        throw new Error("aws mount auth must include an aws block");
      }
      const role = getAwsRoleConfig(aws);
      if (role !== undefined) {
        byProvider.aws = role;
        continue;
      }
      if ("subject_scope" in aws && aws.subject_scope !== undefined) {
        throw new Error("subjectScope requires roleArn");
      }
      byProvider.aws = {
        access_key_id: copyMountSecret(aws.access_key_id, "accessKeyId"),
        secret_access_key: copyMountSecret(
          aws.secret_access_key,
          "secretAccessKey",
        ),
      };
    } else if (provider === "gcp") {
      const gcp = (block as Partial<SandboxGcpAuthRule>).gcp;
      if (gcp === undefined) {
        throw new Error("gcp mount auth must include a gcp block");
      }
      byProvider.gcp = gcpMountAuth(gcp);
    } else {
      const azure = (block as Partial<SandboxAzureAuthRule>).azure;
      if (azure === undefined) {
        throw new Error("azure mount auth must include an azure block");
      }
      byProvider.azure = azureMountAuth(
        azure as unknown as Record<string, unknown>,
      );
    }
  }
  return byProvider;
}

function staticAzureAuthStorageAccount(
  auth: SandboxMountAuth[],
): string | undefined {
  for (const block of auth) {
    if (block?.type !== "azure") continue;
    const azure = (block as SandboxAzureAuthRule).azure as unknown as
      | Record<string, unknown>
      | undefined;
    if (azure && !azure.tenant_id && !azure.client_id) {
      return typeof azure.storage_account === "string"
        ? azure.storage_account
        : undefined;
    }
  }
  return undefined;
}

/**
 * Build mount-scoped auth, or use an enabled rule from proxyConfig: an AWS
 * rule for S3, a GCP workload identity rule for GCS, or an Azure rule for
 * Azure Blob. Pass the same proxyConfig to sandbox creation; that rule remains
 * general proxy auth and is not restricted to the mounts.
 */
export function mountConfig({
  auth = [],
  mounts,
  proxyConfig,
}: {
  auth?: SandboxMountAuth[];
  mounts: SandboxMount[];
  proxyConfig?: SandboxProxyConfig;
}): SandboxMountConfig {
  const normalizedMounts = normalizeMounts(mounts);
  const authByProvider = normalizeMountAuth(auth);
  const mountProviders = new Set(normalizedMounts.map((mount) => mount.type));
  const enabledRules = (proxyConfig?.rules ?? []).filter(
    (rule) => rule?.enabled === true,
  );
  const proxyProviders = new Set(enabledRules.map((rule) => rule.type));
  const hasGcpWorkloadIdentityRule = enabledRules.some(
    (rule) =>
      rule.type === "gcp" &&
      Boolean(
        (rule as Partial<SandboxGcpAuthRule>).gcp?.workload_identity_provider,
      ),
  );

  if (
    mountProviders.has("s3") &&
    authByProvider.aws === undefined &&
    !proxyProviders.has("aws")
  ) {
    throw new Error("s3 mounts require aws auth in mountConfig");
  }
  if (
    mountProviders.has("gcs") &&
    authByProvider.gcp === undefined &&
    !hasGcpWorkloadIdentityRule
  ) {
    throw new Error(
      "gcs mounts require gcp auth in mountConfig or a GCP workload identity rule in proxyConfig",
    );
  }
  if (
    mountProviders.has("azure_blob") &&
    authByProvider.azure === undefined &&
    !proxyProviders.has("azure")
  ) {
    throw new Error("azure_blob mounts require azure auth in mountConfig");
  }
  if (authByProvider.aws !== undefined && !mountProviders.has("s3")) {
    throw new Error("aws auth requires at least one s3 mount in mountConfig");
  }
  if (authByProvider.gcp !== undefined && !mountProviders.has("gcs")) {
    throw new Error("gcp auth requires at least one gcs mount in mountConfig");
  }
  if (authByProvider.azure !== undefined && !mountProviders.has("azure_blob")) {
    throw new Error(
      "azure auth requires at least one azure_blob mount in mountConfig",
    );
  }
  const staticAccount = staticAzureAuthStorageAccount(auth);
  if (staticAccount !== undefined) {
    const accounts = new Set(
      normalizedMounts
        .filter(
          (mount): mount is AzureBlobMountSpec => mount.type === "azure_blob",
        )
        .map((mount) => mount.azure_blob.storage_account),
    );
    if (accounts.size !== 1 || !accounts.has(staticAccount)) {
      throw new Error(
        "azure_blob mounts using an azure account key or SAS token must all use the auth's storageAccount",
      );
    }
  }

  const config: SandboxMountConfig = {
    auth: authByProvider,
    mounts: normalizedMounts,
  };
  validateMountConfigProxyConfig(config, proxyConfig);
  return config;
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
      (ruleType === "aws" || ruleType === "gcp" || ruleType === "azure") &&
      mountConfig.auth[ruleType] !== undefined
    ) {
      throw new Error(
        `${ruleType} auth cannot be provided in both mountConfig and proxyConfig`,
      );
    }
  }
}
