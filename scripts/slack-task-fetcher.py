#!/usr/bin/env python3
"""
slack-task-fetcher.py
Fetch Slack tasks (pushpins + mentions) and manage their status.

Commands:
  fetch   - Fetch new tasks from Slack and save to memory/slack-tasks.json
  report  - Output morning report JSON
  update <id> <status> - Update task status
"""

import json
import os
import sys
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone, timedelta

WORKSPACE_DIR = "/home/node/.openclaw/workspace"
TOKENS_FILE = os.path.join(WORKSPACE_DIR, "memory", "slack-tokens.json")
TASKS_FILE = os.path.join(WORKSPACE_DIR, "memory", "slack-tasks.json")
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
DAYS_BACK = 7


def load_tokens():
    with open(TOKENS_FILE, "r") as f:
        return json.load(f)


def load_tasks():
    if os.path.exists(TASKS_FILE):
        with open(TASKS_FILE, "r") as f:
            return json.load(f)
    return {"tasks": [], "last_updated": None}


def save_tasks(data):
    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    os.makedirs(os.path.dirname(TASKS_FILE), exist_ok=True)
    with open(TASKS_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def slack_api(token, method, params=None):
    """Call Slack API via urllib."""
    url = f"https://slack.com/api/{method}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            if not data.get("ok"):
                print(f"[WARN] Slack API {method} error: {data.get('error')}", file=sys.stderr)
            return data
    except Exception as e:
        print(f"[ERROR] Slack API {method} failed: {e}", file=sys.stderr)
        return {}


def get_user_info(token, user_id):
    """Get display name for a user."""
    resp = slack_api(token, "users.info", {"user": user_id})
    if resp.get("ok") and resp.get("user"):
        profile = resp["user"].get("profile", {})
        return profile.get("display_name") or profile.get("real_name") or user_id
    return user_id


def get_thread_messages(token, channel, thread_ts):
    """Get all messages in a thread."""
    resp = slack_api(token, "conversations.replies", {
        "channel": channel,
        "ts": thread_ts,
        "limit": 50
    })
    if resp.get("ok") and resp.get("messages"):
        return [m.get("text", "") for m in resp["messages"][1:]]  # skip first (main msg)
    return []


def get_permalink(token, channel, ts):
    """Get permalink for a message."""
    resp = slack_api(token, "chat.getPermalink", {"channel": channel, "message_ts": ts})
    if resp.get("ok"):
        return resp.get("permalink", "")
    return ""


def is_task_via_ai(text):
    """Ask Claude Haiku if the message is a task request."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("[WARN] ANTHROPIC_API_KEY not set, treating mention as task", file=sys.stderr)
        return True, "（AI判定スキップ）"

    prompt = (
        "以下の Slack メッセージはあなた（hixi）へのタスク依頼ですか？"
        "タスクとして明確な作業依頼・レビュー依頼・確認依頼が含まれる場合は `true`、"
        "そうでない場合（挨拶、報告、FYIなど）は `false` を JSON で返してください。"
        '{"is_task": true/false, "summary": "タスクの一言要約（日本語）"}\n\n'
        f"メッセージ:\n{text}"
    )

    payload = json.dumps({
        "model": "claude-haiku-4-5",
        "max_tokens": 256,
        "messages": [{"role": "user", "content": prompt}]
    }).encode()

    req = urllib.request.Request(
        ANTHROPIC_API_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read().decode())
            content = result.get("content", [{}])[0].get("text", "{}")
            # Extract JSON from response (may have markdown fences)
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            parsed = json.loads(content.strip())
            return parsed.get("is_task", False), parsed.get("summary", "")
    except Exception as e:
        print(f"[ERROR] Anthropic API failed: {e}", file=sys.stderr)
        return True, "（AI判定失敗、タスクとして扱う）"


def fetch_pushpins(workspace_name, ws_config):
    """Fetch messages that the user pinned with :pushpin: reaction."""
    token = ws_config["token"]
    user_id = ws_config["user_id"]
    tasks = []

    cutoff = time.time() - DAYS_BACK * 86400

    # reactions.list returns items where the user reacted
    cursor = None
    while True:
        params = {"user": user_id, "count": 200}
        if cursor:
            params["cursor"] = cursor

        resp = slack_api(token, "reactions.list", params)
        if not resp.get("ok"):
            break

        items = resp.get("items", [])
        for item in items:
            if item.get("type") != "message":
                continue
            msg = item.get("message", {})
            # Check if :pushpin: reaction from this user
            reactions = msg.get("reactions", [])
            has_pushpin = any(
                r.get("name") == "pushpin" and user_id in r.get("users", [])
                for r in reactions
            )
            if not has_pushpin:
                continue

            msg_ts = float(msg.get("ts", 0))
            if msg_ts < cutoff:
                continue

            channel = item.get("channel")
            ts = msg.get("ts", "")
            thread_ts = msg.get("thread_ts", ts)
            task_id = f"{workspace_name}:{channel}:{thread_ts}"

            sender = msg.get("user", "unknown")
            try:
                sender = get_user_info(token, sender)
            except Exception:
                pass

            thread_messages = []
            if msg.get("thread_ts") and msg["thread_ts"] != ts:
                # This is a reply; get whole thread
                thread_messages = get_thread_messages(token, channel, thread_ts)
            elif msg.get("reply_count", 0) > 0:
                thread_messages = get_thread_messages(token, channel, thread_ts)

            permalink = get_permalink(token, channel, ts)

            tasks.append({
                "id": task_id,
                "workspace": workspace_name,
                "type": "pushpin",
                "from": sender,
                "summary": "📌 ピン留めメッセージ",
                "main_text": msg.get("text", ""),
                "thread_messages": thread_messages,
                "ts": ts,
                "permalink": permalink,
                "status": "pending",
                "added_at": datetime.now(timezone.utc).isoformat(),
            })

        # Pagination
        meta = resp.get("response_metadata", {})
        next_cursor = meta.get("next_cursor", "")
        if not next_cursor:
            break
        cursor = next_cursor

    return tasks


def fetch_mentions(workspace_name, ws_config):
    """Fetch messages mentioning the user via search.messages."""
    token = ws_config["token"]
    user_id = ws_config["user_id"]
    tasks = []

    cutoff = time.time() - DAYS_BACK * 86400

    query = f"<@{user_id}>"
    page = 1
    while True:
        resp = slack_api(token, "search.messages", {
            "query": query,
            "count": 100,
            "page": page,
            "sort": "timestamp",
            "sort_dir": "desc"
        })
        if not resp.get("ok"):
            break

        messages_data = resp.get("messages", {})
        matches = messages_data.get("matches", [])
        if not matches:
            break

        for match in matches:
            msg_ts = float(match.get("ts", 0))
            if msg_ts < cutoff:
                continue

            channel_info = match.get("channel", {})
            channel = channel_info.get("id", "")
            ts = match.get("ts", "")
            thread_ts = match.get("thread_ts", ts) or ts
            task_id = f"{workspace_name}:{channel}:{thread_ts}"

            text = match.get("text", "")
            sender = match.get("username", "unknown")

            # AI判定
            is_task, summary = is_task_via_ai(text)
            if not is_task:
                continue

            thread_messages = []
            if match.get("thread_ts") and match["thread_ts"] != ts:
                thread_messages = get_thread_messages(token, channel, thread_ts)
            elif match.get("reply_count", 0) > 0:
                thread_messages = get_thread_messages(token, channel, thread_ts)

            permalink = match.get("permalink", "") or get_permalink(token, channel, ts)

            tasks.append({
                "id": task_id,
                "workspace": workspace_name,
                "type": "mention",
                "from": sender,
                "summary": summary,
                "main_text": text,
                "thread_messages": thread_messages,
                "ts": ts,
                "permalink": permalink,
                "status": "pending",
                "added_at": datetime.now(timezone.utc).isoformat(),
            })

        # Check if more pages
        paging = messages_data.get("paging", {})
        total_pages = paging.get("pages", 1)
        if page >= total_pages:
            break
        page += 1

    return tasks


def cmd_fetch():
    tokens_data = load_tokens()
    existing_data = load_tasks()
    existing_ids = {t["id"] for t in existing_data["tasks"]}

    new_tasks = []

    for ws_name, ws_config in tokens_data["workspaces"].items():
        print(f"[INFO] Processing workspace: {ws_name}", file=sys.stderr)

        try:
            pushpins = fetch_pushpins(ws_name, ws_config)
            print(f"[INFO] {ws_name}: found {len(pushpins)} pushpin candidates", file=sys.stderr)
            for task in pushpins:
                if task["id"] not in existing_ids:
                    new_tasks.append(task)
                    existing_ids.add(task["id"])
        except Exception as e:
            print(f"[ERROR] {ws_name} pushpins failed: {e}", file=sys.stderr)

        try:
            mentions = fetch_mentions(ws_name, ws_config)
            print(f"[INFO] {ws_name}: found {len(mentions)} mention tasks", file=sys.stderr)
            for task in mentions:
                if task["id"] not in existing_ids:
                    new_tasks.append(task)
                    existing_ids.add(task["id"])
        except Exception as e:
            print(f"[ERROR] {ws_name} mentions failed: {e}", file=sys.stderr)

    existing_data["tasks"].extend(new_tasks)
    save_tasks(existing_data)

    print(json.dumps({"new_tasks": new_tasks}, ensure_ascii=False, indent=2))


def cmd_report():
    data = load_tasks()
    tasks = data.get("tasks", [])

    pending = [t for t in tasks if t.get("status") == "pending"]

    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    lines = [f"おはよう！📋 未対応タスクが {len(pending)}件 あるよ。"]
    if pending:
        lines.append("")
        for i, task in enumerate(pending):
            label = letters[i] if i < len(letters) else str(i + 1)
            ts_val = float(task.get("ts", 0))
            date_str = datetime.fromtimestamp(ts_val, tz=timezone.utc).strftime("%m/%d") if ts_val else "?"
            workspace = task.get("workspace", "?")
            from_name = task.get("from", "?")
            summary = task.get("summary", "（要約なし）")
            permalink = task.get("permalink", "")

            lines.append(f"{label}. [{workspace}] {from_name} さんから（{date_str}）")
            lines.append(f"　{summary}")
            if permalink:
                lines.append(f"　🔗 {permalink}")
            lines.append("")

        lines.append("各タスクのステータスを教えて（例：`A 完了`, `B 対応中`, `C スキップ`）")

    report_text = "\n".join(lines)

    output = {
        "new_tasks": [],
        "pending_tasks": pending,
        "report_text": report_text
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


def cmd_update(task_id, status):
    valid_statuses = {"pending", "done", "skipped", "in_progress"}
    if status not in valid_statuses:
        print(f"[ERROR] Invalid status '{status}'. Valid: {valid_statuses}", file=sys.stderr)
        sys.exit(1)

    data = load_tasks()
    found = False
    for task in data["tasks"]:
        if task["id"] == task_id:
            task["status"] = status
            task["updated_at"] = datetime.now(timezone.utc).isoformat()
            found = True
            break

    if not found:
        print(f"[ERROR] Task not found: {task_id}", file=sys.stderr)
        sys.exit(1)

    save_tasks(data)
    print(json.dumps({"updated": task_id, "status": status}, ensure_ascii=False))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "fetch":
        cmd_fetch()
    elif cmd == "report":
        cmd_report()
    elif cmd == "update":
        if len(sys.argv) < 4:
            print("[ERROR] Usage: update <id> <status>", file=sys.stderr)
            sys.exit(1)
        cmd_update(sys.argv[2], sys.argv[3])
    else:
        print(f"[ERROR] Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
