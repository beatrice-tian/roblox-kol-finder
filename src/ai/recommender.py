from openai import OpenAI

from config.settings import Settings
from src.models.creator import CreatorRecord

DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
MAX_NOTE_CHARS = 280

SYSTEM_PROMPT = """你是 Roblox 发行/市场团队的 KOL scouting 分析师。
根据真实数据写「内部 scouting note」，给同事快速判断是否值得跟进。

写作要求：
- 全中文，总长度不超过 220 字
- 像同事在 Slack 里发的备注：具体、直接、有判断
- 禁止套话（如「值得关注」「潜力巨大」「建议进一步观察」等空泛句）
- 必须基于提供的数据推断，数据弱的地方一句话带过，不要编造具体数字
- 用 4 行输出，每行以固定标签开头（不要编号、不要 markdown）：
  值得关注｜…
  玩家群体｜…
  适合游戏｜…
  潜力判断｜是/否/偏早期 + 一句理由"""


class AIRecommender:
    """基于 LLM 生成 Roblox KOL scouting 推荐理由。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model = DEFAULT_OPENAI_MODEL
        self._client: OpenAI | None = None
        if settings.openai_api_key:
            self._client = OpenAI(api_key=settings.openai_api_key)

    @property
    def is_available(self) -> bool:
        return self._client is not None

    def enrich_recommendations(
        self, records: list[CreatorRecord]
    ) -> list[CreatorRecord]:
        for record in records:
            record.ai_recommendation = self.generate_for(record)
        return records

    def generate_for(self, record: CreatorRecord) -> str:
        if not self._client:
            return self._fallback_recommendation(record, no_api_key=True)

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": self._build_prompt(record)},
                ],
                temperature=0.45,
                max_tokens=220,
            )
            text = (response.choices[0].message.content or "").strip()
            text = self._normalize_note(text)
            if text:
                return text
            return self._fallback_recommendation(record)
        except Exception as exc:
            return (
                f"{self._fallback_recommendation(record)} "
                f"（AI 调用失败: {_short_error(exc)}）"
            )

    def _build_prompt(self, record: CreatorRecord) -> str:
        return (
            f"平台: {record.platform.value}\n"
            f"频道: {record.channel_name}\n"
            f"粉丝: {record.subscribers:,}\n"
            f"代表视频(近{record.videos_sampled}条中播放最高): "
            f"{record.video_title}\n"
            f"代表视频数据: 播放 {record.representative_views:,} | "
            f"点赞 {record.likes:,}\n"
            f"最新视频: {record.latest_video_title or '无'}\n"
            f"最新单条: 播放 {record.latest_views:,} | 点赞 {record.latest_likes:,}\n"
            f"近{record.videos_sampled}条均值: 播放 {record.avg_views:,} | "
            f"点赞 {record.avg_likes:,} | 平均互动率 {record.avg_engagement_rate}%\n"
            f"稳定性分: {record.consistency_score} | 播放/粉丝比(均值): {record.views_per_sub}\n"
            f"系统潜力分: {record.potential_score} | 等级: {record.tier} | "
            f"榜单分层: {record.creator_tier or '未分级'}\n"
            f"内容形态: {'Shorts 为主' if record.is_shorts else '长视频/综剪为主'}\n"
            f"规则引擎摘要: {record.rule_based_reason or '无'}\n"
            f"分析信号: {record.signal_coverage}\n"
            f"字幕关键词(transcript_keywords): "
            f"{record.transcript_keywords or '无（metadata-only）'}\n"
            "请结合标题、metadata、播放结构与字幕关键词写判断；"
            "有字幕时以 transcript 为准；无字幕时明确标注依据为标题/metadata。"
        )

    @staticmethod
    def _normalize_note(text: str) -> str:
        cleaned = " ".join(text.split())
        if len(cleaned) <= MAX_NOTE_CHARS:
            return cleaned
        return cleaned[: MAX_NOTE_CHARS - 1] + "…"

    @staticmethod
    def _fallback_recommendation(
        record: CreatorRecord, *, no_api_key: bool = False
    ) -> str:
        shorts = "Shorts" if record.is_shorts else "长视频"
        lines = [
            f"值得关注｜{record.channel_name} 近作 {record.views:,} 播放，"
            f"播放/粉 {record.views_per_sub}，{record.rule_based_reason or '数据待复核'}",
            f"玩家群体｜偏 {shorts} 消费的 Roblox 泛娱乐受众（按标题推断）",
            f"适合游戏｜休闲社交 / 梗向 Simulator 类更易匹配（需人工看视频确认）",
            f"潜力判断｜{'是' if record.tier in ('极高', '高') else '偏早期'}，"
            f"系统等级 {record.tier}，潜力分 {record.potential_score}",
        ]
        note = " ".join(lines)
        if no_api_key:
            note += " （未配置 OPENAI_API_KEY）"
        return note


def _short_error(exc: Exception) -> str:
    text = str(exc)
    if "insufficient_quota" in text or "429" in text:
        return "OpenAI 配额不足"
    if len(text) > 80:
        return text[:80] + "…"
    return text
