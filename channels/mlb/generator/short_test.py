"""Generate one fresh, source-grounded MLB Short and upload it privately."""
import json

from generator.collect_mlb import main as collect_facts
from generator.generate_scripts import main as generate_scripts
from generator.render_video import main as render_video
from generator.run_daily import ensure_voicevox
from generator.synthesize import main as synthesize
from generator.upload_youtube import main as upload_youtube
from generator.visual_assets import collect as collect_assets


def main():
    facts_path = collect_facts()
    script_path = generate_scripts(facts_path)
    data = json.loads(script_path.read_text(encoding="utf-8"))
    data["long_videos"] = []
    data["short_videos"] = data["short_videos"][:1]
    script_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    collect_assets(script_path)
    ensure_voicevox()
    synthesize(script_path)
    render_video(script_path)
    result = upload_youtube(script_path)
    if len(result.get("shorts", [])) != 1 or result.get("longs"):
        raise RuntimeError(f"unexpected test upload result: {result}")
    print(f"[mlb-test] private Short uploaded: https://youtu.be/{result['shorts'][0]}")
    return result


if __name__ == "__main__":
    main()
