import { proxyConfig } from "./proxy_config.js";
import type {
  GCSMountSpec,
  MountCacheConfig,
  S3MountSpec,
  SandboxMount,
  SandboxMountConfig,
  SandboxProxyRule,
} from "./types.js";

function requireNonEmptyString(value: string, field: string): string {
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error(`${field} must be a non-empty string`);
  }
  return value.trim();
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
    if (mount.type !== "s3" && mount.type !== "gcs") {
      throw new Error("mountConfig only supports s3 and gcs mounts");
    }
    return mount;
  });
}

function normalizeAuthRules(
  auth: SandboxProxyRule[],
): Record<string, SandboxProxyRule> {
  if (!Array.isArray(auth)) {
    throw new Error("auth must be an array of provider auth rules");
  }
  const byProvider: Record<string, SandboxProxyRule> = {};
  for (const rule of auth) {
    if (rule === null || typeof rule !== "object" || Array.isArray(rule)) {
      throw new Error("auth must be an array of provider auth rules");
    }
    const provider = (rule as Record<string, unknown>).type;
    if (provider !== "aws" && provider !== "gcp") {
      throw new Error("mountConfig auth only supports aws and gcp rules");
    }
    if (byProvider[provider] !== undefined) {
      throw new Error(`duplicate ${provider} auth rule in mountConfig`);
    }
    byProvider[provider] = rule;
  }
  return byProvider;
}

export function mountConfig({
  auth,
  mounts,
}: {
  auth: SandboxProxyRule[];
  mounts: SandboxMount[];
}): SandboxMountConfig {
  const normalizedMounts = normalizeMounts(mounts);
  const authByProvider = normalizeAuthRules(auth);
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
    mounts: normalizedMounts,
    proxyConfig: proxyConfig({
      rules: ["aws", "gcp"]
        .map((provider) => authByProvider[provider])
        .filter((rule): rule is SandboxProxyRule => rule !== undefined),
    }),
  };
}
