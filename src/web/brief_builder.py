"""从报告数据生成三行式、可溯源的 Creator Brief。"""

from __future__ import annotations

import re
from statistics import median
from typing import Any

_SIGNAL_TRANSCRIPT_OK = frozenset({"🧠 字幕增强", "🟡 部分字幕"})
_THEME_DISCLAIMER = "待字幕数据补充，本期仅基于标题与标签推测，可信度有限。"
_CONSISTENCY_LOW = 40.0
_MAX_TOTAL_CHARS = 120


def _num(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    s = str(value).replace(",", "").replace("%", "").strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def _int_num(value: Any) -> int:
    return int(_num(value))


def _burst_ratio(row: dict[str, Any]) -> float:
    subs = _int_num(row.get("粉丝数"))
    views = _num(row.get("平均播放"))
    if subs <= 0:
        return 0.0
    return views / subs


def _signal_label(row: dict[str, Any]) -> str:
    return str(row.get("分析信号", "")).strip()


def _has_transcript_signal(rows: list[dict[str, Any]]) -> bool:
    return any(_signal_label(r) in _SIGNAL_TRANSCRIPT_OK for r in rows)


def _dominant_transcript_theme(rows: list[dict[str, Any]]) -> str:
    from collections import Counter

    tags: Counter[str] = Counter()
    for row in rows:
        if _signal_label(row) not in _SIGNAL_TRANSCRIPT_OK:
            continue
        kw = str(row.get("字幕关键词", "")).strip()
        if not kw:
            continue
        first = kw.split(",")[0].strip()
        if first:
            tags[first] += 1
    if not tags:
        return ""
    return tags.most_common(1)[0][0]


def _tier1_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in rows if str(r.get("榜单分层", "")).strip() == "Tier 1"]


def _format_ratio(ratio: float) -> str:
    if ratio >= 10:
        return f"{round(ratio)}×"
    return f"{ratio:.1f}×"


def _line_overview(rows: list[dict[str, Any]]) -> str:
    n = len(rows)
    engagements = [_num(r.get("互动率")) for r in rows]
    avg_eng = sum(engagements) / n if n else 0.0
    volatile = sum(1 for r in rows if _num(r.get("稳定度")) < _CONSISTENCY_LOW)
    return (
        f"本期收录 {n} 位创作者，互动率均值 {avg_eng:.1f}%，"
        f"{volatile}/{n} 账号稳定度偏低。"
    )


def _line_top_signal(rows: list[dict[str, Any]]) -> str:
    tier1 = _tier1_rows(rows) or rows
    top = max(tier1, key=_burst_ratio, default=None)
    if top is None:
        return "本期无爆发系数数据。（来源：平均播放、粉丝数）"

    name = str(top.get("创作者", "")).strip()
    ratio = _burst_ratio(top)
    ratios = [_burst_ratio(r) for r in tier1 if _burst_ratio(r) > 0]
    med = median(ratios) if ratios else 0.0
    volatile = _num(top.get("稳定度")) < _CONSISTENCY_LOW

    parts = [f"爆发系数最高为 {name}（{_format_ratio(ratio)}）"]
    if med > 0 and ratio >= med * 1.8:
        parts.append("远超同梯队")
    if volatile:
        parts.append("但播放波动大")

    body = "，".join(parts)
    cite = "稳定度" if volatile else "平均播放、粉丝数"
    line = f"{body}（来源：{cite}字段）"
    theme = _dominant_transcript_theme(rows)
    if theme and _has_transcript_signal(rows):
        line += f"；字幕主题偏 {theme}（来源：字幕关键词）"
    return f"{line}。"


def _line_priority_contact(rows: list[dict[str, Any]]) -> str:
    ranked = sorted(rows, key=_burst_ratio, reverse=True)
    pick = ranked[0]
    tier1_top = _tier1_rows(rows)
    if tier1_top:
        t1_name = str(max(tier1_top, key=_burst_ratio).get("创作者", "")).strip()
        if str(pick.get("创作者", "")).strip() == t1_name:
            tier2 = [r for r in rows if str(r.get("榜单分层", "")).strip() == "Tier 2"]
            if tier2:
                pick = max(tier2, key=_burst_ratio)

    name = str(pick.get("创作者", "")).strip()
    ratio = _burst_ratio(pick)
    subs = _int_num(pick.get("粉丝数"))

    if subs < 10_000:
        reason = (
            f"低粉高播（播放/粉丝比 {_format_ratio(ratio)}），"
            f"适合验证非粉丝触达"
        )
    else:
        reason = f"播放/粉丝比 {_format_ratio(ratio)}，适合优先试投"

    return f"优先接触：{name}，{reason}。"


def _shrink_to_limit(lines: list[str], max_chars: int) -> list[str]:
    if len("".join(lines)) <= max_chars:
        return lines

    shrunk = list(lines)
    shrunk[1] = re.sub(r"，远超同梯队", "", shrunk[1])
    shrunk[2] = shrunk[2].replace("适合验证非粉丝触达", "宜验证非粉丝触达")
    shrunk[2] = shrunk[2].replace("适合优先试投", "宜优先试投")
    return shrunk


class BriefBuilder:
    """固定三行：数据概览 / 最显著信号 / 优先接触。"""

    def build(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        if not rows:
            return {
                "title": "本周 Creator Scout Brief",
                "paragraphs": ["本周暂无 creator 数据。"],
                "footnote": "",
            }

        lines = _shrink_to_limit(
            [
                _line_overview(rows),
                _line_top_signal(rows),
                _line_priority_contact(rows),
            ],
            _MAX_TOTAL_CHARS,
        )

        footnote = ""
        if not _has_transcript_signal(rows):
            footnote = _THEME_DISCLAIMER

        return {
            "title": "本周 Creator Scout Brief",
            "paragraphs": lines,
            "footnote": footnote,
        }
