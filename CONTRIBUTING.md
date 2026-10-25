# Contributing

Open an issue describing the behaviour and versions before a large change. Small fixes and translations are welcome through pull requests.

Use synthetic portal fixtures and keep all runtime files under `custom_components/calor_gas`. Do not commit credentials, account numbers, raw authenticated pages, Home Assistant storage, private hostnames or real household screenshots. Keep the integration read-only and share one coordinator between all sensors.

Run the commands in the README. `npm run test:ui` needs a Playwright Chromium installation or a local Chrome executable and regenerates the committed PNG assets/screenshots. Python 3.12+ is sufficient for the adapter suite; actual runtime compatibility is determined by the declared Home Assistant minimum. Frontend development uses Node 24 or newer.

Playwright is a development dependency used by the browser checks. It is not included in `custom_components/calor_gas` or the manual-install ZIP. Test-tool dependency updates belong in the development changelog and do not require an integration version bump. Commit the matching `package.json` and `package-lock.json` changes together and pass all required CI checks before merging.

The Python test suite uses HA adapters; do not describe it as a full Home Assistant end-to-end test. Test fresh installation, reconfiguration, restart/cache recovery and card loading in a separate HA instance before promoting a stable release. Never use household actuators for testing.

All HACS and Hassfest checks must pass without ignores. Changes to the version require matching `manifest.json`, `const.py`, README resource URLs and changelog updates. Keep `strings.json` and `translations/en.json` in sync. The JavaScript package uses the same normal release version.

Contributions are distributed under the repository's GNU GPL v3.0-only license.

Preserve upstream copyright and licence notices when proposing any third-party code or assets; identify their origin and compatibility in the PR. Do not copy provider branding or imply Calor, Home Assistant or HACS endorsement. Keep GPL SPDX identifiers on project source files.
