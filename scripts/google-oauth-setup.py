#!/usr/bin/env python3
"""
Google OAuth 2.0 の初期認証スクリプト（ローカルで1回だけ実行）
refresh_token を取得して標準出力に表示する。

使い方:
  pip install google-auth-oauthlib
  python3 scripts/google-oauth-setup.py path/to/client_secret_xxx.json
"""

import json
import sys

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print("必要なパッケージをインストールしてください:")
    print("  pip install google-auth-oauthlib")
    sys.exit(1)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

def main():
    if len(sys.argv) < 2:
        print("使い方: python3 google-oauth-setup.py <client_secret_xxx.json のパス>")
        sys.exit(1)

    client_secret_file = sys.argv[1]

    flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, SCOPES)
    creds = flow.run_local_server(port=0)

    result = {
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "refresh_token": creds.refresh_token,
        "token_uri": "https://oauth2.googleapis.com/token",
        "scopes": SCOPES,
    }

    print("\n" + "="*60)
    print("認証成功！以下の情報を 1Password に保存してください。")
    print("vault: banana / item名: google-oauth / フィールド: password")
    print("="*60)
    print(json.dumps(result, indent=2))
    print("="*60)

if __name__ == "__main__":
    main()
