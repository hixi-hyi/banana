#!/usr/bin/env python3
"""
#banana チャンネルから支出メッセージを監視し、自動で loan-tracker.py を実行

トリガーパターン:
  - 「〇〇〇〇円利用」
  - 「〇〇に〇〇〇〇円使った」
  - 「〇〇〇〇円 〇〇で利用」
  - 「借金に〇〇〇〇円追加して」
  - 「〇〇〇〇円」（シンプルパターン：用途は「その他」）
  - 「〇〇（店名等） 〇〇〇〇円」

JSON ファイル: memory/expense-tracker-state.json で処理済みメッセージ ts を記録
"""

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SLACK_CHANNEL = "C0AHBC2B3GB"  # #banana
WORKSPACE_DIR = "/home/node/.openclaw/workspace"
STATE_FILE = os.path.join(WORKSPACE_DIR, "memory", "expense-tracker-state.json")
TOKENS_FILE = os.path.join(WORKSPACE_DIR, "memory", "slack-tokens.json")


def load_tokens():
    """slack-tokens.json から Slack token を取得（複数ワークスペース対応）"""
    if os.path.exists(TOKENS_FILE):
        with open(TOKENS_FILE, "r") as f:
            data = json.load(f)
            # codify ワークスペース優先、なければ最初のワークスペース
            workspaces = data.get("workspaces", {})
            if "codify" in workspaces:
                return workspaces["codify"].get("token")
            # フォールバック
            for ws_data in workspaces.values():
                token = ws_data.get("token")
                if token:
                    return token
    return None


def load_state():
    """処理済みメッセージの ts リストを読み込む"""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"processed_messages": []}


def save_state(state):
    """状態を保存"""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def slack_api(token, method, params=None):
    """Slack API 呼び出し"""
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


def get_channel_messages(token, limit=50):
    """#banana チャンネルの最新メッセージを取得"""
    resp = slack_api(token, "conversations.history", {
        "channel": SLACK_CHANNEL,
        "limit": limit,
    })
    if resp.get("ok"):
        return resp.get("messages", [])
    return []


def extract_amount_and_purpose(text):
    """
    テキストから金額と用途を抽出
    Returns: (amount_int, purpose_str) or (None, None)
    """
    # メンション（<@...>）を除去
    clean_text = re.sub(r"<@[A-Z0-9]+>", "", text).strip()
    
    # パターン1: 「〇〇に〇〇〇〇円使った」「〇〇〇〇円」「〇〇〇〇円利用」
    patterns = [
        (r"(\D+?)に(\d+)円使った", lambda m: (int(m.group(2)), m.group(1))),
        (r"(\D+?)\s+(\d+)円$", lambda m: (int(m.group(2)), m.group(1))),  # 「今井湯 1000円」
        (r"(\d+)円([^円]*?)利用", lambda m: (int(m.group(1)), m.group(2) or "利用")),
        (r"(\d+)円\s+(\D+)で", lambda m: (int(m.group(1)), m.group(2))),
        (r"(\D+?)\s+(\d+)円\s+利用", lambda m: (int(m.group(2)), m.group(1))),
        (r"(\d+)円", lambda m: (int(m.group(1)), "その他")),  # 金額だけ
    ]

    for pattern, extract in patterns:
        match = re.search(pattern, clean_text)
        if match:
            try:
                amount, purpose = extract(match)
                # 用途が数字だけなら「その他」
                if purpose.isdigit() or not purpose:
                    purpose = "その他"
                return amount, purpose.strip()
            except (ValueError, IndexError):
                continue

    return None, None


def run_loan_tracker(purpose, amount):
    """loan-tracker.py を実行"""
    try:
        result = subprocess.run(
            [
                "python3",
                os.path.join(WORKSPACE_DIR, "scripts", "loan-tracker.py"),
                "--purpose", purpose,
                "--amount", str(amount),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] loan-tracker.py failed: {e.stderr}", file=sys.stderr)
        return None


def main():
    token = load_tokens()
    if not token:
        print("[ERROR] Slack token not found", file=sys.stderr)
        sys.exit(1)

    state = load_state()
    processed = set(state.get("processed_messages", []))

    messages = get_channel_messages(token, limit=50)
    results = []

    for msg in messages:
        ts = msg.get("ts")
        if ts in processed:
            continue

        # 自分（banana）のメッセージは処理しない
        if msg.get("bot_id"):
            processed.add(ts)
            continue

        text = msg.get("text", "").strip()
        if not text:
            continue

        # 金額・用途を抽出
        amount, purpose = extract_amount_and_purpose(text)
        if amount and purpose:
            # loan-tracker.py を実行
            output = run_loan_tracker(purpose, amount)
            if output:
                results.append({
                    "ts": ts,
                    "text": text,
                    "amount": amount,
                    "purpose": purpose,
                    "output": output,
                })
                processed.add(ts)

    # 状態を保存
    state["processed_messages"] = list(processed)
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    save_state(state)

    # 結果を出力
    print(json.dumps(results, ensure_ascii=False, indent=2))
    if results:
        print(f"\n[INFO] {len(results)} expense(s) recorded", file=sys.stderr)


if __name__ == "__main__":
    main()
