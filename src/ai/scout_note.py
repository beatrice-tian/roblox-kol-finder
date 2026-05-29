from openai import OpenAI

from config.settings import Settings
from src.ai.recommender import DEFAULT_OPENAI_MODEL
from src.models.creator import CreatorRecord

MAX_SCOUT_NOTE_CHARS = 200

SYSTEM_PROMPT = """你是 Roblox 发行团队的 creator strategist，写内部 Scout Note（1~2句话）。

风格：
- 全中文，总共不超过 80 字（1~2句）
- 像 Slack 里给同事的 quick take：有观点、口语化一点，但专业
- 回答「为什么这个 creator 值得/不值得跟进」的内容方向
- 禁止复述具体数字（播放、粉丝、百分比等）
- 禁止套话：「值得关注」「潜力巨大」「建议观察」「综上所述」
- 不要像 ChatGPT 总结或分点列表
- 不要重复 AI 合作建议里的原句

可参考内容形态（Shorts/长视频）和稳定性印象，用定性说法。"""


class ScoutNoteGenerator:
    """生成 1~2 句 Scout Note，用于 scouting brief。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model = DEFAULT_OPENAI_MODEL
        self._client: OpenAI | None = None
        if settings.openai_api_key:
            self._client = OpenAI(api_key=settings.openai_api_key)

    @property
    def is_available(self) -> bool:
        return self._client is not None

    def enrich_notes(self, records: list[CreatorRecord]) -> list[CreatorRecord]:
        for record in records:
            record.scout_note = self.generate_for(record)
        return records

    def generate_for(self, record: CreatorRecord) -> str:
        if not self._client:
            return self._fallback_note(record)

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": self._build_prompt(record)},
                ],
                temperature=0.55,
                max_tokens=120,
            )
            text = (response.choices[0].message.content or "").strip()
            return self._normalize(text) or self._fallback_note(record)
        except Exception:
            return self._fallback_note(record)

    def _build_prompt(self, record: CreatorRecord) -> str:
        rep_views = record.representative_views or record.views
        stability = (
            "播放较稳"
            if record.consistency_score >= 50
            else "爆款波动大"
            if record.consistency_score < 30
            else "稳定性一般"
        )
        return (
            f"创作者: {record.channel_name}\n"
            f"代表视频: {record.video_title}\n"
            f"代表视频播放量: {rep_views:,}\n"
            f"近作平均播放: {record.avg_views:,}\n"
            f"稳定性印象: {stability} (consistency_score={record.consistency_score})\n"
            f"是否 Shorts 为主: {'是' if record.is_shorts else '否'}\n"
            f"分析信号: {record.signal_coverage}\n"
            f"字幕关键词: {record.transcript_keywords or '无（metadata-only）'}\n"
            f"已有 AI 合作建议（勿复述）:\n{record.ai_recommendation[:400]}\n"
            "写 1~2 句 Scout Note。"
        )

    @staticmethod
    def _normalize(text: str) -> str:
        cleaned = " ".join(text.split())
        cleaned = cleaned.replace("Scout Note：", "").replace("Scout Note:", "")
        if len(cleaned) <= MAX_SCOUT_NOTE_CHARS:
            return cleaned
        return cleaned[: MAX_SCOUT_NOTE_CHARS - 1] + "…"

    @staticmethod
    def _fallback_note(record: CreatorRecord) -> str:
        if record.is_shorts:
            return "短视频节奏快，适合活动预热和梗向传播，但需盯后续是否还能持续出片。"
        if record.consistency_score >= 50:
            return "近作表现相对稳，更像可持续带量的合作对象，而不是赌单条爆款。"
        if record.consistency_score < 30:
            return "有明显爆款能力，但波动偏大，更适合短期话题合作而非长线绑定。"
        return "内容方向偏泛 Roblox 娱乐，合作前建议先看代表作是否和游戏调性对得上。"
