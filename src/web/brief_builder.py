"""从报告数据生成 scouting 风格 Creator Brief。"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

_SIGNAL_TRANSCRIPT_OK = frozenset({"🧠 字幕增强", "🟡 部分字幕"})
_THEME_DISCLAIMER = "待字幕数据补充，本期仅基于标题与标签推测，可信度有限。"
_VIRAL_HIT_LABEL = "有爆款"
_CONSISTENCY_STABLE_BASE = 40.0

_TRACK_PATTERNS: tuple[tuple[str, str], ...] = (
    ("Brainrot", r"brainrot|steal a brainrot|skibidi"),
    ("Battlegrounds", r"battleground|strongest|pvp|rivals"),
    ("Meme Shorts", r"meme|shorts|#short|funny|chaos|mm2|forsaken"),
    ("MM2 / 悬疑", r"mm2|murder mystery|mystery"),
    ("模拟 / Obby", r"simulator|obby|tycoon|grow a garden"),
)

_TRACK_BLURBS: dict[str, str] = {
    "Brainrot": (
        "多位创作者获得超出粉丝规模的曝光，"
        "适合快节奏梗向与轻度玩法试水。"
    ),
    "Battlegrounds": (
        "以 PvP 和高操作内容为主，"
        "互动表现普遍较好，适合竞技向项目做高光切片。"
    ),
    "Meme Shorts": (
        "Shorts 分发效率高，"
        "更适合短期曝光而非长视频深度转化。"
    ),
    "MM2 / 悬疑": "悬疑搞笑高光易出圈，但受众偏垂类。",
    "模拟 / Obby": "偏长线留存玩法展示，合作节奏宜稳不宜急。",
}


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


def _row_text_blob(row: dict[str, Any]) -> str:
    return " ".join(
        [
            str(row.get("代表视频", "")),
            str(row.get("字幕关键词", "")),
            str(row.get("推荐原因", "")),
            str(row.get("运营观察", "")),
        ]
    ).lower()


def _detect_track_counts(rows: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        blob = _row_text_blob(row)
        matched = False
        for label, pattern in _TRACK_PATTERNS:
            if re.search(pattern, blob, re.I):
                counts[label] += 1
                matched = True
        if not matched:
            counts["其他"] += 1
    return counts


def _format_ratio(ratio: float) -> str:
    if ratio >= 10:
        return f"{round(ratio)}×"
    return f"{ratio:.1f}×"


def _fmt_subs_short(n: int) -> str:
    if n >= 10_000:
        return f"{round(n / 10_000, 1)}万".replace(".0万", "万")
    if n >= 1_000:
        return f"{round(n / 1_000, 1)}千".replace(".0千", "千")
    return str(n)


def _headline_trend(rows: list[dict[str, Any]]) -> str:
    n = len(rows)
    low_fan = [r for r in rows if _int_num(r.get("粉丝数")) < 10_000]
    low_fan_high_play = [
        r
        for r in low_fan
        if _num(r.get("平均播放")) >= 100_000
    ]
    viral_hits = sum(
        1 for r in rows if str(r.get("爆款记录", "")).strip() == _VIRAL_HIT_LABEL
    )
    shorts_heavy = sum(1 for r in rows if str(r.get("Shorts占比", "")).strip() == "是")

    if len(low_fan_high_play) >= max(2, (n + 1) // 3):
        return (
            f"本期低粉高播账号数量明显增加。"
            f"{n} 位入选创作者中，{len(low_fan_high_play)} 位粉丝不足 1 万，"
            f"但平均播放已超过 10 万，"
            f"说明 Roblox 内容仍存在较强的自然流量机会。"
        )

    if viral_hits >= max(3, n // 2):
        return (
            f"本期榜单呈现「基础盘 + 爆款」结构："
            f"{viral_hits}/{n} 位有单条爆款记录，"
            f"整体更适合用短周期 campaign 验证，而非按粉丝量直接下注。"
        )

    if shorts_heavy >= n // 2:
        return (
            f"本期 Shorts 向创作者占多数（{shorts_heavy}/{n}），"
            f"流量获取更依赖单条节奏与梗点密度，"
            f"合作设计应优先轻量曝光素材。"
        )

    avg_eng = sum(_num(r.get("互动率")) for r in rows) / n if n else 0.0
    return (
        f"本期入选账号整体互动率均值 {avg_eng:.1f}%，"
        f"播放效率与粉丝规模分化明显，"
        f"更适合按「单账号试投 → 再放大」的节奏推进。"
    )


def _track_insight_text(rows: list[dict[str, Any]]) -> str:
    """赛道洞察：压缩为 1~2 句话，无独立标题。"""
    counts = _detect_track_counts(rows)
    ranked = [(k, v) for k, v in counts.most_common() if k != "其他" and v > 0]
    if not ranked:
        return "本期赛道信号较分散，建议结合单卡代表视频进一步判断。"

    labels = [label for label, _ in ranked[:3]]
    top_label, top_count = ranked[0]
    blurbs = _TRACK_BLURBS.get(top_label, "值得优先安排试玩素材验证。")

    return (
        f"本期创作者内容主要集中在 {'、'.join(labels)}，"
        f"其中 {top_label} 占比最高（{top_count}/{len(rows)} 位）。"
        f"{blurbs}"
    )


def _pick_priority_creator(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ranked = sorted(rows, key=_burst_ratio, reverse=True)
    pick = ranked[0]
    tier1 = [r for r in rows if str(r.get("榜单分层", "")).strip() == "Tier 1"]
    if tier1:
        t1_best = max(tier1, key=_burst_ratio)
        if str(pick.get("创作者", "")) == str(t1_best.get("创作者", "")):
            tier2 = [r for r in rows if str(r.get("榜单分层", "")).strip() == "Tier 2"]
            if tier2:
                pick = max(tier2, key=_burst_ratio)
    return pick


def _next_action(row: dict[str, Any]) -> str:
    subs = _int_num(row.get("粉丝数"))
    ratio = _burst_ratio(row)
    stable = _num(row.get("稳定度")) >= _CONSISTENCY_STABLE_BASE
    viral = str(row.get("爆款记录", "")).strip() == _VIRAL_HIT_LABEL
    tier = str(row.get("潜力等级", "")).strip()

    if subs < 5_000 and ratio >= 15:
        return "建议先发 DM 试探合作意向，配小预算试投验证非粉丝触达。"
    if viral and not stable:
        return "建议先观察 2–3 条新作表现，再决定是否带报价方案接触。"
    if tier in ("高", "极高") and stable:
        return "数据较完整，可直接带报价方案发 DM 推进合作。"
    if subs >= 50_000:
        return "建议先观察一周内容节奏，再发 DM 沟通定制合作。"
    return "建议轻量发 DM 介绍游戏，确认档期后再给报价。"


def _why_contact_now(row: dict[str, Any]) -> str:
    subs = _int_num(row.get("粉丝数"))
    ratio = _burst_ratio(row)
    avg_views = _num(row.get("平均播放"))
    viral = str(row.get("爆款记录", "")).strip() == _VIRAL_HIT_LABEL
    stable = _num(row.get("稳定度")) >= _CONSISTENCY_STABLE_BASE

    parts: list[str] = []
    if subs < 10_000:
        parts.append(f"粉丝量级 {_fmt_subs_short(subs)}（偏小盘）")
    else:
        parts.append(f"粉丝量级 {_fmt_subs_short(subs)}")

    parts.append(f"播放/粉丝比 {_format_ratio(ratio)}")
    if avg_views >= 100_000:
        parts.append("近作平均播放已超 10 万")
    if viral:
        parts.append("有单条爆款记录")
    if stable:
        parts.append("基础盘播放较稳")
    else:
        parts.append("基础盘仍在验证期")

    return "，".join(parts) + "，当前数据窗口值得接触"


def _priority_contact(rows: list[dict[str, Any]]) -> str:
    pick = _pick_priority_creator(rows)
    name = str(pick.get("创作者", "")).strip()
    why = _why_contact_now(pick)
    action = _next_action(pick)
    return f"优先接触：{name}。{why}；{action}"


class BriefBuilder:
    """Brief：连续段落（整体趋势 → 赛道 1~2 句 → 优先接触）。"""

    def build(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        if not rows:
            return {
                "title": "本周 Creator Scout Brief",
                "paragraphs": ["本周暂无 creator 数据。"],
                "footnote": "",
            }

        footnote = ""
        if not _has_transcript_signal(rows):
            footnote = _THEME_DISCLAIMER

        return {
            "title": "本周 Creator Scout Brief",
            "paragraphs": [
                _headline_trend(rows),
                _track_insight_text(rows),
                _priority_contact(rows),
            ],
            "footnote": footnote,
        }
