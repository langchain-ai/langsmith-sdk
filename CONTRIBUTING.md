# Contributing to langsmith-sdk

This repo contains the Python and JS clients for the LangSmith platform.

See [`python/AGENTS.md`](python/AGENTS.md) for Python-specific lint/test instructions.

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
