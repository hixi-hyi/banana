#!/usr/bin/env python3
"""
Railway Cost Reporter
- Fetches actual usage/estimated data from Railway GraphQL API
- Calculates costs by project
- Sends formatted report to Slack
"""

import json
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Any
import subprocess
import urllib.request
import urllib.error

# Configuration
RAILWAY_API_URL = "https://backboard.railway.com/graphql/internal"
WORKSPACE_ID = "d327b30e-dbc7-489d-a9be-9b0291afedb8"
SLACK_CHANNEL = "C0AHUGG1C82"

# Railway pricing (per unit)
# Source: https://docs.railway.app/reference/pricing/plans
# CPU_USAGE and MEMORY_USAGE_GB API values are in per-MINUTE units.
# DISK / BACKUP are within the Hobby plan's included 100 GB → $0.
PRICING = {
    "cpu_per_vcpu_minute": 20.0 / 43200,   # $20/vCPU/month ÷ 43200 min
    "memory_per_gb_minute": 10.0 / 43200,  # $10/GB/month  ÷ 43200 min
    "network_per_gb": 0.05,                 # $0.05/GB egress
}

# Day of month the billing cycle starts (check Railway dashboard > Usage)
BILLING_CYCLE_DAY = 3

MEASUREMENTS = ["MEMORY_USAGE_GB", "CPU_USAGE", "NETWORK_TX_GB", "DISK_USAGE_GB", "BACKUP_USAGE_GB"]

JPY_RATE = 155.0


def get_secret(secret_path: str) -> str:
    """Get secret from 1Password using op CLI"""
    try:
        result = subprocess.run(
            ["op", "read", secret_path],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Failed to read secret {secret_path}: {e}", file=sys.stderr)
        sys.exit(1)


def query_railway_api(query: str, variables: Dict = None) -> Dict[str, Any]:
    """Execute GraphQL query against Railway API"""
    railway_token = get_secret("op://banana/railway/password")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {railway_token}",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
        "Origin": "https://railway.com",
        "Referer": "https://railway.com/",
    }

    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    request_body = json.dumps(payload).encode("utf-8")

    try:
        req = urllib.request.Request(
            RAILWAY_API_URL,
            data=request_body,
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))

        if "errors" in data:
            print(f"GraphQL errors: {data['errors']}", file=sys.stderr)
            return {}

        return data.get("data", {})
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.reason}", file=sys.stderr)
        try:
            print(f"Response: {e.read().decode('utf-8', errors='ignore')[:300]}", file=sys.stderr)
        except Exception:
            pass
        return {}
    except urllib.error.URLError as e:
        print(f"URL Error: {e.reason}", file=sys.stderr)
        return {}
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}", file=sys.stderr)
        return {}


def get_billing_period_start() -> datetime:
    """Return the start of the current billing period based on BILLING_CYCLE_DAY"""
    now = datetime.now(timezone.utc)
    if now.day >= BILLING_CYCLE_DAY:
        start = datetime(now.year, now.month, BILLING_CYCLE_DAY, tzinfo=timezone.utc)
    else:
        # Previous month
        if now.month == 1:
            start = datetime(now.year - 1, 12, BILLING_CYCLE_DAY, tzinfo=timezone.utc)
        else:
            start = datetime(now.year, now.month - 1, BILLING_CYCLE_DAY, tzinfo=timezone.utc)
    return start


def fetch_current_usage(start_date: datetime, end_date: datetime) -> tuple[Dict[str, Dict[str, float]], Dict[str, str]]:
    """
    Fetch current month-to-date usage per project.
    Returns (usage_by_project_id, project_names).

    API units:
      CPU_USAGE      → vCPU-hours
      MEMORY_USAGE_GB → GB-minutes
      NETWORK_TX_GB  → GB
      DISK_USAGE_GB  → GB-hours
      BACKUP_USAGE_GB → GB-hours
    """
    query = """
    query allProjectCurrentUsage(
      $workspaceId: String
      $usageMeasurements: [MetricMeasurement!]!
      $startDate: DateTime!
      $endDate: DateTime!
      $includeDeleted: Boolean
      $useSmallDateChunks: Boolean
    ) {
      usage(
        workspaceId: $workspaceId
        measurements: $usageMeasurements
        groupBy: [PROJECT_ID]
        startDate: $startDate
        endDate: $endDate
        includeDeleted: $includeDeleted
        useSmallDateChunks: $useSmallDateChunks
      ) {
        measurement
        value
        tags {
          projectId
        }
      }
      projects(first: 5000 includeDeleted: true workspaceId: $workspaceId) {
        edges {
          node {
            id
            name
          }
        }
      }
    }
    """

    variables = {
        "workspaceId": WORKSPACE_ID,
        "usageMeasurements": MEASUREMENTS,
        "startDate": start_date.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "endDate": end_date.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "includeDeleted": True,
        "useSmallDateChunks": True,
    }

    data = query_railway_api(query, variables)
    if not data:
        return {}, {}

    # Build project id → name map (use first occurrence to avoid duplicates)
    project_names: Dict[str, str] = {}
    for edge in data.get("projects", {}).get("edges", []):
        node = edge.get("node", {})
        pid = node.get("id")
        name = node.get("name", "Unknown")
        if pid and pid not in project_names:
            project_names[pid] = name

    # Sum usage values per project (multiple chunks with useSmallDateChunks=true)
    usage: Dict[str, Dict[str, float]] = {}
    for row in data.get("usage", []):
        pid = row.get("tags", {}).get("projectId")
        measurement = row.get("measurement")
        value = row.get("value") or 0.0
        if not pid or not measurement:
            continue
        if pid not in usage:
            usage[pid] = {}
        usage[pid][measurement] = usage[pid].get(measurement, 0.0) + value

    return usage, project_names


