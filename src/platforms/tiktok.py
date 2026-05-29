from config.settings import Settings
from src.models.creator import CreatorRecord, Platform
from src.platforms.base import PlatformClient


class TikTokClient(PlatformClient):
    """
    TikTok 采集器占位实现。

    后续可在此接入 TikTok Research API / 官方 Business API /
    或合规的第三方数据服务，实现与 YouTubeClient 相同的 search_creators 接口。
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def platform_name(self) -> str:
        return Platform.TIKTOK.value

    def validate_config(self) -> None:
        # 预留：TikTok API 密钥校验
        # token = os.getenv("TIKTOK_ACCESS_TOKEN")
        pass

    def search_creators(self, keywords: list[str]) -> list[CreatorRecord]:
        raise NotImplementedError(
            "TikTok 采集尚未实现。请在 .env 中保持 enabled_platforms 仅含 youtube，"
            "或实现 TikTokClient.search_creators 后启用 tiktok。"
        )
