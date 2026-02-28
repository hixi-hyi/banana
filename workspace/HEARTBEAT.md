# HEARTBEAT.md

## Git Auto-Push

ワークスペースに変更があれば、commit して push する。

手順:
1. `git -C /home/node/.openclaw/repo status --porcelain` で変更確認
2. 変更があれば `git -C /home/node/.openclaw/repo add -A && git -C /home/node/.openclaw/repo commit -m "chore: auto-sync [heartbeat]" && git -C /home/node/.openclaw/repo push`
3. 変更がなければスキップ

⚠️ git 操作は必ず `/home/node/.openclaw/repo`（リポジトリルート）で行う。
ワークスペースは `repo/workspace/` サブディレクトリにあるため、`workspace/` から git を実行すると正しいパスで commit される。
