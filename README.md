# Fly.io Usage Reporter

Fly Usage Reporter runs once a day. It reads Fly.io Machine configuration and Prometheus metrics for the previous 24 hours, then estimates infrastructure cost and emails the result. GitHub Actions supplies the scheduler and runtime, so the project needs no server of its own.

Companion post: [Fly.io Doesn't Have a Daily Billing Endpoint, So I Built One](http://dvoorhees.com/2026/08/06/fly-io-doesnt-have-a-daily-billing-endpoint-so-i-built-one/)

## What it does

- Lists Machines for each configured Fly app through the Machines API.
- Reads CPU count, memory allocation, and current Machine state.
- Queries Fly Prometheus for network activity during the reporting window.
- Estimates compute cost from CPU and memory rates you configure, not from anything hardcoded.
- Sends a plain-text report through SMTP.

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

Add the following values under **Settings → Secrets and variables → Actions**:

| Secret | Purpose |
|---|---|
| `FLY_TOKEN` | Read-only Fly API token. |
| `FLY_ORG_SLUG` | Organization slug used in the Prometheus URL. |
| `FLY_APPS` | Comma-separated Fly app names. |
| `CPU_RATE_PER_HOUR` | CPU rate used by the estimator. |
| `MEMORY_RATE_PER_GB_HOUR` | Memory rate used by the estimator. |
| `EMAIL_FROM` | SMTP sender address. |
| `EMAIL_TO` | Report recipient. |
| `EMAIL_PASSWORD` | SMTP app password. |

Update the CPU and memory rate secrets when Fly's pricing changes. Keeping the rates outside the script means a price change never touches the code.

The script sends mail through `smtp.gmail.com` specifically. If `EMAIL_FROM` is a Gmail address, enable 2-Step Verification on that account and generate an [App Password](https://myaccount.google.com/apppasswords) — `EMAIL_PASSWORD` must be the app password, not the account's login password. To use a different provider, edit the `smtplib.SMTP_SSL` host in `fly_usage_report.py`.

## Local execution

```bash
export FLY_TOKEN="..."
export FLY_ORG_SLUG="..."
export FLY_APPS="app-one,app-two"
export CPU_RATE_PER_HOUR="..."
export MEMORY_RATE_PER_GB_HOUR="..."
export EMAIL_FROM="..."
export EMAIL_TO="..."
export EMAIL_PASSWORD="..."

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

1. Push the repo and add all eight secrets (see Configuration).
2. In the GitHub Actions tab, select the workflow and click **Run workflow** to trigger `workflow_dispatch` manually rather than waiting for the schedule.
3. Confirm the email arrives and check the Action's run log for errors (auth failures, missing secrets, Prometheus query errors).
4. Compare the estimated compute total in the email against the actual numbers on your Fly.io billing dashboard for the same window.
5. If the estimate is off, adjust `CPU_RATE_PER_HOUR` and `MEMORY_RATE_PER_GB_HOUR` to match Fly's current pricing, or revisit the cost model below if the gap looks structural (e.g., Machines that start/stop during the day).

## Tests

The repository currently has no automated test suite. The first useful tests should mock the Machines API and Prometheus responses, then verify Machine parsing, 24-hour window handling, cost calculation, and report formatting without sending real email.

## Tradeoffs and limits

The project favors a transparent estimate over a hidden number. Every major input appears in the report or in the repository configuration, so you can compare the result against the Fly dashboard and adjust the model.

The estimate excludes exact Machine state history, Fly invoice adjustments, taxes, credits, volume billing, dedicated IPv4 charges, and final bandwidth charges. A future version could record hourly state snapshots and calculate active runtime per Machine.

## License

MIT — see [LICENSE](LICENSE).
