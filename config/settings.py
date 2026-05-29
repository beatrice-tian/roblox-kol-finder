import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"


@dataclass(frozen=True)
class Settings:
    youtube_api_key: str = field(
        default_factory=lambda: os.getenv("YOUTUBE_API_KEY", "")
    )
    openai_api_key: str = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY", "")
    )
    openai_model: str = field(
        default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    )

    search_keywords: tuple[str, ...] = (
        "roblox",
        "roblox funny moments",
        "roblox shorts",
        "grow a garden roblox",
        "steal a brainrot roblox",
    )
    lookback_days: int = 7
    max_results_per_keyword: int = 20
    recent_videos_per_channel: int = 5
    max_subscribers: int = 100_000
    top_n: int = 10
    output_dir: Path = OUTPUT_DIR
    report_filename: str = "roblox_kol_report.csv"
    transcript_cache_path: Path = PROJECT_ROOT / "transcript_cache.json"
    transcript_top_videos_per_creator: int = field(
        default_factory=lambda: min(
            2,
            max(1, int(os.getenv("TRANSCRIPT_VIDEOS_PER_CREATOR", "2"))),
        )
    )
    transcript_max_requests_per_run: int = field(
        default_factory=lambda: int(os.getenv("TRANSCRIPT_MAX_REQUESTS", "20"))
    )
    transcript_delay_min: float = 2.5
    transcript_delay_max: float = 5.0
    transcript_enabled: bool = field(
        default_factory=lambda: os.getenv("TRANSCRIPT_ENABLED", "true").lower()
        in ("1", "true", "yes")
    )
    transcript_use_cache: bool = field(
        default_factory=lambda: os.getenv("TRANSCRIPT_USE_CACHE", "true").lower()
        in ("1", "true", "yes")
    )

    enabled_platforms: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            p.strip()
            for p in os.getenv("ENABLED_PLATFORMS", "youtube").split(",")
            if p.strip()
        )
    )


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
