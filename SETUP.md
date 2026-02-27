# Banana Agent - セットアップ完了 🍌

## 作成日時
2026-02-27

## 構成

### Workspace
- **パス**: `~/Workspaces/github.com/hixi-hyi/banana`
- **Git管理**: 有効（初期コミット済み）
- **Agent ID**: `banana`

### ファイル構造

```
~/Workspaces/github.com/hixi-hyi/banana/
├── .git/               # Git リポジトリ
├── .gitignore          # Git除外設定
├── SOUL.md             # Bananaの性格・価値観
├── AGENTS.md           # ワークスペースルール
├── USER.md             # ユーザー情報（要編集）
├── MEMORY.md           # 長期記憶
├── HEARTBEAT.md        # 定期チェックタスク
├── README.md           # ドキュメント
├── SETUP.md            # このファイル
├── memory/             # 日次ログディレクトリ
├── skills/             # カスタムスキル
├── projects/           # 作業プロジェクト
└── config/             # 設定ファイル
```

### OpenClaw設定

**設定ファイル**: `~/.openclaw/openclaw.json`

```json
{
  "agents": {
    "list": [
      {
        "id": "banana",
        "name": "Banana",
        "workspace": "~/Workspaces/github.com/hixi-hyi/banana",
        "agentDir": "~/.openclaw/agents/banana/agent",
        "identity": {
          "name": "Banana",
          "emoji": "🍌"
        }
      }
    ]
  }
}
```

**Agent Directory**: `~/.openclaw/agents/banana/agent`

## 使い方

### 1. USER.md を編集
```bash
vim ~/Workspaces/github.com/hixi-hyi/banana/USER.md
```

自分の情報、好み、プロジェクト情報を追記してください。

### 2. SOUL.md をカスタマイズ（オプション）
```bash
vim ~/Workspaces/github.com/hixi-hyi/banana/SOUL.md
```

Bananaの性格や価値観をあなた好みに調整できます。

### 3. Git でバージョン管理
```bash
cd ~/Workspaces/github.com/hixi-hyi/banana

# 変更をコミット
git add .
git commit -m "Update USER.md with my information"

# リモートリポジトリを追加（GitHub等）
git remote add origin https://github.com/hixi-hyi/banana.git
git push -u origin main
```

### 4. ゲートウェイの再起動
設定を変更した後は、ゲートウェイを再起動してください：

```bash
cd ~/Workspaces/github.com/openclaw/openclaw
docker compose restart openclaw-gateway

# または
openclaw-restart  # エイリアスを使用
```

### 5. エージェントの確認
```bash
docker compose run --rm openclaw-cli agents list
```

## 次のステップ

1. **チャンネル設定**: WhatsApp, Telegram, Discord などを設定
2. **AIプロバイダー設定**: Claude, OpenAI などの API キーを設定
3. **バインディング設定**: どのチャンネルからBananaを呼び出すか設定

詳細: https://docs.openclaw.ai/concepts/multi-agent

## トラブルシューティング

### エージェントが認識されない
```bash
# 設定を確認
docker compose run --rm openclaw-cli config get agents.list

# 設定が正しいか検証
docker compose run --rm openclaw-cli doctor
```

### Workspace が見つからない
パスが正しいか確認：
```bash
ls -la ~/Workspaces/github.com/hixi-hyi/banana
```

### ゲートウェイのログを確認
```bash
docker compose logs -f openclaw-gateway
```

---

🍌 Stay flexible, stay positive!
