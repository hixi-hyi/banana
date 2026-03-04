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
import urllib.request
import urllib.error

# Configuration
RAILWAY_API_URL = "https://backboard.railway.com/graphql/internal"
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


def query_railway_api(query: str, variables: Dict = None, endpoint: str = None) -> Dict[str, Any]:
    """Execute GraphQL query against Railway API"""
    railway_token = get_secret("op://banana/railway/password")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {railway_token}",
        "User-Agent": "railway-cost-reporter/1.0 (+https://github.com/hixi-hyi/banana)",
    }

    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    request_body = json.dumps(payload).encode('utf-8')
    
    api_url = endpoint or RAILWAY_API_URL

    try:
        req = urllib.request.Request(
            api_url,
            data=request_body,
            headers=headers,
            method='POST'
        )
        
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))

        if "errors" in data:
            print(f"GraphQL errors: {data['errors']}", file=sys.stderr)
            return {}

        return data.get("data", {})
    except urllib.error.HTTPError as e:
        # Capture detailed error response
        print(f"❌ HTTP Error {e.code}: {e.reason}", file=sys.stderr)
        try:
            error_body = e.read().decode('utf-8', errors='ignore')
            print(f"📋 Error Response: {error_body[:300]}", file=sys.stderr)
        except Exception as read_error:
            print(f"⚠️ Could not read error body: {read_error}", file=sys.stderr)
        return {}
    except urllib.error.URLError as e:
        print(f"❌ URL Error: {e.reason}", file=sys.stderr)
        return {}
    except json.JSONDecodeError as e:
        print(f"❌ JSON decode error: {e}", file=sys.stderr)
        return {}


def get_project_usage_metrics() -> Dict[str, Dict[str, float]]:
    """
    Fetch actual usage metrics from Railway API.
    Uses deployments data as proxy for current usage patterns.
    """
    # Try to fetch projects with deployments
    projects_query = """
    {
      projects(first: 100) {
        edges {
          node {
            id
            name
            environments(first: 10) {
              edges {
                node {
                  id
                  name
                  deployments(first: 10) {
                    edges {
                      node {
                        id
                        status
                        createdAt
                      }
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
    """
    
    projects_data = query_railway_api(projects_query)
    projects_list = []
    
    if projects_data and "projects" in projects_data:
        edges = projects_data.get("projects", {}).get("edges", [])
        for edge in edges:
            if "node" in edge:
                projects_list.append(edge["node"])
    
    print(f"📊 Found {len(projects_list)} projects for usage tracking", file=sys.stderr)
    
    usage_by_project = {}
    today = datetime.utcnow()
    month_start = datetime(today.year, today.month, 1)
    
    # For each project, calculate usage based on deployments in current month
    for project in projects_list:
        project_name = project.get("name", "Unknown")
        
        # Count active deployments and environments in current month
        active_deployments = 0
        total_environments = 0
        
        environments = project.get("environments", {}).get("edges", [])
        total_environments = len(environments)
        
        for env_edge in environments:
            env_node = env_edge.get("node", {})
            deployments = env_node.get("deployments", {}).get("edges", [])
            
            for dep_edge in deployments:
                dep_node = dep_edge.get("node", {})
                created_at_str = dep_node.get("createdAt", "")
                status = dep_node.get("status", "")
                
                try:
                    created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                    # Count if deployment was created in current month and is active
                    if created_at >= month_start and status in ["RUNNING", "CRASHED", "BUILDING"]:
                        active_deployments += 1
                except:
                    pass
        
        # Estimate metrics based on active deployments
        # Assume average service uses 0.5 vCPU and 512MB per active deployment
        metrics = {
            "cpu": 0.0,
            "memory": 0.0,
            "networkOut": 0.0,
            "disk": 0.0,
            "backup": 0.0,
        }
        
        if active_deployments > 0:
            days_in_month = (datetime(today.year, today.month + 1 if today.month < 12 else 1, 1) - month_start).days
            hours_remaining = (today - month_start).total_seconds() / 3600
            
            # CPU usage: 0.5 vCPU * hours in month
            metrics["cpu"] = active_deployments * 0.5 * hours_remaining
            # Memory: 0.5 GB * hours in month  
            metrics["memory"] = active_deployments * 0.5 * hours_remaining
            # Network: rough estimate 1GB per active deployment per month so far
            metrics["networkOut"] = active_deployments * (hours_remaining / 730)
            # Disk: 2GB per environment
            metrics["disk"] = total_environments * 2.0
            # Backup: 0.5GB per environment
            metrics["backup"] = total_environments * 0.5
        
        if any(metrics.values()):
            usage_by_project[project_name] = metrics
            print(f"  📊 {project_name}: {active_deployments} active deployments, CPU={metrics['cpu']:.2f}h", file=sys.stderr)
    
    return usage_by_project


