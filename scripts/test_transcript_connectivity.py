"""
最小 YouTube transcript 连通性测试（不跑 pipeline、不用缓存、不调 OpenAI）。
用法: python scripts/test_transcript_connectivity.py
"""

from __future__ import annotations

import csv
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "output" / "roblox_kol_report.csv"
SAMPLE_SIZE = 2

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    print("ERROR: 未安装 youtube-transcript-api")
    sys.exit(1)


def _video_id(url: str) -> str:
    if "watch?v=" in url:
        return url.split("watch?v=", 1)[1].split("&")[0]
    if "youtu.be/" in url:
        return url.split("youtu.be/", 1)[1].split("?")[0]
    return ""


def _load_sample_rows(n: int) -> list[dict[str, str]]:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"找不到报告: {CSV_PATH}")
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError("CSV 为空")
    k = min(n, len(rows))
    return random.sample(rows, k)


def _first_sentences(text: str, max_chars: int = 220) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", text)
    preview = " ".join(parts[:2]).strip()
    if len(preview) > max_chars:
        preview = preview[: max_chars - 1] + "…"
    return preview


def _classify_error(exc: Exception, video_id: str) -> str:
    name = type(exc).__name__
    msg = str(exc).lower()

    if "ipblocked" in name.lower() or "ip blocked" in msg:
        return "IP_BLOCKED（请求被 YouTube 按 IP 拦截）"
    if "requestblocked" in name.lower() or "request blocked" in msg:
        return "REQUEST_BLOCKED（请求被拦截，常见于风控/反爬）"
    if "toomanyrequests" in name.lower() or "429" in msg or "too many requests" in msg:
        return "RATE_LIMITED（请求频率过高 / 429）"
    if "transcriptsdisabled" in name.lower() or "transcript disabled" in msg:
        return "TRANSCRIPT_DISABLED（上传者关闭字幕）"
    if "notranscriptfound" in name.lower() or "no transcript" in msg:
        return "NO_TRANSCRIPT（该视频无可用字幕轨）"
    if "videounavailable" in name.lower() or "video unavailable" in msg:
        return "VIDEO_UNAVAILABLE（视频不可用或受限）"
    if "could not retrieve" in msg and "transcript" in msg:
        return "NO_TRANSCRIPT（无法获取字幕轨）"

    return f"UNKNOWN（{name}: {exc}）"


def _fetch_fresh(video_id: str) -> tuple[bool, str, int, str, str]:
    """直连网络，不读缓存。"""
    api = YouTubeTranscriptApi()
    try:
        fetched = api.fetch(
            video_id,
            languages=["en", "en-US", "en-GB", "zh", "zh-Hans", "zh-CN"],
        )
        text = " ".join(snippet.text for snippet in fetched)
        preview = _first_sentences(text)
        return True, "", len(text), preview, "manual/auto caption"
    except Exception as exc:
        reason = _classify_error(exc, video_id)
        shorts_hint = ""
        if "NO_TRANSCRIPT" in reason or "TRANSCRIPT_DISABLED" in reason:
            shorts_hint = "（Shorts 常见：无人工字幕 / 仅自动字幕未开放 API）"
        return False, reason + shorts_hint, 0, "", type(exc).__name__


def _safe_print(text: str) -> None:
    enc = getattr(sys.stdout, "encoding", None) or "utf-8"
    print(text.encode(enc, errors="replace").decode(enc))


def main() -> None:
    random.seed()
    samples = _load_sample_rows(SAMPLE_SIZE)

    _safe_print("=" * 60)
    _safe_print("YouTube Transcript 连通性测试（最小）")
    _safe_print(f"数据源: {CSV_PATH}")
    _safe_print(f"抽样: {len(samples)} 个代表视频（随机，无缓存）")
    _safe_print("=" * 60)

    for i, row in enumerate(samples, 1):
        creator = row.get("创作者", "?")
        title = row.get("代表视频", "")
        shorts = row.get("Shorts占比", "")
        url = str(row.get("视频链接", "")).strip()
        vid = _video_id(url)

        _safe_print(f"\n--- [{i}] {creator} ---")
        _safe_print(f"video_id:     {vid or '(无效 URL)'}")
        _safe_print(f"代表视频:     {title[:72]}{'…' if len(title) > 72 else ''}")
        _safe_print(f"Shorts占比:   {shorts or '—'}")

        if not vid:
            _safe_print("成功:         否")
            _safe_print("失败原因:     INVALID_URL")
            continue

        ok, reason, length, preview, extra = _fetch_fresh(vid)
        _safe_print(f"成功:         {'是' if ok else '否'}")
        if ok:
            _safe_print(f"transcript长度: {length} 字符")
            _safe_print(f"字幕类型:     {extra}")
            _safe_print(f"前 1~2 句:    {preview or '(空)'}")
        else:
            _safe_print(f"transcript长度: 0")
            _safe_print(f"失败原因:     {reason}")
            _safe_print(f"异常类型:     {extra}")

    _safe_print("\n" + "=" * 60)
    _safe_print("测试结束（未调用 OpenAI / 未写缓存 / 未跑 pipeline）")
    _safe_print("=" * 60)


if __name__ == "__main__":
    main()
