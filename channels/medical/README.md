# 医療ニュースチャンネル

PMDA・厚生労働省・JIHS・PubMedを収集し、台本、VOICEVOX音声、動画を生成してYouTubeへ非公開アップロードするパイプラインです。

## 安全な初期設定

```bash
cp .env.example .env
```

`.env`へAPIキーを設定します。キーはコードやGitへ保存しません。

- OpenAI: `MEDICAL_NEWS_LLM_PROVIDER=openai` と `OPENAI_API_KEY`
- Anthropic: `MEDICAL_NEWS_LLM_PROVIDER=anthropic` と `ANTHROPIC_API_KEY`
- 従来CLI: `MEDICAL_NEWS_LLM_PROVIDER=claude-cli`

アップロードの既定は非公開です。`YOUTUBE_UPLOAD_PRIVACY`に指定できるのは`private`または`unlisted`だけです。自動公開も既定で無効です。非公開動画を確認した後に限り、`ENABLE_AUTO_PUBLISH=1`を設定してください。

## ローカル実行

VOICEVOX Engineを起動してから実行します。

```bash
python -m pip install -r requirements.txt
python -m generator.run_daily
```

FFmpegの既定タイムアウトは1800秒です。長い動画では`FFMPEG_TIMEOUT=3600`などへ変更できます。音声、モーションクリップ、合成動画、最終動画は実体を検証し、正常なものを再利用します。アップロードも`data/uploads/*.partial.json`単位で再開します。

ネットワークやアップロードを行わず、完成動画だけ検査できます。

```bash
python -m generator.upload_youtube --validate-only data/scripts/YYYYMMDD_HHMMSS.json
```

## YouTube OAuth診断・再認証

診断は読み取り専用で、トークンを書き換えません。

```bash
python -m generator.check_youtube_auth
```

期限切れ、`invalid_grant`、refresh token不在と表示された場合:

1. `credentials/client_secret.json`がGoogle Cloud Consoleで発行したデスクトップアプリ用か確認します。
2. 既存の`credentials/token.json`をバックアップします。削除は必須ではありません。
3. `python -m generator.youtube_auth --reauthorize`を実行し、ブラウザで対象チャンネルのアカウントを選びます。既存トークンは新規同意が成功するまで保持され、成功時のみ権限600のファイルへ原子的に置換されます。
4. 成功後、再度`python -m generator.check_youtube_auth`を実行します。
5. Docker運用では、ホストで再認証してから`credentials`をコンテナへ読み取り可能にマウントします。

## Linux / Docker

手動で非公開アップロードまで実行:

```bash
docker compose --profile manual run --rm pipeline
```

常駐スケジューラーを起動:

```bash
docker compose --profile scheduled up -d voicevox scheduler
```

`data`と`credentials`はホストへ永続化されます。Dockerのcronは03:00に生成・非公開アップロード、06:00に公開工程を呼びますが、`ENABLE_AUTO_PUBLISH=0`の間は公開しません。確認後に明示的に有効化してください。

VOICEVOXを別ホストで動かす場合は`VOICEVOX_URL`を変更します。LinuxでDockerを使わず自動起動する場合は`VOICEVOX_START_COMMAND`を指定できます。

## 障害復旧

同じ日の再実行は、選定済み台本、正常な音声、動画、アップロード済みIDを順に再利用します。壊れたファイルだけが再生成されます。ロックの失効時間は`PIPELINE_STALE_LOCK_SECONDS`で設定でき、既定は6時間です。

APIキー、OAuthファイル、`data`ディレクトリは削除・上書きしないでください。
