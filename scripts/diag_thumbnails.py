"""诊断代表视频 thumbnail 字段与 URL 可达性。"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check_url(url: str) -> str:
    if not url:
        return "EMPTY"
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return str(resp.status)
    except urllib.error.HTTPError as exc:
        return str(exc.code)
    except Exception as exc:  # noqa: BLE001
        return f"ERR:{exc.__class__.__name__}"


def audit_file(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    creators = data.get("creators", [])
    print(f"\n== {path.relative_to(ROOT)} ({len(creators)} creators) ==")
    empty_thumb = 0
    for c in creators:
        thumb_url_field = c.get("thumbnail_url", "__MISSING__")
        video_thumb = c.get("video_thumbnail", "")
        video_url = c.get("video_url", "")
        status = check_url(video_thumb) if video_thumb else "N/A"
        if not video_thumb:
            empty_thumb += 1
        print(
            f"rank={c.get('rank'):>2} "
            f"thumbnail_url={thumb_url_field!r} "
            f"video_thumbnail={'SET' if video_thumb else 'EMPTY'} "
            f"http={status} "
            f"video_url={video_url}"
        )
        if video_thumb:
            print(f"         src={video_thumb}")
    print(f"empty video_thumbnail: {empty_thumb}/{len(creators)}")


def main() -> None:
    targets = [
        ROOT / "web" / "data" / "report.json",
        *sorted((ROOT / "web" / "data" / "reports").glob("*.json")),
    ]
    for path in targets:
        if path.name == "index.json" or not path.exists():
            continue
        audit_file(path)


if __name__ == "__main__":
    main()
