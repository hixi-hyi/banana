#!/usr/bin/env python3
"""
Slack Task Fetcher - 各ワークスペースのDM・メンションからタスクを収集・管理する
"""

import json
import os
import sys
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
import urllib.request
import urllib.parse

WORKSPACE = Path("/home/node/.openclaw/workspace")
TOKENS_FILE = WORKSPACE / "memory/slack-tokens.json"
TASKS_FILE = WORKSPACE / "memory/slack-tasks.json"

JST = timezone(timedelta(hours=9))


def slack_api(token, method, params=None):
    url = f"https://slack.com/api/{method}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def get_user_info(token, user_id):
    r = slack_api(token, "users.info", {"user": user_id})
    if r.get("ok"):
        return r["user"].get("real_name") or r["user"].get("name", user_id)
    return user_id


def fetch_tasks_from_workspace(name, config):
    token = config["token"]
    user_id = config["user_id"]
    tasks = []

    # 直近7日のメッセージを対象
    oldest = str((datetime.now() - timedelta(days=7)).timestamp())

    # DM一覧を取得
    ims = slack_api(token, "conversations.list", {
        "types": "im",
        "exclude_archived": "true",
        "limit": 100
    })
    if not ims.get("ok"):
        print(f"[{name}] conversations.list failed: {ims.get('error')}", file=sys.stderr)
        return tasks

    for ch in ims.get("channels", []):
        ch_id = ch["id"]
        # DM履歴を取得
        hist = slack_api(token, "conversations.history", {
            "channel": ch_id,
            "oldest": oldest,
            "limit": 20
        })
        if not hist.get("ok"):
            continue

        sender_name = get_user_info(token, ch.get("user", "?"))
        for msg in hist.get("messages", []):
            if msg.get("user") == user_id:
                continue  # 自分の発言はスキップ
            text = msg.get("text", "")
            ts = msg["ts"]
            permalink = f"https://{config.get('domain', name + '.slack.com')}/archives/{ch_id}/p{ts.replace('.', '')}"
            tasks.append({
                "id": f"{name}:{ch_id}:{ts}",
                "workspace": name,
                "type": "dm",
                "from": sender_name,
                "text": text[:300],
                "ts": ts,
                "permalink": permalink,
                "status": "pending",
                "added_at": datetime.now(JST).isoformat()
            })

    # メンション検索
    search = slack_api(token, "search.messages", {
        "query": f"<@{user_id}>",
        "count": 20,
        "sort": "timestamp",
        "sort_dir": "desc"
    })
    if search.get("ok"):
        for msg in search.get("messages", {}).get("matches", []):
            ts = msg["ts"]
            if float(ts) < float(oldest):
                continue
            ch_id = msg["channel"]["id"]
            tasks.append({
                "id": f"{name}:{ch_id}:{ts}",
                "workspace": name,
                "type": "mention",
                "from": msg.get("username", "?"),
                "text": msg.get("text", "")[:300],
                "ts": ts,
                "permalink": msg.get("permalink", ""),
                "status": "pending",
                "added_at": datetime.now(JST).isoformat()
            })

    return tasks


def load_tasks():
    if TASKS_FILE.exists():
        return json.loads(TASKS_FILE.read_text())
    return {"tasks": [], "last_updated": None}


def save_tasks(data):
    TASKS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def merge_tasks(existing_tasks, new_tasks):
    existing_ids = {t["id"] for t in existing_tasks}
    merged = list(existing_tasks)
    added = 0
    for t in new_tasks:
        if t["id"] not in existing_ids:
            merged.append(t)
            added += 1
    return merged, added


def fetch_all():
    tokens_data = json.loads(TOKENS_FILE.read_text())
    workspaces = tokens_data.get("workspaces", {})

    all_new_tasks = []
    for name, config in workspaces.items():
        print(f"Fetching from {name}...", file=sys.stderr)
        try:
            tasks = fetch_tasks_from_workspace(name, config)
            all_new_tasks.extend(tasks)
            print(f"  {len(tasks)} messages found", file=sys.stderr)
        except Exception as e:
            print(f"  Error: {e}", file=sys.stderr)

    data = load_tasks()
    merged, added = merge_tasks(data["tasks"], all_new_tasks)
    data["tasks"] = merged
    data["last_updated"] = datetime.now(JST).isoformat()
    save_tasks(data)
    print(json.dumps({"added": added, "total": len(merged)}))


def morning_report():
    """朝の通知用レポートを生成"""
    data = load_tasks()
    tasks = data.get("tasks", [])
    pending = [t for t in tasks if t["status"] == "pending"]

    if not pending:
        print(json.dumps({"message": "pending tasks: 0"}))
        return

    # 時刻が新しい順にソート
    pending.sort(key=lambda t: t["ts"], reverse=True)

    report = {
        "pending_count": len(pending),
        "tasks": []
    }
    for i, t in enumerate(pending[:10]):  # 最大10件
        ts_dt = datetime.fromtimestamp(float(t["ts"]), JST)
        report["tasks"].append({
            "index": i + 1,
            "workspace": t["workspace"],
            "type": t["type"],
            "from": t["from"],
            "text": t["text"],
            "date": ts_dt.strftime("%m/%d %H:%M"),
            "permalink": t["permalink"],
            "id": t["id"]
        })
    print(json.dumps(report, ensure_ascii=False))


def update_status(task_id, status):
    """タスクのステータスを更新"""
    data = load_tasks()
    for t in data["tasks"]:
        if t["id"] == task_id:
            t["status"] = status
            t["updated_at"] = datetime.now(JST).isoformat()
            break
    save_tasks(data)
    print(json.dumps({"ok": True}))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "fetch"
    if cmd == "fetch":
        fetch_all()
    elif cmd == "report":
        morning_report()
    elif cmd == "update" and len(sys.argv) >= 4:
        update_status(sys.argv[2], sys.argv[3])
    else:
        print(f"Usage: {sys.argv[0]} fetch|report|update <id> <status>", file=sys.stderr)
