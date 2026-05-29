import sys
from pathlib import Path

from config.settings import Settings
from src.analysis.archetype import ArchetypeTagger
from src.analysis.transcript import TranscriptKeywordExtractor
from src.ai.recommender import AIRecommender
from src.ai.scout_note import ScoutNoteGenerator
from src.export.csv_report import CsvReportExporter
from src.models.creator import CreatorRecord
from src.platforms.base import PlatformClient
from src.platforms.tiktok import TikTokClient
from src.platforms.youtube import YouTubeClient
from src.scoring.scorer import CreatorScorer


class KolFinderPipeline:
    """端到端：多平台采集 → 评分 → AI 建议 → 导出报告。"""

    def __init__(self, settings: Settings | None = None) -> None:
        from config.settings import get_settings

        self._settings = settings or get_settings()
        self._scorer = CreatorScorer(
            max_subscribers=self._settings.max_subscribers
        )
        self._ai = AIRecommender(self._settings)
        self._scout_note = ScoutNoteGenerator(self._settings)
        self._archetype = ArchetypeTagger()
        self._transcript = TranscriptKeywordExtractor()
        self._exporter = CsvReportExporter()

    def run(self) -> tuple[list[CreatorRecord], Path]:
        all_records: list[CreatorRecord] = []

        for client in self._build_platform_clients():
            print(f"\n正在从 {client.platform_name} 采集创作者…")
            client.validate_config()
            keywords = list(self._settings.search_keywords)
            records = client.search_creators(keywords)
            print(f"  获取 {len(records)} 条频道样本")
            all_records.extend(records)

        eligible = self._scorer.filter_eligible(all_records)
        print(f"\n符合粉丝上限（<{self._settings.max_subscribers:,}）的创作者: {len(eligible)}")

        tier1_count = len(self._scorer.filter_quality_gate(eligible))
        print(f"Tier 1（高质量）创作者: {tier1_count}")

        top = self._scorer.build_top_creators(
            eligible, top_n=self._settings.top_n
        )
        tier2_in_top = sum(1 for r in top if r.creator_tier == "Tier 2")
        print(
            f"最终榜单: {len(top)} 人 "
            f"(Tier 1: {len(top) - tier2_in_top}, Tier 2 补充: {tier2_in_top})"
        )

        self._archetype.tag_all(top)

        from config.settings import get_settings

        settings = get_settings()
        if settings.transcript_enabled:
            print(
                "\n正在安全拉取字幕（每 creator 最高播放 "
                f"{settings.transcript_top_videos_per_creator} 条，"
                f"上限 {settings.transcript_max_requests_per_run} 次网络请求）…"
            )
        else:
            print("\n字幕分析已关闭（TRANSCRIPT_ENABLED=false）…")
        self._transcript.enrich_all(top)
        with_keywords = sum(1 for r in top if r.transcript_keywords)
        transcript_backed = sum(
            1 for r in top if "Transcript-backed" in r.signal_coverage
        )
        partial = sum(1 for r in top if "Partial transcript" in r.signal_coverage)
        print(
            f"  字幕关键词: {with_keywords}/{len(top)} | "
            f"字幕增强: {transcript_backed}/{len(top)} | "
            f"部分字幕: {partial}/{len(top)}"
        )

        if self._ai.is_available:
            print("\n正在生成 AI 合作建议…")
            self._ai.enrich_recommendations(top)
        else:
            print("\n未配置 OPENAI_API_KEY，将使用规则模板生成建议。")
            for record in top:
                record.ai_recommendation = self._ai.generate_for(record)

        print("\n正在生成 Scout Note…")
        self._scout_note.enrich_notes(top)

        self._print_summary(top)

        output_path = self._settings.output_dir / self._settings.report_filename
        self._exporter.export(top, output_path)
        self._export_web_data(output_path)
        return top, output_path

    def _export_web_data(self, csv_path: Path) -> None:
        try:
            from src.web.data_export import export_web_data

            json_path = Path(__file__).resolve().parents[2] / "web" / "data" / "report.json"
            export_web_data(csv_path, json_path)
            self._safe_print(f"Web 情报流数据已更新: {json_path}")
        except Exception as exc:
            self._safe_print(f"Web 数据导出跳过: {exc}")

    def _build_platform_clients(self) -> list[PlatformClient]:
        clients: list[PlatformClient] = []
        enabled = set(self._settings.enabled_platforms)

        if "youtube" in enabled:
            clients.append(YouTubeClient(self._settings))
        if "tiktok" in enabled:
            clients.append(TikTokClient(self._settings))

        if not clients:
            raise ValueError(
                "enabled_platforms 为空。请在 config/settings.py 或环境变量中启用至少一个平台。"
            )
        return clients

    @staticmethod
    def _safe_print(text: str) -> None:
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        safe = text.encode(encoding, errors="replace").decode(encoding)
        print(safe)

    def _print_summary(self, records: list[CreatorRecord]) -> None:
        self._safe_print("\n" + "=" * 60)
        self._safe_print("Roblox 潜力创作者 TOP 列表")
        self._safe_print("=" * 60)

        for idx, record in enumerate(records, start=1):
            self._safe_print(
                f"\n#{idx} {record.channel_name} "
                f"[{record.tier}] {record.creator_tier}"
            )
            self._safe_print(
                f"  平台: {record.platform.value} | 粉丝: {record.subscribers:,}"
            )
            self._safe_print(
                f"  播放: {record.views:,} | 潜力分: {record.potential_score}"
            )
            rep_title = record.video_title
            if len(rep_title) > 60:
                rep_title = rep_title[:60] + "…"
            self._safe_print(f"  代表视频: {rep_title}")
            latest = record.latest_video_title
            if latest and latest != record.video_title:
                if len(latest) > 50:
                    latest = latest[:50] + "…"
                self._safe_print(f"  最新视频: {latest}")
            note = record.scout_note
            if len(note) > 100:
                note = note[:100] + "…"
            self._safe_print(f"  Scout: {note}")
            self._safe_print(f"  规则: {record.rule_based_reason}")
            ai = record.ai_recommendation
            if len(ai) > 120:
                ai = ai[:120] + "…"
            self._safe_print(f"  AI: {ai}")
