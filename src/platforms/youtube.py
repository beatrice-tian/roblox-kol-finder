import time
from datetime import datetime, timedelta, timezone
from statistics import mean

from googleapiclient.discovery import build

from config.settings import Settings
from src.models.creator import CreatorRecord, Platform
from src.platforms.base import PlatformClient

_BATCH_SIZE = 50


class YouTubeClient(PlatformClient):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._service = build(
            "youtube",
            "v3",
            developerKey=settings.youtube_api_key,
        )

    @property
    def platform_name(self) -> str:
        return Platform.YOUTUBE.value

    def validate_config(self) -> None:
        if not self._settings.youtube_api_key:
            raise ValueError("缺少 YOUTUBE_API_KEY，请在 .env 中配置。")

    def search_creators(self, keywords: list[str]) -> list[CreatorRecord]:
        snippets: list[dict] = []

        for keyword in keywords:
            snippets.extend(
                self._search_video_snippets(
                    keyword,
                    self._settings.max_results_per_keyword,
                )
            )

        if not snippets:
            return []

        channels: dict[str, str] = {}
        for s in snippets:
            cid = s["channel_id"]
            if cid:
                channels[cid] = s["channel_name"]

        if not channels:
            return []

        sample_size = self._settings.recent_videos_per_channel
        channel_details = self._fetch_channel_details(list(channels.keys()))
        channel_videos: dict[str, list[dict]] = {}
        all_video_ids: list[str] = []

        for channel_id, details in channel_details.items():
            playlist_id = details.get("uploads_playlist_id")
            if not playlist_id:
                continue
            recent = self._fetch_playlist_recent_videos(
                playlist_id, sample_size
            )
            if not recent:
                continue
            channel_videos[channel_id] = recent
            all_video_ids.extend(v["video_id"] for v in recent)
            time.sleep(0.05)

        if not all_video_ids:
            return []

        video_stats = self._fetch_video_stats(all_video_ids)

        records: list[CreatorRecord] = []
        for channel_id, videos in channel_videos.items():
            record = self._build_channel_record(
                channel_id=channel_id,
                channel_name=channels[channel_id],
                videos=videos,
                video_stats=video_stats,
                subscribers=channel_details.get(channel_id, {}).get(
                    "subscribers", 0
                ),
            )
            if record is not None:
                records.append(record)

        return records

    def _build_channel_record(
        self,
        channel_id: str,
        channel_name: str,
        videos: list[dict],
        video_stats: dict[str, dict[str, int]],
        subscribers: int,
    ) -> CreatorRecord | None:
        views_list: list[int] = []
        likes_list: list[int] = []
        engagement_rates: list[float] = []
        valid_videos: list[tuple[dict, dict[str, int]]] = []

        for video in videos:
            stats = video_stats.get(video["video_id"])
            if not stats:
                continue
            views = stats["views"]
            likes = stats["likes"]
            views_list.append(views)
            likes_list.append(likes)
            valid_videos.append((video, stats))
            if views > 0:
                engagement_rates.append((likes / views) * 100)

        if not views_list:
            return None

        avg_views = int(round(mean(views_list)))
        avg_likes = int(round(mean(likes_list)))
        avg_engagement = (
            round(mean(engagement_rates), 2) if engagement_rates else 0.0
        )

        latest_video, latest_stats = valid_videos[0]
        representative_video, rep_stats = max(
            valid_videos,
            key=lambda item: item[1]["views"],
        )

        return CreatorRecord(
            platform=Platform.YOUTUBE,
            channel_id=channel_id,
            channel_name=channel_name,
            video_id=representative_video["video_id"],
            video_title=representative_video["title"],
            views=rep_stats["views"],
            likes=rep_stats["likes"],
            representative_views=rep_stats["views"],
            subscribers=subscribers,
            published_at=latest_video["published_at"],
            latest_video_id=latest_video["video_id"],
            latest_video_title=latest_video["title"],
            latest_views=latest_stats["views"],
            latest_likes=latest_stats["likes"],
            is_shorts=any(
                self._detect_shorts(video["title"])
                for video, _ in valid_videos
            ),
            avg_views=avg_views,
            avg_likes=avg_likes,
            avg_engagement_rate=avg_engagement,
            videos_sampled=len(views_list),
            recent_views=views_list,
            recent_likes=likes_list,
            recent_videos=[
                {
                    "video_id": video["video_id"],
                    "title": video["title"],
                    "views": stats["views"],
                }
                for video, stats in valid_videos
            ],
        )

    def _published_after_iso(self) -> str:
        since = datetime.now(timezone.utc) - timedelta(
            days=self._settings.lookback_days
        )
        return since.isoformat()

    def _search_video_snippets(
        self, keyword: str, max_results: int
    ) -> list[dict]:
        response = (
            self._service.search()
            .list(
                q=keyword,
                part="snippet",
                type="video",
                maxResults=max_results,
                order="viewCount",
                publishedAfter=self._published_after_iso(),
            )
            .execute()
        )

        snippets: list[dict] = []
        for item in response.get("items", []):
            vid = item.get("id", {}).get("videoId")
            snippet = item.get("snippet", {})
            if not vid:
                continue
            snippets.append(
                {
                    "video_id": vid,
                    "channel_id": snippet.get("channelId", ""),
                    "channel_name": snippet.get("channelTitle", ""),
                    "title": snippet.get("title", ""),
                    "published_at": snippet.get("publishedAt", ""),
                }
            )
        return snippets

    def _fetch_channel_details(
        self, channel_ids: list[str]
    ) -> dict[str, dict[str, object]]:
        result: dict[str, dict[str, object]] = {}

        for i in range(0, len(channel_ids), _BATCH_SIZE):
            batch = channel_ids[i : i + _BATCH_SIZE]
            response = (
                self._service.channels()
                .list(
                    part="statistics,contentDetails",
                    id=",".join(batch),
                )
                .execute()
            )
            for item in response.get("items", []):
                cid = item["id"]
                stats = item.get("statistics", {})
                uploads = (
                    item.get("contentDetails", {})
                    .get("relatedPlaylists", {})
                    .get("uploads")
                )
                result[cid] = {
                    "subscribers": int(stats.get("subscriberCount", 0)),
                    "uploads_playlist_id": uploads,
                }

        return result

    def _fetch_playlist_recent_videos(
        self, playlist_id: str, max_results: int
    ) -> list[dict]:
        response = (
            self._service.playlistItems()
            .list(
                part="snippet",
                playlistId=playlist_id,
                maxResults=max_results,
            )
            .execute()
        )

        videos: list[dict] = []
        for item in response.get("items", []):
            snippet = item.get("snippet", {})
            resource = snippet.get("resourceId", {})
            vid = resource.get("videoId")
            if not vid:
                continue
            videos.append(
                {
                    "video_id": vid,
                    "title": snippet.get("title", ""),
                    "published_at": snippet.get("publishedAt", ""),
                }
            )
        return videos

    def _fetch_video_stats(
        self, video_ids: list[str]
    ) -> dict[str, dict[str, int]]:
        result: dict[str, dict[str, int]] = {}

        for i in range(0, len(video_ids), _BATCH_SIZE):
            batch = video_ids[i : i + _BATCH_SIZE]
            response = (
                self._service.videos()
                .list(part="statistics", id=",".join(batch))
                .execute()
            )
            for item in response.get("items", []):
                vid = item["id"]
                stats = item.get("statistics", {})
                result[vid] = {
                    "views": int(stats.get("viewCount", 0)),
                    "likes": int(stats.get("likeCount", 0)),
                }

        return result

    @staticmethod
    def _detect_shorts(title: str) -> bool:
        lower = title.lower()
        return "#shorts" in lower or "shorts" in lower
