# Releasing LangSmith SDKs

This is the contributor release process for Python and JavaScript.

## Python Release

1. From `python/`, prepare the release PR by running:
    ```bash
    uv run bump2version patch # or minor|major
    ```
1. Open PR with title `release(py): <version>` and merge to `main`.
1. Confirm the `Release` GitHub Action succeeds.

## JavaScript Release

1. From `js/`, prepare the release PR by running:
    ```bash
    yarn run bump-version
    # or: yarn run bump-version <version>
    ```
1. Open PR with title `release(js): <version>` and merge to `main`.
1. Confirm the `JS Release` GitHub Action succeeds.

## Internal Pointers

- Python workflow: `.github/workflows/release.yml`
- JS workflow: `.github/workflows/release_js.yml`
- Python version files: `python/langsmith/__init__.py`, `python/.bumpversion.cfg`
- JS version files/scripts: `js/package.json`, `js/src/index.ts`, `js/scripts/bump-version.js`
