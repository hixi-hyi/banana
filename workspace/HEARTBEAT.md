# HEARTBEAT.md

## Git Auto-Push

ワークスペース（`workspace/`）に変更があれば、commit して push する。

手順:
1. `git -C /home/node/.openclaw/repo status --porcelain workspace/` で変更確認
2. 変更があれば以下を実行:
   ```
   git -C /home/node/.openclaw/repo add workspace/
   git -C /home/node/.openclaw/repo commit -m "chore: auto-sync [heartbeat]"
   git -C /home/node/.openclaw/repo push
   ```
3. 変更がなければスキップ

⚠️ `workspace/` 以外のファイル（Dockerfile, runtime/ 等）は commit しない。
