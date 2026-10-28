"""Per-platform Apify actor input builders.

Actor schemas differ. These conservative payloads match the common official/store
actors and remain isolated so a configured actor can be swapped without touching
the provider client.
"""

from backend.social_inventory.schemas import StartProviderRunRequest


def _common(request: StartProviderRunRequest) -> dict:
    payload: dict = {"resultsLimit": request.max_items}
    if request.date_from:
        payload["onlyPostsNewerThan"] = request.date_from.isoformat()
    if request.date_to:
        payload["onlyPostsOlderThan"] = request.date_to.isoformat()
    return payload


class InstagramActorInputBuilder:
    def build(self, request: StartProviderRunRequest) -> dict:
        return {**_common(request), "directUrls": [request.source_url], "resultsType": "posts", "addParentData": True, "includeComments": request.include_comments, "commentsLimit": request.max_comments_per_post}


class TikTokActorInputBuilder:
    def build(self, request: StartProviderRunRequest) -> dict:
        return {**_common(request), "profiles": [request.source_url], "shouldDownloadVideos": False, "commentsPerPost": request.max_comments_per_post if request.include_comments else 0}


class FacebookActorInputBuilder:
    def build(self, request: StartProviderRunRequest) -> dict:
        payload = {**_common(request), "startUrls": [{"url": request.source_url}], "maxPosts": request.max_items}
        payload.pop("resultsLimit", None)
        return payload


class YouTubeActorInputBuilder:
    def build(self, request: StartProviderRunRequest) -> dict:
        return {**_common(request), "startUrls": [{"url": request.source_url}], "maxResults": request.max_items, "downloadSubtitles": False}


class XActorInputBuilder:
    def build(self, request: StartProviderRunRequest) -> dict:
        return {**_common(request), "startUrls": [request.source_url], "maxItems": request.max_items}


class LinkedInActorInputBuilder:
    def build(self, request: StartProviderRunRequest) -> dict:
        return {**_common(request), "profileUrls": [request.source_url], "maxPosts": request.max_items}


BUILDERS = {
    "instagram": InstagramActorInputBuilder(), "tiktok": TikTokActorInputBuilder(),
    "facebook": FacebookActorInputBuilder(), "youtube": YouTubeActorInputBuilder(),
    "x": XActorInputBuilder(), "linkedin": LinkedInActorInputBuilder(),
}
