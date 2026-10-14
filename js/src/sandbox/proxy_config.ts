import type {
  SandboxAccessControl,
  SandboxAwsAuthRule,
  SandboxAzureAuthRule,
  SandboxAzureResource,
  SandboxGcpAuthRule,
  SandboxProxyConfig,
  SandboxProxyRule,
  SandboxProxySecret,
} from "./types.js";

function requireNonEmptyString(value: unknown, field: string): string {
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
  if (gcp?.scopes !== undefined) {
    requireNonEmptyStringArray(gcp.scopes, "scopes");
  }
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
  const roleArn = requireNonEmptyString(config.role_arn, "roleArn");
  if (
    Object.keys(config).some(
      (key) => key !== "role_arn" && key !== "subject_scope",
    )
  ) {
    throw new Error(
      "AWS role auth must contain only role_arn and subject_scope",
    );
  }
  return roleArn;
}

/** Normalized AWS role descriptor, or undefined for static credentials. */
export function getAwsRoleConfig(
  aws: unknown,
): { role_arn: string; subject_scope?: string } | undefined {
  const roleArn = getAwsRoleArn(aws);
  if (roleArn === undefined) {
    return undefined;
  }
  const subjectScope = (aws as Record<string, unknown>).subject_scope;
  return subjectScope === undefined
    ? { role_arn: roleArn }
    : {
        role_arn: roleArn,
        subject_scope: requireNonEmptyString(subjectScope, "subjectScope"),
      };
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
  /**
   * Workload identity token subject: `"workspace"` (default) or
   * `"tag:<tag value id>"`, which must be one of the sandbox's tag value IDs.
   */
  subjectScope?: string;
  accessKeyId?: never;
  secretAccessKey?: never;
};

/**
 * Sign supported AWS HTTPS requests using static keys or an IAM role.
 * The role is assumed with AssumeRoleWithWebIdentity using a LangSmith-signed
 * workload identity token, is configured at sandbox creation, and LangSmith
 * renews its credentials.
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
  subjectScope,
  name = "aws",
  enabled = true,
  envVars,
}:
  | (AwsStaticAuthOptions & { subjectScope?: string })
  | AwsRoleAuthOptions): SandboxAwsAuthRule {
  const candidate: Record<string, unknown> = {};
  if (roleArn !== undefined) candidate.role_arn = roleArn;
  if (subjectScope !== undefined) candidate.subject_scope = subjectScope;
  if (accessKeyId !== undefined) candidate.access_key_id = accessKeyId;
  if (secretAccessKey !== undefined)
    candidate.secret_access_key = secretAccessKey;
  const roleConfig = getAwsRoleConfig(candidate);
  let aws: SandboxAwsAuthRule["aws"];
  if (roleConfig !== undefined) {
    aws = roleConfig;
  } else {
    if (subjectScope !== undefined) {
      throw new Error("subjectScope requires roleArn");
    }
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

interface ProviderAuthCommonOptions {
  name?: string;
  enabled?: boolean;
  envVars?: Record<string, string>;
}

type GcpServiceAccountAuthOptions = ProviderAuthCommonOptions & {
  serviceAccountJson: SandboxProxySecret;
  /** OAuth scopes; the server defaults to cloud-platform when omitted. */
  scopes?: string[];
  workloadIdentityProvider?: never;
  serviceAccountEmail?: never;
  subjectScope?: never;
};

type GcpWorkloadIdentityAuthOptions = ProviderAuthCommonOptions & {
  /**
   * Full provider name of a workload identity provider that trusts
   * LangSmith's OIDC issuer:
   * `//iam.googleapis.com/projects/<number>/locations/global/workloadIdentityPools/<pool>/providers/<provider>`.
   */
  workloadIdentityProvider: string;
  /** Service account to impersonate; omitted uses the federated principal. */
  serviceAccountEmail?: string;
  /** `"workspace"` (default) or `"tag:<tag value id>"`. */
  subjectScope?: string;
  /** OAuth scopes; the server defaults to cloud-platform when omitted. */
  scopes?: string[];
  serviceAccountJson?: never;
};

/**
 * Build a sandbox proxy rule that injects GCP OAuth bearer auth, from a
 * service account key or workload identity federation. Workload identity is
 * configured at sandbox creation.
 */
