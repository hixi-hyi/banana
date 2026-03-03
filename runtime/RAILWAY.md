# RAILWAY.md - Railway デプロイ運用ガイド

## 概要

- **プロジェクト:** `a34ec417-49f4-4bcb-bdbd-1f64d0b075b8`
- **サービス:** `44670adb-2cc2-41d6-86c2-c30319e7d961`（openclaw-gateway）
- **URL:** `https://openclaw-gateway-production-d702.up.railway.app/`
- **Control UI:** URL の末尾に `/openclaw` を付ける
- **Volume:** `/home/node/.openclaw` にマウント（状態・設定が永続化される）

## 環境変数（Railway に設定済み）

| 変数名 | 用途 |
|--------|------|
| `OP_SERVICE_ACCOUNT_TOKEN` | 1Password Service Account トークン（これ1つですべての秘密を取得） |
| `OPENCLAW_STATE_DIR` | `/home/node/.openclaw` |
| `SETUP_PASSWORD` | `/setup` ページのパスワード |

以前は `ANTHROPIC_API_KEY`, `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `DISCORD_BOT_TOKEN`,
`OPENCLAW_GATEWAY_TOKEN`, `GITHUB_TOKEN` を個別に設定していたが、すべて 1Password に移行済み。

## 1Password Vault 構成

Vault 名: `banana`

| アイテム名 | フィールド | 用途 |
|-----------|-----------|------|
| `github` | `password` | GitHub clone/push 用 PAT |
| `anthropic` | `password` | Claude API キー |
| `slack-bot` | `password` | Slack Bot トークン |
| `slack-app` | `password` | Slack App トークン（Socket Mode） |
| `discord` | `password` | Discord Bot トークン |
| `openclaw-gateway` | `password` | Web UI 認証トークン |

## よく使うスクリプト（リポジトリルートから実行）

| スクリプト | 用途 |
|-----------|------|
| `./runtime/scripts/logs [行数]` | ログ確認（デフォルト 100 行） |
| `./runtime/scripts/logs-follow` | ログをリアルタイムで追う（Ctrl+C で終了） |
| `./runtime/scripts/deploy` | Railway にデプロイ |
| `./runtime/scripts/status` | デプロイ状況 + 直近ログを表示 |
| `./runtime/scripts/ssh [コマンド]` | コンテナに SSH（引数なしでシェル起動） |
| `./runtime/scripts/config-get [jqフィルタ]` | コンテナ上の openclaw.json を確認 |
| `./runtime/scripts/config-reset` | openclaw.json をリセットして再デプロイ |

## リポジトリ構成

```
banana/
├── railway.toml          # Railway CLI 用（root 必須）
├── openclaw.json         # openclaw 設定（op://参照でシークレットを管理）
├── AGENTS.md / SOUL.md / IDENTITY.md / MEMORY.md / USER.md
├── HEARTBEAT.md / TOOLS.md
├── memory/
└── runtime/              # 実行環境（このファイルもここ）
    ├── Dockerfile
    ├── startup.sh
    ├── docker-compose.yml
    └── RAILWAY.md
```

## startup.sh の処理フロー（毎回起動時）

1. `op read "op://banana/github/token"` → `GITHUB_TOKEN` を取得
2. リポジトリ全体を `/home/node/.openclaw/workspace/` に clone/pull
3. git 認証情報を設定（`/root/.git-credentials`）
4. `op read "op://banana/anthropic/credential"` → `auth-profiles.json` に書き込む
5. `op inject -i workspace/openclaw.json -o openclaw.json` → シークレットを展開
6. `openclaw gateway run` で起動

必要な Railway 環境変数は **`OP_SERVICE_ACCOUNT_TOKEN` のみ**。

## openclaw.json の管理

`openclaw.json` はリポジトリに直接コミットされている。シークレット部分は `{{ op://... }}` 形式の
テンプレート参照になっているため、git に入れても安全。

起動時に `op inject` が参照を実値に展開して `/home/node/.openclaw/openclaw.json` に書き出す。

### 設定を変更したいとき

openclaw の設定を変更すると `/home/node/.openclaw/openclaw.json`（volume）が更新される。
変更をリポジトリに反映するには `config-sync-container` を実行する：

```bash
railway ssh -- node /home/node/.openclaw/workspace/runtime/scripts/config-sync-container
```

または Banana に頼む：

```
node /home/node/.openclaw/workspace/runtime/scripts/config-sync-container
```

## 何か問題が起きたときの対処

### gateway が起動しない / 応答しない

1. まずログを確認：`railway logs --tail 50`
2. エラーメッセージを見て原因を特定

**よくある原因と対処:**

| エラー | 原因 | 対処 |
|--------|------|------|
| `OP_SERVICE_ACCOUNT_TOKEN not set` | Railway の env var 未設定 | Railway ダッシュボードで設定 |
| `[AUTH] 401 Unauthorized` | 1Password トークン期限切れ | Service Account を再生成 |
| `Invalid config: channels.slack.dmPolicy` | エージェントが openclaw.json に無効な値を書いた | `railway up --detach` で再デプロイ |
| `EACCES: permission denied` | ボリュームのパーミッション問題 | Dockerfile が `USER root` になっているか確認 |
| `pairing required` | ブラウザが未承認デバイス | `railway ssh` → `openclaw devices approve <id>` |

### openclaw.json を直接修正したい

```bash
railway ssh -- node -e "
const fs = require('fs');
const p = '/home/node/.openclaw/openclaw.json';
let c = JSON.parse(fs.readFileSync(p, 'utf8'));
// ここで修正（例）
delete c.channels.slack.dmPolicy;
fs.writeFileSync(p, JSON.stringify(c, null, 2));
console.log('done');
"
```

### 設定をリセットしたい

再デプロイすれば `startup.sh` が `openclaw.json`（git）を `op inject` で再展開する：

```bash
railway up --detach
```

### ローカルで docker-compose を使う

```bash
# OP_SERVICE_ACCOUNT_TOKEN を .env に追加してから
docker compose -f runtime/docker-compose.yml up
```
