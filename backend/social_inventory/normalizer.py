"""Normalize heterogeneous provider rows without inventing unavailable values."""

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any

from backend.social_inventory.schemas import InventoryAuthor, InventoryMedia, InventoryMetrics, NormalizedSocialItem

SECRET_KEYS = {"token", "access_token", "authorization", "cookie", "cookies", "session", "sessionid", "proxy", "password"}


def _secret_key(key: str) -> bool:
    normalized = key.casefold().replace("-", "_")
    compact = normalized.replace("_", "")
    return normalized in SECRET_KEYS or any(marker in compact for marker in ("token", "authorization", "cookie", "sessionid", "proxycredential", "password"))


def sanitize_provider_response(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: "[REDACTED]" if _secret_key(key) else sanitize_provider_response(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_provider_response(item) for item in value]
    return value


def _first(raw: dict, *names: str) -> Any:
    for name in names:
        value = raw.get(name)
        if value is not None:
            return value
    return None


def _integer(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(str(value).replace(",", "")))
    except (TypeError, ValueError):
        return None


def _datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000 if value > 10_000_000_000 else value, tz=UTC)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        return None


def _content_type(raw: dict) -> str:
    value = str(_first(raw, "type", "contentType", "mediaType", "productType") or "post").casefold()
    if value in {"sidecar", "carousel", "carousel_container"}:
        return "carousel"
    if value in {"clips", "clip", "reel", "reels"}:
        return "reel"
    return value


def _media_url_status(platform: str) -> str:
    return "observed_temporary" if platform == "instagram" else "permanent"


def _media_from_row(raw: dict, platform: str, content_type: str) -> list[InventoryMedia]:
    """Map one provider row or one Instagram child post to normalized media."""
    result: list[InventoryMedia] = []
    video_url = _first(raw, "videoUrl", "video_url")
    display_url = _first(raw, "displayUrl", "display_url", "imageUrl", "image_url", "thumbnail")
    is_video = isinstance(video_url, str) or content_type in {"video", "reel"}
    if isinstance(video_url, str) and video_url.startswith("https://"):
        result.append(InventoryMedia(
            type="video", url=video_url,
            thumbnail_url=display_url if isinstance(display_url, str) and display_url.startswith("https://") else None,
            width=_integer(_first(raw, "dimensionsWidth", "originalWidth", "width")),
            height=_integer(_first(raw, "dimensionsHeight", "originalHeight", "height")),
            duration_seconds=_float(_first(raw, "videoDuration", "duration", "duration_seconds")),
            url_status=_media_url_status(platform),
        ))
        return result
    images = raw.get("images") or []
    if isinstance(images, (str, dict)):
        images = [images]
    if not images and isinstance(display_url, str):
        images = [display_url]
    for image in images:
        item = {"url": image} if isinstance(image, str) else image
        if not isinstance(item, dict):
            continue
        url = _first(item, "url", "src", "displayUrl", "imageUrl")
        if isinstance(url, str) and url.startswith("https://"):
            result.append(InventoryMedia(
                type="video" if is_video else "image", url=url,
                thumbnail_url=url if is_video else _first(item, "thumbnailUrl", "thumbnail_url"),
                width=_integer(_first(item, "dimensionsWidth", "width", "originalWidth",)) or _integer(_first(raw, "dimensionsWidth", "width", "originalWidth")),
                height=_integer(_first(item, "dimensionsHeight", "height", "originalHeight")) or _integer(_first(raw, "dimensionsHeight", "height", "originalHeight")),
                duration_seconds=_float(_first(item, "videoDuration", "duration", "duration_seconds")),
                url_status=_media_url_status(platform),
            ))
    return result


