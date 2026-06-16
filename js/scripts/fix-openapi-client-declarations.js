import { readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

function abs(relativePath) {
  return resolve(dirname(fileURLToPath(import.meta.url)), relativePath);
}

async function patchFile(relativePath, replacements) {
  const filePath = abs(relativePath);
  let content = await readFile(filePath, "utf8");

  for (const [search, replacement] of replacements) {
    const nextContent = content.replace(search, replacement);
    if (nextContent === content) {
      throw new Error(`Expected declaration snippet not found in ${relativePath}`);
    }
    content = nextContent;
  }

  await writeFile(filePath, content, "utf8");
}

await patchFile("../dist/_openapi_client/internal/headers.d.ts", [
  [
    /^type HeaderValue = string \| undefined \| null;\n/,
    `type HeaderValue = string | undefined | null;
declare const brand_privateNullableHeaders: unique symbol;
/**
 * Users can pass explicit nulls to unset default headers. When we parse them
 * into a standard headers type we need to preserve that information.
 */
export type NullableHeaders = {
    /** Brand check, prevent users from creating a NullableHeaders. */
    [brand_privateNullableHeaders]: true;
    /** Parsed headers. */
    values: Headers;
    /** Set of lowercase header names explicitly set to null. */
    nulls: Set<string>;
};
`,
  ],
]);

await patchFile("../dist/_openapi_client/internal/types.d.ts", [
  [
    /\/\*\*\n \* These imports attempt[\s\S]*?\[1\]: https:\/\/www\.typescriptlang\.org\/tsconfig\/#typeAcquisition\n \*\/\n(?:\/\*\* @ts-ignore[\s\S]*?\n){5}/,
    "",
  ],
  [
    /type RequestInits = NotAny<UndiciTypesRequestInit> \| NotAny<UndiciRequestInit> \| NotAny<BunRequestInit> \| NotAny<NodeFetch2RequestInit> \| NotAny<NodeFetch3RequestInit> \| NotAny<RequestInit> \| NotAny<FetchRequestInit>;/,
    `type RequestInits = NotAny<RequestInit> | NotAny<FetchRequestInit>;`,
  ],
]);
