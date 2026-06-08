import type {
  SandboxAwsAuthRule,
  SandboxProxyConfig,
  SandboxProxySecret,
} from "./types.js";

function requireNonEmptyString(value: string, field: string): string {
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error(`${field} must be a non-empty string`);
  }
  return value.trim();
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

/** Build a sandbox proxy config that signs AWS HTTPS requests with SigV4. */
export function awsAuthProxyConfig({
  accessKeyId,
  secretAccessKey,
  name = "aws",
  enabled = true,
}: {
  accessKeyId: SandboxProxySecret;
  secretAccessKey: SandboxProxySecret;
  name?: string;
  enabled?: boolean;
}): SandboxProxyConfig {
  const rule: SandboxAwsAuthRule = {
    name: requireNonEmptyString(name, "name"),
    type: "aws",
    enabled,
    aws: {
      access_key_id: accessKeyId,
      secret_access_key: secretAccessKey,
    },
  };
  return { rules: [rule] };
}
