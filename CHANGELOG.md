# Changes

## Unreleased

### Development

- Update the Playwright browser-test dependency from 1.62.1 to 1.64.1, including its upstream bug fixes.
- This maintenance change affects development and CI only. The Home Assistant integration, sensors, portal polling, saved readings and dashboard cards are unchanged.

## 1.1.0b1 — 2026-10-15

First public beta, packaged as a HACS custom integration under GNU GPL v3.0 only.

- Native email/password setup, reauthentication and credential reconfiguration.
- Six shared sensors and fixed six-hour polling.
- Persistent validated snapshots retained during portal outages and restarts.
- Capped forecasts such as `365+` preserve their lower-bound meaning.
- Two tank-card presets, with or without quick links, a visual editor, phone/compact layouts and automatic light/dark styling.
- Full-width standard cards, compact presets and readable status text in both themes.
- Automatic storage-managed module registration and documented YAML fallback.
- Original local logos, privacy-filtered diagnostics, regression tests and CI validation.
