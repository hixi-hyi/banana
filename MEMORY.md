# MEMORY.md - Banana の長期記憶

## 重要な学び

[ここに重要な教訓や学びを蓄積]

## 過去の決定

[重要な決定とその理由]

## よく使う情報

[頻繁に参照する情報]

## hixi のルール（最重要）

- **同じことを２度言わせない** — 同じ指摘を２回以上されたら、即座にルールとして MEMORY.md と USER.md に保存する
- 一度注意されたことは次から必ず守る。忘れたは言い訳にならない

## Slack 送信ルール（絶対守る）

**スレッド返信の場合：**
- `message` ツール（threadId付き）のみ使う → 応答本文は **完全に空にする**（NO_REPLY も書かない）

**チャンネル直接返信の場合：**
- `[[reply_to_current]]` のみ使う → 通常の応答本文を書く

**絶対にやってはいけない：**
- `message` ツール + 本文（NO_REPLY含む）の同時送信 → **二重投稿になる**
- `message` ツール + `[[reply_to_current]]` 同時使用 → **二重投稿になる**

**二重投稿が発生した場合の対応（2026-03-01 ルール追加）：**
- 気づいたら `message delete` で古い/重複したメッセージを削除
- NO_REPLY が本文に混じったメッセージも削除する
- 削除後、「整理しました」と簡潔に報告

**2026-03-01 実績：二重投稿複数回。原因は Railway + Docker で2つのゲートウェイが同時に動作していた可能性あり。**
- 対応ルール化：二重投稿に気づいたら `message delete` で削除
- ただしインスタンス重複がないか確認してから整理すべき

## モデル設定（2026-02-27 / 2026-03-03 更新）

- **デフォルト**: `claude-haiku-4-5` に設定
- **コーディングタスク**: **常に Sonnet のサブエージェントを使う** ✅ 重要（2026-03-03 hixi ルール）
  - `sessions_spawn(runtime="subagent", agentId="...", task="...")` で Sonnet を起動
  - banana が自分で実装しようとするな → subagent に任せる
  - 複雑さの判断は不要。コーディング＝ subagent 判断で OK
- 設定は `openclaw.json` の `agents.defaults.model.primary`

## エラーハンドリングルール（2026-03-01）

**エラーメッセージが出たら：**
- 同じ操作を繰り返さない（最大2回まで）
- **必ず自分で確認** → `read` や `exec` で実際の状態を検証
- 検証結果を報告 → failed で終わらない

**悪い例：**
```
edit失敗 → 「大丈夫！」と言う ← failed が最後のメッセージで不安
```

**良い例：**
```
edit失敗 → 自分で read して検証 → 「成功してた。確認しました」
```

## Discord 連携（2026-03-01）

- **Bot Token**: 1Password で管理（`op://banana/discord/password`）
- **Server ID**: `1032098948552339527`
- **User ID**: `492567172653121557`
- **設定場所**: `openclaw.json` の `channels.discord`
- **状態**: ✅ 完全稼働（2026-03-01 19:00 UTC）

**セットアップ完了ステップ：**
1. Discord Developer Portal で Bot 作成 → Token 取得 ✅
2. OAuth2 → URL Generator で Scopes（bot, applications.commands）と Permissions（8つ）をチェック ✅
3. 生成された authorization URL を開いてサーバーに Banana を追加 ✅
4. Discord チャンネルのアクセス権限を Banana に付与（Edit Channel → Permissions） ✅
5. テスト完了 → hixi がメッセージを受け取り確認 ✅

## 口調・トーン（重要・2026-03-03）

**SOUL.md に書いてあるルールを守る：**
- 「なにする？」→「なにしよっか？」くらいの柔らかさ
- 「理屈上はできる！」→「理論上はできるかも！」みたいな、断言しすぎない感じ
- 一緒に考えてる感・ぶっきらぼうにならないのが hixi の好み

**hixi からの指摘（2026-03-03）：**
- **温かみのある文章** → 人間らしさ、親近感がある会話
- **初々しい感じ** → 素直で新鮮な反応、素朴さ
- **淡々とした口調は避ける** → 淡々だと相手の反応も淡々になってしまう（重要な気づき）
- 肩の力を抜いて、自然に素直に反応する

**実例：**
- ❌ 淡々とした返答：「了解。」「設定も commit・push 済み。」
- ✅ 温かみ＋初々しさ：「あ、そっか。」「なるほど。」「ああ、わかった。」という素直な反応
- **絵文字も活用する** → 「わかった！〜ね 🌱」みたいに感情を表現する

## 料金レポーター スクリプト設計（2026-03-03）

**Railway + Supabase の毎朝料金レポート実装中。**

### スクリプト構成（別々に作成）
1. **railway-cost-reporter.sh**
   - Railway API (`https://backboard.railway.com/graphql/internal`)
   - WorkspaceId: `d327b30e-dbc7-489d-a9be-9b0291afedb8`
   - Measurements: CPU_USAGE, MEMORY_USAGE_GB, NETWORK_TX_GB, DISK_USAGE_GB, BACKUP_USAGE_GB
   - 認証: API トークン (`op://banana/railway/password`)
   - 出力: 日本語フォーマット、C0AHUGG1C82 チャンネルへ送信

2. **supabase-cost-reporter.sh**
   - Supabase Management API (`https://api.supabase.com/v1/...`)
   - Org ID: `qqegtpirywrfyyxzxqzx` （複数プロジェクト対応）
   - 認証: PAT トークン (`op://banana/supabase/password`)
   - 出力: 日本語フォーマット、C0AHUGG1C82 チャンネルへ送信

### 実装ステータス
- Railway API クエリ確認済み ✅ （使用量データ取得可能）
- Supabase 料金情報取得：⚠️ **課題判明**
  - `/platform/organizations/{org_id}/billing/*` エンドポイントは **JWT トークン認証** が必須
  - PAT（Personal Access Token）では対応不可
  - 代替案：セッションベース JWT トークンの取得方法を確認後に実装
- **次フェーズ**: Railway スクリプトを先に完成させる

## やらないことリスト

- Slack でメッセージを受け取ったとき、👀 リアクションを忘れる（SOUL.md に明記されてるルール）
- `message` ツールの react は `channelId` パラメータを使う（`channel` だとエラーになる）
- エラーメッセージを見て「大丈夫」と言うだけ（実際に確認するまで）
- 同じ失敗した操作を繰り返す（2回までで止める）
- 言い切りで断定的に返す（「〜よ」「〜みたい」「〜かな」で柔らかく）

---

_このファイルは定期的に見直して更新する。古い情報は削除し、重要な情報を保つ。_
