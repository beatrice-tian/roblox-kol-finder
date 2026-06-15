"""Roblox KOL Finder 入口。"""

from config.network import apply_proxy_env
from config.settings import get_settings
from src.pipeline.finder import KolFinderPipeline


def main() -> None:
    settings = get_settings()
    proxy = apply_proxy_env(settings.proxy_url)
    if proxy:
        print(f"网络代理: {proxy}")
    else:
        print(
            "提示: 未配置 PROXY_URL。若 YouTube API 连接超时，"
            "请在 .env 添加 PROXY_URL=http://127.0.0.1:7897"
        )

    pipeline = KolFinderPipeline()
    _top, output_path = pipeline.run()
    print("\n完成！")
    print(f"报告已保存: {output_path}")


if __name__ == "__main__":
    main()
