from src.models.creator import CreatorRecord

ARCHETYPE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Anime RPG",
        (
            "blox fruits",
            "bloxfruits",
            "blox fruit",
            "sailor piece",
            "one piece",
            "fruit",
            "leveling",
            "levelling",
            "raids",
            "raid",
            "boss fight",
            "boss",
            "build",
            "stats",
            "gear",
            "dungeon",
            "quest",
            "grinding",
            "progression",
            "third sea",
            "second sea",
        ),
    ),
    (
        "Meme Shorts",
        (
            "meme",
            "memes",
            "funny",
            "brainrot",
            "steal a brainrot",
            "cursed",
            "#shorts",
            "shorts",
            "viral",
            "plsgoviral",
            "robux",
            "gangsta",
        ),
    ),
    (
        "Simulator Grinder",
        (
            "simulator",
            "grinding",
            "grind",
            "farm",
            "farming",
            "tycoon",
            "afk",
            "idle",
            "grow a garden",
            "pet sim",
        ),
    ),
    (
        "RP Creator",
        (
            "brookhaven",
            " roleplay",
            "roleplay",
            " rp",
            "#rp",
            "adopt me",
            "life sim",
        ),
    ),
    (
        "Anime PvP",
        (
            "anime",
            "battlegrounds",
            "fighting",
            "pvp",
            "jjs",
            "jailbreak",
            "combat",
            "battles",
        ),
    ),
    (
        "Chaos / Trolling",
        (
            "trolling",
            "troll",
            "chaos",
            "admin abuse",
            "hacker",
            "hackers",
            "sab",
            "sabotage",
        ),
    ),
)

DEFAULT_ARCHETYPE = "Variety Roblox"


class ArchetypeTagger:
    """基于标题与频道名的规则型 Roblox 创作者 archetype 标注。"""

    def tag(self, record: CreatorRecord) -> str:
        text = self._build_text(record)
        archetype = self._classify(text)
        record.archetype = archetype
        return archetype

    def tag_all(self, records: list[CreatorRecord]) -> list[CreatorRecord]:
        for record in records:
            self.tag(record)
        return records

    @staticmethod
    def _build_text(record: CreatorRecord) -> str:
        parts = [
            record.channel_name,
            record.video_title,
            record.latest_video_title,
        ]
        return " ".join(p for p in parts if p).lower()

    @classmethod
    def _classify(cls, text: str) -> str:
        best_name = DEFAULT_ARCHETYPE
        best_score = 0

        for name, keywords in ARCHETYPE_RULES:
            score = sum(1 for keyword in keywords if keyword in text)
            if score > best_score:
                best_score = score
                best_name = name

        return best_name
