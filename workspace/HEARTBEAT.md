# HEARTBEAT.md

## Git Auto-Push

ワークスペースに変更があれば、commit して push する。

手順:
1. `git -C /home/node/.openclaw/workspace status --porcelain` で変更確認
2. 変更があれば `git add -A && git commit -m "chore: auto-sync [heartbeat]" && git push`
3. 変更がなければスキップ
