# YouTube Cloud Automation

医療・MLB・NBAの3チャンネルをGitHub Actions上で生成し、YouTubeへ非公開アップロードする公開用モノレポです。認証情報、APIキー、生成動画、状態データはGitへ追加しません。

## 安全設計

- OAuthのチャンネルIDが固定値と一致しなければ生成前に停止
- 動画は必ず `private` でアップロード
- FFprobe品質検査に合格した場合のみ、Repository Variable `ENABLE_AUTO_PUBLISH=true` のとき公開
- 同一チャンネルの同時実行を `concurrency` で禁止
- Gemini無料枠の上限・API障害時は失敗終了し、課金APIへフォールバックしない
- Secretsの値をログへ出力しない

## 必要なGitHub Secrets

- `GEMINI_API_KEY`
- `MEDICAL_YT_CLIENT_SECRET_JSON`, `MEDICAL_YT_TOKEN_JSON`
- `MLB_YT_CLIENT_SECRET_JSON`, `MLB_YT_TOKEN_JSON`
- `NBA_YT_CLIENT_SECRET_JSON`, `NBA_YT_TOKEN_JSON`

最初は `ENABLE_AUTO_PUBLISH` を未設定または `false` にします。非公開動画を数日確認後、問題がなければ `true` に変更します。

## スケジュール（Asia/Tokyo）

- 医療: 03:17
- MLB: 04:17
- NBA: 05:17

GitHub側の混雑により開始が遅れる場合があります。各ワークフローは手動実行にも対応します。
