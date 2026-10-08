## External contributor PRs

Do not authorize GitHub Actions on external contributors' PRs. When asked to take over one, follow [Taking over an external contributor's PR](CONTRIBUTING.md#taking-over-an-external-contributors-pr): review the code before pushing, cherry-pick the reviewed commits onto an internal branch, preserve contributor attribution, and open a replacement PR.

<!-- OPENWIKI:START -->

## OpenWiki

This repository has a generated `openwiki/` evidence index. It is optional just-in-time context, not required startup reading.

- Treat source code and tests as authoritative. A brief's unknowns and review items are verification gaps, not automatic requirements.
- Prefer the narrowest quiet validation that proves the changed behavior. Preserve complete failure output.

The scheduled OpenWiki GitHub Actions workflow refreshes the repository wiki. Do not hand-edit generated OpenWiki pages unless explicitly asked; prefer updating source code/docs and letting OpenWiki regenerate.

<!-- OPENWIKI:END -->
