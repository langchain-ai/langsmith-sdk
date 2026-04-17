/**
 * Safe fetch wrapper that prevents credential leakage on cross-origin redirects.
 *
 * Browser/Node `fetch` with `redirect: "follow"` (the default) will replay the
 * original request — including headers like `X-Api-Key` and request bodies —
 * against the redirect target. If a LangSmith endpoint ever exposed an open
 * redirect, this could leak credentials to a third party. This helper
 * manually follows redirects and strips sensitive headers (and bodies on
 * 307/308) when the redirect target has a different origin.
 */

const SENSITIVE_HEADERS = [
  "authorization",
  "x-api-key",
  "x-tenant-id",
  "x-organization-id",
  "cookie",
];

const MAX_REDIRECTS = 20;

function sameOrigin(a: string, b: string): boolean {
  try {
    const ua = new URL(a);
    const ub = new URL(b);
    return ua.protocol === ub.protocol && ua.host === ub.host;
  } catch {
    return false;
  }
}

function stripSensitiveHeaders(headers: Headers): void {
  for (const name of SENSITIVE_HEADERS) {
    headers.delete(name);
  }
}

/**
 * Wrap a fetch implementation so that cross-origin redirects do not replay
 * credentials or sensitive request bodies.
 */
export function _wrapFetchWithSafeRedirects(
  fetchImpl: (...args: any[]) => any
): typeof fetch {
  const wrapped = async (
    input: RequestInfo | URL,
    init: RequestInit = {}
  ): Promise<Response> => {
    let currentUrl: string;
    if (typeof input === "string") {
      currentUrl = input;
    } else if (
      typeof (input as URL).toString === "function" &&
      "href" in (input as URL)
    ) {
      currentUrl = (input as URL).toString();
    } else {
      currentUrl = (input as Request).url;
    }
    let currentInit: RequestInit = { ...init, redirect: "manual" };

    for (let i = 0; i <= MAX_REDIRECTS; i++) {
      const response: Response = await fetchImpl(currentUrl, currentInit);
      const status = response.status;
      const isRedirect = status >= 300 && status < 400 && status !== 304;
      if (!isRedirect) {
        return response;
      }
      const location =
        typeof response.headers?.get === "function"
          ? response.headers.get("location")
          : null;
      if (!location) {
        return response;
      }
      const nextUrl = new URL(location, currentUrl).toString();
      const crossOrigin = !sameOrigin(currentUrl, nextUrl);

      const nextHeaders = new Headers(currentInit.headers);
      if (crossOrigin) {
        stripSensitiveHeaders(nextHeaders);
      }

      let nextMethod = currentInit.method ?? "GET";
      let nextBody = currentInit.body;
      if (status === 301 || status === 302 || status === 303) {
        if (nextMethod.toUpperCase() !== "HEAD") {
          nextMethod = "GET";
        }
        nextBody = undefined;
        nextHeaders.delete("content-type");
        nextHeaders.delete("content-length");
      } else if ((status === 307 || status === 308) && crossOrigin) {
        nextBody = undefined;
        nextHeaders.delete("content-type");
        nextHeaders.delete("content-length");
      }

      currentUrl = nextUrl;
      currentInit = {
        ...currentInit,
        method: nextMethod,
        body: nextBody,
        headers: nextHeaders,
        redirect: "manual",
      };
    }
    throw new Error(`Exceeded maximum redirects (${MAX_REDIRECTS})`);
  };
  return wrapped as typeof fetch;
}
