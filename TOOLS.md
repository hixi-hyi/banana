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

openclaw の設定（チャンネル設定、モデル設定など）を変更すると `/home/node/.openclaw/openclaw.json`（volume）が更新される。
変更をリポジトリに反映するには `config-sync-container` を実行すること。

### 仕組み

```
openclaw が設定変更 → /home/node/.openclaw/openclaw.json 更新（実値）
     ↓
config-sync-container を実行
     ↓
シークレットフィールドを {{ op://... }} 参照に戻して
workspace/openclaw.json に書き出し → commit → push
```

### 手動で sync する場合

```bash
node /home/node/.openclaw/workspace/runtime/scripts/config-sync-container
```

（op:// 参照に戻す → write → commit → push まで一括実行）

### なぜ必要か

- `/home/node/.openclaw/openclaw.json` は Railway volume にあり、コンテナ再構築時に `op inject` で `workspace/openclaw.json`（git）から再生成される
- 同期しないと設定変更が次回デプロイ時に失われる

---

## リポジトリ構成（重要）

```
/home/node/.openclaw/workspace/   ← git リポジトリルート = エージェントのワークスペース
├── AGENTS.md, SOUL.md, IDENTITY.md ...  ← エージェントファイル（ここが "home"）
├── memory/, skills/
├── openclaw.json                 ← openclaw 設定（op://参照でシークレット管理）
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
- **認証**: 起動時に `op read "op://banana/github/token"` で取得し `/root/.git-credentials` に設定済み
  - push コマンド: `git -C /home/node/.openclaw/workspace push`
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

---

## 借金管理スプレッドシート

hixi の借金（120万円）の利用記録を管理するスプレッドシート。

**スプレッドシート:** https://docs.google.com/spreadsheets/d/1KVGjNshPbFWPXbDQTRwieQHNwEAFnjAqO-AxdPjan9w/edit

### トリガーパターン

以下のようなメッセージを受け取ったら、金額と用途を解釈してスクリプトを実行する:

- 「〇〇〇〇円利用」
- 「〇〇に〇〇〇〇円使った」
- 「〇〇〇〇円 〇〇で利用」
- 「借金に〇〇〇〇円追加して」

自然言語から **金額**（円）と **用途** を抽出して実行すること。

### 実行コマンド

```bash
python3 /home/node/.openclaw/workspace/scripts/loan-tracker.py \
  --purpose "用途" \
  --amount 金額（整数）\
  [--date YYYY-MM-DD]  # 省略時は今日のJST
```

### 実行例

```bash
python3 /home/node/.openclaw/workspace/scripts/loan-tracker.py --purpose "食費" --amount 5000
python3 /home/node/.openclaw/workspace/scripts/loan-tracker.py --purpose "交通費" --amount 3000 --date 2026-03-01
```

### 実行後

スクリプトの出力（記録した内容・残高の変化）をそのままユーザーに返す。
