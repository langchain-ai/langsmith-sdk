import { LangSmithValidationError } from "./errors.js";

/** How a delegation grant derives its permission set. */
export type AccessDelegationMode = "INHERIT" | "EXPLICIT";

/**
 * Grant letting code inside a sandbox call the LangSmith API as the creator.
 *
 * `INHERIT` tracks everything the creator can do; `EXPLICIT` is capped to
 * `permissions`. Permissions are a ceiling re-checked on every request rather
 * than a snapshot, so access the creator loses is lost here too.
 */
export interface AccessDelegation {
  mode: AccessDelegationMode;
  permissions?: string[];
}

/** Rejects grants the server would refuse, without the round trip. */
export function validateAccessDelegation(
  value: AccessDelegation,
): AccessDelegation {
  if (value.mode !== "INHERIT" && value.mode !== "EXPLICIT") {
    throw new LangSmithValidationError(
      'accessDelegation.mode must be "INHERIT" or "EXPLICIT"',
      "accessDelegation",
    );
  }

  const { permissions } = value;
  if (permissions !== undefined && !Array.isArray(permissions)) {
    throw new LangSmithValidationError(
      "accessDelegation.permissions must be an array of strings",
      "accessDelegation",
    );
  }

  if (value.mode === "INHERIT") {
    if (permissions !== undefined && permissions.length > 0) {
      throw new LangSmithValidationError(
        'accessDelegation.permissions is not allowed with mode "INHERIT"',
        "accessDelegation",
      );
    }
    return { mode: "INHERIT" };
  }

  if (permissions === undefined || permissions.length === 0) {
    throw new LangSmithValidationError(
      'accessDelegation.permissions is required with mode "EXPLICIT"',
      "accessDelegation",
    );
  }
  return { mode: "EXPLICIT", permissions: [...permissions] };
}
