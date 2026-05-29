"""Feed 卡片用短摘要：主判断 + 风格观察。"""

from __future__ import annotations

import re
from typing import Any

_DETAIL_LABELS = ("玩家群体", "适合游戏", "潜力判断")
_METRIC_HINTS = ("播放", "互动率", "粉丝", "潜力分", "均值", "波动", "早期")

_TITLE_STYLE: list[tuple[str, str]] = [
    (r"shorts?|#short", "Shorts 节奏向，偏快速曝光"),
    (r"mm2|murder", "MM2 高光 / 悬疑梗剪辑"),
    (r"battleground|strongest|pvp", "PvP / Battleground 高光切片"),
    (r"brainrot|skibidi", "brainrot chaos 传播向"),
    (r"meme|funny|chaos|comedy", "chaos humor / meme 反应向"),
    (r"music|song", "音乐 / 二创混剪感"),
    (r"reaction|moment", "高光 moment 综剪"),
]


def _video_id_from_url(url: str) -> str:
    if "watch?v=" in url:
        return url.split("watch?v=", 1)[1].split("&")[0]
    if "youtu.be/" in url:
        return url.split("youtu.be/", 1)[1].split("?")[0]
    return ""


def video_thumbnail_url(video_url: str) -> str:
    vid = _video_id_from_url(video_url)
    if not vid:
        return ""
    return f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"


def extract_recommendation_verdict(recommendation: str, max_len: int = 160) -> str:
    """首页主判断：1~2 句，止于玩家群体/适合游戏等长分析。"""
    if not recommendation.strip():
        return ""

    text = recommendation.replace("|", "｜").strip()
    text = re.sub(r"^值得关注[｜|]\s*", "", text)

    stop = len(text)
    for marker in ("｜", " 玩家群体", " 适合游戏", " 潜力判断"):
        idx = text.find(marker)
        if idx >= 0:
            stop = min(stop, idx)
    chunk = text[:stop].strip()

    parts = re.split(r"(?<=[。！？；])", chunk)
    verdict = "".join(p.strip() for p in parts[:2] if p.strip())
    if not verdict:
        verdict = chunk

    if len(verdict) > max_len:
        cut = verdict[: max_len - 1]
        for sep in ("。", "；", "，"):
            pos = cut.rfind(sep)
            if pos > 40:
                verdict = cut[: pos + 1]
                break
        else:
            verdict = cut + "…"
    return verdict


def _title_style_hints(title: str) -> list[str]:
    hints: list[str] = []
    t = title.lower()
    for pattern, label in _TITLE_STYLE:
        if re.search(pattern, t, re.I) and label not in hints:
            hints.append(label)
    return hints[:2]


def _is_metric_clause(clause: str) -> bool:
    return any(k in clause for k in _METRIC_HINTS)


def build_scout_style(
    scout_note: str,
    highlight: str,
    video_title: str = "",
) -> list[str]:
    """运营观察：风格向 2~4 行，融合数据简评中非重复信息。"""
    lines: list[str] = []

    if scout_note.strip():
        for part in re.split(r"[。！]", scout_note):
            p = part.strip()
            if not p:
                continue
            if not p.endswith("。"):
                p += "。"
            if p not in lines:
                lines.append(p)
            if len(lines) >= 2:
                break

    for clause in re.split(r"[；;]", highlight):
        c = clause.strip()
        if not c or _is_metric_clause(c):
            continue
        if any(c in ln or ln in c for ln in lines):
            continue
        if len(c) > 48:
            c = c[:45] + "…"
        lines.append(c)
        if len(lines) >= 3:
            break

    for hint in _title_style_hints(video_title):
        if len(lines) >= 4:
            break
        if not any(hint[:8] in ln for ln in lines):
            lines.append(hint)

    return lines[:4] if lines else ["风格信号不足，建议点开完整分析。"]


def enrich_creator_fields(row: dict[str, Any]) -> dict[str, str | list[str]]:
    scout = str(row.get("运营观察", "")).strip()
    highlight = str(row.get("数据简评", "")).strip()
    recommendation = str(row.get("推荐原因", "")).strip()
    video_url = str(row.get("视频链接", "")).strip()
    video_title = str(row.get("代表视频", "")).strip()

    return {
        "recommendation_verdict": extract_recommendation_verdict(recommendation),
        "scout_style": build_scout_style(scout, highlight, video_title),
        "video_id": _video_id_from_url(video_url),
        "video_thumbnail": video_thumbnail_url(video_url),
    }
