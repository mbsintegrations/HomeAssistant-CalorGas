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

## Default catalogue status and installation

Calor Gas was accepted into the default HACS catalogue on **2 November 2026**. Maintainers approved and merged [submission #12620](https://github.com/hacs/default/pull/12620), and `mbsintegrations/HomeAssistant-CalorGas` is listed in the official [integration catalogue](https://github.com/hacs/default/blob/master/integration).

The recommended installation is now **HACS → search for Calor Gas → Download → restart Home Assistant**. Follow the [complete HACS instructions](../README.md#install-with-hacs), then connect the MyCalorGas account through Home Assistant's native integration dialog.

The README retains both the [custom-repository fallback](../README.md#custom-repository-fallback) for a catalogue entry that is not visible locally and the [full manual installation steps](../README.md#manual-installation), including the release ZIP, directory layout and checksum verification. Existing HACS installations do not need to be reinstalled because of catalogue acceptance.

This is an independently maintained custom integration distributed through HACS. Default catalogue inclusion does not turn it into a Home Assistant Core integration or imply endorsement by Calor.

## Maintaining the listing

Keep the repository metadata, `hacs.json`, integration manifest and documentation accurate. Continue running the official HACS validator and Hassfest without ignored checks, and publish matching normal releases for integration updates. The existing catalogue entry is already merged; a duplicate submission is unnecessary. Refer to the [official publishing documentation](https://www.hacs.xyz/docs/publish/start/) when maintaining the repository.

The current release remains **1.1.0**. Catalogue acceptance and these documentation updates do not change runtime code or require a new integration release.

## Legacy HACS icons

The integration bundles its own `brand/` assets, which Home Assistant uses after installation. Legacy **HACS 2.0.5** can display a placeholder in its repository list even when those installed assets are valid.

The earlier [HACS frontend PR #937](https://github.com/hacs/frontend/pull/937) was closed without merging. [HACS issue #5171](https://github.com/hacs/integration/issues/5171#issuecomment-6222990878) was closed after maintainers reported that icon handling is addressed in the announced Home Assistant Marketplace integration for Home Assistant 2026.11. See the [upstream transition announcement](https://github.com/hacs/integration/issues/5590). This is upstream status, not a Marketplace installation test of Calor Gas; the HACS and manual installation paths documented here remain available.

## Before a release

- Test and review code, package contents, screenshots and documentation for private data.
- Keep version strings aligned and ensure all mandatory checks pass.
- Build `dist/calor_gas.zip` and `dist/SHA256SUMS` with `python scripts/build_release.py`.
- Publish a matching tag and release with those assets; use the normal release number without a beta suffix.
- Verify remote commit, release tag and downloaded asset checksums.
