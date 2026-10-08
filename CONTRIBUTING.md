# Contributing to langsmith-sdk

This repo contains the Python and JS clients for the LangSmith platform.

See [`python/AGENTS.md`](python/AGENTS.md) for Python-specific lint/test instructions.

## Taking over an external contributor's PR

For security reasons, maintainers do **not** authorize GitHub Actions to run on external contributors' PRs. Instead, review the contribution, cherry-pick its commits onto a branch in `langchain-ai/langsmith-sdk`, and open a maintainer-owned PR so CI can run there.

1. Inspect the original PR's complete diff and commit list without approving its workflows. Review code, tests, dependency changes, and any scripts or workflow changes that CI would execute. Moving code to an internal branch does not make it safe; finish this review before pushing.
2. Start from the latest target branch in a clean checkout. Fetch the original PR's head and cherry-pick only the reviewed commits, oldest first:

   ```bash
   git fetch origin
   git switch -c external-pr-<number> origin/<target-branch>
   git fetch origin pull/<number>/head
   git cherry-pick -x <reviewed-commit-sha> [<next-reviewed-commit-sha> ...]
   ```

   Use explicit SHAs from the original PR, not a moving branch head. `-x` records the source commit, and cherry-picking preserves the contributor's authorship. If a cherry-pick conflicts, resolve and review the resulting diff before continuing, or abort with `git cherry-pick --abort`.
3. Check the final diff against the target branch, run the relevant local checks, then push the branch to `origin` (not the contributor's fork) and open a new PR against the original target branch. Link the original PR, credit the contributor, and describe any changes made during the takeover. Agents should use their PR-creation tool when available.
4. Run CI and obtain the usual review on the replacement PR. Do not approve workflows on the original PR or weaken CI security settings. Link the replacement from the original PR; close the original as superseded once the replacement is merged.

If the contributor adds commits later, review and cherry-pick those explicitly as well; do not automatically sync unreviewed updates.

## Auto-generated OpenAPI client

The directories `python/langsmith/_openapi_client/` and `js/src/_openapi_client/` are **auto-generated** from the LangSmith OpenAPI spec via [Stainless](https://www.stainlessapi.com/). Do not edit files in these directories manually — your changes will be overwritten on the next sync.

Updates are applied automatically by the [`stlc_sync_python_and_js_sdks`](https://github.com/langchain-ai/langchainplus/actions/workflows/stlc_sync_python_and_js_sdks.yml) workflow in `langchain-ai/langchainplus`, which opens PRs from the `sync/langsmith-api` branch. A CI check ([`protect-openapi-client.yml`](.github/workflows/protect-openapi-client.yml)) blocks any PR that touches these directories from a source other than that workflow.

For the full end-to-end process — how the spec is generated, how the sync PRs are produced, and how to review and land them — see [Releasing the SDKs](https://github.com/langchain-ai/langchainplus/tree/main/smith-sdks#releasing-the-sdks) in `langchain-ai/langchainplus` (internal).

## Merges are mirrored to the staging repos

Every merge to `main` touching `python/` or `js/` is mirrored hourly, one PR at a time, by a cron workflow in [langsmith-python-staging](https://github.com/langchain-ai/langsmith-python-staging) or [langsmith-javascript-staging](https://github.com/langchain-ai/langsmith-javascript-staging), with paths rewritten. Those repos are the future home of the SDKs: open new work there when you can. `pyproject.toml`, `package.json` and lockfile changes are not mirrored and need a manual port.

## Cutting a release

Releases are published by GitHub Actions workflows that fire on `main` when specific files change:

- **Python** (`.github/workflows/release.yml`) — fires on changes to `python/langsmith/__init__.py`. Builds, tags `vX.Y.Z`, and publishes to PyPI.
- **JS** (`.github/workflows/release_js.yml`) — fires on changes to `js/package.json`. Builds and publishes to npm.

To cut a release, open a version-bump PR against `main`. Each workflow runs independently, so Python and JS releases go in **separate PRs**.

### Python

```bash
git checkout main && git pull
git checkout -b release-py-X.Y.Z
cd python
uv run bump2version patch   # or minor/major
```

`bump2version` edits `python/.bumpversion.cfg` and `python/langsmith/__init__.py`, auto-commits, and creates a **local** tag. Do **not** push the tag — the release workflow creates the authoritative tag on `main` after merge.

```bash
git push origin release-py-X.Y.Z   # no --tags / --follow-tags
gh pr create --title "release(py): X.Y.Z"
```

On merge, the workflow checks `python/langsmith/__init__.py`, verifies `vX.Y.Z` doesn't already exist as a tag, builds, tags, and publishes.

### JS

```bash
git checkout main && git pull
git checkout -b release-js-X.Y.Z
cd js
pnpm run bump-version   # or: pnpm run bump-version X.Y.Z
```

`bump-version` edits `js/package.json` and `js/src/index.ts` but does **not** commit. Commit manually:

```bash
git add js/package.json js/src/index.ts
git commit -m "release(js): X.Y.Z"
git push origin release-js-X.Y.Z
gh pr create --title "release(js): X.Y.Z"
```

On merge, the workflow runs `check-version` / `check-npm-version` and calls `npm publish` if the version is new.

### Notes

- Keep release PRs to the two version files only. Example prior PRs: #2778 (Python), #2774 (JS).
- Both workflows support `workflow_dispatch` with `dangerous-non-main-release=true` for manual/non-main releases (use with care).
