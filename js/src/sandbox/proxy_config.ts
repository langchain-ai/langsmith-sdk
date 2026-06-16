import type {
  SandboxAccessControl,
  SandboxAwsAuthRule,
  SandboxGcpAuthRule,
  SandboxProxyConfig,
  SandboxProxyRule,
  SandboxProxySecret,
} from "./types.js";

const DEFAULT_GCP_AUTH_MATCH_HOSTS = [
  "storage.googleapis.com",
  "www.googleapis.com",
];
const PROVIDER_RULE_TYPES = new Set(["aws", "gcp"]);

function requireNonEmptyString(value: string, field: string): string {
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error(`${field} must be a non-empty string`);
  }
  return value.trim();
}

function requireNonEmptyStringArray(values: string[], field: string): string[] {
  if (!Array.isArray(values) || values.length === 0) {
    throw new Error(`${field} must be a non-empty array of strings`);
  }
  return values.map((value) => requireNonEmptyString(value, field));
}

function requireProxyRules(
  rules: SandboxProxyRule[] | undefined,
): SandboxProxyRule[] {
  if (rules === undefined) {
    return [];
  }
  if (!Array.isArray(rules)) {
    throw new Error("rules must be an array of proxy rule objects");
  }
  return rules.map((rule) => {
    if (rule === null || typeof rule !== "object" || Array.isArray(rule)) {
      throw new Error("rules must be an array of proxy rule objects");
    }
    return rule;
  });
}

/** Reference a LangSmith workspace secret in a sandbox proxy configuration. */
export function workspaceSecret(name: string): SandboxProxySecret {
  const normalized = requireNonEmptyString(name, "name");
  const startsWithBrace = normalized.startsWith("{");
  const endsWithBrace = normalized.endsWith("}");
  if (startsWithBrace !== endsWithBrace) {
    throw new Error("workspace secret must be a name or a {NAME} reference");
  }
  if (startsWithBrace && normalized.slice(1, -1).trim() === "") {
    throw new Error("workspace secret reference must contain a name");
  }
  return {
    type: "workspace_secret",
    value: startsWithBrace ? normalized : `{${normalized}}`,
  };
}

/** Provide a write-only secret value for a sandbox proxy configuration. */
export function opaqueSecret(value: string): SandboxProxySecret {
  return {
    type: "opaque",
    value: requireNonEmptyString(value, "value"),
  };
}

/** Build a sandbox proxy config from one or more proxy rules. */
export function proxyConfig({
  rules,
  noProxy,
  accessControl,
}: {
  rules?: SandboxProxyRule[];
  noProxy?: string[];
  accessControl?: SandboxAccessControl;
} = {}): SandboxProxyConfig {
  const config: SandboxProxyConfig = {
    rules: requireProxyRules(rules),
  };
  if (noProxy !== undefined) {
    config.no_proxy = requireNonEmptyStringArray(noProxy, "noProxy");
  }
  if (accessControl !== undefined) {
    config.access_control = { ...accessControl };
  }
  return config;
}

function providerRuleTypes(config: SandboxProxyConfig): Set<string> {
  const providers = new Set<string>();
  for (const rule of config.rules ?? []) {
    if (rule === null || typeof rule !== "object" || Array.isArray(rule)) {
      continue;
    }
    const ruleType = (rule as Record<string, unknown>).type;
    if (typeof ruleType === "string" && PROVIDER_RULE_TYPES.has(ruleType)) {
      providers.add(ruleType);
    }
  }
  return providers;
}

export function mergeProxyConfigs(
  generatedConfig: SandboxProxyConfig | undefined,
  explicitConfig: SandboxProxyConfig | undefined,
): SandboxProxyConfig | undefined {
  if (generatedConfig === undefined) {
    return explicitConfig;
  }
  if (explicitConfig === undefined) {
    return generatedConfig;
  }
  const generatedProviders = providerRuleTypes(generatedConfig);
  for (const provider of providerRuleTypes(explicitConfig)) {
    if (generatedProviders.has(provider)) {
      throw new Error(
        `${provider} auth cannot be provided in both mountConfig and proxyConfig`,
      );
    }
  }
  return {
    ...generatedConfig,
    ...explicitConfig,
    rules: [...(generatedConfig.rules ?? []), ...(explicitConfig.rules ?? [])],
  };
}

/** Build a sandbox proxy rule that signs AWS HTTPS requests with SigV4. */
export function awsAuth({
  accessKeyId,
  secretAccessKey,
  name = "aws",
  enabled = true,
}: {
  accessKeyId: SandboxProxySecret;
  secretAccessKey: SandboxProxySecret;
  name?: string;
  enabled?: boolean;
}): SandboxAwsAuthRule {
  return {
    name: requireNonEmptyString(name, "name"),
    type: "aws",
    enabled,
    aws: {
      access_key_id: accessKeyId,
      secret_access_key: secretAccessKey,
    },
  };
}

/** Build a sandbox proxy rule that injects GCP OAuth bearer auth. */
export function gcpAuth({
  serviceAccountJson,
  scopes,
  matchHosts = DEFAULT_GCP_AUTH_MATCH_HOSTS,
  name = "gcp",
  enabled = true,
}: {
  serviceAccountJson: SandboxProxySecret;
  scopes: string[];
  matchHosts?: string[];
  name?: string;
  enabled?: boolean;
}): SandboxGcpAuthRule {
  return {
    name: requireNonEmptyString(name, "name"),
    type: "gcp",
    enabled,
    match_hosts: requireNonEmptyStringArray(matchHosts, "matchHosts"),
    gcp: {
      service_account_json: serviceAccountJson,
      scopes: requireNonEmptyStringArray(scopes, "scopes"),
    },
  };
}
