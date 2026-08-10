"""Asset policy for the MLB channel.

Generated videos default to original diagrams. Optional local assets may be
listed in config/licensed_assets.json, but are accepted only when every credit
field and a permissive license are explicitly recorded.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSET_DIR = ROOT / "data" / "assets"
REGISTRY = ROOT / "config" / "licensed_assets.json"
ALLOWED = {"CC0", "Public Domain", "CC BY", "CC BY-SA"}


def collect(script_path):
    script_path = Path(script_path)
    data = json.loads(script_path.read_text(encoding="utf-8"))
    run_dir = ASSET_DIR / script_path.stem
    run_dir.mkdir(parents=True, exist_ok=True)
    registry = json.loads(REGISTRY.read_text(encoding="utf-8")) if REGISTRY.exists() else []
    valid = {
        str(item.get("key")): item for item in registry
        if item.get("license") in ALLOWED
        and all(item.get(k) for k in ("local_path", "source_page", "author", "license"))
        and Path(item["local_path"]).exists()
    }
    manifest = []
    for video in data.get("long_videos", []):
        for section in video.get("sections", []):
            key = section.get("visual", {}).get("asset_key")
            if key and key in valid:
                item = valid[key]
                section["visual"].update(local_path=item["local_path"], credit=f"{item['author']} / {item['license']}")
                manifest.append(item)
    (run_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    data["visual_manifest"] = manifest
    script_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[mlb] licensed assets: {len(manifest)}; original diagrams used otherwise")
    return run_dir / "manifest.json"


if __name__ == "__main__":
    import sys
    collect(sys.argv[1])
