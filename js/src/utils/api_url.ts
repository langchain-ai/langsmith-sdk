export function getOpenAPIBaseUrl(apiUrl: string): string {
  const url = apiUrl.replace(/\/$/, "");
  for (const suffix of ["/api/v1", "/api"]) {
    if (url.endsWith(suffix)) return url.slice(0, -suffix.length);
  }
  return url;
}
