# Instructions for code modifications in the JS/TS SDK

This folder contains the JavaScript/TypeScript version of the LangSmith SDK.

When modifying code in this library, run the following from this directory before
submitting a pull request:

```
pnpm format
pnpm lint
pnpm test
```

To run a single test file, pass it to Jest, e.g.:

```bash
NODE_OPTIONS=--experimental-vm-modules npx jest src/tests/context.test.ts
```

## Conventions

### Constructing request URLs

Do not hardcode a leading `/v1` (or other `apiUrl`-dependent prefix) into request
paths. `LANGSMITH_ENDPOINT` may already include `/api/v1`, so a hardcoded `/v1/...`
produces a duplicated `/api/v1/v1/...` path and 404s.

For platform endpoints, build the path with the existing `_getPlatformEndpointPath`
helper, which only adds the `/v1` prefix when the configured `apiUrl` does not
already end in `/v1`:

```ts
`${this.apiUrl}${this._getPlatformEndpointPath(`hub/repos/${owner}/${name}/directories`)}`
```

When adding a new platform endpoint, follow the same pattern instead of inlining
`/v1/platform/...`.
