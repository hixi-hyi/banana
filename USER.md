# USER.md - About Your Human

_Learn about the person you're helping. Update this as you go._

- **Name:** hixi
- **What to call them:**
- **Pronouns:** _(optional)_
- **Timezone:**
- **Notes:**
  - **同じことを２度言わせない** — ２回注意されたことは即ルール保存。忘れたは通じない
  - Slack 返信ルール：
    - **常にスレッドで返す**（チャンネルメッセージもスレッド返信）
    - **メンションなしでも返信する**（#banana チャンネルでは常に反応する）
  - Slack 送信ルール（二重投稿・NO_REPLY漏れ防止）：
    - **常に `message` ツール（threadId付き）でスレッド返信** → 応答本文は完全に NO_REPLY
    - `message` ツールと `[[reply_to_current]]` を同時に使わない（二重投稿になる）
    - `message` ツールで送信した場合、応答は完全に NO_REPLY（本文なし）
  - エラーメッセージが出たら：
    - **自分で確認する**（read/exec で実際の状態検証）
    - 同じ操作を繰り返さない（最大2回まで）
    - 検証結果を報告する（failed で終わらない）
  - Slack 通知ルール：
    - 定期通知系（朝レポート、タスク管理など）→ `C0AHUGG1C82` チャンネルに送る
    - **Morning Report**: 毎日10:00 UTC に自動実行 (OpenClaw cron scheduler via `cron-jobs.json`)

## Context

_(What do they care about? What projects are they working on? What annoys them? What makes them laugh? Build this over time.)_

---

The more you know, the better you can help. But remember — you're learning about a person, not building a dossier. Respect the difference.
