# Contributing to langsmith-sdk

This repo contains the Python and JS clients for the LangSmith platform.

> **This repository is archived.**
> The Python and JavaScript SDKs now live in [langsmith-python](https://github.com/langchain-ai/langsmith-python)
> and [langsmith-javascript](https://github.com/langchain-ai/langsmith-javascript).
> Open new issues and pull requests in the corresponding repository.

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
