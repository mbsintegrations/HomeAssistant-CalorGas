# Changes

## Unreleased

### Documentation

- Record acceptance into the default HACS catalogue on 2 November 2026 and make HACS search the primary installation method.
- Keep the custom-repository fallback and full manual installation instructions, and update the HACS badge, listing guidance and legacy icon status.

### Development

- Update the GitHub Python setup action to 7.1.0 and refresh the Hassfest action pin. These CI-only changes do not alter the installed integration or dashboard cards.

## 1.1.0 — 2026-10-25

Normal public release, packaged as a HACS custom integration under GNU GPL v3.0 only.

- Native email/password setup, reauthentication and credential reconfiguration.
- Six shared sensors and fixed six-hour polling.
- Persistent validated snapshots retained during portal outages and restarts.
- Capped forecasts such as `365+` preserve their lower-bound meaning.
- Two tank-card presets, with or without quick links, a visual editor, phone/compact layouts and automatic light/dark styling.
- Full-width standard cards, compact presets and readable status text in both themes.
- Automatic storage-managed module registration and documented YAML fallback.
- Original local logos, privacy-filtered diagnostics, regression tests and CI validation.

### Development

- Update Playwright from 1.62.1 to 1.64.1. This dependency is used for tests only and is not included in the integration.