def fetch_estimated_usage() -> Dict[str, Dict[str, float]]:
    """
    Fetch end-of-billing-period estimated usage per project.
    Returns usage_by_project_id with same measurement keys.
    """
    query = """
    query allProjectEstimatedUsage(
      $workspaceId: String
      $usageMeasurements: [MetricMeasurement!]!
      $includeDeleted: Boolean
    ) {
      estimatedUsage(
        workspaceId: $workspaceId
        measurements: $usageMeasurements
        includeDeleted: $includeDeleted
      ) {
        measurement
        estimatedValue
        projectId
      }
    }
    """

    variables = {
        "workspaceId": WORKSPACE_ID,
        "usageMeasurements": MEASUREMENTS,
        "includeDeleted": True,
    }

    data = query_railway_api(query, variables)
    if not data:
        return {}

    estimated: Dict[str, Dict[str, float]] = {}
    for row in data.get("estimatedUsage", []):
        pid = row.get("projectId")
        measurement = row.get("measurement")
        value = row.get("estimatedValue") or 0.0
        if not pid or not measurement:
            continue
        if pid not in estimated:
            estimated[pid] = {}
        estimated[pid][measurement] = value

    return estimated


def calculate_cost(usage: Dict[str, float]) -> float:
    """Calculate total cost (USD) from usage metrics.

    Units from Railway API:
      CPU_USAGE       → vCPU-minutes
      MEMORY_USAGE_GB → GB-minutes
      NETWORK_TX_GB   → GB
      DISK/BACKUP     → within Hobby 100 GB free tier → $0
    """
    cpu = usage.get("CPU_USAGE", 0.0) * PRICING["cpu_per_vcpu_minute"]
    memory = usage.get("MEMORY_USAGE_GB", 0.0) * PRICING["memory_per_gb_minute"]
    network = usage.get("NETWORK_TX_GB", 0.0) * PRICING["network_per_gb"]
    return cpu + memory + network


def format_slack_message(
    project_names: Dict[str, str],
    current_usage: Dict[str, Dict[str, float]],
    estimated_usage: Dict[str, Dict[str, float]],
    billing_start: datetime,
    now: datetime,
) -> str:
    """Format report as Slack message"""
    date_str = now.strftime("%Y年%m月%d日")
    period_str = f"{billing_start.strftime('%m/%d')}〜{now.strftime('%m/%d')}"

    # Collect all project IDs that have any usage
    all_pids = set(current_usage.keys()) | set(estimated_usage.keys())

    rows = []
    total_current = 0.0
    total_estimated = 0.0

    for pid in sorted(all_pids, key=lambda p: project_names.get(p, p)):
        name = project_names.get(pid, pid[:8])
        cur = calculate_cost(current_usage.get(pid, {}))
        est = calculate_cost(estimated_usage.get(pid, {}))
        if cur == 0.0 and est == 0.0:
            continue
        total_current += cur
        total_estimated += est
        rows.append((name, cur, est))

    lines = [
        f"💰 Railway 料金レポート — {date_str}",
        "",
        f"📅 請求期間: {period_str}",
        f"💵 現在の合計: ${total_current:.2f}  (¥{int(total_current * JPY_RATE):,})",
        f"📈 月末予測合計: ${total_estimated:.2f}  (¥{int(total_estimated * JPY_RATE):,})",
        "",
        "プロジェクト別:",
    ]

    for name, cur, est in rows:
        lines.append(
            f"  • {name}:  現在 ${cur:.2f}  /  予測 ${est:.2f}  (¥{int(est * JPY_RATE):,})"
        )

    return "\n".join(lines)


def send_slack_message(message: str) -> bool:
    """Send formatted message to Slack"""
    slack_token = get_secret("op://banana/slack-bot/password")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {slack_token}",
    }

    payload = {
        "channel": SLACK_CHANNEL,
        "text": message,
        "mrkdwn": True,
    }

    request_body = json.dumps(payload).encode("utf-8")

    try:
        req = urllib.request.Request(
            "https://slack.com/api/chat.postMessage",
            data=request_body,
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            result = json.loads(response.read().decode("utf-8"))

        if not result.get("ok"):
            print(f"Slack API error: {result.get('error', 'Unknown error')}", file=sys.stderr)
            return False
        return True
    except urllib.error.HTTPError as e:
        print(f"Slack HTTP Error {e.code}: {e.reason}", file=sys.stderr)
        return False
    except urllib.error.URLError as e:
        print(f"URL Error: {e.reason}", file=sys.stderr)
        return False


def main():
    now = datetime.now(timezone.utc)
    billing_start = get_billing_period_start()

    print(f"📡 Fetching current usage ({billing_start.strftime('%Y-%m-%d')} → now)...", file=sys.stderr)
    current_usage, project_names = fetch_current_usage(billing_start, now)
    print(f"  {len(current_usage)} project(s) with usage data", file=sys.stderr)

    print("📡 Fetching estimated usage...", file=sys.stderr)
    estimated_usage = fetch_estimated_usage()
    print(f"  {len(estimated_usage)} project(s) with estimated data", file=sys.stderr)

    if not current_usage and not estimated_usage:
        print("No usage data available", file=sys.stderr)
        sys.exit(1)

    message = format_slack_message(project_names, current_usage, estimated_usage, billing_start, now)

    print("\n📨 Sending to Slack...", file=sys.stderr)
    if send_slack_message(message):
        print("✅ Done", file=sys.stderr)
        print(message)
    else:
        print("Failed to send Slack message", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
