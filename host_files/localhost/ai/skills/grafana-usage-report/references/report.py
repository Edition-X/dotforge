#!/usr/bin/env python3
"""Grafana Cloud usage & estimated monthly-cost report.

Reads a Grafana Cloud *Access Policy* token from the GRAFANA_TOKEN environment
variable, queries the built-in `grafanacloud-usage` billing datasource
(https://billing.grafana.net), and prints current-month usage together with an
estimated monthly bill.

No personal API key required: it uses the shared service-account token in
GRAFANA_TOKEN. The org ID used as the basic-auth username is derived from the
token payload, so nothing org-specific is hard-coded in this file.

Environment:
  GRAFANA_TOKEN     (required)  Grafana Cloud access-policy token, e.g. "glc_..."
  GRAFANA_ORG_SLUG  (optional)  Org slug, used only for the report header.
  GRAFANA_ORG_ID    (optional)  Override the basic-auth username (defaults to the
                                org ID decoded from the token).

Pricing below reflects the Grafana Cloud Pro / usage-based plan (USD), as of
2026-05. Adjust the PRICING / FREE-ALLOTMENT constants if your plan differs.
"""

import base64
import calendar
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import UTC, datetime

BILLING_QUERY_URL = "https://billing.grafana.net/api/prom/api/v1/query"
GB = 1_000_000_000  # decimal GB, as used for Grafana Cloud billing

# --- Pricing: Grafana Cloud Pro / usage-based, USD, as of 2026-05 -----------
PLATFORM_FEE = 19.00            # flat platform fee per month
PRICE_METRICS_PER_1K = 6.50    # per 1,000 active series / month
PRICE_LOGS_PER_GB = 0.50       # per GB ingested (0.40 write + 0.10 retain)
PRICE_TRACES_PER_GB = 0.50     # per GB ingested
PRICE_PROFILES_PER_GB = 0.50   # per GB ingested
PRICE_K6_PER_VUH = 0.15        # per virtual-user-hour
PRICE_USER = 8.00              # per active Grafana user / month

# Free allotments included in the Pro plan
FREE_METRICS_SERIES = 10_000
FREE_LOGS_GB = 50
FREE_TRACES_GB = 50
FREE_PROFILES_GB = 50
FREE_K6_VUH = 500
FREE_USERS = 3


def die(msg):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def org_id_from_token(token):
    """Grafana Cloud `glc_` tokens carry a base64 payload whose `o` field is the
    org ID. That ID is the basic-auth username for the usage datasource."""
    try:
        payload = token.split("_", 1)[1]
        payload += "=" * (-len(payload) % 4)  # pad base64
        return str(json.loads(base64.b64decode(payload))["o"])
    except Exception:
        return None


