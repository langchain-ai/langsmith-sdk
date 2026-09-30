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
    entries.map(([name, value]) => {
      // Validated on the trimmed form, stored verbatim: whitespace can be significant.
      requireNonEmptyString(value, `envVars[${name}]`);
      return [requireNonEmptyString(name, "envVars name"), value];
    }),
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
  if (rule.type === "aws") {
    getAwsRoleArn(rule.aws);
    return;
  }
  if ((rule as Record<string, unknown>).type !== "gcp") {
    return;
  }
  const gcp = (rule as Partial<SandboxGcpAuthRule>).gcp;
  if (gcp === undefined || gcp.scopes === undefined) {
    throw new Error("gcp proxy auth rules require scopes");
  }
  requireNonEmptyStringArray(gcp.scopes, "scopes");
}

/** Validate role-only descriptors without tightening legacy static inputs. */
export function getAwsRoleArn(aws: unknown): string | undefined {
  if (aws === null || typeof aws !== "object" || Array.isArray(aws)) {
    return undefined;
  }
  const config = aws as Record<string, unknown>;
  if (!("role_arn" in config) || config.role_arn === "") {
    return undefined;
  }
  const roleArn = requireNonEmptyString(config.role_arn as string, "roleArn");
  if (Object.keys(config).some((key) => key !== "role_arn")) {
    throw new Error("AWS role auth must contain only role_arn");
  }
  return roleArn;
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
  accessControl,
}: {
  rules?: SandboxProxyRule[];
  /** @deprecated Ignored. The sandbox runtime has no proxy bypass list. */
  noProxy?: string[];
  accessControl?: SandboxAccessControl;
} = {}): SandboxProxyConfig {
  const config: SandboxProxyConfig = {
    rules: requireProxyRules(rules),
  };
  if (accessControl !== undefined) {
    config.access_control = { ...accessControl };
  }
  return config;
}

interface AwsAuthCommonOptions {
  name?: string;
  enabled?: boolean;
  envVars?: Record<string, string>;
}

type AwsStaticAuthConfig = Extract<
  SandboxAwsAuthRule["aws"],
  { access_key_id: SandboxProxySecret }
>;

type AwsRoleAuthConfig = Extract<
  SandboxAwsAuthRule["aws"],
  { role_arn: string }
>;

type AwsStaticAuthOptions = AwsAuthCommonOptions & {
  accessKeyId: SandboxProxySecret;
  secretAccessKey: SandboxProxySecret;
  roleArn?: "";
};

type AwsRoleAuthOptions = AwsAuthCommonOptions & {
  roleArn: string;
  accessKeyId?: never;
  secretAccessKey?: never;
};

/**
 * Sign supported AWS HTTPS requests using static keys or an IAM role.
 * Role auth requires backend support and is configured at sandbox creation.
 * LangSmith supplies the workspace External ID and renews credentials.
 * A role in proxyConfig uses its effective IAM permissions; the same helper
 * in mountConfig.auth uses the backend's mount-scoped S3 permissions.
 */
export function awsAuth(
  options: AwsStaticAuthOptions,
): SandboxAwsAuthRule<AwsStaticAuthConfig>;
export function awsAuth(
  options: AwsRoleAuthOptions,
): SandboxAwsAuthRule<AwsRoleAuthConfig>;
export function awsAuth(
  options: AwsStaticAuthOptions | AwsRoleAuthOptions,
): SandboxAwsAuthRule;
export function awsAuth({
  accessKeyId,
  secretAccessKey,
  roleArn,
  name = "aws",
  enabled = true,
  envVars,
}: AwsStaticAuthOptions | AwsRoleAuthOptions): SandboxAwsAuthRule {
  const candidate: Record<string, unknown> = {};
  if (roleArn !== undefined) candidate.role_arn = roleArn;
  if (accessKeyId !== undefined) candidate.access_key_id = accessKeyId;
  if (secretAccessKey !== undefined)
    candidate.secret_access_key = secretAccessKey;
  const normalizedRole = getAwsRoleArn(candidate);
  let aws: SandboxAwsAuthRule["aws"];
  if (normalizedRole !== undefined) {
    aws = { role_arn: normalizedRole };
  } else {
    if (accessKeyId === undefined || secretAccessKey === undefined) {
      throw new Error("AWS auth requires roleArn or both static credentials");
    }
    aws = { access_key_id: accessKeyId, secret_access_key: secretAccessKey };
  }
  const rule: SandboxAwsAuthRule = {
    name: requireNonEmptyString(name, "name"),
    type: "aws",
    enabled,
    aws,
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
