import json
import random
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import PROJECT_ROOT, get_settings
from src.models.creator import CreatorRecord

try:
    from youtube_transcript_api import YouTubeTranscriptApi

    _TRANSCRIPT_AVAILABLE = True
except ImportError:
    _TRANSCRIPT_AVAILABLE = False

MAX_KEYWORDS = 12
DEFAULT_CACHE_PATH = PROJECT_ROOT / "transcript_cache.json"

SIGNAL_TRANSCRIPT_BACKED = "🧠 Transcript-backed"
SIGNAL_PARTIAL = "🟡 Partial transcript"
SIGNAL_METADATA_ONLY = "⚪ Metadata-only"

STOPWORDS = frozenset(
    {
        "the", "and", "you", "that", "this", "with", "for", "are", "was",
        "but", "not", "have", "from", "they", "will", "what", "when", "your",
        "can", "all", "one", "out", "like", "just", "about", "into", "more",
        "than", "then", "them", "some", "been", "would", "there", "their",
        "yeah", "okay", "gonna", "wanna", "dont", "didnt", "its", "im", "ive",
        "oh", "uh", "um", "lol", "bro", "guys", "video", "watch", "subscribe",
    }
)

THEME_PHRASES: tuple[tuple[str, str], ...] = (
    ("brainrot", r"\bbrainrot\b|\bsteal a brainrot\b"),
    ("chaos humor", r"\bchaos\b|\bchaotic\b|\binsane\b|\bcrazy\b"),
    ("trolling", r"\btroll(?:ing)?\b|\bprank\b"),
    ("grinding", r"\bgrind(?:ing)?\b|\bfarm(?:ing)?\b|\bafk\b"),
    ("fruit build", r"\bblox fruits?\b|\bfruit\b|\braid\b|\bboss\b"),
    ("roleplay", r"\bbrookhaven\b|\broleplay\b|\brp\b"),
    ("pvp combat", r"\bpvp\b|\bfight(?:ing)?\b|\bbattlegrounds\b"),
    ("simulator", r"\bsimulator\b|\btycoon\b"),
    ("horror", r"\bhorror\b|\bscary\b|\bsurvival\b|\b99 nights\b"),
    ("meme slang", r"\bmeme\b|\brizz\b|\bsigma\b|\bskibidi\b"),
    ("robux economy", r"\brobux\b|\bfree robux\b"),
    ("dress to impress", r"\bdress to impress\b|\bdti\b"),
    ("murder mystery", r"\bmm2\b|\bmurder mystery\b"),
    ("jailbreak", r"\bjailbreak\b|\bjjs\b"),
)

GAME_TERMS = frozenset(
    {
        "roblox", "blox", "fruits", "brookhaven", "adopt", "brainrot",
        "simulator", "tycoon", "obby", "pvp", "raid", "boss", "grind",
        "forsaken", "robux", "shorts", "minecraft",
    }
)


def classify_transcript_error(exc: Exception) -> str:
    name = type(exc).__name__
    msg = str(exc).lower()
    if "ipblocked" in name.lower() or "ip blocked" in msg:
        return "IP_BLOCKED"
    if "requestblocked" in name.lower() or "request blocked" in msg:
        return "REQUEST_BLOCKED"
    if "toomanyrequests" in name.lower() or "429" in msg or "too many" in msg:
        return "RATE_LIMITED"
    if "transcriptsdisabled" in name.lower() or "disabled" in msg:
        return "TRANSCRIPT_DISABLED"
    if "notranscriptfound" in name.lower() or "no transcript" in msg:
        return "NO_TRANSCRIPT"
    if "videounavailable" in name.lower():
        return "VIDEO_UNAVAILABLE"
    return name or "UNKNOWN"


def _is_blocked_error(exc: Exception) -> bool:
    code = classify_transcript_error(exc)
    return code in ("IP_BLOCKED", "REQUEST_BLOCKED", "RATE_LIMITED")


class TranscriptCache:
    """本地字幕缓存；失败记录不阻止 pipeline，但默认可跳过错误缓存重试。"""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                self._data = raw
        except (json.JSONDecodeError, OSError):
            self._data = {}

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_usable_text(self, video_id: str, *, use_cache: bool) -> str | None:
        if not use_cache or video_id not in self._data:
            return None
        entry = self._data[video_id]
        if entry.get("error"):
            return None
        text = entry.get("text", "")
        return text if text else None

    def set_text(self, video_id: str, text: str, *, error: str = "") -> None:
        self._data[video_id] = {
            "text": text,
            "error": error,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }


