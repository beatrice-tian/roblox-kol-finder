"""将 CSV 报告导出为 Web 情报流 JSON（按日期归档，不覆盖历史）。"""

from __future__ import annotations

import csv
import json
import re
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
                "viral_hit": str(row.get("爆款记录", "")).strip(),
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


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def reports_dir(project_root: Path | None = None) -> Path:
    root = project_root or Path(__file__).resolve().parents[2]
    return root / "web" / "data" / "reports"


def legacy_report_path(project_root: Path | None = None) -> Path:
    root = project_root or Path(__file__).resolve().parents[2]
    return root / "web" / "data" / "report.json"


def week_title(when: datetime) -> str:
    return f"Week {when.isocalendar()[1]}"


def report_date_str(when: datetime | None = None) -> str:
    moment = when or datetime.now().astimezone()
    return moment.date().isoformat()


def load_reports_index(index_path: Path) -> list[dict[str, str]]:
    if not index_path.exists():
        return []
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [e for e in data if isinstance(e, dict) and e.get("date")]


def save_reports_index(index_path: Path, entries: list[dict[str, str]]) -> None:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def upsert_reports_index(index_path: Path, date: str, title: str) -> list[dict[str, str]]:
    entries = [e for e in load_reports_index(index_path) if e.get("date") != date]
    entries.append({"date": date, "title": title})
    entries.sort(key=lambda e: e["date"], reverse=True)
    save_reports_index(index_path, entries)
    return entries


def _title_for_report_file(path: Path) -> str:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            if payload.get("title"):
                return str(payload["title"])
            generated_at = payload.get("generated_at")
            if generated_at:
                when = datetime.fromisoformat(str(generated_at).replace("Z", "+00:00"))
                if when.tzinfo is None:
                    when = when.replace(tzinfo=timezone.utc)
                return week_title(when.astimezone())
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    try:
        when = datetime.strptime(path.stem, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return week_title(when)
    except ValueError:
        return path.stem


def rebuild_reports_index(reports_path: Path) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for path in reports_path.glob("*.json"):
        if path.name == "index.json":
            continue
        if not _DATE_RE.match(path.stem):
            continue
        entries.append({"date": path.stem, "title": _title_for_report_file(path)})
    entries.sort(key=lambda e: e["date"], reverse=True)
    save_reports_index(reports_path / "index.json", entries)
    return entries


def migrate_legacy_report(project_root: Path | None = None) -> Path | None:
    """将旧版 web/data/report.json 迁入 reports/ 目录（仅当尚无对应日期文件时）。"""
    root = project_root or Path(__file__).resolve().parents[2]
    legacy = legacy_report_path(root)
    if not legacy.exists():
        return None

    try:
        payload = json.loads(legacy.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None

    generated_at = payload.get("generated_at")
    if generated_at:
        when = datetime.fromisoformat(str(generated_at).replace("Z", "+00:00"))
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        date_str = report_date_str(when.astimezone())
        title = payload.get("title") or week_title(when.astimezone())
    else:
        when = datetime.now().astimezone()
        date_str = report_date_str(when)
        title = week_title(when)

    target = reports_dir(root) / f"{date_str}.json"
    if not target.exists():
        payload.setdefault("report_date", date_str)
        payload.setdefault("title", title)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    rebuild_reports_index(reports_dir(root))
    return target


def export_web_data(
    csv_path: Path,
    project_root: Path | None = None,
) -> tuple[dict[str, Any], Path]:
    root = project_root or Path(__file__).resolve().parents[2]
    reports_path = reports_dir(root)
    index_path = reports_path / "index.json"

    migrate_legacy_report(root)

    rows = load_csv_rows(csv_path)
    brief = BriefBuilder().build(rows)
    avatars = _load_channel_avatars(rows)

    now = datetime.now().astimezone()
    date_str = report_date_str(now)
    title = week_title(now)
    json_path = reports_path / f"{date_str}.json"

    payload: dict[str, Any] = {
        "report_date": date_str,
        "title": title,
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
    upsert_reports_index(index_path, date_str, title)
    return payload, json_path


def default_paths(project_root: Path | None = None) -> tuple[Path, Path]:
    root = project_root or Path(__file__).resolve().parents[2]
    csv_path = root / "output" / "roblox_kol_report.csv"
    return csv_path, reports_dir(root)
