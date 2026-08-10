# MLB日本人選手ラボ

日本人メジャーリーガーを中心に、MLB公式データと独自図解で毎日動画を作るYouTube制作パイプラインです。

- 毎日: 長尺1〜2本、Shorts 2〜3本
- 情報源: MLB公式JSONエンドポイント。取得したURLと事実を実行単位で保存
- 映像: 独自図解を標準とし、試合・放送映像や球団ロゴを無断利用しない
- 外部素材: `config/licensed_assets.json` に作者・ライセンス・元ページを登録した素材だけを使用
- 音声・字幕: VOICEVOXとSRT
- 動画: FFmpeg
- 投稿: YouTube Data API。まず非公開でアップロードし、指定時刻に公開

## 日次処理

```text
MLB公式データ収集
  → 日本人選手の事実パケット保存
  → 長尺1〜2本・Shorts 2〜3本の台本生成
  → 独自図解・音声・字幕・MP4生成
  → YouTubeへ非公開投稿
  → 公開時刻に公開
```

前日の試合に設定済み選手が出場していない場合は、MLB公式選手プロフィールとシーズン成績を使った解説へ切り替わります。対象選手は `config/japanese_players.json` で更新できます。

## Docker/Linux VM

1. `credentials/client_secret.json` と認証済みの `credentials/token.json` を配置します。OAuth初回認証はブラウザを使える環境で `python -m generator.youtube_auth` を一度実行してください。
2. `.env.example` を `.env` にコピーし、APIキー、利用可能なAnthropicモデルID、時刻を設定します。
3. 起動します。

```bash
docker compose up -d --build
docker compose logs -f generator
```

VOICEVOXは公式の `voicevox/voicevox_engine:cpu-latest` コンテナを使用します。`data/` と `credentials/` はホストへ永続化されるため、VM再起動後も生成物とYouTube認証が残ります。

プレビューだけを作る場合:

```bash
docker compose run --rm generator python -c "from generator.run_daily import main; main(upload=False)"
```

## 起動前チェック

秘密値を表示せず、AI、YouTube OAuth、VOICEVOX、字幕対応FFmpegを確認します。

```bash
.venv/bin/python3 -m generator.preflight
docker compose run --rm generator python -m generator.preflight
```

YouTube OAuthが失効している場合、ブラウザを使えるPCで次の1コマンドだけを実行します。

```bash
.venv/bin/python3 -m generator.youtube_auth --reauthorize
```

生成された `credentials/token.json` をVMの同じ場所へ安全に転送してください。ファイル権限は`600`を推奨します。

## 工程別の実行・再開

工程は `collect → script → assets → audio → video → upload-private` です。同日の既存成果物を利用して途中から再開できます。

```bash
# 全工程。ただしYouTube APIは呼ばない
.venv/bin/python3 -m generator.pipeline --dry-run

# 音声から動画まで再開
.venv/bin/python3 -m generator.pipeline --from-stage audio --to-stage video --run-id YYYYMMDD_HHMMSS

# 完成済み動画を非公開アップロードするだけ
.venv/bin/python3 -m generator.pipeline --from-stage upload-private --run-id YYYYMMDD_HHMMSS

# Dockerでも同じ引数を使用
docker compose run --rm generator python -m generator.pipeline --from-stage video --to-stage upload-private --run-id YYYYMMDD_HHMMSS
```

アップロード進捗は `data/uploads/<実行ID>.partial.json` に保存されます。アップロードだけが失敗した場合、音声・動画は再生成せず、未完了の投稿から再開します。

ネットワーク、AI、VOICEVOX、YouTubeを使わない完全モックでは、実際に字幕入りMP4まで作成します。

```bash
.venv/bin/python3 -m generator.pipeline --mock
```

## 朝のスケジュール

コンテナ内時刻は常に `Asia/Tokyo` として判定します。既定値は5:00生成・非公開投稿、7:00公開ですが、自動公開は安全のため無効です。

```dotenv
GENERATE_HOUR=5
GENERATE_MINUTE=0
PUBLISH_HOUR=7
PUBLISH_MINUTE=0
ENABLE_AUTO_PUBLISH=false
```

公開検証が完了するまでは `ENABLE_AUTO_PUBLISH=false` のままにしてください。macOSの旧 `sciencewonder` launchdジョブも停止・無効化し、新しい日次ジョブはpreflight成功時だけ非公開アップロードします。catch-upと自動公開のplistは既定で無効です。

## クラウドVM導入前の残作業

- Docker Engine / ComposeをVMへ導入し、`docker compose config`とコンテナ起動を確認する
- `.env`へAnthropic APIキーと利用可能なモデルIDを設定する
- YouTube OAuthを上記1コマンドで再認証し、権限600でVMへ配置する
- `docker compose run --rm generator python -m generator.preflight`を全項目OKにする
- 公式MLBデータを使った収集・台本生成をdry-runで確認する
- 非公開アップロード1回をYouTube Studioで確認する
- VMのディスク容量監視、バックアップ、ログローテーションを設定する
- 公開時刻・タイトル・概要欄・権利表記を人手確認してから自動公開を有効化する

## 外部素材の登録

素材をプロジェクト内へ保存し、`config/licensed_assets.json` に次の情報を登録します。

```json
{
  "key": "unique-key",
  "local_path": "/app/assets/example.jpg",
  "source_page": "https://example.org/source",
  "author": "Author name",
  "license": "CC BY"
}
```

許可される表記は `CC0`、`Public Domain`、`CC BY`、`CC BY-SA` です。未登録素材、出典不明素材、NC・ND素材は自動採用されません。

## 主な設定

- `config/channel.json`: 本数、チャンネル名、公開時刻
- `config/japanese_players.json`: 追跡する日本人選手と優先度
- `config/licensed_assets.json`: 使用許可を確認した素材台帳
- `LLM_PROVIDER=anthropic`: Linux/Docker向けAPI実行
- `LLM_PROVIDER=claude_cli`: 従来のローカルCLI実行

※MLB、球団名、選手名などの商標は説明・報道目的の識別にのみ使用し、公式チャンネルであるかのような表示は避けてください。
