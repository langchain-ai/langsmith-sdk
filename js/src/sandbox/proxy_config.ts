import type {
  SandboxAccessControl,
  SandboxAwsAuthRule,
  SandboxGcpAuthRule,
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

function requireNonEmptyStringArray(values: string[], field: string): string[] {
  if (!Array.isArray(values) || values.length === 0) {
    throw new Error(`${field} must be a non-empty array of strings`);
  }
  return values.map((value) => requireNonEmptyString(value, field));
}

function requireEnvVars(
  envVars: Record<string, string>,
): Record<string, string> {
  if (
    envVars === null ||
    typeof envVars !== "object" ||
    Array.isArray(envVars)
  ) {
    throw new Error("envVars must be a non-empty object of names to values");
  }
  const entries = Object.entries(envVars);
  if (entries.length === 0) {
    throw new Error("envVars must be a non-empty object of names to values");
  }
  return Object.fromEntries(
    entries.map(([name, value]) => [
      requireNonEmptyString(name, "envVars name"),
      requireNonEmptyString(value, `envVars[${name}]`),
    ]),
  );
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
    validateProxyProviderRule(rule);
    return rule;
  });
}

function validateProxyProviderRule(rule: SandboxProxyRule): void {
  if ((rule as Record<string, unknown>).type !== "gcp") {
    return;
  }
  const gcp = (rule as Partial<SandboxGcpAuthRule>).gcp;
  if (gcp === undefined || gcp.scopes === undefined) {
    throw new Error("gcp proxy auth rules require scopes");
  }
  requireNonEmptyStringArray(gcp.scopes, "scopes");
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

/** Build a sandbox proxy rule that signs AWS HTTPS requests with SigV4. */
export function awsAuth({
  accessKeyId,
  secretAccessKey,
  name = "aws",
  enabled = true,
  envVars,
}: {
  accessKeyId: SandboxProxySecret;
  secretAccessKey: SandboxProxySecret;
  name?: string;
  enabled?: boolean;
  envVars?: Record<string, string>;
}): SandboxAwsAuthRule {
  const rule: SandboxAwsAuthRule = {
    name: requireNonEmptyString(name, "name"),
    type: "aws",
    enabled,
    aws: {
      access_key_id: accessKeyId,
      secret_access_key: secretAccessKey,
    },
  };
  if (envVars !== undefined) {
    rule.env_vars = requireEnvVars(envVars);
  }
  return rule;
}

/** Build a sandbox proxy rule that injects GCP OAuth bearer auth. */
export function gcpAuth({
  serviceAccountJson,
  scopes,
  name = "gcp",
  enabled = true,
  envVars,
}: {
  serviceAccountJson: SandboxProxySecret;
  scopes?: string[];
  name?: string;
  enabled?: boolean;
  envVars?: Record<string, string>;
}): SandboxGcpAuthRule {
  const gcp: SandboxGcpAuthRule["gcp"] = {
    service_account_json: serviceAccountJson,
  };
  if (scopes !== undefined) {
    gcp.scopes = requireNonEmptyStringArray(scopes, "scopes");
  }
  const rule: SandboxGcpAuthRule = {
    name: requireNonEmptyString(name, "name"),
    type: "gcp",
    enabled,
    gcp,
  };
  if (envVars !== undefined) {
    rule.env_vars = requireEnvVars(envVars);
  }
  return rule;
}
