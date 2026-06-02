from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Platform(str, Enum):
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"


@dataclass
class CreatorRecord:
    platform: Platform
    channel_id: str
    channel_name: str
    video_id: str
    video_title: str
    views: int
    likes: int
    subscribers: int
    published_at: str
    latest_video_id: str = ""
    latest_video_title: str = ""
    latest_views: int = 0
    latest_likes: int = 0
    representative_views: int = 0
    is_shorts: bool = False

    avg_views: int = 0
    avg_likes: int = 0
    avg_engagement_rate: float = 0.0
    consistency_score: float = 0.0
    viral_hit_record: str = ""
    videos_sampled: int = 0
    recent_views: list[int] = field(default_factory=list)
    recent_likes: list[int] = field(default_factory=list)
    recent_videos: list[dict] = field(default_factory=list)
    transcript_keywords: str = ""
    signal_coverage: str = "⚪ Metadata-only"

    views_per_sub: float = 0.0
    engagement_rate: float = 0.0
    potential_score: float = 0.0
    tier: str = ""
    creator_tier: str = ""
    archetype: str = ""
    rule_based_reason: str = ""
    ai_recommendation: str = ""
    scout_note: str = ""

    @property
    def video_url(self) -> str:
        if self.platform == Platform.YOUTUBE:
            return f"https://www.youtube.com/watch?v={self.video_id}"
        if self.platform == Platform.TIKTOK:
            return f"https://www.tiktok.com/@{self.channel_id}/video/{self.video_id}"
        return ""

    @property
    def channel_url(self) -> str:
        if self.platform == Platform.YOUTUBE:
            return f"https://www.youtube.com/channel/{self.channel_id}"
        if self.platform == Platform.TIKTOK:
            return f"https://www.tiktok.com/@{self.channel_id}"
        return ""

    def to_export_row(self, rank: int) -> dict[str, Any]:
        return {
            "排名": rank,
            "创作者": self.channel_name,
            "平台": self.platform.value,
            "榜单分层": self.creator_tier,
            "潜力等级": self.tier,
            "潜力分": self.potential_score,
            "粉丝数": self.subscribers,
            "平均播放": self.avg_views,
            "平均点赞": self.avg_likes,
            "互动率": self.avg_engagement_rate,
            "稳定度": self.consistency_score,
            "爆款记录": self.viral_hit_record,
            "代表视频": self.video_title,
            "代表视频播放": self.representative_views or self.views,
            "视频链接": self.video_url,
            "频道链接": self.channel_url,
            "Shorts占比": "是" if self.is_shorts else "否",
            "分析信号": _format_signal_coverage(self.signal_coverage),
            "字幕关键词": self.transcript_keywords,
            "运营观察": self.scout_note,
            "数据简评": self.rule_based_reason,
            "推荐原因": self.ai_recommendation,
            "发布时间": self.published_at,
        }


def _format_signal_coverage(value: str) -> str:
    labels = {
        "🧠 Transcript-backed": "🧠 字幕增强",
        "🟡 Partial transcript": "🟡 部分字幕",
        "⚪ Metadata-only": "⚪ 仅基础数据",
    }
    return labels.get(value, value or "⚪ 仅基础数据")
