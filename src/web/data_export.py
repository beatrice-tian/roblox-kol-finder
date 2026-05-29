"""将 CSV 报告导出为 Web 情报流 JSON。"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import get_settings
from src.web.avatars import fetch_channel_avatars
from src.web.brief_builder import BriefBuilder
from src.web.summaries import enrich_creator_fields


def _parse_number(value: Any) -> int:
    if value is None or value == "":
        return 0
    s = str(value).replace(",", "").strip()
    try:
        return int(float(s))
    except ValueError:
        return 0


def _format_engagement(value: Any) -> str:
    n = str(value).replace("%", "").strip()
    if not n:
        return "—"
    try:
        f = float(n)
        return f"{f:.2f}%" if "%" not in str(value) else str(value)
    except ValueError:
        return str(value)


def _format_consistency(value: Any) -> str:
    if value is None or value == "":
        return "—"
    try:
        f = float(str(value).replace(",", ""))
        if f <= 0:
            return "波动大"
        if f >= 70:
            return "较稳定"
        if f >= 40:
            return "中等"
        return "波动大"
    except ValueError:
        return str(value)


def _channel_id_from_url(url: str) -> str:
    if "/channel/" in url:
        return url.rstrip("/").split("/channel/")[-1].split("?")[0]
    return ""


def load_csv_rows(csv_path: Path) -> list[dict[str, Any]]:
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def rows_to_creators(
    rows: list[dict[str, Any]],
    avatar_by_channel: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    avatars = avatar_by_channel or {}
    creators: list[dict[str, Any]] = []
    for row in rows:
        channel_url = str(row.get("频道链接", "")).strip()
        channel_id = _channel_id_from_url(channel_url)
        extra = enrich_creator_fields(row)
        video_url = str(row.get("视频链接", "")).strip()
        recommendation = str(row.get("推荐原因", "")).strip()
        creators.append(
            {
                "rank": _parse_number(row.get("排名")),
                "name": str(row.get("创作者", "")).strip(),
                "platform": str(row.get("平台", "")).strip(),
                "list_tier": str(row.get("榜单分层", "")).strip(),
                "tier": str(row.get("潜力等级", "")).strip(),
                "potential_score": row.get("潜力分", ""),
                "subscribers": row.get("粉丝数", ""),
                "avg_views": row.get("平均播放", ""),
                "avg_views_num": _parse_number(row.get("平均播放")),
                "engagement": _format_engagement(row.get("互动率")),
                "consistency": _format_consistency(row.get("稳定度")),
                "consistency_raw": row.get("稳定度", ""),
                "scout_note": str(row.get("运营观察", "")).strip(),
                "scout_style": extra["scout_style"],
                "recommendation": recommendation,
                "recommendation_verdict": extra["recommendation_verdict"],
                "highlight": str(row.get("数据简评", "")).strip(),
                "video_title": str(row.get("代表视频", "")).strip(),
                "video_views": row.get("代表视频播放", ""),
                "video_url": video_url,
                "video_id": extra["video_id"],
                "video_thumbnail": extra["video_thumbnail"],
                "channel_url": channel_url,
                "channel_id": channel_id,
                "avatar_url": avatars.get(channel_id, ""),
                "signal": str(row.get("分析信号", "")).strip(),
                "shorts": str(row.get("Shorts占比", "")).strip(),
                "published_at": str(row.get("发布时间", "")).strip(),
            }
        )
    return creators


def _load_channel_avatars(rows: list[dict[str, Any]]) -> dict[str, str]:
    ids = [
        _channel_id_from_url(str(row.get("频道链接", "")).strip())
        for row in rows
    ]
    settings = get_settings()
    if not settings.youtube_api_key:
        return {}
    try:
        return fetch_channel_avatars(ids, settings.youtube_api_key)
    except Exception:
        return {}


def export_web_data(
    csv_path: Path,
    json_path: Path,
) -> dict[str, Any]:
    rows = load_csv_rows(csv_path)
    brief = BriefBuilder().build(rows)
    avatars = _load_channel_avatars(rows)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_csv": str(csv_path),
        "brief": brief,
        "creators": rows_to_creators(rows, avatars),
    }
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload


def default_paths(project_root: Path | None = None) -> tuple[Path, Path]:
    root = project_root or Path(__file__).resolve().parents[2]
    csv_path = root / "output" / "roblox_kol_report.csv"
    json_path = root / "web" / "data" / "report.json"
    return csv_path, json_path
