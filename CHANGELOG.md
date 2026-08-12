# Changelog

All notable changes to this project are documented in this file.

## [1.4] - 2026-08-12

### Changed

- Removed the `FLY_APPS` secret. The script now calls `GET /v1/apps?org_slug=...` on the Machines API to discover every app in `FLY_ORG_SLUG` at run time, so new apps appear in the next report automatically instead of requiring a manual secret update.

## [1.3] - 2026-08-11

### Changed

- Email body is now sent as HTML (`MIMEText(..., "html")`) instead of plain text, so section headers (`Fly.io Usage Estimate`, `Machines:`, `Network metrics`, `Excluded from this first estimate:`) render bold.
- `Estimated compute total` now appears above the per-machine breakdown instead of below it.
- The `Window:` line shows `mm/dd/yyyy` plus a 12-hour clock (e.g. `08/11/2026 9am`) instead of raw ISO timestamps, and is converted from UTC to a fixed GMT-6 offset for display. The underlying Prometheus query still uses the real UTC instant.

## [1.2] - 2026-08-11

### Fixed

- Machines API and Prometheus API requests now send the `FLY_TOKEN` value as-is instead of prefixing it with `Bearer `. Tokens from `fly tokens create` already include a `FlyV1 ` scheme prefix; the Machines API tolerated the doubled-up `Bearer FlyV1 ...` header, but the Prometheus API rejected it with a 401.

### Added

- `SMTP_HOST` and `SMTP_PORT` secrets. The script previously hardcoded `smtp.gmail.com:465`, so any non-Gmail `EMAIL_FROM` address failed SMTP login outright. The GitHub Actions workflow now passes both secrets through to the job.

## [1.1] - 2026-08-11

### Added

- `calculate_rates.py` — derives `CPU_RATE_PER_HOUR` and `MEMORY_RATE_PER_GB_HOUR` from two `RAM_MB:PRICE_PER_SECOND` pairs copied off Fly's pricing page for a single CPU tier, including a fit check that flags mismatched CPU tiers.

### Changed

- README's "Finding CPU_RATE_PER_HOUR and MEMORY_RATE_PER_GB_HOUR" section now walks through running the calculator instead of doing the per-second-to-per-hour math by hand.

## [1.0] - 2026-08-06

### Added

- Initial release: `fly_usage_report.py`, daily GitHub Actions workflow, README, MIT license.
