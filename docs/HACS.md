# HACS compliance and publication

This repository follows the [integration requirements](https://www.hacs.xyz/docs/publish/integration/) and [general requirements](https://www.hacs.xyz/docs/publish/start/).

| Requirement | Implementation |
| --- | --- |
| Public GitHub repository | `mbsintegrations/HomeAssistant-CalorGas` |
| One integration | Only `custom_components/calor_gas` |
| All runtime dependencies bundled appropriately | Python, JavaScript, English translations and brand PNGs are within that integration directory; no external runtime pip requirements |
| Required manifest fields | Domain, name, version, documentation, issue tracker and codeowners are present |
| Local branding | `brand/icon.png` plus high-resolution icon and light/dark wordmarks |
| Root HACS manifest | `hacs.json` declares name, Ireland and minimum HA version |
| Usage information | README covers requirements, setup, HACS/manual installation, card, updates, removal and limitations |
| Discoverability | GitHub description, topics and enabled issue tracker |
| Reproducible checks | HACS validator, Hassfest, Python/Node regression tests and synthetic Playwright UI checks |
| Release | Full normal GitHub release with a manual ZIP and SHA-256 checksum |

The bundled card is part of the integration. All its runtime files are inside the integration directory so HACS installs them together. It is not a separate HACS plugin repository.

## Custom repository versus default catalogue

Users may add this repository themselves as **Integration** in HACS. This does not imply inclusion in the default catalogue.

For default inclusion, follow [HACS's official submission process](https://www.hacs.xyz/docs/publish/include/):

1. Confirm a clean HA installation and update path work, including credential setup and bundled card loading.
2. Pass official HACS validation and Hassfest without errors or ignores.
3. Publish a full GitHub release after those checks pass.
4. As owner or major contributor, fork `hacs/default`, create a new branch from its `master`, and add `mbsintegrations/HomeAssistant-CalorGas` in sorted order to the `integration` file.
5. Complete the PR template truthfully, permit maintainer edits and wait for review. Review may take months.

Do not claim default catalogue acceptance until HACS maintainers have approved and merged the submission. Until catalogue acceptance, install version 1.1.0 as a custom repository.

## Before a release

- Test and review code, package contents, screenshots and documentation for private data.
- Keep version strings aligned and ensure all mandatory checks pass.
- Build `dist/calor_gas.zip` and `dist/SHA256SUMS` with `python scripts/build_release.py`.
- Publish a matching tag and release with those assets; use the normal release number without a beta suffix.
- Verify remote commit, release tag and downloaded asset checksums.
