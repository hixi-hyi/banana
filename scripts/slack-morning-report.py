#!/usr/bin/env python3
"""
毎朝 Slack の pending タスクをまとめて #banana に通知する
"""

import json
import subprocess
import sys
import urllib.request
import urllib.parse
import os
from pathlib import Path

WORKSPACE = Path("/home/node/.openclaw/workspace")
TASKS_FILE = WORKSPACE / "memory/slack-tasks.json"

# OpenClaw Slack Bot Token (環境変数から取得)
# banana の Slack 接続トークン
BANANA_SLACK_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
BANANA_CHANNEL = "C0AHUGG1C82"  # pending タスク通知先チャンネル


def slack_post(token, channel, text):
    url = "https://slack.com/api/chat.postMessage"
    payload = json.dumps({"channel": channel, "text": text}).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def main():
    # まず最新のタスクを取得
    subprocess.run(
        ["python3", str(WORKSPACE / "scripts/slack-task-fetcher.py"), "fetch"],
        capture_output=True
    )

    # レポート生成
    result = subprocess.run(
        ["python3", str(WORKSPACE / "scripts/slack-task-fetcher.py"), "report"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print("report failed", file=sys.stderr)
        return

    report = json.loads(result.stdout)
    count = report.get("pending_count", 0)
    tasks = report.get("tasks", [])

    if count == 0:
        # タスクなし
        msg = "おはよう！📋 現在 pending のタスクはなし。今日も快調！"
        print(msg)
        return

    lines = [f"おはよう！📋 未対応タスクが *{count}件* あるよ。ステータスを確認しよう。\n"]

    for t in tasks:
        label = chr(ord('A') + t['index'] - 1)  # A, B, C, ...
        ws = t['workspace']
        from_ = t['from']
        date = t['date']
        text_preview = t['text'][:80].replace('\n', ' ')
        url = t['permalink']

        lines.append(
            f"*{label}. [{ws}]* {from_} さんから（{date}）\n"
            f"　{text_preview}\n"
            f"　<{url}|🔗 元メッセージ>"
        )

    lines.append("\n各タスクのステータスを教えて（例：`A 完了`, `B 対応中`, `C スキップ`）")

    msg = "\n".join(lines)
    print(msg)

    # ファイルに保存（banana が読み上げ用に使う）
    report_file = WORKSPACE / "memory/morning-report-latest.txt"
    report_file.write_text(msg)
    report_tasks_file = WORKSPACE / "memory/morning-report-tasks.json"
    report_tasks_file.write_text(json.dumps(tasks, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
