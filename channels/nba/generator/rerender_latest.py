import json
import os
from pathlib import Path

from generator import render_video, synthesize, upload_youtube
from generator.generate_scripts import SCRIPTS_DIR


def main():
    scripts = sorted(SCRIPTS_DIR.glob("*.json"))
    if not scripts:
        raise RuntimeError("no cached NBA script is available to rerender")

    source = scripts[-1]
    suffix = os.environ.get("RERENDER_SUFFIX", "caption_test")
    target = SCRIPTS_DIR / f"{source.stem}_{suffix}.json"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    data = json.loads(target.read_text(encoding="utf-8"))
    print(f"[info] rerendering cached script: {source.name}")
    synthesize.main(target)
    render_video.main(target)
    result = upload_youtube.main(target)
    print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == "__main__":
    main()
