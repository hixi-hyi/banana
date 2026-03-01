# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

Add whatever helps you do your job. This is your cheat sheet.

## openclaw 設定の変更と同期（重要）

openclaw の設定（チャンネル設定、モデル設定など）を変更した場合は、必ず git に同期すること。

### 設定変更のワークフロー

1. openclaw のコマンドや設定変更を行う（openclaw.json が更新される）
2. 以下のコマンドで git に同期する：

```bash
node /home/node/.openclaw/workspace/runtime/scripts/config-sync-container
```

このスクリプトが行うこと：
- `/home/node/.openclaw/openclaw.json` を読み込む
- token 等の秘密情報を `__FROM_ENV__` に置換（git に秘密情報を入れない）
- Railway 固有の設定（gateway.bind 等）を base 値に戻す
- `openclaw-config-base.json` に書き出して commit & push

### なぜ必要か

- `openclaw.json` は Railway volume にあり、コンテナが再構築されると内容が `openclaw-config-base.json`（git）で上書きされる
- 同期しないと設定変更が次回デプロイ時に失われる

---

## リポジトリ構成（重要）

```
/home/node/.openclaw/workspace/   ← git リポジトリルート = エージェントのワークスペース
├── AGENTS.md, SOUL.md, IDENTITY.md ...  ← エージェントファイル（ここが "home"）
├── memory/, skills/
├── openclaw-config-base.json
└── runtime/                      ← デプロイ設定（Dockerfile等。git push しない）
```

**git 操作は `/home/node/.openclaw/workspace/` で行う（= リポジトリルート）。**

ファイルを書いて commit する場合:
```
git -C /home/node/.openclaw/workspace add AGENTS.md SOUL.md MEMORY.md ...
git -C /home/node/.openclaw/workspace commit -m "..."
git -C /home/node/.openclaw/workspace push
```

⚠️ **`git add -A` や `git add .` は使わない** — runtime/ 等の infra ファイルが混入する。

## Git 設定

- リモート: `https://github.com/hixi-hyi/banana`
- user.name: `Banana (Railway)` / user.email: `banana-railway@openclaw`
- **認証**: `GITHUB_TOKEN` 環境変数で渡されている
  - push コマンド: `git -C /home/node/.openclaw/workspace push`（credentials は `/root/.git-credentials` に設定済み）
  - ⚠️ `git remote set-url` でトークンを埋め込むと TTY なし環境で失敗するので上記方法を使う

## Environment Notes

### Logs

- ログファイル: `/tmp/openclaw/openclaw-YYYY-MM-DD.log`
- 読み方: `cat /tmp/openclaw/openclaw-$(date +%Y-%m-%d).log | python3 -c "import sys,json; [print(l.get('1','')) for line in sys.stdin if (l:=json.loads(line.strip()))]"`

### Gateway (Railway/Docker環境)

- systemd は使えない（Docker内のため）
- **安全な再起動:** `kill -USR1 $(pgrep openclaw-gateway)` — プロセスを落とさずに設定を再読み込み
- ⚠️ `kill -HUP` や `kill` は使わない（セッションが切れる）

### Railway 接続

- SSH: `railway ssh` (プロジェクト選択後)
- ログ: `railway logs`
- 詳細は `runtime/RAILWAY.md` 参照
