#!/usr/bin/env python3
"""
Railway Cost Reporter
- Fetches usage data from Railway GraphQL API
- Calculates costs by project
- Sends formatted report to Slack
"""

import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any
import subprocess
import requests

# Configuration
RAILWAY_API_URL = "https://api.railway.app/graphql"
WORKSPACE_ID = "d327b30e-dbc7-489d-a9be-9b0291afedb8"
SLACK_CHANNEL = "C0AHUGG1C82"

# Pricing (USD per unit)
PRICING = {
    "cpu_per_hour": 0.000278,
    "memory_per_gb_hour": 0.000086,
    "network_tx_per_gb": 0.02,
    "disk_per_gb_month": 0.125,
    "backup_per_gb_month": 0.05,
}

# JPY exchange rate (approximate)
JPY_RATE = 155.0  # ~155 JPY per USD


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
    }

    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    try:
        response = requests.post(RAILWAY_API_URL, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

        if "errors" in data:
            print(f"GraphQL errors: {data['errors']}", file=sys.stderr)
            return {}

        return data.get("data", {})
    except requests.RequestException as e:
        print(f"API request failed: {e}", file=sys.stderr)
        return {}


def get_projects() -> List[Dict[str, Any]]:
    """Fetch all projects in workspace"""
    query = """
    query GetProjects($workspaceId: String!) {
      workspace(id: $workspaceId) {
        id
        name
        projects {
          edges {
            node {
              id
              name
              plugins {
                edges {
                  node {
                    id
                    name
                  }
                }
              }
            }
          }
        }
      }
    }
    """

    data = query_railway_api(query, {"workspaceId": WORKSPACE_ID})

    if not data or "workspace" not in data:
        return []

    projects = []
    workspace = data["workspace"]

    if (
        workspace
        and "projects" in workspace
        and "edges" in workspace["projects"]
    ):
        for edge in workspace["projects"]["edges"]:
            if edge and "node" in edge:
                projects.append(edge["node"])

    return projects


def get_usage_metrics(project_id: str) -> Dict[str, Any]:
    """
    Fetch usage metrics for a project
    Returns aggregated usage for current month to date
    """
    # Calculate date range (month start to today)
    today = datetime.utcnow()
    month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_end = today.replace(hour=23, minute=59, second=59, microsecond=999999)

    query = """
    query GetMetrics($projectId: String!, $from: DateTime!, $to: DateTime!) {
      project(id: $projectId) {
        id
        name
        metrics(from: $from, to: $to) {
          cpu
          memory
          networkOut
          disk
          backup
        }
      }
    }
    """

    variables = {
        "projectId": project_id,
        "from": month_start.isoformat() + "Z",
        "to": month_end.isoformat() + "Z",
    }

    data = query_railway_api(query, variables)
    return data.get("project", {})


def calculate_monthly_cost(metrics: Dict[str, Any]) -> Dict[str, float]:
    """
    Calculate monthly cost based on metrics
    Metrics are expected to be aggregated usage values
    """
    costs = {
        "cpu": 0.0,
        "memory": 0.0,
        "network": 0.0,
        "disk": 0.0,
        "backup": 0.0,
    }

    # CPU: hours of usage
    if "cpu" in metrics and metrics["cpu"]:
        costs["cpu"] = (metrics["cpu"] * PRICING["cpu_per_hour"]) * 730  # hours/month

    # Memory: GB-hours of usage
    if "memory" in metrics and metrics["memory"]:
        costs["memory"] = (
            metrics["memory"] * PRICING["memory_per_gb_hour"]
        ) * 730

    # Network TX: GB transferred
    if "networkOut" in metrics and metrics["networkOut"]:
        costs["network"] = metrics["networkOut"] * PRICING["network_tx_per_gb"]

    # Disk: GB provisioned
    if "disk" in metrics and metrics["disk"]:
        costs["disk"] = metrics["disk"] * PRICING["disk_per_gb_month"]

    # Backup: GB stored
    if "backup" in metrics and metrics["backup"]:
        costs["backup"] = metrics["backup"] * PRICING["backup_per_gb_month"]

    return costs


def format_slack_message(costs_by_project: Dict[str, Dict[str, float]]) -> str:
    """Format report as Slack message"""
    today = datetime.utcnow().strftime("%Y年%m月%d日")

    total_usd = sum(
        sum(costs.values()) for costs in costs_by_project.values()
    )
    total_jpy = total_usd * JPY_RATE

    message = f"💰 Railway 料金レポート - {today}\n\n"
    message += f"📊 予測月額合計: ¥{int(total_jpy):,} (${total_usd:.2f})\n\n"
    message += "プロジェクト別内訳：\n"

    for project_name, costs in sorted(costs_by_project.items()):
        project_total = sum(costs.values())
        project_total_jpy = project_total * JPY_RATE

        message += f"\n🔹 {project_name}\n"
        message += f"  CPU: ${costs['cpu']:.4f}\n"
        message += f"  Memory: ${costs['memory']:.4f}\n"
        message += f"  Network: ${costs['network']:.4f}\n"
        message += f"  Disk: ${costs['disk']:.4f}\n"
        message += f"  Backup: ${costs['backup']:.4f}\n"
        message += f"  小計: ${project_total:.4f} (≈ ¥{int(project_total_jpy):,})\n"

    return message


def send_slack_message(message: str) -> bool:
    """Send formatted message to Slack"""
    slack_token = get_secret("op://banana/slack/token")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {slack_token}",
    }

    payload = {
        "channel": SLACK_CHANNEL,
        "text": message,
        "mrkdwn": True,
    }

    try:
        response = requests.post(
            "https://slack.com/api/chat.postMessage",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        result = response.json()

        if not result.get("ok"):
            print(
                f"Slack API error: {result.get('error', 'Unknown error')}",
                file=sys.stderr,
            )
            return False

        return True
    except requests.RequestException as e:
        print(f"Slack request failed: {e}", file=sys.stderr)
        return False


def main():
    """Main execution"""
    print("🚀 Starting Railway cost reporter...", file=sys.stderr)

    # Fetch projects
    projects = get_projects()
    if not projects:
        print(
            "❌ No projects found or API error",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"📦 Found {len(projects)} project(s)", file=sys.stderr)

    # Calculate costs by project
    costs_by_project = {}

    for project in projects:
        project_id = project.get("id")
        project_name = project.get("name", "Unknown")

        print(f"  📊 Processing: {project_name}", file=sys.stderr)

        metrics = get_usage_metrics(project_id)
        if not metrics:
            print(f"    ⚠️  No metrics found for {project_name}", file=sys.stderr)
            continue

        costs = calculate_monthly_cost(metrics.get("metrics", {}))
        costs_by_project[project_name] = costs

    # Format and send report
    if not costs_by_project:
        print("❌ No cost data to report", file=sys.stderr)
        sys.exit(1)

    message = format_slack_message(costs_by_project)

    print("\n📨 Sending to Slack...", file=sys.stderr)
    if send_slack_message(message):
        print("✅ Report sent successfully!", file=sys.stderr)
        print(message)
    else:
        print("❌ Failed to send Slack message", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
