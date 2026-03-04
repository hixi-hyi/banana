#!/usr/bin/env python3
"""
借金管理スプレッドシートへの記録スクリプト

スプレッドシート構成:
  行1: (空) | 初期借金 | 1200000
  行2: (空) | 残高     | =C1-SUM(C5:C)  ← 数式で自動計算
  行3: (空行)
  行4: 日付 | 内容 | 負担額  ← ヘッダー
  行5〜: データ行

使い方:
  python3 scripts/loan-tracker.py --purpose "食費" --amount 5000
  python3 scripts/loan-tracker.py --purpose "交通費" --amount 3000 --date 2026-03-01

1Password: op://banana/google-oauth/password に以下のJSONが保存されていること
  {
    "client_id": "...",
    "client_secret": "...",
    "refresh_token": "...",
    "token_uri": "https://oauth2.googleapis.com/token"
  }
"""

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

SPREADSHEET_ID = "1KVGjNshPbFWPXbDQTRwieQHNwEAFnjAqO-AxdPjan9w"
SHEET_NAME = "シート1"
JST = timezone(timedelta(hours=9))
BASE_URL = f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}"


def get_secret(secret_path: str) -> str:
    try:
        result = subprocess.run(
            ["op", "read", secret_path],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"1Password からシークレットを取得できません: {e}", file=sys.stderr)
        sys.exit(1)


def get_access_token(oauth_json: dict) -> str:
    data = urllib.parse.urlencode({
        "client_id": oauth_json["client_id"],
        "client_secret": oauth_json["client_secret"],
        "refresh_token": oauth_json["refresh_token"],
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=data,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())["access_token"]
    except urllib.error.HTTPError as e:
        print(f"トークン取得に失敗: {e.read().decode()}", file=sys.stderr)
        sys.exit(1)


def sheets_request(method: str, path: str, access_token: str, body: dict = None) -> dict:
    sheet_encoded = urllib.parse.quote(SHEET_NAME, safe="")
    path = path.replace("{sheet}", sheet_encoded)
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode() if body else None,
        method=method,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"Sheets API エラー: {e.read().decode()}", file=sys.stderr)
        sys.exit(1)


def get_current_balance(access_token: str) -> int:
    """E列で「残高」ラベルを探し、隣のF列の値を返す"""
    range_ = urllib.parse.quote(f"{SHEET_NAME}!E:F", safe="!:")
    result = sheets_request("GET", f"/values/{range_}", access_token)
    for row in result.get("values", []):
        if len(row) >= 2 and str(row[0]).strip() == "残高":
            raw = str(row[1]).replace(",", "").replace("¥", "").replace("￥", "").strip()
            try:
                return int(float(raw))
            except ValueError:
                print(f"残高の解析に失敗: {raw}", file=sys.stderr)
                sys.exit(1)
    print("「残高」ラベルが見つかりません（E列を確認してください）", file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="借金管理スプレッドシートに利用記録を追加")
    parser.add_argument("--purpose", required=True, help="利用用途（例: 食費、交通費）")
    parser.add_argument("--amount", required=True, type=int, help="負担額（円）")
    parser.add_argument("--date", default=None, help="日付（YYYY-MM-DD、省略時は今日のJST）")
    args = parser.parse_args()

    date_str = args.date or datetime.now(JST).strftime("%Y/%m/%d")
    amount = args.amount
    purpose = args.purpose

    # 1Password から OAuth 認証情報を取得
    oauth_raw = get_secret("op://banana/google-oauth/password")
    try:
        oauth_json = json.loads(oauth_raw)
    except json.JSONDecodeError:
        print("1Password の google-oauth フィールドが JSON 形式ではありません", file=sys.stderr)
        sys.exit(1)

    access_token = get_access_token(oauth_json)

    # 残高を取得（追記前）
    balance_before = get_current_balance(access_token)

    # データ行を追記（ヘッダー行1の直後から append）
    range_ = urllib.parse.quote(f"{SHEET_NAME}!A2:C2", safe="!:")
    sheets_request(
        "POST",
        f"/values/{range_}:append?valueInputOption=USER_ENTERED&insertDataOption=INSERT_ROWS",
        access_token,
        {"values": [[date_str, purpose, amount]]},
    )

    # 追記後の残高を取得
    balance_after = get_current_balance(access_token)

    print(f"記録しました: {date_str} / {purpose} / {amount:,}円")
    print(f"残高: {balance_before:,}円 → {balance_after:,}円")


if __name__ == "__main__":
    main()