def make_querier(token, username):
    auth = base64.b64encode(f"{username}:{token}".encode()).decode()

    def query(promql):
        """Run an instant PromQL query. Returns the summed scalar value across all
        series (0.0 if the metric exists but has no series), or None on failure."""
        url = BILLING_QUERY_URL + "?" + urllib.parse.urlencode({"query": promql})
        req = urllib.request.Request(url, headers={"Authorization": f"Basic {auth}"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                die("token rejected by billing datasource (check GRAFANA_TOKEN "
                    "and that its access policy has `metrics:read` scope)")
            return None
        except Exception:
            return None
        if data.get("status") != "success":
            return None
        results = data.get("data", {}).get("result", [])
        return sum(float(s["value"][1]) for s in results)

    return query


def fmt_usd(x):
    return f"${x:,.2f}"


def main():
    token = os.environ.get("GRAFANA_TOKEN")
    if not token:
        die("GRAFANA_TOKEN is not set")

    org_slug = os.environ.get("GRAFANA_ORG_SLUG", "")
    username = os.environ.get("GRAFANA_ORG_ID") or org_id_from_token(token)
    if not username:
        die("could not determine org ID; set GRAFANA_ORG_ID")

    query = make_querier(token, username)

    # Billing period: the current calendar month, to date.
    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elapsed_s = max(int((now - month_start).total_seconds()), 1)
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    full_month_s = days_in_month * 86_400
    window = f"{elapsed_s}s"  # PromQL range matching month-to-date

    # --- Usage queries ------------------------------------------------------
    # Metrics & users are levels -> the month-to-date value is the bill basis.
    # Bytes-rate & k6 counter are accumulations -> project to a full month.
    series_p95 = query(
        f"sum(quantile_over_time(0.95, grafanacloud_instance_billable_usage[{window}]))")
    users = query("sum(grafanacloud_grafana_instance_billable_users)")
    logs_bps = query(
        f"avg_over_time(grafanacloud_logs_instance_billable_bytes_received_per_second[{window}])")
    traces_bps = query(
        f"avg_over_time(grafanacloud_traces_instance_billable_bytes_received_per_second[{window}])")
    profiles_bps = query(
        f"avg_over_time(grafanacloud_profiles_instance_billable_bytes_received_per_second[{window}])")
    k6_vuh_mtd = query(
        f"sum(increase(grafanacloud_org_k6_usage_virtual_user_hours_total[{window}]))")

    if series_p95 is None and users is None and logs_bps is None:
        die("no usage data returned (token may lack scope, or the org has no usage)")

    # --- Convert to billable quantities ------------------------------------
    series_p95 = series_p95 or 0.0
    users = int(round(users or 0.0))

    def project_gb(bps):
        if bps is None:
            return None
        return bps * full_month_s / GB

    logs_gb = project_gb(logs_bps)
    traces_gb = project_gb(traces_bps)
    profiles_gb = project_gb(profiles_bps)
    k6_vuh = ((k6_vuh_mtd or 0.0) / elapsed_s) * full_month_s

    # --- Cost (projected full month) ---------------------------------------
    def over(amount, free):
        return max(0.0, amount - free)

    c_platform = PLATFORM_FEE
    c_metrics = over(series_p95, FREE_METRICS_SERIES) / 1000 * PRICE_METRICS_PER_1K
    c_users = over(users, FREE_USERS) * PRICE_USER
    c_logs = over(logs_gb or 0.0, FREE_LOGS_GB) * PRICE_LOGS_PER_GB
    c_traces = over(traces_gb or 0.0, FREE_TRACES_GB) * PRICE_TRACES_PER_GB
    c_profiles = over(profiles_gb or 0.0, FREE_PROFILES_GB) * PRICE_PROFILES_PER_GB
    c_k6 = over(k6_vuh, FREE_K6_VUH) * PRICE_K6_PER_VUH
    total = c_platform + c_metrics + c_users + c_logs + c_traces + c_profiles + c_k6

    # --- Render -------------------------------------------------------------
    org_label = org_slug or f"org {username}"
    pct = elapsed_s / full_month_s * 100
    days_elapsed = elapsed_s / 86_400

    def gb_str(v):
        return f"{v:,.1f} GB" if v is not None else "n/a"

    print()
    print("=" * 60)
    print(f"  Grafana Cloud usage & cost  ·  {org_label}")
    print(f"  {now:%B %Y}  (month-to-date: {days_elapsed:.1f}/{days_in_month} "
          f"days, {pct:.0f}%)")
    print(f"  as of {now:%Y-%m-%d %H:%M UTC}")
    print("=" * 60)
    print()
    print("  Usage")
    print("  -----")
    print(f"  Metrics (P95 billable series)   {series_p95:>14,.0f}")
    print(f"  Logs ingested (proj. month)     {gb_str(logs_gb):>14}")
    print(f"  Traces ingested (proj. month)   {gb_str(traces_gb):>14}")
    print(f"  Profiles ingested (proj. month) {gb_str(profiles_gb):>14}")
    print(f"  k6 virtual-user-hours (proj.)   {k6_vuh:>14,.1f}")
    print(f"  Active Grafana users            {users:>14,d}")
    print()
    print("  Estimated cost (projected full month)")
    print("  -------------------------------------")
    rows = [
        ("Platform fee", c_platform),
        (f"Metrics  ({max(0.0, series_p95 - FREE_METRICS_SERIES):,.0f} billable series)", c_metrics),
        (f"Users    ({max(0, users - FREE_USERS)} billable)", c_users),
        ("Logs", c_logs),
        ("Traces", c_traces),
        ("Profiles", c_profiles),
        ("k6", c_k6),
    ]
    for label, cost in rows:
        print(f"  {label:<42}{fmt_usd(cost):>13}")
    print("  " + "-" * 53)
    print(f"  {'TOTAL estimated monthly cost':<42}{fmt_usd(total):>13}")
    print()
    print("  Note: estimate only. Pro-plan list prices (USD, 2026-05);")
    print("  metrics billed on P95 active series, ingestion projected to a")
    print("  full month. Actual invoices may differ (commitments, discounts,")
    print("  query/retention components). Tune constants in this file to fit.")
    print()


if __name__ == "__main__":
    main()
