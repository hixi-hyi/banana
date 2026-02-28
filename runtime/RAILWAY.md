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
| `ANTHROPIC_API_KEY` | Claude API 認証 |
| `SLACK_BOT_TOKEN` | Slack Bot トークン |
| `SLACK_APP_TOKEN` | Slack App トークン（Socket Mode） |
| `OPENCLAW_GATEWAY_TOKEN` | Web UI 認証トークン |
| `GITHUB_TOKEN` | ワークスペース git clone/push 用 |
| `OPENCLAW_STATE_DIR` | `/home/node/.openclaw` |
| `SETUP_PASSWORD` | `/setup` ページのパスワード |

## 接続・操作コマンド

```bash
# リポジトリのディレクトリで実行すること（cd ~/Workspaces/github.com/hixi-hyi/banana）

# ログ確認（直近 50 行）
railway logs --tail 50

# SSH でコンテナに入る（インタラクティブ）
railway ssh

# SSH でコマンドを実行
railway ssh -- node -e "console.log('hello')"
railway ssh -- cat /home/node/.openclaw/openclaw.json

# デプロイ（ローカルファイルを Railway にアップロード）
railway up --detach

# デプロイ状況確認
railway deployment list
```

## リポジトリ構成

```
banana/
├── railway.toml          # Railway CLI 用（root 必須）
├── workspace/            # エージェントの人格・記憶（openclaw ワークスペース）
│   ├── AGENTS.md
│   ├── SOUL.md / IDENTITY.md / MEMORY.md / USER.md
│   ├── HEARTBEAT.md / TOOLS.md / BOOTSTRAP.md
│   ├── openclaw-config-base.json
│   ├── memory/
│   └── skills/
└── runtime/              # 実行環境（このファイルもここ）
    ├── Dockerfile
    ├── startup.sh
    ├── docker-compose.yml
    └── RAILWAY.md
```

## 同期されているファイル（git → Railway）

起動時に `runtime/startup.sh` がリポジトリ全体を `/home/node/.openclaw/repo/` に clone/pull し、Railway に反映される：

| パス | 内容 |
|------|------|
| `workspace/AGENTS.md` | ワークスペースルール |
| `workspace/SOUL.md` | エージェントの核心 |
| `workspace/IDENTITY.md` | アイデンティティ |
| `workspace/MEMORY.md` | 長期記憶 |
| `workspace/USER.md` | ユーザー情報 |
| `workspace/HEARTBEAT.md` | ハートビート設定 |
| `workspace/TOOLS.md` | ツール設定 |
| `workspace/openclaw-config-base.json` | openclaw 設定ベース（秘密情報なし） |
| `workspace/memory/` | 日次ログ |
| `runtime/startup.sh` | 起動スクリプト |

**秘密情報（git には入れない）:** API キー、Slack トークン、Gateway トークン → Railway の環境変数で管理

## startup.sh の処理フロー（毎回起動時）

1. リポジトリ全体を `/home/node/.openclaw/repo/` に clone/pull
2. エージェントワークスペース = `repo/workspace/`（ここに AGENTS.md 等が入る）
3. git 認証情報を設定（GITHUB_TOKEN → `/root/.git-credentials`）
4. `ANTHROPIC_API_KEY` を `agents/banana/agent/auth-profiles.json` に書き込む
5. `repo/workspace/openclaw-config-base.json` を読んで既存の `openclaw.json` と deep merge
6. Railway 固有の設定を上書き（bind=lan, trustedProxies, allowInsecureAuth 等）
7. Slack トークンを env var から注入
8. 無効なフィールド（dmPolicy 等）を削除
9. `openclaw gateway run` で起動

## 何か問題が起きたときの対処

### gateway が起動しない / 応答しない

1. まずログを確認：`railway logs --tail 50`
2. エラーメッセージを見て原因を特定

**よくある原因と対処:**

| エラー | 原因 | 対処 |
|--------|------|------|
| `Invalid config: channels.slack.dmPolicy` | エージェントが openclaw.json に無効な値を書いた | `railway up --detach` で再デプロイ（startup.sh が修正する） |
| `non-loopback Control UI requires ...allowedOrigins` | gateway の設定不足 | startup.sh に `dangerouslyAllowHostHeaderOriginFallback=true` が入っているので再デプロイで直る |
| `EACCES: permission denied` | ボリュームのパーミッション問題 | Dockerfile が `USER root` になっているか確認 |
| `pairing required` | ブラウザが未承認デバイス | `railway ssh` → `openclaw devices list` → `openclaw devices approve <id>` |

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

再デプロイすれば `runtime/startup.sh` が `workspace/openclaw-config-base.json`（git 上のベース設定）を読み直して再構築する：

```bash
railway up --detach
```

### ローカルの設定変更を Railway に反映したい

1. `~/.openclaw/openclaw.json` の秘密情報を除いた版を `workspace/openclaw-config-base.json` に更新
2. git commit & push
3. Railway を再デプロイ（または次回再起動時に自動反映）

```bash
# ローカル設定を sanitize してリポジトリに保存するコマンド（リポジトリルートで実行）
cat ~/.openclaw/openclaw.json | python3 -c "
import json, sys
d = json.load(sys.stdin)
def sanitize(obj):
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            if k in {'botToken', 'appToken', 'key', 'token'} and isinstance(v, str) and len(v) > 10:
                result[k] = '__FROM_ENV__'
            else:
                result[k] = sanitize(v)
        return result
    elif isinstance(obj, list):
        return [sanitize(i) for i in obj]
    return obj
print(json.dumps(sanitize(d), indent=2))
" > workspace/openclaw-config-base.json
```

### ローカルで docker-compose を使う

```bash
# リポジトリルートから実行
docker compose -f runtime/docker-compose.yml up
```
