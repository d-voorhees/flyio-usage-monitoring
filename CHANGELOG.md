# Changelog

All notable changes to this project are documented in this file.

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
