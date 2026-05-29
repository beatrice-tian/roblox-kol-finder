import statistics
from dataclasses import dataclass

from src.models.creator import CreatorRecord


@dataclass(frozen=True)
class ScoringWeights:
    reach: float = 0.50
    engagement: float = 0.20
    consistency: float = 0.30


@dataclass(frozen=True)
class TierThresholds:
    very_high: float = 38.0
    high: float = 22.0
    medium: float = 10.0


@dataclass(frozen=True)
class EngagementTierCeiling:
    """互动率决定潜力等级上限（资格项，不仅是加分）。"""

    max_tier_below: float = 0.5
    max_tier_medium: float = 1.0
    max_tier_high: float = 2.5


TIER_RANK = {"低": 0, "中": 1, "高": 2, "极高": 3}


@dataclass(frozen=True)
class QualityGateThresholds:
    min_avg_views: int = 5_000
    min_subscribers: int = 1_000
    min_total_recent_views: int = 30_000
    min_peak_video_views: int = 20_000
    min_avg_engagement_rate: float = 1.0


@dataclass(frozen=True)
class PotentialGateThresholds:
    """Tier 2：潜力型 hidden gem，门槛放宽但仍需增长信号。"""

    min_avg_views: int = 1_500
    min_subscribers: int = 500
    min_total_recent_views: int = 8_000
    min_peak_video_views: int = 5_000
    min_avg_engagement_rate: float = 0.5
    min_views_per_sub: float = 8.0
    min_potential_score: float = 4.0


