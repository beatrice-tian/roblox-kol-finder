"""快速检测 YouTube API 是否可通过代理连通。"""
from __future__ import annotations

import sys

from config.network import apply_proxy_env, build_google_http
from config.settings import get_settings
from googleapiclient.discovery import build


def main() -> int:
    settings = get_settings()
    if not settings.youtube_api_key:
        print("缺少 YOUTUBE_API_KEY")
        return 1

    proxy = apply_proxy_env(settings.proxy_url)
    if proxy:
        print(f"代理: {proxy}")
    else:
        print("未配置 PROXY_URL / HTTP_PROXY（直连 Google）")

    build_kwargs: dict = {"developerKey": settings.youtube_api_key}
    http = build_google_http(settings.proxy_url)
    if http is not None:
        build_kwargs["http"] = http

    service = build("youtube", "v3", **build_kwargs)
    try:
        response = (
            service.search()
            .list(part="snippet", q="roblox", type="video", maxResults=1)
            .execute()
        )
        count = len(response.get("items", []))
        print(f"YouTube API 连通成功，返回 {count} 条结果")
        return 0
    except Exception as exc:
        print(f"YouTube API 失败: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
