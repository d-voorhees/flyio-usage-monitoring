# Fly.io Usage Reporter

**Version:** 1.4 — see [CHANGELOG.md](CHANGELOG.md) for history.

Fly Usage Reporter runs once a day. It reads Fly.io Machine configuration and Prometheus metrics for the previous 24 hours, then estimates infrastructure cost and emails the result. GitHub Actions supplies the scheduler and runtime, so the project needs no server of its own.

Companion post: [Fly.io Doesn't Have a Daily Billing Endpoint, So I Built One](http://dvoorhees.com/2026/08/06/fly-io-doesnt-have-a-daily-billing-endpoint-so-i-built-one/)

## What it does

- Discovers every app in your Fly org through the Machines API, then lists Machines for each one.
- Reads CPU count, memory allocation, and current Machine state.
- Queries Fly Prometheus for network activity during the reporting window.
- Estimates compute cost from CPU and memory rates you configure, not from anything hardcoded.
- Sends an HTML report through SMTP.

The report is an operational estimate. Fly's organization billing records remain the source for official charges.

## Architecture

```text
GitHub Actions
      |
      v
fly_usage_report.py
   |          |          |
   v          v          v
Machines   Prometheus   SMTP
API        API          server
```

The Python script owns the data flow. It calls the Machines API and queries Prometheus, then applies the cost model. From there it formats the report and sends the email. The workflow supplies secrets and starts the script once per day.

## Cost model

```text
estimated_compute_cost =
    active_hours × cpu_count × cpu_rate_per_hour
  + active_hours × memory_gb × memory_rate_per_gb_hour
```

The current version assumes that a Machine observed as `started` ran for the full reporting window. That assumption works best for continuously running services. It overstates cost when a Machine starts, stops, or changes size during the window.

Network counters appear in the report as usage data. The current version does not convert network bytes into a final bandwidth charge, because regional pricing and invoice rules require inputs the script doesn't have yet.

## Repository structure

```text
.
├── fly_usage_report.py
├── calculate_rates.py
├── requirements.txt
└── .github/workflows/daily-report.yml
```

## Setup

### 1. Push the repo to your own GitHub account

```bash
git init
git add fly_usage_report.py requirements.txt .gitignore .github README.md
git commit -m "Add Fly.io usage reporter"
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

The GitHub Actions workflow only runs once the repository lives on GitHub — a local clone alone will not trigger the schedule.

### 2. Set up locally for testing

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a read-only Fly token with `fly tokens create readonly`. Store the token in GitHub (see Configuration below). Do not commit it to the repository.

## Configuration

Every app that exists in `FLY_ORG_SLUG` at run time is included automatically — there's no separate app allowlist to maintain. Create a new Fly app and it shows up in the next report with no config change.

Add the following values under **Settings → Secrets and variables → Actions**:

| Secret | Purpose |
|---|---|
| `FLY_TOKEN` | Read-only Fly API token. |
| `FLY_ORG_SLUG` | Organization slug used to discover apps and query Prometheus. |
| `CPU_RATE_PER_HOUR` | CPU rate used by the estimator. |
| `MEMORY_RATE_PER_GB_HOUR` | Memory rate used by the estimator. |
| `EMAIL_FROM` | SMTP sender address. |
| `EMAIL_TO` | Report recipient. |
| `EMAIL_PASSWORD` | SMTP account/app password. |
| `SMTP_HOST` | SMTP server hostname (e.g. `smtp.gmail.com`, `smtp.office365.com`, your provider's mail server). |
| `SMTP_PORT` | SMTP server port for SSL (typically `465`). |

### Finding CPU_RATE_PER_HOUR and MEMORY_RATE_PER_GB_HOUR

Fly doesn't publish these two numbers directly — it publishes one bundled price per (CPU tier, RAM size), like "shared-cpu-1x @ 256MB = $0.00000075/s." `calculate_rates.py` backs out the per-vCPU and per-GB-RAM components for you:

1. Open [fly.io/docs/about/pricing](https://fly.io/docs/about/pricing/) and find your CPU tier — almost certainly `shared-cpu-1x` unless you know otherwise.
2. Copy the per-second price for **two different RAM sizes** on that same tier's row(s).
3. Run:

   ```bash
   python calculate_rates.py 256:0.00000075 512:0.00000123
   ```

   (using your own RAM_MB:PRICE_PER_SECOND pairs). It prints the exact `CPU_RATE_PER_HOUR` and `MEMORY_RATE_PER_GB_HOUR` values to paste into GitHub secrets, plus a fit check — if the "predicted" price doesn't match what you gave it, you likely mixed CPU tiers by accident.
4. To sanity-check the result: after the first live run (see "First run and verification" below), compare the emailed estimate to a real invoice on your Fly org's **Billing** page and re-run the calculator with adjusted inputs if needed.

This only works within one CPU tier — if you later run a mix of `shared-cpu-*` and `performance-*` machines, note the reporting script applies one flat rate to all of them, so pick the tier that matches most of your machines.

Update the CPU and memory rate secrets when Fly's pricing changes. Keeping the rates outside the script means a price change never touches the code.

The script connects over SSL to whatever `SMTP_HOST`/`SMTP_PORT` you configure, so any provider works without touching the code.

**Using Gmail:**

1. Enable 2-Step Verification on the `EMAIL_FROM` Google account.
2. Generate an [App Password](https://myaccount.google.com/apppasswords) — `EMAIL_PASSWORD` must be this app password, not the account's login password.
3. Set `SMTP_HOST` to `smtp.gmail.com` and `SMTP_PORT` to `465`.

**Using another provider:** set `SMTP_HOST`/`SMTP_PORT` to that provider's SSL SMTP endpoint (check their docs — a common alternate port is `587`, but that's usually STARTTLS, not the implicit SSL this script uses, so confirm SSL support on `465` or whichever port you pick). `EMAIL_PASSWORD` is whatever that provider considers its SMTP/app password — often not the same as the account's normal login password.

## Local execution

```bash
export FLY_TOKEN="..."
export FLY_ORG_SLUG="..."
export CPU_RATE_PER_HOUR="..."
export MEMORY_RATE_PER_GB_HOUR="..."
export EMAIL_FROM="..."
export EMAIL_TO="..."
export EMAIL_PASSWORD="..."
export SMTP_HOST="..."
export SMTP_PORT="..."

python fly_usage_report.py
```

The script uses the current time as the end of the reporting window and looks back 24 hours.

## GitHub Actions

The workflow runs once per day and can also be started manually from the Actions tab.

```yaml
on:
  schedule:
    - cron: "0 4 * * *"
  workflow_dispatch:
```

GitHub Actions cron always runs in **UTC**, not local time. `0 4 * * *` is 4:00 AM UTC, which is 10:00 PM Eastern during Daylight Time (UTC-4) or 11:00 PM Eastern during Standard Time (UTC-5). Adjust the hour to match your own timezone and account for daylight saving if it applies.

The scheduled job installs the pinned Python dependency and injects repository secrets. Then it runs `fly_usage_report.py`.

## First run and verification

1. Push the repo and add all nine secrets (see Configuration).
2. In the GitHub Actions tab, select the workflow and click **Run workflow** to trigger `workflow_dispatch` manually rather than waiting for the schedule.
3. Confirm the email arrives and check the Action's run log for errors (auth failures, missing secrets, Prometheus query errors).
4. Compare the estimated compute total in the email against the actual numbers on your Fly.io billing dashboard for the same window.
5. If the estimate is off, adjust `CPU_RATE_PER_HOUR` and `MEMORY_RATE_PER_GB_HOUR` to match Fly's current pricing, or revisit the cost model below if the gap looks structural (e.g., Machines that start/stop during the day).

## Tests

The repository currently has no automated test suite. The first useful tests should mock the Machines API and Prometheus responses, then verify Machine parsing, 24-hour window handling, cost calculation, and report formatting without sending real email.

## Tradeoffs and limits

The project favors a transparent estimate over a hidden number. Every major input appears in the report or in the repository configuration, so you can compare the result against the Fly dashboard and adjust the model.

The estimate excludes exact Machine state history, Fly invoice adjustments, taxes, credits, volume billing, dedicated IPv4 charges, and final bandwidth charges. A future version could record hourly state snapshots and calculate active runtime per Machine.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

## License

MIT — see [LICENSE](LICENSE).