export function gcpAuth({
  serviceAccountJson,
  workloadIdentityProvider,
  serviceAccountEmail,
  subjectScope,
  scopes,
  name = "gcp",
  enabled = true,
  envVars,
}:
  | GcpServiceAccountAuthOptions
  | GcpWorkloadIdentityAuthOptions): SandboxGcpAuthRule {
  let gcp: SandboxGcpAuthRule["gcp"];
  if (workloadIdentityProvider !== undefined) {
    if (serviceAccountJson !== undefined) {
      throw new Error(
        "workloadIdentityProvider and serviceAccountJson are mutually exclusive",
      );
    }
    gcp = {
      workload_identity_provider: requireNonEmptyString(
        workloadIdentityProvider,
        "workloadIdentityProvider",
      ),
    };
    if (serviceAccountEmail !== undefined) {
      gcp.service_account_email = requireNonEmptyString(
        serviceAccountEmail,
        "serviceAccountEmail",
      );
    }
    if (subjectScope !== undefined) {
      gcp.subject_scope = requireNonEmptyString(subjectScope, "subjectScope");
    }
  } else {
    if (serviceAccountEmail !== undefined || subjectScope !== undefined) {
      throw new Error(
        "serviceAccountEmail and subjectScope require workloadIdentityProvider",
      );
    }
    if (serviceAccountJson === undefined) {
      throw new Error(
        "GCP auth requires serviceAccountJson or workloadIdentityProvider",
      );
    }
    gcp = { service_account_json: serviceAccountJson };
  }
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

type AzureWorkloadIdentityAuthOptions = ProviderAuthCommonOptions & {
  /** Entra tenant ID (GUID). */
  tenantId: string;
  /** App registration or user-assigned managed identity client ID (GUID). */
  clientId: string;
  /** `"workspace"` (default) or `"tag:<tag value id>"`. */
  subjectScope?: string;
  /** Resources to request tokens for; all supported ones when omitted. */
  resources?: SandboxAzureResource[];
  storageAccount?: never;
  accountKey?: never;
  sasToken?: never;
};

type AzureAccountKeyAuthOptions = ProviderAuthCommonOptions & {
  storageAccount: string;
  accountKey: SandboxProxySecret;
  sasToken?: never;
  tenantId?: never;
  clientId?: never;
  subjectScope?: never;
  resources?: never;
};

type AzureSasAuthOptions = ProviderAuthCommonOptions & {
  storageAccount: string;
  sasToken: SandboxProxySecret;
  accountKey?: never;
  tenantId?: never;
  clientId?: never;
  subjectScope?: never;
  resources?: never;
};

/**
 * Build a sandbox proxy rule that authenticates requests to built-in Azure
 * hosts. Use exactly one form: Entra workload identity (`tenantId` and
 * `clientId` of an app registration or user-assigned managed identity that
 * trusts LangSmith's OIDC issuer; configured at sandbox creation), a storage
 * account key, or a SAS token. Keys and SAS tokens must be `workspaceSecret`
 * or `opaqueSecret` values.
 */
export function azureAuth({
  tenantId,
  clientId,
  subjectScope,
  resources,
  storageAccount,
  accountKey,
  sasToken,
  name = "azure",
  enabled = true,
  envVars,
}:
  | AzureWorkloadIdentityAuthOptions
  | AzureAccountKeyAuthOptions
  | AzureSasAuthOptions): SandboxAzureAuthRule {
  let azure: SandboxAzureAuthRule["azure"];
  if (tenantId !== undefined || clientId !== undefined) {
    if (
      storageAccount !== undefined ||
      accountKey !== undefined ||
      sasToken !== undefined
    ) {
      throw new Error(
        "tenantId/clientId and storageAccount, accountKey or sasToken are mutually exclusive",
      );
    }
    azure = {
      tenant_id: requireNonEmptyString(tenantId, "tenantId"),
      client_id: requireNonEmptyString(clientId, "clientId"),
    };
    if (subjectScope !== undefined) {
      azure.subject_scope = requireNonEmptyString(subjectScope, "subjectScope");
    }
    if (resources !== undefined) {
      azure.resources = requireNonEmptyStringArray(
        resources,
        "resources",
      ) as SandboxAzureResource[];
    }
  } else {
    if (subjectScope !== undefined || resources !== undefined) {
      throw new Error(
        "subjectScope and resources require tenantId and clientId",
      );
    }
    if ((accountKey === undefined) === (sasToken === undefined)) {
      throw new Error(
        "Azure auth requires tenantId and clientId, or storageAccount with exactly one of accountKey or sasToken",
      );
    }
    const account = requireNonEmptyString(storageAccount, "storageAccount");
    azure =
      accountKey !== undefined
        ? { storage_account: account, account_key: accountKey }
        : {
            storage_account: account,
            sas_token: sasToken as SandboxProxySecret,
          };
  }
  const rule: SandboxAzureAuthRule = {
    name: requireNonEmptyString(name, "name"),
    type: "azure",
    enabled,
    azure,
  };
  if (envVars !== undefined) {
    rule.env_vars = requireEnvVars(envVars);
  }
  return rule;
}
