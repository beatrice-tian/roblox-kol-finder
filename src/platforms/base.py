from abc import ABC, abstractmethod

from src.models.creator import CreatorRecord


class PlatformClient(ABC):
    """各内容平台采集器的统一接口，便于后续接入 TikTok 等。"""

    @property
    @abstractmethod
    def platform_name(self) -> str:
        pass

    @abstractmethod
    def search_creators(self, keywords: list[str]) -> list[CreatorRecord]:
        """按关键词搜索并返回创作者样本（每个频道一条代表记录）。"""
        pass

    def validate_config(self) -> None:
        """子类可覆盖：启动前检查 API 密钥等配置。"""
        return
