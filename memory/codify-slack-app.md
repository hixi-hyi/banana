# Codify Slack App セットアップ手順

新しいワークスペースに Codify アプリを追加するとき、この手順に従う。

## 手順

1. https://api.slack.com/apps を開く
2. "Codify" アプリを選択（なければ新規作成: "Create New App" → "From scratch" → App Name: `Codify`）
3. 左サイドバーの "App Manifest" をクリック
4. 下記の Manifest JSON で置き換えて "Save Changes"
5. "OAuth & Permissions" → "Install to Workspace"（または "Reinstall to Workspace"）
6. 対象ワークスペースを選択して承認
7. 発行された `xoxp-...` トークンを banana に渡す

## App Manifest

```json
{
  "display_information": {
    "name": "Codify"
  },
  "oauth_config": {
    "scopes": {
      "user": [
        "channels:history",
        "channels:read",
        "groups:history",
        "groups:read",
        "im:history",
        "im:read",
        "mpim:history",
        "mpim:read",
        "users:read",
        "search:read",
        "reactions:read",
        "bookmarks:read"
      ]
    }
  },
  "settings": {
    "org_deploy_enabled": false,
    "socket_mode_enabled": false,
    "token_rotation_enabled": false
  }
}
```

## 取得できる情報

- DM の履歴（`im:history`）
- パブリック/プライベートチャンネルの履歴
- 自分が付けたリアクション（`reactions:read`） → :pushpin: でタスクフラグ
- メンション検索（`search:read`）

## 登録済みワークスペース

| ワークスペース | User | 登録日 |
|---|---|---|
| 株式会社CloudBrains | hiroyoshi.hochi | 2026-03-01 |
| Codify Inc | houchi.hiroyoshi | 2026-03-01 |
