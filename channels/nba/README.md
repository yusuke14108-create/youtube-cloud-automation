# 日本人選手中心 NBA動画 自動生成チャンネル

日本人選手に関するNBAニュースを収集し、毎日、長尺1〜2本とShorts合計2〜3本を生成してYouTubeへ投稿するパイプラインです。

## 生成フロー

1. `NBA_PLAYERS` の選手名ごとに日本語ニュースRSSを収集
2. AIが、根拠を確認でき、試合映像なしでも解説できるテーマを最大2件選定
3. 記事本文と一次情報を確認し、長尺台本とShorts台本を生成
4. VOICEVOXで音声と実測同期字幕を生成
5. 独自の比較・時系列図解と、ライセンス確認済み静止画だけでFFmpegレンダリング
6. `ENABLE_UPLOAD=true` の場合だけYouTubeへ非公開投稿
7. `ENABLE_AUTO_PUBLISH=true` の場合だけ、指定時刻以降に公開

初期値ではアップロード・公開とも無効です。

## 本番前チェックと安全な検証

```bash
# 秘密値を表示せず、AI API設定・OAuth・VOICEVOX・FFmpeg字幕機能・書込先を検査
.venv/bin/python -m generator.cli preflight

# AI、ネットワーク、VOICEVOX、YouTubeを使わず、収集モックからMP4まで検証
.venv/bin/python -m generator.cli mock-pipeline

# 実ニュースで動画まで生成するが、YouTubeには送信しない
.venv/bin/python -m generator.cli run --dry-run

# 内容確認後、公開せず非公開アップロードだけを明示的に許可
.venv/bin/python -m generator.cli run --upload-private
```

途中状態は `data/runs/YYYYMMDD.json` に保存されます。再実行時は存在する台本、音声、字幕、動画を検査して続きから再開します。非公開アップロード途中で失敗した場合も、`data/upload_progress/` の動画IDを使い、完了済みの長尺・Shortsを再アップロードしません。

## 権利ポリシー

- NBA中継、試合映像、放送画面、SNS転載動画は取得・使用しません。
- 外部素材はWikimedia CommonsのCC0、Public Domain、CC BY、CC BY-SAの静止画だけを採用します。
- NC（非営利限定）とND（改変禁止）は除外します。
- 採用素材は `data/assets/<run_id>/licenses.json` に作者、ライセンス、参照ページを保存し、YouTube概要欄にも記載します。
- 素材が見つからない場合は、写真で代用せず独自生成した抽象背景と図解を使います。
- ニュース候補のRSS本文は事実確認の根拠にせず、リンク先と一次情報を確認するよう台本生成AIへ要求します。

## Dockerで起動

```bash
cp .env.example .env
# .env のAI_API_KEY、選手名、本数、公開時刻を設定
docker compose up -d --build
docker compose logs -f app
```

`credentials/client_secret.json` を配置し、YouTube再認証が必要な場合は次の1コマンドだけを実行します。

```bash
.venv/bin/python -m generator.youtube_auth --reauthorize
```

生成された `credentials/token.json` をVMへ安全に転送してください。以後のトークン更新はコンテナ内で自動実行されます。認証ファイルと `.env` はGitへコミットしないでください。

## 主な環境変数

- `NBA_PLAYERS`: 追跡する日本人選手名。カンマ区切り
- `DAILY_LONG_VIDEOS`: 1〜2
- `DAILY_SHORTS`: 2〜3（全長尺の合計）
- `TZ`: `Asia/Tokyo`を指定
- `GENERATE_HOUR`, `GENERATE_MINUTE`: 生成開始時刻
- `PUBLISH_HOUR`, `PUBLISH_MINUTE`: 公開開始時刻
- `ENABLE_UPLOAD`: `true`で非公開アップロードを許可
- `ENABLE_AUTO_PUBLISH`: `true`で公開変更を許可。検証中は必ず`false`
- `AI_API_URL`, `AI_API_KEY`, `AI_MODEL`: JSON Schema対応の生成AI API
- `VOICEVOX_URL`: Composeでは自動的にVOICEVOXコンテナへ接続

毎日15分間隔で再実行します。指定時刻を過ぎた後にVMが再起動しても、その日の未完了工程を追いつき実行します。生成物と処理状態はホスト側の `data/` に永続化されます。

旧 `com.yishitoya.fintechnewsch.catchup` launchdジョブは使用しません。ローカルlaunchd運用では `launchd/com.yishitoya.nbachannel.catchup.plist` だけを使い、Docker運用と同時に起動しないでください。