class CreatorScorer:
    """Roblox 创作者潜力评分与分级（基于近 N 条视频均值 + 稳定性）。"""

    def __init__(
        self,
        weights: ScoringWeights | None = None,
        tiers: TierThresholds | None = None,
        max_subscribers: int = 100_000,
        early_stage_subscribers: int = 10_000,
        reach_cap: float = 120.0,
        quality_gate: QualityGateThresholds | None = None,
        potential_gate: PotentialGateThresholds | None = None,
        engagement_ceiling: EngagementTierCeiling | None = None,
    ) -> None:
        self._weights = weights or ScoringWeights()
        self._tiers = tiers or TierThresholds()
        self._engagement_ceiling = engagement_ceiling or EngagementTierCeiling()
        self._quality_gate = quality_gate or QualityGateThresholds()
        self._potential_gate = potential_gate or PotentialGateThresholds()
        self._max_subscribers = max_subscribers
        self._early_stage_subscribers = early_stage_subscribers
        self._reach_cap = reach_cap

    def filter_eligible(self, records: list[CreatorRecord]) -> list[CreatorRecord]:
        return [r for r in records if r.subscribers < self._max_subscribers]

    def filter_quality_gate(
        self, records: list[CreatorRecord]
    ) -> list[CreatorRecord]:
        return [r for r in records if self.passes_quality_gate(r)]

    def build_top_creators(
        self, records: list[CreatorRecord], top_n: int = 10
    ) -> list[CreatorRecord]:
        """优先 Tier 1，不足时用 Tier 2 补足至 top_n。"""
        self.score_all(records)

        tier1 = [r for r in records if self.passes_quality_gate(r)]
        for record in tier1:
            record.creator_tier = "Tier 1"

        tier1_ranked = self.rank(tier1)
        if len(tier1_ranked) >= top_n:
            return tier1_ranked[:top_n]

        used_keys = {self._record_key(r) for r in tier1_ranked}
        remaining_slots = top_n - len(tier1_ranked)

        tier2_pool = [
            r
            for r in records
            if self._record_key(r) not in used_keys and self.passes_potential_gate(r)
        ]
        for record in tier2_pool:
            record.creator_tier = "Tier 2"
            self._append_tier2_reason(record)

        tier2_ranked = self.rank(tier2_pool)
        combined = tier1_ranked + tier2_ranked[:remaining_slots]

        if len(combined) < top_n:
            used_keys = {self._record_key(r) for r in combined}
            fallback = [
                r for r in records if self._record_key(r) not in used_keys
            ]
            for record in fallback:
                record.creator_tier = "Tier 2"
                self._append_tier2_reason(record)
            combined.extend(self.rank(fallback)[: top_n - len(combined)])

        final = combined[:top_n]
        self._cap_low_tier_count(final, max_low=3)
        return final

    def passes_quality_gate(self, record: CreatorRecord) -> bool:
        gate = self._quality_gate
        metrics = self._recent_metrics(record)
        return (
            record.avg_views >= gate.min_avg_views
            and record.subscribers >= gate.min_subscribers
            and metrics["total_views"] >= gate.min_total_recent_views
            and metrics["peak_views"] >= gate.min_peak_video_views
            and metrics["engagement"] >= gate.min_avg_engagement_rate
        )

    def passes_potential_gate(self, record: CreatorRecord) -> bool:
        if self.passes_quality_gate(record):
            return False

        gate = self._potential_gate
        metrics = self._recent_metrics(record)
        views_per_sub = record.avg_views / max(record.subscribers, 1)

        return (
            record.avg_views >= gate.min_avg_views
            and record.subscribers >= gate.min_subscribers
            and metrics["total_views"] >= gate.min_total_recent_views
            and metrics["peak_views"] >= gate.min_peak_video_views
            and metrics["engagement"] >= gate.min_avg_engagement_rate
            and views_per_sub >= gate.min_views_per_sub
            and record.potential_score >= gate.min_potential_score
        )

    @staticmethod
    def _record_key(record: CreatorRecord) -> str:
        return record.channel_id or record.channel_name

    @staticmethod
    def _append_tier2_reason(record: CreatorRecord) -> None:
        prefix = "潜力型 hidden gem（Tier 2）"
        if prefix not in record.rule_based_reason:
            record.rule_based_reason = (
                f"{prefix}；{record.rule_based_reason}"
                if record.rule_based_reason
                else prefix
            )

    def _recent_metrics(self, record: CreatorRecord) -> dict[str, float]:
        recent_views = record.recent_views or []
        total_views = sum(recent_views)
        peak_views = max(recent_views) if recent_views else 0
        engagement = record.avg_engagement_rate
        if engagement <= 0 and record.avg_views > 0:
            engagement = (record.avg_likes / record.avg_views) * 100
        return {
            "total_views": float(total_views),
            "peak_views": float(peak_views),
            "engagement": engagement,
        }

    def score_all(self, records: list[CreatorRecord]) -> list[CreatorRecord]:
        for record in records:
            self._apply_scores(record)
        return records

    def rank(
        self, records: list[CreatorRecord], top_n: int | None = None
    ) -> list[CreatorRecord]:
        sorted_records = sorted(
            records,
            key=lambda r: r.potential_score,
            reverse=True,
        )
        if top_n is not None:
            return sorted_records[:top_n]
        return sorted_records

    def _apply_scores(self, record: CreatorRecord) -> None:
        subs = max(record.subscribers, 1)
        avg_views = max(record.avg_views, 0)
        avg_likes = max(record.avg_likes, 0)

        if record.avg_engagement_rate > 0:
            avg_engagement = record.avg_engagement_rate
        elif avg_views > 0:
            avg_engagement = (avg_likes / avg_views) * 100
        else:
            avg_engagement = 0.0

        record.avg_engagement_rate = round(avg_engagement, 2)
        record.consistency_score = self._compute_consistency_score(
            record.recent_views
        )

        views_per_sub = avg_views / subs
        reach_component = min(views_per_sub, self._reach_cap)

        viral_penalty = self._viral_penalty(record.recent_views, avg_views)
        low_perf_penalty = self._low_performance_penalty(avg_views, subs)

        raw_score = (
            reach_component * self._weights.reach
            + avg_engagement * self._weights.engagement
            + record.consistency_score * self._weights.consistency
        )
        engagement_penalty = self._engagement_score_penalty(avg_engagement)
        potential_score = (
            raw_score * viral_penalty * low_perf_penalty * engagement_penalty
        )

        record.views_per_sub = round(views_per_sub, 2)
        record.engagement_rate = record.avg_engagement_rate
        record.potential_score = round(potential_score, 2)
        raw_tier = self._tier_label(potential_score)
        record.tier = self._apply_engagement_tier_ceiling(
            raw_tier, avg_engagement
        )
        record.rule_based_reason = self._build_rule_reason(record)

    @staticmethod
    def _compute_consistency_score(views: list[int]) -> float:
        if len(views) < 2:
            return 50.0

        mean_views = statistics.mean(views)
        if mean_views <= 0:
            return 0.0

        if len(views) == 2:
            spread = abs(views[0] - views[1]) / 2
        else:
            spread = statistics.stdev(views)

        cv = spread / mean_views
        score = 100 * max(0.0, 1.0 - min(cv / 1.2, 1.0))
        return round(score, 2)

    @staticmethod
    def _viral_penalty(views: list[int], avg_views: float) -> float:
        """Roblox 生态常见爆款波动，仅轻度降权，最低系数 0.9。"""
        if not views or avg_views <= 0:
            return 1.0
        peak_ratio = max(views) / avg_views
        if peak_ratio <= 3.0:
            return 1.0
        return max(0.9, 1.0 - (peak_ratio - 3.0) * 0.02)

    def _cap_low_tier_count(
        self, records: list[CreatorRecord], max_low: int = 3
    ) -> None:
        """最终榜单中「低」不超过 max_low，优先保留潜力分更高者的低档位。"""
        low_records = [r for r in records if r.tier == "低"]
        if len(low_records) <= max_low:
            return

        low_records.sort(key=lambda r: r.potential_score)
        for record in low_records[max_low:]:
            record.tier = "中"

    @staticmethod
    def _low_performance_penalty(avg_views: float, subscribers: int) -> float:
        ratio = avg_views / max(subscribers, 1)
        if ratio < 0.5:
            return 0.82
        if ratio < 2.0:
            return 0.92
        return 1.0

    def _tier_label(self, score: float) -> str:
        if score > self._tiers.very_high:
            return "极高"
        if score > self._tiers.high:
            return "高"
        if score > self._tiers.medium:
            return "中"
        return "低"

    def _engagement_tier_cap(self, engagement: float) -> str:
        ceiling = self._engagement_ceiling
        if engagement < ceiling.max_tier_below:
            return "低"
        if engagement < ceiling.max_tier_medium:
            return "中"
        if engagement < ceiling.max_tier_high:
            return "高"
        return "极高"

    def _apply_engagement_tier_ceiling(
        self, raw_tier: str, engagement: float
    ) -> str:
        cap = self._engagement_tier_cap(engagement)
        if TIER_RANK[raw_tier] > TIER_RANK[cap]:
            return cap
        return raw_tier

    @staticmethod
    def _engagement_score_penalty(engagement: float) -> float:
        if engagement < 0.5:
            return 0.78
        if engagement < 1.0:
            return 0.88
        if engagement < 2.0:
            return 0.94
        return 1.0

    def _build_rule_reason(self, record: CreatorRecord) -> str:
        reasons: list[str] = []

        if record.views_per_sub > 20:
            reasons.append("近作平均播放相对粉丝数表现突出")
        if record.avg_engagement_rate > 3:
            reasons.append("近作平均互动率较好")
        elif record.avg_engagement_rate < 1.0:
            reasons.append("互动率偏低，播放含金量有限")
        elif record.avg_engagement_rate < 2.5:
            reasons.append("互动率一般，潜力等级设上限")
        if record.consistency_score >= 70:
            reasons.append("近5条视频播放表现较稳定")
        elif record.consistency_score < 40:
            reasons.append("近作播放波动大，可能存在单条爆款拉动")
        if record.subscribers < self._early_stage_subscribers:
            reasons.append("仍处于早期成长阶段")
        if record.is_shorts:
            reasons.append("内容以 Shorts 为主，适合短视频合作")

        return "；".join(reasons) if reasons else "数据表现平稳，可进一步观察"
