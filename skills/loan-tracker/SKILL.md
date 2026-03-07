---
name: loan-tracker
description: hixi の立替金（支払い代行）をスプレッドシートに自動記録する
user-invocable: false
---

## 立替金トラッカー

hixi の立替金（支払い代行）の記録を管理するスプレッドシート。

スプレッドシート: https://docs.google.com/spreadsheets/d/1KVGjNshPbFWPXbDQTRwieQHNwEAFnjAqO-AxdPjan9w/edit

### トリガー：メッセージに「立替」という単語が含まれていたら即実行

確認不要。聞き返さずにそのまま実行すること。

メッセージ例（すべてこのパターンで動く）:
- `立替 今井湯 1000円`
- `立替 食費 5000`
- `立替 ACMの年会費 28434円`

### 金額・用途の抽出ルール

- 用途: 金額以外の名詞部分（「今井湯」「食費」「ACMの年会費」など）
- 金額: 数字部分（円・¥は除去して整数に変換。「1000円」→ 1000）
- 金額が万円表記の場合: 「1万円」→ 10000、「1.5万」→ 15000
- 日付の指定がなければ今日の JST を使う

### 実行コマンド

```
python3 /home/node/.openclaw/workspace/scripts/loan-tracker.py --purpose "用途" --amount 金額（整数）
```

### 実行後

スクリプトの出力をそのままユーザーに返す。エラーがあればエラー内容を伝える。
