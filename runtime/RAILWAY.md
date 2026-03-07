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

1. `op read "op://banana/github/password"` → `GITHUB_TOKEN` を取得
2. リポジトリ全体を `/home/node/.openclaw/workspace/` に clone/pull
3. git 認証情報を設定（`/root/.git-credentials`）
4. `workspace/runtime/auth-profiles.json` を agent dir にコピー
5. `workspace/openclaw.json` を `/home/node/.openclaw/openclaw.json` にコピー
6. `openclaw gateway run` で起動

シークレットは openclaw の SecretRef 機能で起動時に 1Password から直接取得する（`op inject` 不要）。

必要な Railway 環境変数は **`OP_SERVICE_ACCOUNT_TOKEN`** と **`OPENCLAW_GATEWAY_TOKEN`**。

## openclaw.json の管理

`openclaw.json` はリポジトリに直接コミットされている。シークレット部分は openclaw の
`SecretRef`（`{ "source": "exec", "provider": "op-*", "id": "value" }` 形式）で管理しており、
git に入れても安全。openclaw が起動時に 1Password から直接取得する。

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

再デプロイすれば `startup.sh` が最新の `openclaw.json`（git）をコピーして起動する：

```bash
railway up --detach
```

### ローカルで docker-compose を使う

```bash
# OP_SERVICE_ACCOUNT_TOKEN を .env に追加してから
docker compose -f runtime/docker-compose.yml up
```

---

## ローカル検証方法

openclaw の設定変更を Railway にデプロイする前にローカルで検証する手順。

### 前提

- Docker Desktop が起動していること
- `OP_SERVICE_ACCOUNT_TOKEN` が手元にあること（1Password Service Account）
- Mac (Apple Silicon) の場合は `--platform linux/amd64` が必要

### 1. テスト用 Docker イメージのビルド

```bash
# フルイメージ（1Password CLI 含む）
docker build --platform linux/amd64 -t openclaw-test -f runtime/Dockerfile .

# ビルドに失敗する場合は --no-cache を付ける
docker build --platform linux/amd64 --no-cache -t openclaw-test -f runtime/Dockerfile .
```

`op` のインストールパスを確認：

```bash
docker run --platform linux/amd64 --rm --entrypoint "" openclaw-test which op
# → /usr/bin/op
```

### 2. config の schema バリデーション

openclaw.json に構文・スキーマエラーがないか確認する。

```bash
docker run --platform linux/amd64 --rm \
  --entrypoint "" \
  -e HOME=/home/node \
  -e OPENCLAW_STATE_DIR=/home/node/.openclaw \
  -e OPENCLAW_GATEWAY_TOKEN=test-token \
  -v $(pwd)/openclaw.json:/home/node/.openclaw/openclaw.json \
  openclaw-test \
  node /app/openclaw.mjs gateway run --port 18789 --bind loopback --auth token 2>&1 &
PID=$!; sleep 5; kill $PID 2>/dev/null; wait $PID 2>/dev/null
```

エラーがなければ起動ログのみ表示される。スキーマエラーがある場合は即座に
`Invalid config: <field>: <reason>` が出力される。

### 3. SecretRef（1Password 連携）の確認

`OP_SERVICE_ACCOUNT_TOKEN` を渡して、シークレットが正しく解決されるか確認する。

```bash
docker run --platform linux/amd64 --rm \
  --entrypoint "" \
  -e HOME=/home/node \
  -e OPENCLAW_STATE_DIR=/home/node/.openclaw \
  -e OPENCLAW_GATEWAY_TOKEN=test-token \
  -e OP_SERVICE_ACCOUNT_TOKEN="<トークン>" \
  -v $(pwd)/openclaw.json:/home/node/.openclaw/openclaw.json \
  -v $(pwd)/runtime/auth-profiles.json:/home/node/.openclaw/agents/banana/agent/auth-profiles.json \
  openclaw-test \
  node /app/openclaw.mjs secrets audit --check 2>&1
```

正常時の出力例：
```
Secrets audit: ok. plaintext=0, unresolved=0, shadowed=0, legacy=0.
```

エラーがある場合は `[REF_UNRESOLVED]` や `[PLAINTEXT]` などが表示される。

### 4. `op` が特定のシークレットを取得できるか確認

```bash
docker run --platform linux/amd64 --rm \
  --entrypoint "" \
  -e HOME=/home/node \
  -e OP_SERVICE_ACCOUNT_TOKEN="<トークン>" \
  openclaw-test \
  op read "op://banana/anthropic/password" | cut -c1-10
# → sk-ant-api（先頭10文字のみ表示）
```

### 注意事項

- `secrets audit` は通るが `secrets audit --check` は exit code 2 で失敗することがある（タイムアウト起因）
- `op` exec provider はデフォルト 5 秒タイムアウト。ローカルの Docker（QEMU エミュレーション）は遅いため Railway 本番より失敗しやすい
- `auth-profiles.json` の `keyRef` は `secrets audit` の対象外（openclaw.json の SecretRef のみ評価される）
- `gateway.auth.token` は JSON スキーマが `string` 型のみ（SecretRef オブジェクト不可）。Railway の `OPENCLAW_GATEWAY_TOKEN` 環境変数で代替
