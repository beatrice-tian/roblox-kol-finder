"""出站 HTTP(S) 代理（Clash Verge 等）。"""

from __future__ import annotations

import os

import httplib2

_PROXY_ENV_KEYS = ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy")


def resolve_proxy_url(explicit: str | None = None) -> str:
    if explicit and explicit.strip():
        return explicit.strip()
    for key in ("PROXY_URL", "HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY"):
        val = os.getenv(key, "").strip()
        if val:
            return val
    return ""


def apply_proxy_env(proxy_url: str | None = None) -> str:
    """将代理写入 HTTP(S)_PROXY，供 OpenAI 等库使用。返回生效的代理 URL。"""
    url = resolve_proxy_url(proxy_url)
    if not url:
        return ""
    for key in _PROXY_ENV_KEYS:
        if not os.getenv(key):
            os.environ[key] = url
    return url


def _proxy_info_from_url(proxy_url: str) -> httplib2.ProxyInfo:
    return httplib2.proxy_info_from_url(proxy_url)


def build_google_http(proxy_url: str | None = None, timeout: int = 60) -> httplib2.Http | None:
    """googleapiclient 专用：显式注入 httplib2 代理（Windows 上比仅靠环境变量更可靠）。"""
    url = resolve_proxy_url(proxy_url)
    if not url:
        return None
    if httplib2.socks is None:
        raise RuntimeError(
            "已配置 PROXY_URL，但未安装 PySocks，httplib2 无法走代理。"
            "请运行: python -m pip install PySocks"
        )
    return httplib2.Http(
        proxy_info=_proxy_info_from_url(url),
        timeout=timeout,
    )


def build_transcript_api(proxy_url: str | None = None):
    """youtube-transcript-api 实例；与 YouTube Data API 一样需显式走代理。"""
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api.proxies import GenericProxyConfig

    url = resolve_proxy_url(proxy_url)
    if not url:
        return YouTubeTranscriptApi()
    proxy_config = GenericProxyConfig(http_url=url, https_url=url)
    return YouTubeTranscriptApi(proxy_config=proxy_config)
