import json
from datetime import date, timedelta
from pathlib import Path

from googleapiclient.discovery import build

from generator.youtube_auth import get_credentials

ROOT = Path(__file__).resolve().parent.parent
UPLOADS_DIR = ROOT / "data" / "uploads"
SCRIPTS_DIR = ROOT / "data" / "scripts"
ANALYTICS_DIR = ROOT / "data" / "analytics"
DIGEST_PATH = ANALYTICS_DIR / "digest.txt"
HISTORY_PATH = ANALYTICS_DIR / "history.json"

MIN_VIDEOS_FOR_DIGEST = 5
NO_DATA_DIGEST = "過去動画のデータがまだ少ないため、傾向分析はまだ行えません。構成やテーマは多様に試してください。"
RETENTION_GUIDANCE = """\
視聴者維持率を基準にした制作・公開後改善ルール:
- 冒頭3秒で結論または最大の驚きを提示し、挨拶・ロゴだけの導入・同じ説明の言い換えを置かない。
- 各区間は新しい事実、画像、比較のいずれかを必ず追加し、内容が進まない区間を作らない。
- 公開48〜72時間後に維持率曲線を確認し、冒頭の急落と局所的な急落を修正候補として記録する。
- 急落区間は原因を確認してからYouTubeエディタで削除候補にする。自動削除や、事実関係が崩れる切り方はしない。
- 好調動画の題材だけでなく、離脱が少ない導入長・説明順・画面変化の間隔を次回台本へ反映する。"""


def _with_retention_guidance(text: str) -> str:
    if RETENTION_GUIDANCE in text:
        return text
    return f"{text}\n\n{RETENTION_GUIDANCE}"


def _analytics_client():
    creds = get_credentials()
    return build("youtubeAnalytics", "v2", credentials=creds)


def fetch_video_stats(days: int = 90) -> dict:
    yta = _analytics_client()
    end = date.today()
    start = end - timedelta(days=days)
    response = yta.reports().query(
        ids="channel==MINE",
        startDate=start.isoformat(),
        endDate=end.isoformat(),
        metrics="views,averageViewDuration,averageViewPercentage,likes",
        dimensions="video",
        sort="-views",
        maxResults=200,
    ).execute()

    headers = [h["name"] for h in response.get("columnHeaders", [])]
    stats = {}
    for row in response.get("rows", []):
        record = dict(zip(headers, row))
        stats[record["video"]] = {
            "views": record.get("views", 0),
            "avg_view_pct": record.get("averageViewPercentage", 0),
            "avg_view_duration": record.get("averageViewDuration", 0),
            "likes": record.get("likes", 0),
        }
    return stats


def _load_runs():
    runs = []
    for uploads_path in sorted(UPLOADS_DIR.glob("*.json")):
        run_id = uploads_path.stem
        script_path = SCRIPTS_DIR / f"{run_id}.json"
        if not script_path.exists():
            continue
        uploads = json.loads(uploads_path.read_text(encoding="utf-8"))
        script = json.loads(script_path.read_text(encoding="utf-8"))
        runs.append({"run_id": run_id, "uploads": uploads, "script": script})
    return runs


def _describe_longs(run: dict) -> list:
    videos = run["script"].get("long_videos", [])
    ids = run["uploads"].get("longs", [])
    return [
        {"video_id": ids[i], "kind": "long", "title": video.get("title", ""),
         "categories": "+".join(sorted({s.get("category", "MLB") for s in video.get("sections", [])}))}
        for i, video in enumerate(videos) if i < len(ids)
    ]


def _describe_shorts(run: dict) -> list:
    script = run["script"]
    shorts_ids = run["uploads"].get("shorts", [])
    out = []
    for i, short in enumerate(script.get("short_videos", [])):
        if i >= len(shorts_ids):
            continue
        out.append({
            "video_id": shorts_ids[i],
            "kind": "short",
            "hook": short.get("hook", ""),
            "category": short.get("category", "MLB"),
        })
    return out


def build_digest() -> str:
    runs = _load_runs()
    stats = fetch_video_stats()

    records = []
    for run in runs:
        for long_meta in _describe_longs(run):
            long_meta["stats"] = stats.get(long_meta["video_id"])
            records.append(long_meta)
        for short_meta in _describe_shorts(run):
            short_meta["stats"] = stats.get(short_meta["video_id"])
            records.append(short_meta)

    ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    longs = [r for r in records if r["kind"] == "long" and r["stats"]]

    if len(longs) < MIN_VIDEOS_FOR_DIGEST:
        digest = _with_retention_guidance(NO_DATA_DIGEST)
        DIGEST_PATH.write_text(digest, encoding="utf-8")
        return digest

    longs.sort(key=lambda r: r["stats"]["avg_view_pct"], reverse=True)
    top = longs[:3]
    bottom = longs[-3:]

    lines = ["過去の長尺動画の視聴維持率ランキング（上位が好調、下位が不調）:"]
    for r in top:
        lines.append(
            f"- 好調: 「{r['title']}」(維持率{r['stats']['avg_view_pct']:.0f}%, "
            f"カテゴリ={r['categories']})"
        )
    for r in bottom:
        lines.append(
            f"- 不調: 「{r['title']}」(維持率{r['stats']['avg_view_pct']:.0f}%, "
            f"カテゴリ={r['categories']})"
        )
    lines.append("この傾向を参考にしつつ、同じテーマ・構成を毎回繰り返さないこと。")

    digest = _with_retention_guidance("\n".join(lines))
    DIGEST_PATH.write_text(digest, encoding="utf-8")
    return digest


def load_digest() -> str:
    if DIGEST_PATH.exists():
        return _with_retention_guidance(DIGEST_PATH.read_text(encoding="utf-8"))
    return _with_retention_guidance(NO_DATA_DIGEST)


def main():
    digest = build_digest()
    print(digest)
    return digest


if __name__ == "__main__":
    main()
