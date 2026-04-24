import { getInvalidPromptIdentifierMsg } from "./error.js";

/**
 * Parse a hub repo identifier (owner/name:hash, name, etc.).
 *
 * Prompts, agents, and skills share the same identifier grammar on Hub.
 */
export function parseHubIdentifier(
  identifier: string
): [string, string, string] {
  if (
    !identifier ||
    identifier.split("/").length > 2 ||
    identifier.startsWith("/") ||
    identifier.endsWith("/") ||
    identifier.split(":").length > 2
  ) {
    throw new Error(getInvalidPromptIdentifierMsg(identifier));
  }

  const [ownerNamePart, commitPart] = identifier.split(":");
  const commit = commitPart || "latest";

  if (ownerNamePart.includes("/")) {
    const [owner, name] = ownerNamePart.split("/", 2);
    if (!owner || !name) {
      throw new Error(getInvalidPromptIdentifierMsg(identifier));
    }
    return [owner, name, commit];
  } else {
    if (!ownerNamePart) {
      throw new Error(getInvalidPromptIdentifierMsg(identifier));
    }
    return ["-", ownerNamePart, commit];
  }
}
