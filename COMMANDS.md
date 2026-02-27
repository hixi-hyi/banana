# Banana Agent - コマンド一覧

## シェルエイリアス

以下のコマンドがどこからでも使えます（新しいターミナルで自動適用）。

### 基本コマンド

```bash
# Banana workspace に移動
openclaw-banana-workspace

# ゲートウェイを起動
openclaw-banana-up

# ゲートウェイを停止
openclaw-banana-down

# ゲートウェイを再起動
openclaw-banana-restart

# ログを表示
openclaw-banana-logs

# CLI コマンドを実行
openclaw-banana-cli agents list
openclaw-banana-cli config get agents.list
```

### 使用例

```bash
# 1. workspace に移動して編集
openclaw-banana-workspace
vim SOUL.md

# 2. 変更をコミット
git add .
git commit -m "Update SOUL.md"

# 3. ゲートウェイを再起動
openclaw-banana-restart

# 4. ログで確認
openclaw-banana-logs
```

## 直接コマンド（エイリアスなし）

```bash
# workspace 指定で起動
OPENCLAW_WORKSPACE_DIR=~/Workspaces/github.com/hixi-hyi/banana \
  docker compose -f ~/Workspaces/github.com/openclaw/openclaw/docker-compose.yml \
  up -d openclaw-gateway

# CLI 実行
docker compose -f ~/Workspaces/github.com/openclaw/openclaw/docker-compose.yml \
  run --rm openclaw-cli agents list
```

## 便利なワンライナー

```bash
# workspace 内のファイル一覧
openclaw-banana-workspace && ls -la

# 最近のコミットログ
openclaw-banana-workspace && git log --oneline -5

# ゲートウェイのステータス確認
docker compose -f $OPENCLAW_COMPOSE_FILE ps

# banana エージェントの設定を表示
openclaw-banana-cli config get agents.list | grep -A 10 banana
```

## エイリアスの再読み込み

エイリアスを追加・変更した後は：

```bash
source ~/.zshrc
```

---

🍌 Quick access to Banana workspace!
