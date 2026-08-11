import os
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText

import requests


FLY_TOKEN = os.environ["FLY_TOKEN"]
FLY_ORG_SLUG = os.environ["FLY_ORG_SLUG"]
FLY_APPS = [
    app.strip()
    for app in os.environ["FLY_APPS"].split(",")
    if app.strip()
]

EMAIL_FROM = os.environ["EMAIL_FROM"]
EMAIL_TO = os.environ["EMAIL_TO"]
EMAIL_PASSWORD = os.environ["EMAIL_PASSWORD"]

FLY_API = "https://api.machines.dev/v1"
PROMETHEUS_API = f"https://api.fly.io/prometheus/{FLY_ORG_SLUG}/api/v1"

HEADERS = {
    # FLY_TOKEN from `fly tokens create` already includes the "FlyV1 " scheme
    # prefix, so it's used as-is here. Fly's Machines API tolerates a
    # "Bearer " prefix in front of that, but the Prometheus API rejects it.
    "Authorization": FLY_TOKEN,
}

# Set these from the current Fly pricing page.
CPU_RATE_PER_HOUR = float(os.environ["CPU_RATE_PER_HOUR"])
MEMORY_RATE_PER_GB_HOUR = float(os.environ["MEMORY_RATE_PER_GB_HOUR"])

REQUEST_TIMEOUT = 30


def get_machines(app_name):
    url = f"{FLY_API}/apps/{app_name}/machines"
    response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()


def query_prometheus_instant(query, at):
    """Run an instant query (a single point in time) against Fly's
    Prometheus endpoint. Used here for 24h increase() totals, where a
    single value at `at` is what we want rather than a range series.
    """
    params = {
        "query": query,
        "time": at.isoformat(),
    }

    response = requests.get(
        f"{PROMETHEUS_API}/query",
        headers=HEADERS,
        params=params,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def machine_estimate(machine):
    config = machine.get("config", {})
    guest = config.get("guest", {})
    state = machine.get("state", "")

    cpu_count = guest.get("cpus", 0)
    memory_mb = guest.get("memory_mb", 0)

    running_hours = 24 if state == "started" else 0
    memory_gb = memory_mb / 1024

    cpu_cost = cpu_count * CPU_RATE_PER_HOUR * running_hours
    memory_cost = memory_gb * MEMORY_RATE_PER_GB_HOUR * running_hours

    return {
        "id": machine.get("id", "unknown"),
        "state": state,
        "cpus": cpu_count,
        "memory_mb": memory_mb,
        "cpu_cost": cpu_cost,
        "memory_cost": memory_cost,
        "total": cpu_cost + memory_cost,
    }


def format_network_result(result):
    if result.get("status") != "success":
        return "Unavailable"

    series = result.get("data", {}).get("result", [])
    if not series:
        return "0"

    total = 0.0
    for item in series:
        value = item.get("value")
        if value and len(value) == 2:
            try:
                total += float(value[1])
            except ValueError:
                pass

    return f"{total:,.0f}"


def send_email(subject, body):
    message = MIMEText(body)
    message["From"] = EMAIL_FROM
    message["To"] = EMAIL_TO
    message["Subject"] = subject

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_FROM, EMAIL_PASSWORD)
        server.send_message(message)


def main():
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=24)

    machine_rows = []

    for app_name in FLY_APPS:
        machines = get_machines(app_name)
        for machine in machines:
            row = machine_estimate(machine)
            row["app"] = app_name
            machine_rows.append(row)

    sent_query = "sum by (app) (increase(fly_instance_net_sent_bytes[24h]))"
    received_query = "sum by (app) (increase(fly_instance_net_recv_bytes[24h]))"

    sent_result = query_prometheus_instant(sent_query, end)
    received_result = query_prometheus_instant(received_query, end)

    compute_total = sum(row["total"] for row in machine_rows)

    report_lines = [
        "Fly.io Usage Estimate",
        f"Window: {start.isoformat()} to {end.isoformat()}",
        "",
        "This report estimates compute cost from the current Machine "
        "configuration. It does not represent an official Fly invoice.",
        "",
        "Machines:",
    ]

    for row in machine_rows:
        report_lines.append(
            f"- {row['app']} / {row['id']}: "
            f"{row['state']}, "
            f"{row['cpus']} CPU, "
            f"{row['memory_mb']} MB, "
            f"${row['total']:.4f} estimated"
        )

    report_lines.extend(
        [
            "",
            f"Estimated compute total: ${compute_total:.4f}",
            "",
            "Network metrics (last 24h):",
            f"- Sent bytes: {format_network_result(sent_result)}",
            f"- Received bytes: {format_network_result(received_result)}",
            "",
            "Excluded from this first estimate:",
            "- Volumes",
            "- Exact Fly invoice adjustments",
            "- Region-specific bandwidth pricing",
            "- Machines started or stopped during the period",
        ]
    )

    body = "\n".join(report_lines)
    subject = f"Fly.io usage estimate - {end.date()}"

    send_email(subject, body)


if __name__ == "__main__":
    main()
