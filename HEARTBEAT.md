# HEARTBEAT.md

## Git Auto-Push

ワークスペース（`/home/node/.openclaw/workspace/`）のエージェントファイルに変更があれば、commit して push する。

手順:
1. 変更確認:
   ```
   git -C /home/node/.openclaw/workspace status --porcelain
   ```
2. 変更があれば以下を実行（**エージェントファイルのみ** add すること）:
   ```
   git -C /home/node/.openclaw/workspace add AGENTS.md SOUL.md IDENTITY.md MEMORY.md HEARTBEAT.md TOOLS.md USER.md BOOTSTRAP.md openclaw-config-base.json memory/ skills/ 2>/dev/null || true
   git -C /home/node/.openclaw/workspace commit -m "chore: auto-sync [heartbeat]"
   git -C /home/node/.openclaw/workspace push
   ```
3. 変更がなければスキップ

⚠️ **絶対に `git add -A` や `git add .` を使わない。**  
⚠️ `runtime/`, `Dockerfile`, `railway.toml` など infra ファイルは commit しない。
⚠️ `git add` に列挙したファイル・ディレクトリのみ commit 対象。