class TranscriptKeywordExtractor:
    """每 creator 仅 Top1~2 高播放视频拉字幕；失败即 fallback metadata-only。"""

    def __init__(
        self,
        cache_path: Path | None = None,
        max_requests_per_run: int | None = None,
        delay_min: float | None = None,
        delay_max: float | None = None,
        top_videos_per_creator: int | None = None,
    ) -> None:
        settings = get_settings()
        self._cache = TranscriptCache(cache_path or settings.transcript_cache_path)
        self._max_requests = (
            max_requests_per_run or settings.transcript_max_requests_per_run
        )
        self._top_videos = (
            top_videos_per_creator or settings.transcript_top_videos_per_creator
        )
        self._use_cache = settings.transcript_use_cache
        self._delay_min = delay_min if delay_min is not None else settings.transcript_delay_min
        self._delay_max = delay_max if delay_max is not None else settings.transcript_delay_max
        self._requests_this_run = 0
        self._blocked = False
        self._stats: dict[str, Any] = {
            "cache_hit": 0,
            "fetched": 0,
            "skipped": 0,
            "blocked": 0,
            "failed": 0,
            "success": 0,
            "fallback": 0,
            "failure_reasons": Counter(),
        }

    def enrich_all(self, records: list[CreatorRecord]) -> list[CreatorRecord]:
        settings = get_settings()
        if not settings.transcript_enabled:
            print("  [transcript] 已关闭，全部 metadata-only")
            for record in records:
                record.transcript_keywords = ""
                record.signal_coverage = SIGNAL_METADATA_ONLY
            self._stats["fallback"] = len(records)
            self._print_run_summary(len(records))
            return records

        if not _TRANSCRIPT_AVAILABLE:
            print("  [transcript] 未安装 youtube-transcript-api，全部 metadata-only")
            for record in records:
                record.transcript_keywords = ""
                record.signal_coverage = SIGNAL_METADATA_ONLY
            self._stats["fallback"] = len(records)
            self._print_run_summary(len(records))
            return records

        print(
            f"  [transcript] 安全模式: 每 creator 最多 {self._top_videos} 条字幕, "
            f"单次网络上限 {self._max_requests}, "
            f"缓存={'开' if self._use_cache else '关'}"
        )

        for record in records:
            keywords, transcript_hits = self.extract_for(record)
            record.transcript_keywords = keywords
            record.signal_coverage = self._signal_coverage_label(transcript_hits)
            if transcript_hits == 0:
                self._stats["fallback"] += 1

        self._cache.save()
        self._print_run_summary(len(records))
        return records

    def _print_run_summary(self, creator_count: int) -> None:
        s = self._stats
        reasons = s.get("failure_reasons", Counter())
        reason_str = ", ".join(f"{k}={v}" for k, v in reasons.most_common()) or "无"

        print(
            f"  [transcript] 网络请求: {self._requests_this_run}/{self._max_requests} | "
            f"success: {s['success']} | failure: {s['failed']} | "
            f"fallback(creator): {s['fallback']}/{creator_count}"
        )
        print(
            f"  [transcript] cache_hit: {s['cache_hit']} | fetched: {s['fetched']} | "
            f"skipped: {s['skipped']} | blocked: {s['blocked']}"
        )
        print(f"  [transcript] failure_reasons: {reason_str}")
        if self._blocked:
            print(
                "  [transcript] 已检测到 IP/风控拦截，后续请求已跳过（metadata fallback）"
            )

    @staticmethod
    def _signal_coverage_label(transcript_hits: int) -> str:
        settings = get_settings()
        need = settings.transcript_top_videos_per_creator
        if transcript_hits >= need:
            return SIGNAL_TRANSCRIPT_BACKED
        if transcript_hits >= 1:
            return SIGNAL_PARTIAL
        return SIGNAL_METADATA_ONLY

    def extract_for(self, record: CreatorRecord) -> tuple[str, int]:
        video_ids = self._top_video_ids_by_views(record, self._top_videos)
        if not video_ids:
            return "", 0

        combined_text = ""
        transcript_hits = 0
        for vid in video_ids:
            text = self._resolve_transcript_text(vid, record.channel_name)
            if text:
                transcript_hits += 1
                combined_text += " " + text

        if not combined_text.strip():
            return "", transcript_hits

        keywords = self._extract_keywords(combined_text)
        if not keywords:
            return "", transcript_hits

        return ", ".join(keywords[:MAX_KEYWORDS]), transcript_hits

    def _resolve_transcript_text(self, video_id: str, channel_name: str) -> str:
        cached = self._cache.get_usable_text(video_id, use_cache=self._use_cache)
        if cached is not None:
            self._stats["cache_hit"] += 1
            self._stats["success"] += 1
            print(f"  [transcript] cache hit: {video_id} ({channel_name})")
            return cached

        if self._blocked:
            self._stats["skipped"] += 1
            print(f"  [transcript] skipped (blocked): {video_id}")
            return ""

        if self._requests_this_run >= self._max_requests:
            self._stats["skipped"] += 1
            print(f"  [transcript] skipped (run limit): {video_id}")
            return ""

        delay = random.uniform(self._delay_min, self._delay_max)
        time.sleep(delay)

        text, error_code = self._fetch_transcript_network(video_id)
        self._requests_this_run += 1

        if error_code in ("IP_BLOCKED", "REQUEST_BLOCKED", "RATE_LIMITED"):
            self._blocked = True
            self._stats["blocked"] += 1
            self._stats["failed"] += 1
            self._stats["failure_reasons"][error_code] += 1
            self._cache.set_text(video_id, "", error=error_code)
            print(f"  [transcript] blocked: {video_id} -> {error_code}")
            return ""

        if text:
            self._stats["fetched"] += 1
            self._stats["success"] += 1
            self._cache.set_text(video_id, text)
            print(f"  [transcript] ok: {video_id} ({len(text)} chars)")
            return text

        self._stats["failed"] += 1
        self._stats["failure_reasons"][error_code or "NO_TRANSCRIPT"] += 1
        self._cache.set_text(video_id, "", error=error_code or "NO_TRANSCRIPT")
        print(f"  [transcript] fail: {video_id} -> {error_code}")
        return ""

    @staticmethod
    def _fetch_transcript_network(video_id: str) -> tuple[str, str]:
        try:
            api = YouTubeTranscriptApi()
            fetched = api.fetch(
                video_id,
                languages=["en", "en-US", "en-GB", "zh", "zh-Hans", "zh-CN"],
            )
            text = " ".join(snippet.text for snippet in fetched).lower()
            return text, ""
        except Exception as exc:
            code = classify_transcript_error(exc)
            if _is_blocked_error(exc):
                return "", code
            return "", code

    @staticmethod
    def _top_video_ids_by_views(
        record: CreatorRecord, limit: int
    ) -> list[str]:
        if record.recent_videos:
            sorted_videos = sorted(
                record.recent_videos,
                key=lambda v: v.get("views", 0),
                reverse=True,
            )
            return [
                v["video_id"]
                for v in sorted_videos[:limit]
                if v.get("video_id")
            ]

        return [record.video_id] if record.video_id else []

    @classmethod
    def _extract_keywords(cls, text: str) -> list[str]:
        found: list[str] = []

        for label, pattern in THEME_PHRASES:
            if re.search(pattern, text, re.IGNORECASE):
                found.append(label)

        tokens = re.findall(r"[a-z][a-z0-9]{2,}", text)
        token_counts = Counter(
            t for t in tokens if t not in STOPWORDS and len(t) >= 3
        )

        for term in GAME_TERMS:
            if term in token_counts and term not in found:
                found.append(term)

        for word, count in token_counts.most_common(8):
            if count >= 3 and word not in found:
                found.append(word)

        bigrams = cls._recurring_bigrams(tokens)
        for phrase in bigrams[:3]:
            if phrase not in found:
                found.append(phrase)

        seen: set[str] = set()
        unique: list[str] = []
        for item in found:
            key = item.lower()
            if key not in seen:
                seen.add(key)
                unique.append(item)
        return unique

    @staticmethod
    def _recurring_bigrams(tokens: list[str]) -> list[str]:
        pairs = [
            f"{tokens[i]} {tokens[i + 1]}"
            for i in range(len(tokens) - 1)
            if tokens[i] not in STOPWORDS and tokens[i + 1] not in STOPWORDS
        ]
        counts = Counter(pairs)
        return [p for p, c in counts.most_common(5) if c >= 2]
