"""通过 YouTube Data API 拉取频道高清头像。"""

from __future__ import annotations

from googleapiclient.discovery import build

from config.network import apply_proxy_env, build_google_http

_BATCH_SIZE = 50


def _pick_avatar_url(thumbnails: dict) -> str:
    for key in ("high", "medium", "default"):
        entry = thumbnails.get(key) or {}
        url = entry.get("url") if isinstance(entry, dict) else None
        if url:
            return str(url)
    return ""


def fetch_channel_avatars(
    channel_ids: list[str],
    api_key: str,
    proxy_url: str = "",
) -> dict[str, str]:
    """返回 channel_id -> 最高可用分辨率头像 URL。"""
    unique = [cid for cid in dict.fromkeys(channel_ids) if cid]
    if not unique or not api_key:
        return {}

    apply_proxy_env(proxy_url)
    build_kwargs: dict = {"developerKey": api_key}
    http = build_google_http(proxy_url)
    if http is not None:
        build_kwargs["http"] = http
    service = build("youtube", "v3", **build_kwargs)
    result: dict[str, str] = {}

    for i in range(0, len(unique), _BATCH_SIZE):
        batch = unique[i : i + _BATCH_SIZE]
        response = (
            service.channels()
            .list(part="snippet", id=",".join(batch))
            .execute()
        )
        for item in response.get("items", []):
            cid = item.get("id", "")
            snippet = item.get("snippet") or {}
            thumbs = snippet.get("thumbnails") or {}
            url = _pick_avatar_url(thumbs)
            if cid and url:
                result[cid] = url

    return result
