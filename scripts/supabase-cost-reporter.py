#!/usr/bin/env python3
"""
Supabase Cost Reporter
- Fetches org plan and project billing addons from Supabase Management API
- Calculates estimated monthly costs per project
- Sends formatted report to Slack
"""

import json
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import subprocess
import urllib.request
import urllib.error

# Configuration
SUPABASE_API_URL = "https://api.supabase.com/v1"
SLACK_CHANNEL = "C0AHUGG1C82"

# Supabase Pro plan base fee (USD/month)
# https://supabase.com/pricing
PLAN_FEES = {
    "free": 0.0,
    "pro": 25.0,
    "team": 599.0,
}

# Compute credit included per org per month (Pro/Team plan)
COMPUTE_CREDIT_USD = 10.0

# Hours per month (30 days)
HOURS_PER_MONTH = 720.0

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


def call_api(path: str, token: str) -> Any:
    """Call Supabase Management API"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    try:
        req = urllib.request.Request(
            f"{SUPABASE_API_URL}{path}",
            headers={
                **headers,
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
                "Origin": "https://supabase.com",
                "Referer": "https://supabase.com/",
            },
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="ignore")[:200]
        except Exception:
            pass
        print(f"HTTP Error {e.code} for {path}: {e.reason} — {body}", file=sys.stderr)
        return None
    except urllib.error.URLError as e:
        print(f"URL Error for {path}: {e.reason}", file=sys.stderr)
        return None
    except json.JSONDecodeError as e:
        print(f"JSON decode error for {path}: {e}", file=sys.stderr)
        return None


def fetch_organizations(token: str) -> List[Dict[str, Any]]:
    """Fetch all organizations"""
    data = call_api("/organizations", token)
    return data if isinstance(data, list) else []


def fetch_org_detail(slug: str, token: str) -> Dict[str, Any]:
    """Fetch org details (includes plan)"""
    data = call_api(f"/organizations/{slug}", token)
    return data if isinstance(data, dict) else {}


def fetch_projects(token: str) -> List[Dict[str, Any]]:
    """Fetch all projects"""
    data = call_api("/projects", token)
    return data if isinstance(data, list) else []


def fetch_billing_addons(ref: str, token: str) -> Dict[str, Any]:
    """Fetch selected billing addons for a project"""
    data = call_api(f"/projects/{ref}/billing/addons", token)
    return data if isinstance(data, dict) else {}


def estimate_addon_monthly_cost(addon: Dict[str, Any]) -> float:
    """Calculate estimated monthly cost (USD) for a single addon"""
    price = addon.get("variant", {}).get("price", {})
    amount = price.get("amount", 0.0)
    interval = price.get("interval", "monthly")

    if interval == "hourly":
        return amount * HOURS_PER_MONTH
    else:
        return amount


def calculate_project_costs(projects: List[Dict[str, Any]], token: str) -> List[Dict[str, Any]]:
    """
    For each project, fetch billing addons and calculate estimated monthly cost.
    Returns list of dicts with name, ref, region, addons, and monthly_cost_usd.
    """
    results = []
    for proj in projects:
        ref = proj.get("ref", "")
        name = proj.get("name", ref)
        region = proj.get("region", "")
        status = proj.get("status", "")

        print(f"  Fetching addons for {name} ({ref})...", file=sys.stderr)
        billing = fetch_billing_addons(ref, token)
        selected = billing.get("selected_addons", [])

        total = 0.0
        addon_lines = []
        for addon in selected:
            addon_type = addon.get("type", "")
            variant = addon.get("variant", {})
            variant_name = variant.get("name", "")
            price_desc = variant.get("price", {}).get("description", "")
            cost = estimate_addon_monthly_cost(addon)
            total += cost
            addon_lines.append({
                "type": addon_type,
                "variant": variant_name,
                "price_desc": price_desc,
                "monthly_usd": cost,
            })

        results.append({
            "name": name,
            "ref": ref,
            "region": region,
            "status": status,
            "addons": addon_lines,
            "monthly_cost_usd": total,
        })

    return results


def format_slack_message(
    org_name: str,
    plan: str,
    project_costs: List[Dict[str, Any]],
    now: datetime,
) -> str:
    """Format the cost report as a Slack message"""
    date_str = now.strftime("%Y年%m月%d日")
    plan_fee = PLAN_FEES.get(plan, 0.0)

    total_addons = sum(p["monthly_cost_usd"] for p in project_costs)
    credit = COMPUTE_CREDIT_USD if plan in ("pro", "team") else 0.0
    total_usd = plan_fee + max(0.0, total_addons - credit)

    lines = [
        f"💰 Supabase 料金レポート — {date_str}",
        "",
        f"🏢 組織: {org_name}  (プラン: {plan.upper()})",
        f"💵 推定月額合計: ${total_usd:.2f}  (¥{int(total_usd * JPY_RATE):,})",
        "",
        f"  プラン基本料: ${plan_fee:.2f}/月",
        f"  コンピュートクレジット: -${credit:.2f}/月 (含む)",
        f"  アドオン合計: ${total_addons:.2f}/月",
        "",
        "プロジェクト別:",
    ]

    for proj in sorted(project_costs, key=lambda p: p["name"]):
        name = proj["name"]
        region = proj["region"]
        cost = proj["monthly_cost_usd"]
        status_icon = "🟢" if proj["status"] == "ACTIVE_HEALTHY" else "🔴"
        lines.append(f"  {status_icon} {name}  ({region})  ≈ ${cost:.2f}/月  (¥{int(cost * JPY_RATE):,})")
        for a in proj["addons"]:
            lines.append(f"      • {a['variant']} {a['type']}: {a['price_desc']}")

    lines.append("")
    lines.append("_※ 料金は選択中のアドオンから推計。実際の請求は Supabase ダッシュボードで確認してください。_")

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
    supabase_token = get_secret("op://banana/supabase/password")

    print("📡 Fetching organizations...", file=sys.stderr)
    orgs = fetch_organizations(supabase_token)
    if not orgs:
        print("No organizations found", file=sys.stderr)
        sys.exit(1)

    # Use first org (or could iterate over all)
    org = orgs[0]
    org_slug = org.get("slug", org.get("id", ""))
    org_name = org.get("name", org_slug)

    print(f"📡 Fetching org details for {org_name}...", file=sys.stderr)
    org_detail = fetch_org_detail(org_slug, supabase_token)
    plan = org_detail.get("plan", "free").lower()
    print(f"  Plan: {plan}", file=sys.stderr)

    print("📡 Fetching projects...", file=sys.stderr)
    projects = fetch_projects(supabase_token)
    # Filter to this org only
    projects = [p for p in projects if p.get("organization_slug") == org_slug or p.get("organization_id") == org_slug]
    print(f"  {len(projects)} project(s) found", file=sys.stderr)

    print("📡 Fetching billing addons...", file=sys.stderr)
    project_costs = calculate_project_costs(projects, supabase_token)

    message = format_slack_message(org_name, plan, project_costs, now)

    print("\n📨 Sending to Slack...", file=sys.stderr)
    if send_slack_message(message):
        print("✅ Done", file=sys.stderr)
        print(message)
    else:
        print("Failed to send Slack message", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
