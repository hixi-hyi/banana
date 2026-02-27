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

## Git 設定

- リモート: `https://github.com/hixi-hyi/banana`
- user.name: `banana` / user.email: `banana@codify.jp`
- **認証**: `GITHUB_TOKEN` 環境変数で渡されている
  - push コマンド: `git -c credential.helper="" push "https://$GITHUB_TOKEN@github.com/hixi-hyi/banana" main`
  - ⚠️ `git remote set-url` でトークンを埋め込むと TTY なし環境で失敗するので上記方法を使う

## Environment Notes

### Logs

- ログファイル: `/tmp/openclaw/openclaw-YYYY-MM-DD.log`
- 読み方: `cat /tmp/openclaw/openclaw-$(date +%Y-%m-%d).log | python3 -c "import sys,json; [print(l.get('1','')) for line in sys.stdin if (l:=json.loads(line.strip()))]"`

### Gateway (Docker環境)

- systemd は使えない（Docker内のため）
- **安全な再起動:** `kill -USR1 $(pgrep openclaw-gateway)` — プロセスを落とさずに設定を再読み込み
- ⚠️ `kill -HUP` や `kill` は使わない（セッションが切れる）