def _media(raw: dict, platform: str, content_type: str) -> list[InventoryMedia]:
    child_posts = raw.get("childPosts")
    if isinstance(child_posts, list) and child_posts:
        result: list[InventoryMedia] = []
        for child in child_posts:
            if isinstance(child, dict):
                result.extend(_media_from_row(child, platform, _content_type(child)))
        if result:
            return result
    if platform == "instagram":
        return _media_from_row(raw, platform, content_type)
    result = []
    candidates = raw.get("media") or raw.get("images") or raw.get("attachments") or []
    if isinstance(candidates, dict):
        candidates = [candidates]
    if not candidates:
        url = _first(raw, "videoUrl", "video_url", "imageUrl", "image_url", "displayUrl", "thumbnail")
        candidates = [{"url": url}] if url else []
    for item in candidates:
        if isinstance(item, str):
            item = {"url": item}
        url = _first(item, "url", "src", "videoUrl", "imageUrl")
        if isinstance(url, str) and url.startswith("https://"):
            result.append(InventoryMedia(type=str(_first(item, "type", "mediaType") or ("video" if raw.get("videoUrl") else "image")).lower(), url=url, thumbnail_url=_first(item, "thumbnailUrl", "thumbnail_url"), width=_integer(item.get("width")), height=_integer(item.get("height")), duration_seconds=_float(item.get("duration") or item.get("duration_seconds")), url_status=_media_url_status(platform)))
    return result


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _valid_instagram_username(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    username = value.strip().lstrip("@")
    return username if re.fullmatch(r"[A-Za-z0-9._]{1,30}", username) else None


def normalize_item(platform: str, raw: dict[str, Any], provider: str = "apify") -> NormalizedSocialItem:
    author_raw = raw.get("author") if isinstance(raw.get("author"), dict) else {}
    username = _first(author_raw, "username", "uniqueId", "handle") or _first(raw, "ownerUsername", "username", "channelName", "authorName")
    canonical_url = _first(raw, "url", "postUrl", "webVideoUrl", "tweetUrl", "link")
    external_id = _first(raw, "id", "shortCode", "videoId", "postId", "tweetId", "urn")
    if platform == "instagram" and not canonical_url and raw.get("shortCode"):
        canonical_url = f"https://www.instagram.com/p/{raw['shortCode']}/"
    if not canonical_url and external_id:
        canonical_url = f"https://{platform}.invalid/{external_id}"
    if not canonical_url:
        raise ValueError("Provider item has neither canonical URL nor external ID")
    caption = _first(raw, "caption", "text", "description", "content", "message")
    title = _first(raw, "title", "name")
    hashtags = raw.get("hashtags") or re.findall(r"#([\w\-]+)", str(caption or title or ""))
    if hashtags and isinstance(hashtags[0], dict):
        hashtags = [_first(item, "name", "tag") for item in hashtags]
    comments = sanitize_provider_response(raw.get("comments")) if isinstance(raw.get("comments"), list) else []
    content_type = _content_type(raw)
    instagram_username = _valid_instagram_username(username) if platform == "instagram" else None
    profile_url = _first(author_raw, "url", "profileUrl")
    if profile_url is None and instagram_username:
        profile_url = f"https://www.instagram.com/{instagram_username}/"
    explicit_comments = _integer(_first(raw, "commentsCount", "commentCount"))
    return NormalizedSocialItem(
        platform=platform, external_id=str(external_id) if external_id is not None else None,
        canonical_url=str(canonical_url), content_type=content_type,
        title=str(title) if title is not None else None, caption=str(caption) if caption is not None else None,
        language=_first(raw, "language", "lang"), published_at=_datetime(_first(raw, "timestamp", "publishedAt", "createTime", "date", "createdAt")),
        author=InventoryAuthor(external_id=str(_first(author_raw, "id", "userId") or raw.get("ownerId")) if _first(author_raw, "id", "userId") is not None or raw.get("ownerId") is not None else None, username=str(username) if username else None, display_name=_first(author_raw, "displayName", "name") or _first(raw, "ownerFullName", "authorName"), profile_url=profile_url, avatar_url=_first(author_raw, "avatar", "avatarUrl", "profilePicUrl") or raw.get("profilePicUrl"), followers_count=_integer(_first(author_raw, "followers", "followersCount") if _first(author_raw, "followers", "followersCount") is not None else raw.get("followersCount")), verified=_first(author_raw, "verified", "isVerified") if _first(author_raw, "verified", "isVerified") is not None else raw.get("verified")),
        media=_media(raw, platform, content_type),
        metrics=InventoryMetrics(views=_integer(_first(raw, "videoViewCount", "videoPlayCount", "views", "viewCount", "playCount")), likes=_integer(_first(raw, "likesCount", "likes", "likeCount", "diggCount")), comments=explicit_comments if explicit_comments is not None else (len(comments) if comments else None), shares=_integer(_first(raw, "sharesCount", "shares", "shareCount", "retweetCount")), saves=_integer(_first(raw, "savesCount", "saves", "saveCount", "bookmarkCount"))),
        hashtags=[str(item).lstrip("#") for item in hashtags if item], mentions=[str(item) for item in (raw.get("mentions") or []) if item],
        location=raw.get("location") if isinstance(raw.get("location"), dict) else None, comments=comments,
        observed_at=datetime.now(UTC), provider=provider, provider_response=sanitize_provider_response(raw),
    )


def content_hash(item: NormalizedSocialItem) -> str:
    stable = {"platform": item.platform, "username": item.author.username, "published_at": item.published_at.isoformat() if item.published_at else None, "text": " ".join((item.caption or item.title or "").casefold().split())}
    return hashlib.sha256(json.dumps(stable, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
