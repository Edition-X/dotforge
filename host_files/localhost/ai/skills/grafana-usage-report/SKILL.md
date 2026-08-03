---
name: grafana-usage-report
description: Run a report of Grafana Cloud usage and estimated monthly cost. Use whenever someone asks to check Grafana Cloud usage, view billing, generate a cost report, or run a Grafana spending summary. Also triggers on "Grafana daily report", "how much are we spending on Grafana", or "Grafana usage this month". Prints a concise cost summary to the terminal — no personal API key required, uses a shared service-account token from the GRAFANA_TOKEN env variable.
---

# Grafana Cloud Usage Report

Reports current-month Grafana Cloud usage and an estimated monthly bill for the
org. Built for scheduled (e.g. daily) runs as well as ad-hoc checks.

## How to run

Set the shared service-account token and run the script:

```bash
export GRAFANA_TOKEN="glc_..."          # Grafana Cloud access-policy token
export GRAFANA_ORG_SLUG="your-org-slug" # optional, header label only

# Locate the bundled script regardless of cwd or install type (plugin or user skill)
report=$(find "${CLAUDE_PLUGIN_ROOT:-$HOME/.claude}" -path '*/grafana-usage-report/references/report.py' 2>/dev/null | head -1)
python3 "$report"
```

`GRAFANA_TOKEN` is the only required variable. The org ID (used as the
basic-auth username for the usage datasource) is decoded from the token itself,
so nothing org-specific is hard-coded.

## What it does

1. Queries the built-in `grafanacloud-usage` billing datasource at
   `https://billing.grafana.net/api/prom` (Prometheus HTTP API, basic auth:
   `org_id : token`).
2. Pulls month-to-date usage: metrics P95 billable active series, logs/traces/
   profiles ingestion rate, k6 virtual-user-hours, and active Grafana users.
3. Projects accumulating dimensions (ingestion, k6) to a full month, subtracts
   the Pro-plan free allotments, applies list prices, and prints a per-product
   cost breakdown plus a total estimated monthly cost.

## Requirements

- **Token**: a Grafana Cloud *access-policy* token (`glc_...`) whose policy has
  the `metrics:read` scope on the org realm. Create it in the Cloud portal under
  **Access Policies**; this is a service-account credential, not a personal key.
- **Python 3** with the standard library only — no pip installs.

## Accuracy notes

- Prices are **Grafana Cloud Pro / usage-based list prices (USD, as of 2026-05)**
  defined as constants at the top of `references/report.py`. Edit them if your
  org is on a different plan, has a committed-use discount, or prices change.
- Metrics are billed on the 95th-percentile active series over the billing
  period; logs/traces/profiles are billed per GB ingested and are projected
  from the month-to-date average rate. The output is an **estimate** — query and
  retention components and contract discounts can move the real invoice.

## Scheduling

To run it daily, wire the two `export`s plus the `python3` invocation into a
cron job, a CI schedule, or a Claude Code scheduled task. Keep the token in the
scheduler's secret store — never commit it.