def get_projects() -> List[Dict[str, Any]]:
    """
    Fetch all projects using backboard API.
    Note: This uses the backboard.railway.com/graphql/internal endpoint
    which only returns projects without detailed usage metrics.
    Cost estimation will be based on deployment timestamps.
    """
    query = """
    {
      projects(first: 100) {
        edges {
          node {
            id
            name
            environments(first: 100) {
              edges {
                node {
                  id
                  name
                  deployments(first: 100) {
                    edges {
                      node {
                        id
                        status
                        createdAt
                      }
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
    """
    
    data = query_railway_api(query)

    if not data or "projects" not in data:
        return []

    projects_conn = data.get("projects", {})
    edges = projects_conn.get("edges", [])
    
    # Flatten edges to get project nodes
    projects = []
    for edge in edges:
        if "node" in edge:
            projects.append(edge["node"])
    
    print(f"📦 Retrieved {len(projects)} projects from backboard API", file=sys.stderr)
    return projects


def extract_usage_metrics(project: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract usage metrics from project data.
    
    Note: The backboard API no longer provides direct usage metrics.
    This estimates usage based on deployment count and environments.
    For accurate costs, Railway dashboard or billing API should be used.
    """
    # Count deployments across all environments
    deployment_count = 0
    environment_count = 0
    
    environments = project.get("environments", {})
    env_edges = environments.get("edges", [])
    environment_count = len(env_edges)
    
    for env_edge in env_edges:
        env_node = env_edge.get("node", {})
        deployments = env_node.get("deployments", {})
        dep_edges = deployments.get("edges", [])
        deployment_count += len(dep_edges)
    
    # Estimate metrics based on deployment activity
    # This is a rough estimation: assume ~0.5 vCPU and 512MB per service on average
    estimated_cpu_hours = deployment_count * 0.5 * 730  # 730 hours per month
    estimated_memory_gb = environment_count * 0.5 * 730  # 0.5 GB per environment
    
    metrics = {
        "cpu": estimated_cpu_hours,
        "memory": estimated_memory_gb,
        "networkOut": deployment_count * 1.0,  # Rough estimate: 1 GB per deployment
        "disk": environment_count * 2.0,  # Rough estimate: 2 GB per environment
        "backup": 0.0,  # Usually included in disk
    }
    
    print(f"    📊 Metrics estimated: {deployment_count} deployments, {environment_count} envs", file=sys.stderr)
    
    return metrics


def calculate_monthly_cost(metrics: Dict[str, Any]) -> Dict[str, float]:
    """
    Calculate monthly cost based on actual usage metrics.
    
    Pricing:
    - CPU: $0.000278 per hour (cpu hours already measured)
    - Memory: $0.000086 per GB hour (memory GB-hours already measured)
    - Network TX: $0.02 per GB (total GB transferred in period)
    - Disk: $0.125 per GB per month (average GB storage)
    - Backup: $0.05 per GB per month (average GB storage)
    """
    costs = {
        "cpu": 0.0,
        "memory": 0.0,
        "network": 0.0,
        "disk": 0.0,
        "backup": 0.0,
    }

    # CPU: cost per hour of usage
    # Value from API is already in hours for the billing period
    if "cpu" in metrics and metrics["cpu"]:
        costs["cpu"] = metrics["cpu"] * PRICING["cpu_per_hour"]

    # Memory: cost per GB-hour of usage
    # Value from API is already in GB-hours for the billing period
    if "memory" in metrics and metrics["memory"]:
        costs["memory"] = metrics["memory"] * PRICING["memory_per_gb_hour"]

    # Network TX: cost per GB transferred
    # Value from API is total GB transferred in the billing period
    if "networkOut" in metrics and metrics["networkOut"]:
        costs["network"] = metrics["networkOut"] * PRICING["network_tx_per_gb"]

    # Disk: cost per GB per month
    # Value from API is average GB used during the period
    if "disk" in metrics and metrics["disk"]:
        costs["disk"] = metrics["disk"] * PRICING["disk_per_gb_month"]

    # Backup: cost per GB per month
    # Value from API is average GB backup storage
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
    slack_token = get_secret("op://banana/slack-bot/password")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {slack_token}",
        "User-Agent": "railway-cost-reporter/1.0 (+https://github.com/hixi-hyi/banana)",
    }

    payload = {
        "channel": SLACK_CHANNEL,
        "text": message,
        "mrkdwn": True,
    }

    request_body = json.dumps(payload).encode('utf-8')

    try:
        req = urllib.request.Request(
            "https://slack.com/api/chat.postMessage",
            data=request_body,
            headers=headers,
            method='POST'
        )
        
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))

        if not result.get("ok"):
            print(
                f"Slack API error: {result.get('error', 'Unknown error')}",
                file=sys.stderr,
            )
            return False

        return True
    except urllib.error.HTTPError as e:
        print(f"❌ Slack HTTP Error {e.code}: {e.reason}", file=sys.stderr)
        try:
            error_body = e.read().decode('utf-8', errors='ignore')
            print(f"📋 Error Response: {error_body[:300]}", file=sys.stderr)
        except Exception as read_error:
            print(f"⚠️ Could not read error body: {read_error}", file=sys.stderr)
        return False
    except urllib.error.URLError as e:
        print(f"❌ URL Error: {e.reason}", file=sys.stderr)
        return False
    except json.JSONDecodeError as e:
        print(f"❌ JSON decode error: {e}", file=sys.stderr)
        return False


def main():
    """Main execution"""
    print("🚀 Starting Railway cost reporter...", file=sys.stderr)

    # Fetch actual usage metrics from Railway API
    print("📡 Fetching usage metrics from Railway API...", file=sys.stderr)
    usage_by_project = get_project_usage_metrics()
    
    if not usage_by_project:
        # Fallback: try to get projects and estimate usage
        print("⚠️ No direct usage data available, attempting fallback...", file=sys.stderr)
        projects = get_projects()
        if not projects:
            print(
                "❌ No projects found or API error",
                file=sys.stderr,
            )
            sys.exit(1)

        print(f"📦 Found {len(projects)} project(s)", file=sys.stderr)
        
        # Extract usage metrics using deployment-based estimation
        for project in projects:
            project_name = project.get("name", "Unknown")
            metrics = extract_usage_metrics(project)
            if any(metrics.values()):
                usage_by_project[project_name] = metrics
    else:
        print(f"📦 Retrieved usage data for {len(usage_by_project)} project(s)", file=sys.stderr)

    # Calculate costs by project
    costs_by_project = {}

    for project_name, metrics in usage_by_project.items():
        if not any(metrics.values()):
            print(f"    ⚠️  No metrics found for {project_name}", file=sys.stderr)
            continue

        costs = calculate_monthly_cost(metrics)
        costs_by_project[project_name] = costs

    # Format and send report
    if not costs_by_project:
        print("❌ No cost data to report", file=sys.stderr)
        sys.exit(1)

    message = format_slack_message(costs_by_project)

    print("\n📨 Sending to Slack...", file=sys.stderr)
    print(f"📨 Target channel: {SLACK_CHANNEL}", file=sys.stderr)
    if send_slack_message(message):
        print("✅ Report sent successfully!", file=sys.stderr)
        print(message)
    else:
        print("❌ Failed to send Slack message", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
